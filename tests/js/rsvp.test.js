const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const scriptPath = path.join(__dirname, '../../app/static/rsvp.js');
const destination = 'slack://channel?team=T02J2AVLSCT&id=C0B2VN1LU11&ts=1788546377.776679';

function run({ type = 'navigate', visibility = 'visible', blocked = false } = {}) {
  const attempts = [];
  const link = { href: destination };
  const context = {
    document: {
      visibilityState: visibility,
      getElementById: (id) => id === 'open-rsvp' ? link : null,
    },
    window: {
      location: {
        replace(url) {
          attempts.push(url);
          if (blocked) throw new Error('Browser blocked external navigation');
        },
      },
    },
    performance: { getEntriesByType: () => [{ type }] },
  };
  vm.runInNewContext(fs.readFileSync(scriptPath, 'utf8'), context);
  return { attempts, link };
}

test('opening the SMS page immediately attempts the same destination as the app button once', () => {
  assert.deepEqual(run().attempts, [destination]);
});

test('a blocked launch leaves the app button available and does not retry', () => {
  const result = run({ blocked: true });
  assert.deepEqual(result.attempts, [destination]);
  assert.equal(result.link.href, destination);
});

test('going back to the page does not send the user straight back to Slack', () => {
  assert.deepEqual(run({ type: 'back_forward' }).attempts, []);
});

test('a background page does not try to launch another app', () => {
  assert.deepEqual(run({ visibility: 'hidden' }).attempts, []);
});
