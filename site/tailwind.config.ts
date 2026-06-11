import type { Config } from 'tailwindcss';
import forms from '@tailwindcss/forms';
import typography from '@tailwindcss/typography';

// Raw oklch values, shared between the color tokens (which append
// `<alpha-value>`) and the typography theme below (which needs plain colors:
// a literal `<alpha-value>` placeholder would leak into the prose CSS vars).
const palette = {
  navy: 'oklch(0.25 0.06 260)',
  'navy-deep': 'oklch(0.18 0.05 260)',
  mint: 'oklch(0.91 0.12 155)',
  // L=0.52: measured 4.95:1 on paper and 4.74:1 on paper-card (AA for body
  // text). The original L=0.55 measured 4.37:1 / 4.18:1 and failed AA.
  'mint-deep': 'oklch(0.52 0.13 155)',
  coral: 'oklch(0.74 0.16 15)',
  paper: 'oklch(0.985 0.003 90)',
  'paper-card': 'oklch(0.97 0.004 90)',
  ink: 'oklch(0.18 0.04 260)',
  slate: 'oklch(0.50 0.02 260)',
};

/** Palette color with a fixed alpha (for prose rules/borders). */
const alpha = (color: keyof typeof palette, a: number) =>
  palette[color].replace(')', ` / ${a})`);

export default {
  content: ['./src/**/*.{astro,html,ts,tsx,md,mdx}'],
  theme: {
    extend: {
      // `/ <alpha-value>` is REQUIRED on every token: without it Tailwind 3.4
      // cannot inject opacity modifiers, so classes like border-mint/20 or
      // bg-ink/95 are silently dropped from the build (borders then fall back
      // to preflight gray-200).
      colors: Object.fromEntries(
        Object.entries(palette).map(([name, value]) => [
          name,
          value.replace(')', ' / <alpha-value>)'),
        ]),
      ),
      // Theme the typography plugin to the club palette: markdoc bodies
      // (coach bios, trip descriptions, wax entries) render through `prose`
      // and would otherwise fall back to the plugin's default grays.
      typography: {
        DEFAULT: {
          css: {
            '--tw-prose-body': palette.ink,
            '--tw-prose-headings': palette.navy,
            '--tw-prose-lead': palette.slate,
            '--tw-prose-links': palette['mint-deep'],
            '--tw-prose-bold': palette.ink,
            '--tw-prose-counters': palette.slate,
            '--tw-prose-bullets': palette['mint-deep'],
            '--tw-prose-hr': alpha('ink', 0.1),
            '--tw-prose-quotes': palette.ink,
            '--tw-prose-quote-borders': palette.mint,
            '--tw-prose-captions': palette.slate,
            '--tw-prose-code': palette.ink,
            '--tw-prose-pre-code': palette.paper,
            '--tw-prose-pre-bg': palette['navy-deep'],
            '--tw-prose-th-borders': alpha('ink', 0.15),
            '--tw-prose-td-borders': alpha('ink', 0.1),
          },
        },
      },
      // One family, two voices: weight separates the display cut from body
      // (headings add font-semibold; global.css pins .font-display to normal
      // width after the expanded cut was retired 2026-06-10).
      fontFamily: {
        sans: ['ArchivoVariable', 'system-ui', 'sans-serif'],
        display: ['ArchivoVariable', 'system-ui', 'sans-serif'],
      },
      maxWidth: { prose: '62ch', 'prose-narrow': '56ch' },
    },
  },
  plugins: [forms, typography],
} satisfies Config;
