import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import {
  descriptionHtml, escapeHtml, formatPrice, raceDayShort, raceYear, renderEventBand,
} from '../src/lib/eventRender.ts';

const API = 'https://tcsc.ski/api/events/dry-tri';
const EVENT = {
  slug: 'dry-tri-2026',
  name: 'TCSC Roll, Ride, and Run Dry Tri 2026',
  location: 'Carver Park Reserve, Parley Lake, Victoria',
  description: "TCSC's fall race.\r\n\r\nSchedule of events\r\n\r\n- 7:30 AM: Packet pickup opens\r\n- 9:00 AM: Long course Wave 1",
  event_date: '2026-10-24T14:00:00Z',
  signup_start: '2026-07-25T05:00:00Z',
  signup_end: '2026-10-23T04:59:00Z',
  registration_path: '/events/dry-tri-2026',
  details_url: 'https://docs.google.com/document/d/x',
  entries: [
    { name: 'Individual Triathlon', description: 'Complete all three legs yourself', price_cents: 5500 },
    { name: 'Relay Triathlon', description: 'One registration covers your whole team.', price_cents: 10500 },
    { name: 'Run-only 6K', description: 'Just the 6K trail run', price_cents: 3000 },
  ],
};
const at = (iso) => Date.parse(iso);
const dom = (html) => new JSDOM(`<div id="b">${html}</div>`).window.document.getElementById('b');

test('prices drop .00 and keep real cents', () => {
  assert.equal(formatPrice(5500), '$55');
  assert.equal(formatPrice(5550), '$55.50');
  assert.equal(formatPrice(0), '$0');
});

test('race day and year format in Central', () => {
  assert.equal(raceDayShort(EVENT.event_date), 'Sat, Oct 24');
  // 11 PM Central on Dec 31 is already Jan 1 in UTC; the year stays Central.
  assert.equal(raceYear('2027-01-01T05:00:00Z'), '2026');
});

test('description handles CRLF and mixed blocks', () => {
  const el = dom(descriptionHtml(EVENT.description));
  assert.deepEqual([...el.querySelectorAll('p')].map((p) => p.textContent), ["TCSC's fall race.", 'Schedule of events']);
  assert.deepEqual([...el.querySelectorAll('li')].map((li) => li.textContent), [
    '7:30 AM: Packet pickup opens', '9:00 AM: Long course Wave 1',
  ]);
  assert.ok(!el.innerHTML.includes('\r'));
});

test('consecutive plain lines stay in one paragraph with a line break', () => {
  const el = dom(descriptionHtml('Line one\nLine two'));
  assert.equal(el.querySelectorAll('p').length, 1);
  assert.equal(el.querySelectorAll('br').length, 1);
});

test('escapes HTML in every field', () => {
  const nasty = '<img src=x onerror=alert(1)> & "q"';
  const event = {
    ...EVENT,
    location: nasty,
    description: nasty,
    details_url: 'javascript:alert(1)',
    entries: [{ name: nasty, description: nasty, price_cents: 100 }],
  };
  const el = dom(renderEventBand(event, at('2026-10-06T15:00:00Z'), API));
  assert.equal(el.querySelector('img'), null);
  assert.ok(el.textContent.includes('<img src=x onerror=alert(1)> & "q"'));
  assert.equal(el.querySelector('a[href^="javascript"]'), null);
  assert.equal(escapeHtml(`<&>"'`), '&lt;&amp;&gt;&quot;&#39;');
});

test('open state shows Register and the closing day', () => {
  const el = dom(renderEventBand(EVENT, at('2026-10-06T15:00:00Z'), API));
  const button = el.querySelector('[data-event-cta] a');
  assert.equal(button.textContent, 'Register');
  assert.equal(button.getAttribute('href'), 'https://tcsc.ski/events/dry-tri-2026');
  assert.ok(el.textContent.includes('Registration closes Thursday, October 22.'));
  assert.equal(el.querySelector('[data-event-cta]').getAttribute('data-state'), 'open');
});

test('upcoming, closed and past copy', () => {
  const text = (iso) => dom(renderEventBand(EVENT, at(iso), API)).querySelector('[data-event-cta]').textContent.trim();
  assert.equal(text('2026-07-01T12:00:00Z'), 'Registration opens Saturday, July 25');
  assert.equal(text('2026-10-23T12:00:00Z'), 'Registration is closed. See you at the start.');
  assert.equal(text('2026-10-26T12:00:00Z'), '');
});

test('shows date, time, location, entries and the details link', () => {
  const el = dom(renderEventBand(EVENT, at('2026-10-06T15:00:00Z'), API));
  assert.ok(el.textContent.includes('Saturday, October 24 · 9:00 AM'));
  assert.ok(el.textContent.includes('Carver Park Reserve, Parley Lake, Victoria'));
  assert.deepEqual([...el.querySelectorAll('[data-entry-price]')].map((p) => p.textContent), ['$55', '$105', '$30']);
  assert.equal(el.querySelector('a[data-event-details]').textContent, 'Full race details');
});

test('no event renders the fallback line linking tcsc.ski/tri', () => {
  const el = dom(renderEventBand(null, at('2026-10-06T15:00:00Z'), API));
  const link = el.querySelector('a');
  assert.equal(link.getAttribute('href'), 'https://tcsc.ski/tri');
  assert.equal(el.textContent.trim(), 'Dates, entries and registration: tcsc.ski/tri');
});

test('no em or en dashes in any rendered copy', () => {
  for (const iso of ['2026-07-01T12:00:00Z', '2026-10-06T15:00:00Z', '2026-10-23T12:00:00Z', '2026-10-26T12:00:00Z']) {
    const html = renderEventBand(EVENT, at(iso), API) + renderEventBand(null, at(iso), API);
    assert.ok(!/[–—]/.test(html), `dash in ${iso}`);
  }
});
