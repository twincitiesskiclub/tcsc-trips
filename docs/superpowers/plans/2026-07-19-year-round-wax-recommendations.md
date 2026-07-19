# Year-Round Wax Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render real venue temperatures and the existing winter wax recommendations year round whenever the conditions API returns a healthy payload.

**Architecture:** Keep the API, Astro markup, visual system, and live renderer unchanged. Make `conditionsDisplayMode()` payload-first so healthy data always selects `live`, then use the browser month only to choose between the existing `off-season` and `unavailable` failure states. Protect the behavior with both a unit contract and a rendered-DOM regression.

**Tech Stack:** Astro 7, TypeScript, Node test runner, JSDOM 29, Python Playwright, Tailwind CSS 4, Flask/Pytest regression suite

## Global Constraints

- A healthy payload means no top-level `error` and a non-empty `locations` array.
- A healthy payload must select `live` in every month.
- An unhealthy April-through-October payload must select `off-season`.
- An unhealthy November-through-March payload must select `unavailable`.
- Use the existing temperature, wax band, wax label, timestamp, venue, grooming, and Birkie data without transformation.
- Add no summer-specific copy, visual treatment, badge, color, icon, animation, or interaction.
- Keep `Trail report`, the existing live updated-time stamp, all wax labels, wax thresholds, responsive visibility, Birkie Fever, audio, accessibility, refresh behavior, and failure copy unchanged.
- Make no backend, API schema, content schema, package, or global design-token change.

---

## File Structure

- Modify `site/src/lib/conditionsDisplayMode.ts`: make payload health take precedence over the seasonal failure choice.
- Modify `site/src/components/LiveConditions.client.ts`: correct the `renderQuiet()` comment so it documents the new failure-only off-season path. Do not alter rendering logic.
- Modify `site/tests/conditionsDisplayMode.test.mjs`: update the July unit contract and add one healthy-summer rendered-DOM regression.
- Leave `site/src/components/LiveConditions.astro`, `site/package.json`, and every backend file unchanged.

### Task 1: Render Healthy Conditions Year Round

**Files:**

- Modify: `site/src/lib/conditionsDisplayMode.ts:8-20`
- Modify: `site/src/components/LiveConditions.client.ts:94-99`
- Test: `site/tests/conditionsDisplayMode.test.mjs:17-123`

**Interfaces:**

- Consumes: `conditionsDisplayMode(payload: unknown, at?: Date): ConditionsDisplayMode`, the existing `/api/conditions` payload, and the existing `LiveConditions` DOM hooks.
- Produces: the unchanged `ConditionsDisplayMode` union (`'off-season' | 'live' | 'unavailable'`) with payload-first selection semantics.

- [ ] **Step 1: Write the failing selector and rendered-DOM tests**

In `site/tests/conditionsDisplayMode.test.mjs`, replace the current healthy-July test with:

```js
test('uses live mode for a healthy, non-empty July payload', () => {
  const at = new Date('2026-07-19T12:00:00-05:00');

  assert.equal(conditionsDisplayMode(healthyPayload, at), 'live');
});
```

Then insert this test immediately before `restores venue cells when November unavailable follows October off-season`:

```js
test('renders real temperatures and wax recommendations from a healthy July payload', async () => {
  const builtHome = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const assetPath = builtHome.match(
    /<script\b[^>]*\bsrc="(\/_astro\/LiveConditions\.[^"]+\.js)"[^>]*><\/script>/i,
  )?.[1];
  assert.ok(assetPath, 'built home must load the Live Conditions client bundle');

  const dom = new JSDOM(builtHome, { pretendToBeVisual: true });
  const roots = [...dom.window.document.querySelectorAll('[data-live-conditions]')];
  assert.ok(roots.length > 0, 'built home must include a Live Conditions root');
  roots.slice(1).forEach((root) => root.remove());
  const root = roots[0];

  const original = {
    Date: globalThis.Date,
    document: globalThis.document,
    fetch: globalThis.fetch,
    setInterval: globalThis.setInterval,
    setTimeout: globalThis.setTimeout,
    window: globalThis.window,
  };
  const now = '2026-07-19T15:14:56-05:00';
  const payload = {
    updated_at: now,
    locations: [
      {
        id: 'wirth',
        name: 'Theo',
        temp_f: 88,
        wind_chill_f: 88,
        snow_conditions: null,
        wax_band: 'red',
        wax_label: 'Red wax · klister conditions',
        source_url: null,
        report_date: null,
        groomed_for: null,
      },
    ],
    birkie: {
      status: 'early',
      word: '98.6°',
      detail: 'No fever yet. Birkie 2027 talk starts in November.',
    },
  };

  class TestDate extends original.Date {
    constructor(...args) {
      super(...(args.length > 0 ? args : [now]));
    }

    static now() {
      return new original.Date(now).getTime();
    }
  }

  try {
    globalThis.Date = TestDate;
    globalThis.document = dom.window.document;
    globalThis.window = dom.window;
    globalThis.fetch = async () => ({
      ok: true,
      json: async () => payload,
    });
    globalThis.setTimeout = () => 1;
    globalThis.setInterval = () => 1;

    const assetUrl = new URL(`../dist${assetPath}`, import.meta.url);
    await import(`${assetUrl.href}?healthy-summer-regression`);
    await new Promise((resolve) => original.setTimeout(resolve, 0));

    const wirth = root.querySelector('[data-location="wirth"]');
    assert.ok(wirth, 'home strip must include the Theo venue cell');
    assert.equal(wirth.hidden, false);
    assert.equal(wirth.style.display, '');
    assert.equal(wirth.querySelector('[data-temp]')?.textContent, '88°F');
    assert.equal(
      wirth.querySelector('[data-wax]')?.textContent,
      'Red wax · klister conditions',
    );

    const chip = wirth.querySelector('[data-wax-chip]');
    assert.ok(chip, 'prominent venue cell must include its wax chip');
    assert.equal(chip.hidden, false);
    assert.equal(chip.dataset.band, 'red');
    assert.equal(root.querySelector('[data-dryland-label]'), null);
    assert.match(root.querySelector('[data-updated]')?.textContent ?? '', /^● Live · updated /);
    assert.equal(root.querySelector('[data-birkie-word]')?.textContent, '98.6°');
  } finally {
    globalThis.Date = original.Date;
    globalThis.document = original.document;
    globalThis.fetch = original.fetch;
    globalThis.setInterval = original.setInterval;
    globalThis.setTimeout = original.setTimeout;
    globalThis.window = original.window;
    dom.window.close();
  }
});
```

In the existing October-to-November transition regression, replace its `responses` fixture with two unavailable payloads so the test continues to exercise a failed October response followed by a failed November response:

```js
  const responses = [
    { error: 'Conditions unavailable', locations: [] },
    { error: 'Conditions unavailable', locations: [] },
  ];
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd site
npm run build -- --force
node --test tests/conditionsDisplayMode.test.mjs
```

Expected: the healthy-July unit test fails because the selector returns `off-season`, and the rendered-DOM test fails because the Theo cell is hidden and does not contain `88°F`. The existing failed-July and winter cases must still pass.

- [ ] **Step 3: Implement payload-first display-mode selection**

Replace `conditionsDisplayMode()` in `site/src/lib/conditionsDisplayMode.ts` with:

```ts
export function conditionsDisplayMode(
  payload: unknown,
  at = new Date(),
): ConditionsDisplayMode {
  if (typeof payload === 'object' && payload !== null) {
    const { error, locations } = payload as ConditionsPayload;
    if (!error && Array.isArray(locations) && locations.length > 0) {
      return 'live';
    }
  }

  const month = at.getMonth() + 1;
  return month >= 4 && month <= 10 ? 'off-season' : 'unavailable';
}
```

In `site/src/components/LiveConditions.client.ts`, replace the opening `renderQuiet()` comment with:

```ts
  // Unavailable conditions say it once in the stamp; cells go quiet ("No
  // report") instead of repeating the error four times. Off-season
  // (April-October) is a failure-only fallback; healthy payloads render the
  // same live temperature and wax instrument year round.
```

Do not alter `renderInto()`, `renderQuiet()`, the Astro markup, or any copy.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
cd site
npm run build -- --force
node --test tests/conditionsDisplayMode.test.mjs
```

Expected: 6 tests pass, 0 fail. Confirm that the healthy and failed July cases now select different modes and that the October-to-November regression remains green.

- [ ] **Step 5: Run the full automated regression suite**

Run:

```bash
cd site
npm run test:refinement
npm run test:sponsors
npx astro check
cd ..
/Users/rob/env/tcsc-trips/env/bin/pytest tests/conditions tests/wix_scrape -q
```

Expected:

- 14 refinement tests pass.
- 24 sponsor tests pass.
- Astro reports 0 errors, 0 warnings, and 0 hints.
- 74 backend tests pass.
- The existing empty `trips` and `wax_entries` collection notices may appear during builds; they are unrelated to this feature.

- [ ] **Step 6: Verify both responsive variants with a healthy summer payload**

Start the built site in one terminal:

```bash
cd site
npx astro preview --host 127.0.0.1 --port 4327
```

In another terminal, run:

```bash
/Users/rob/env/tcsc-trips/env/bin/python - <<'PY'
import json

from playwright.sync_api import expect, sync_playwright

payload = {
    "updated_at": "2026-07-19T15:14:56-05:00",
    "locations": [
        {
            "id": venue_id,
            "name": name,
            "temp_f": temp,
            "wind_chill_f": temp,
            "snow_conditions": None,
            "wax_band": "red",
            "wax_label": "Red wax · klister conditions",
            "source_url": None,
            "report_date": None,
            "groomed_for": None,
        }
        for venue_id, name, temp in (
            ("wirth", "Theo", 88),
            ("elm", "Elm", 88),
            ("hyland", "Hyland", 87),
            ("telemark", "Telemark", 82),
        )
    ],
    "birkie": {
        "status": "early",
        "word": "98.6°",
        "detail": "No fever yet. Birkie 2027 talk starts in November.",
    },
}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    for width in (390, 1440):
        context = browser.new_context(viewport={"width": width, "height": 900})
        page = context.new_page()
        page.add_init_script(
            """
            window.__tcscConditionsCls = 0;
            window.__tcscLayoutObserver = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                const root = document.querySelector('[data-live-conditions]');
                const touchesConditions = root && entry.sources?.some(
                  (source) => source.node && root.contains(source.node)
                );
                if (!entry.hadRecentInput && touchesConditions) {
                  window.__tcscConditionsCls += entry.value;
                }
              }
            });
            window.__tcscLayoutObserver.observe({ type: 'layout-shift', buffered: true });
            """
        )
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.route(
            "**/api/conditions",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                headers={"access-control-allow-origin": "*"},
                body=json.dumps(payload),
            ),
        )

        for route_path, surface in (("/", "home"), ("/about", "about")):
            response = page.goto(f"http://127.0.0.1:4327{route_path}", wait_until="networkidle")
            assert response is not None and response.status == 200
            root = page.locator("[data-live-conditions]")
            expect(root.locator('[data-location="wirth"] [data-temp]')).to_have_text("88°F")
            expect(root.locator('[data-location="wirth"] [data-wax]')).to_have_text(
                "Red wax · klister conditions"
            )
            assert root.locator("[data-dryland-label]").count() == 0
            assert "Summer" not in root.inner_text()
            assert page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            ) == 0
            assert page.evaluate("window.__tcscConditionsCls") < 0.01

            if width == 1440:
                for venue_id in ("wirth", "elm", "hyland", "telemark"):
                    assert root.locator(f'[data-location="{venue_id}"]').is_visible()
                expect(root.locator("[data-birkie-word]")).to_have_text("98.6°")
            else:
                assert root.locator('[data-location="wirth"]').is_visible()
                assert not root.locator('[data-location="elm"]').is_visible()

            page.screenshot(
                path=f"/tmp/year-round-wax-{surface}-{width}.png",
                full_page=True,
            )

        assert page_errors == []
        context.close()
    browser.close()
PY
```

Expected:

- Home and About return 200 at 390px and 1440px.
- Theo shows `88°F` and `Red wax · klister conditions` on both variants.
- Desktop shows all four venues and Birkie Fever; mobile shows Theo only.
- No dryland label or summer-specific copy appears with healthy data.
- Every checked page has zero horizontal overflow, cumulative layout shift below 0.01, and no page errors.
- Inspect the four screenshots and confirm the existing hierarchy, spacing, colors, and visual seriousness are unchanged.

- [ ] **Step 7: Review scope and commit the implementation**

Run:

```bash
git diff --check
git status --short
git diff -- site/src/lib/conditionsDisplayMode.ts site/src/components/LiveConditions.client.ts site/tests/conditionsDisplayMode.test.mjs
```

Expected: exactly the selector, explanatory comment, and conditions test file are modified. No Astro, backend, package, content, or token file appears.

Commit:

```bash
git add -- \
  site/src/lib/conditionsDisplayMode.ts \
  site/src/components/LiveConditions.client.ts \
  site/tests/conditionsDisplayMode.test.mjs
git commit -m "fix(site): show wax recommendations year round"
```
