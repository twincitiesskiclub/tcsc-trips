#!/usr/bin/env bash
# Provision the shared libraries and fonts Playwright's Chromium needs, without root.
#
# This box has no sudo and no `playwright install-deps`, so the browser binary
# in ~/.cache/ms-playwright cannot start: `ldd` reports ~15 missing sonames
# (libnspr4, libnss3, libgbm, libasound, the libX* set, ...). We stage those
# libraries into a private sysroot by downloading the Debian packages and
# unpacking them as an unprivileged user, then point LD_LIBRARY_PATH at it.
#
# The same mechanism stages FONTS. The image ships six DejaVu faces and nothing
# else, so every emoji in the admin UI rendered as a tofu box: role chips
# (admin_users.js: `tag.emoji || DEFAULT_EMOJI`), the practices lead pills, and
# the "is attendance" legend on practices-detail. A missing-glyph box has a
# different intrinsic width from the real glyph, so a padding defect triaged
# against it is not the gap production shows. Fonts are part of what makes a
# capture faithful, not a nicety.
#
# Idempotent: if the sysroot already resolves every soname and holds the emoji
# font, this exits without touching the network. Prints the sysroot path on
# stdout; all progress noise goes to stderr so callers can capture the path
# directly. run.sh reads $SYSROOT/fonts.conf out of the printed path and exports
# it as FONTCONFIG_FILE.
#
# Usage:  SYSROOT="$(scripts/ui_audit/browser_deps.sh)"
set -euo pipefail

SYSROOT="${TCSC_UI_AUDIT_SYSROOT:-$HOME/.cache/tcsc-ui-audit/sysroot}"
LIBDIR="$SYSROOT/usr/lib/x86_64-linux-gnu"
# Presence probe for the font half of the staging. fontconfig will not look
# inside the sysroot on its own -- /etc/fonts/fonts.conf lists /usr/share/fonts,
# /usr/local/share/fonts, $XDG_DATA_HOME/fonts and ~/.fonts, none of which we
# can write to meaningfully -- so we also emit a fonts.conf that includes the
# system config and adds this directory.
EMOJI_FONT="$SYSROOT/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
FONTCONF="$SYSROOT/fonts.conf"

ld_path() {
  printf '%s:%s:%s' "$LIBDIR" "$SYSROOT/lib/x86_64-linux-gnu" "$SYSROOT/usr/lib"
}

# Resolve the browser Playwright would actually launch. Any chromium build in
# the cache needs the same library set, so the newest is a fine probe.
probe_browser() {
  find "$HOME/.cache/ms-playwright" -maxdepth 3 -type f \
    \( -name chrome -o -name chrome-headless-shell \) 2>/dev/null | sort | tail -1
}

BROWSER="$(probe_browser)"
if [[ -z "$BROWSER" ]]; then
  echo "No Chromium found under ~/.cache/ms-playwright." >&2
  echo "Install one with: npx playwright install chromium" >&2
  exit 1
fi

missing_count() {
  LD_LIBRARY_PATH="$(ld_path)" ldd "$BROWSER" 2>/dev/null | grep -c 'not found' || true
}

write_fontconfig() {
  mkdir -p "$SYSROOT" "$SYSROOT/fontcache"
  cat > "$FONTCONF" <<XML
<?xml version="1.0"?>
<fontconfig>
  <!-- Written by scripts/ui_audit/browser_deps.sh. Keeps the system
       configuration (aliases, hinting, the DejaVu directory) and adds the
       fonts staged into this sysroot, so Chromium can resolve emoji. -->
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>$SYSROOT/usr/share/fonts</dir>
  <cachedir>$SYSROOT/fontcache</cachedir>
</fontconfig>
XML
}

if [[ "$(missing_count)" == "0" && -f "$EMOJI_FONT" ]]; then
  write_fontconfig
  echo "$SYSROOT"
  exit 0
fi

echo "Staging Chromium's shared libraries and fonts into $SYSROOT ..." >&2

# Pinned to Debian bookworm, matching this container's /etc/os-release. The
# list is every transitive dependency of the sonames Chromium links against.
PACKAGES=(
  libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libavahi-client3
  libavahi-common-data libavahi-common3 libbrotli1 libbsd0 libcairo2
  libcom-err2 libcups2 libdatrie1 libdbus-1-3 libdrm2 libepoxy0 libexpat1
  libffi8 libfontconfig1 libfreetype6 libfribidi0 libgbm1 libgcrypt20 libgl1
  libglapi-mesa libglib2.0-0 libglvnd0 libglx0 libgpg-error0 libgraphite2-3
  libgssapi-krb5-2 libharfbuzz0b libk5crypto3 libkeyutils1 libkrb5-3
  libkrb5support0 liblzma5 libmd0 libnspr4 libnss3 libpango-1.0-0
  libpangocairo-1.0-0 libpcre2-8-0 libpixman-1-0 libpng16-16 libsqlite3-0
  libsystemd0 libthai-data libthai0 libwayland-client0 libwayland-server0
  libx11-6 libxau6 libxcb-dri2-0 libxcb-dri3-0 libxcb-glx0 libxcb-present0
  libxcb-randr0 libxcb-render0 libxcb-shape0 libxcb-shm0 libxcb-sync1
  libxcb-xfixes0 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxdmcp6
  libxext6 libxfixes3 libxi6 libxinerama1 libxkbcommon0 libxrandr2 libxrender1
  libxshmfence1 libxtst6 libz3-4
  # Fonts. fonts-noto-color-emoji is the one that matters -- without it every
  # emoji in the admin UI is a tofu box, which is a silently wrong capture, not
  # a cosmetic one. fonts-dejavu-core duplicates what the image already ships
  # and is listed so the sysroot is self-sufficient rather than depending on the
  # base image keeping its six faces.
  fonts-noto-color-emoji fonts-dejavu-core
)

DEBDIR="$(dirname "$SYSROOT")/debs"
APTSTATE="$(dirname "$SYSROOT")/apt"
mkdir -p "$DEBDIR" "$SYSROOT" "$APTSTATE/lists/partial" "$APTSTATE/cache/archives/partial"

# The image's /var/lib/apt/lists is stale, and refreshing it in place needs
# root. These overrides keep apt's whole state -- lists, cache, logs -- inside
# our own directory, so both update and download run unprivileged. The sources
# come from the system config, so we track the same Debian suites the image does.
apt_local() {
  apt-get \
    -o Dir::State="$APTSTATE" \
    -o Dir::State::Lists="$APTSTATE/lists" \
    -o Dir::Cache="$APTSTATE/cache" \
    -o Dir::Log="$APTSTATE" \
    -o Dir::Etc::SourceList=/dev/null \
    -o Dir::Etc::SourceParts=/etc/apt/sources.list.d \
    "$@"
}

(
  apt_local update
  cd "$DEBDIR"
  # apt-get download needs no root; it only fetches into the cwd.
  apt_local download "${PACKAGES[@]}"
  for deb in *.deb; do
    dpkg-deb -x "$deb" "$SYSROOT"
  done
) >&2

STILL_MISSING="$(missing_count)"
if [[ "$STILL_MISSING" != "0" ]]; then
  echo "Sysroot built but $STILL_MISSING soname(s) still unresolved:" >&2
  LD_LIBRARY_PATH="$(ld_path)" ldd "$BROWSER" 2>/dev/null | grep 'not found' >&2
  exit 1
fi

if [[ ! -f "$EMOJI_FONT" ]]; then
  echo "Sysroot built but the emoji font is missing at $EMOJI_FONT." >&2
  echo "Captures would render every emoji as a tofu box; refusing to continue." >&2
  exit 1
fi

write_fontconfig
# Build the cache now rather than letting each Chromium process scan the
# directory; also the first place a bad fonts.conf shows up.
if command -v fc-cache >/dev/null 2>&1; then
  FONTCONFIG_FILE="$FONTCONF" fc-cache -f >&2 || true
fi

echo "Chromium dependencies and fonts staged." >&2
echo "$SYSROOT"
