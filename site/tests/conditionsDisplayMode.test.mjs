import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { conditionsDisplayMode } from '../src/lib/conditionsDisplayMode.ts';

const healthyPayload = {
  locations: [{ id: 'wirth' }],
};

const errorPayload = {
  error: 'Conditions unavailable',
  locations: [],
};

test('uses live mode for a healthy, non-empty July payload', () => {
  const at = new Date('2026-07-19T12:00:00-05:00');

  assert.equal(conditionsDisplayMode(healthyPayload, at), 'live');
});

test('uses off-season mode for an error/empty July payload', () => {
  const at = new Date('2026-07-19T12:00:00-05:00');

  assert.equal(conditionsDisplayMode(errorPayload, at), 'off-season');
});

test('uses live mode for a healthy, non-empty January payload', () => {
  const at = new Date('2027-01-15T12:00:00-06:00');

  assert.equal(conditionsDisplayMode(healthyPayload, at), 'live');
});

test('uses unavailable mode for an error/empty January payload', () => {
  const at = new Date('2027-01-15T12:00:00-06:00');

  assert.equal(conditionsDisplayMode(errorPayload, at), 'unavailable');
});

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

test('restores venue cells when November unavailable follows October off-season', async () => {
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
  let now = '2026-10-31T12:00:00-05:00';
  let refresh;
  const responses = [
    { error: 'Conditions unavailable', locations: [] },
    { error: 'Conditions unavailable', locations: [] },
  ];

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
      json: async () => responses.shift(),
    });
    globalThis.setTimeout = () => 1;
    globalThis.setInterval = (callback) => {
      refresh = callback;
      return 1;
    };

    const assetUrl = new URL(`../dist${assetPath}`, import.meta.url);
    await import(`${assetUrl.href}?transition-regression`);
    await new Promise((resolve) => original.setTimeout(resolve, 0));

    const venueCells = [...root.querySelectorAll('[data-location]')];
    assert.equal(venueCells.length, 4);
    assert.ok(venueCells.every((cell) => cell.hidden && cell.style.display === 'none'));
    assert.equal(root.querySelectorAll('[data-dryland-label]').length, 1);

    now = '2026-11-01T12:00:00-05:00';
    assert.equal(typeof refresh, 'function', 'client must register its refresh interval');
    refresh();
    await new Promise((resolve) => original.setTimeout(resolve, 0));

    for (const cell of venueCells) {
      assert.equal(cell.hidden, false, 'winter unavailable must unhide each venue');
      assert.equal(cell.style.display, '', 'winter unavailable must clear inline hiding');
      assert.equal(cell.querySelector('[data-wax]')?.textContent, 'No report');
    }
    assert.equal(root.querySelector('[data-dryland-label]'), null);
    assert.equal(root.querySelector('[data-updated]')?.textContent, '● Conditions unavailable');
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
