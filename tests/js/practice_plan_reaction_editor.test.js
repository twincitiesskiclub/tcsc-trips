'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');

const Editor = require('../../app/static/practice_plan_reaction_editor.js');

const intervals = {
  id: 10,
  name: 'Intervals',
  default_plan_reactions: [
    {
      emoji: 'evergreen_tree',
      label: 'Endurance instead of intervals',
    },
  ],
};
const conflictingType = {
  id: 11,
  name: 'Conflicting',
  default_plan_reactions: [
    {emoji: 'athletic_shoe', label: 'Type runner'},
  ],
};
const run = {
  id: 1,
  name: 'A Run',
  default_plan_reactions: [
    {emoji: 'athletic_shoe', label: 'Runner'},
  ],
};
const rollerski = {
  id: 2,
  name: 'B Rollerski',
  default_plan_reactions: [
    {emoji: 'hatching_chick', label: 'New rollerskier'},
    {
      emoji: 'older_adult::skin-tone-4',
      label: 'Experienced rollerskier',
    },
  ],
};
const strength = {
  id: 3,
  name: 'Strength',
  default_plan_reactions: [],
};

function mountEditor({
  types = [intervals, conflictingType],
  activities = [run, rollerski, strength],
  selectedTypeIds = [intervals.id],
  selectedActivityIds = [run.id],
  savedSnapshot = null,
} = {}) {
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="plan-reaction-editor">
      <div id="plan-reaction-rows" class="plan-reaction-rows"></div>
      <p id="plan-reaction-empty">No Plan reactions yet.</p>
      <button type="button" id="restore-plan-reactions">Restore defaults</button>
      <button type="button" id="add-plan-reaction"
              aria-controls="plan-reaction-catalog" aria-expanded="false">
        Add reaction
      </button>
      <label for="plan-reaction-catalog">Choose a configured reaction</label>
      <select id="plan-reaction-catalog" hidden></select>
      <p id="plan-reaction-unconfigured"></p>
      <span id="plan-reaction-status" role="status" aria-live="polite"></span>
    </div>
    <input id="workout_description" value="Keep this workout">
  </body></html>`, {url: 'https://example.test'});
  const document = dom.window.document;
  const root = document.getElementById('plan-reaction-editor');
  const controller = Editor.mount({
    root,
    types,
    activities,
    selectedTypeIds,
    selectedActivityIds,
    savedSnapshot,
  });
  return {dom, controller, document, root};
}

test('practice row renders fixed shortcode, one description input, and no move controls', () => {
  const {controller, document} = mountEditor();
  const row = document.querySelector('[data-reaction-row]');

  assert.equal(row.classList.contains('practice-reaction-row'), true);
  assert.equal(
    row.querySelector('input').classList.contains('practice-reaction-label'),
    true,
  );
  assert.equal(
    row.querySelector('[data-action="remove"]').classList.contains(
      'practice-reaction-action',
    ),
    true,
  );
  assert.equal(
    row.querySelector('.practice-reaction-key').textContent,
    ':evergreen_tree:',
  );
  assert.equal(row.querySelectorAll('input').length, 1);
  assert.equal(row.querySelector('input').maxLength, 80);
  assert.match(
    row.querySelector('input').getAttribute('aria-label'),
    /evergreen_tree/,
  );
  assert.match(
    row.querySelector('input').getAttribute('aria-describedby'),
    /practice-reaction-error-/,
  );
  assert.equal(row.textContent.includes('Up'), false);
  assert.equal(row.textContent.includes('Down'), false);
  assert.deepEqual(controller.snapshot(), [
    {
      emoji: 'evergreen_tree',
      label: 'Endurance instead of intervals',
    },
  ]);
});

test('remove dims with visible Removed and focuses Undo; Undo focuses description', () => {
  const {document} = mountEditor();
  const input = document.querySelector('.practice-reaction-label');
  input.value = 'Edited before removal';

  document.querySelector('[data-action="remove"]').click();
  const removed = document.querySelector('[data-reaction-row]');
  assert.equal(removed.classList.contains('is-removed'), true);
  assert.match(removed.textContent, /Removed/);
  assert.match(removed.textContent, /Edited before removal/);
  assert.equal(document.activeElement.dataset.action, 'undo');
  assert.match(
    document.getElementById('plan-reaction-status').textContent,
    /Removed :evergreen_tree:/,
  );

  document.activeElement.click();
  assert.equal(
    document.activeElement.classList.contains('practice-reaction-label'),
    true,
  );
  assert.equal(document.activeElement.value, 'Edited before removal');
});

test('add picker excludes active and removed keys and uses fixed selected emoji', () => {
  const {controller, document} = mountEditor({
    selectedTypeIds: [],
    selectedActivityIds: [],
    savedSnapshot: null,
  });
  document.getElementById('add-plan-reaction').click();
  const select = document.getElementById('plan-reaction-catalog');
  assert.equal(select.hidden, false);
  select.value = Array.from(select.options).find(option =>
    option.textContent.includes('athletic_shoe')
  ).value;
  select.dispatchEvent(
    new document.defaultView.Event('change', {bubbles: true}),
  );
  assert.equal(
    document.querySelector('.practice-reaction-key').textContent,
    ':athletic_shoe:',
  );

  document.querySelector('[data-action="remove"]').click();
  assert.deepEqual(controller.snapshot(), []);
  document.getElementById('add-plan-reaction').click();
  assert.equal(
    Array.from(select.options).some(option =>
      option.textContent.includes('athletic_shoe')
    ),
    false,
  );
});

test('selector reconciliation replaces only reaction children and keeps edits whose origin survives', () => {
  const {controller, document, root} = mountEditor();
  const unrelated = document.getElementById('workout_description');
  const originalRoot = root;
  document.querySelector('.practice-reaction-label').value = 'Easy endurance';

  controller.setSelection([intervals.id], [run.id, rollerski.id]);

  assert.equal(unrelated.value, 'Keep this workout');
  assert.strictEqual(document.getElementById('workout_description'), unrelated);
  assert.strictEqual(document.getElementById('plan-reaction-editor'), originalRoot);
  assert.equal(
    document.querySelector(
      '[data-emoji="evergreen_tree"] .practice-reaction-label'
    ).value,
    'Easy endurance',
  );
});

test('restore changes only reaction state, allocates new DOM row IDs, and keeps unrelated form values', () => {
  const {controller, document} = mountEditor({
    savedSnapshot: [{emoji: 'wheel', label: 'Protected'}],
  });
  const oldRowId = document.querySelector('[data-reaction-row]').dataset.rowId;
  const unrelated = document.getElementById('workout_description');
  unrelated.value = 'Keep me';

  controller.restore();

  assert.equal(unrelated.value, 'Keep me');
  assert.strictEqual(document.getElementById('workout_description'), unrelated);
  assert.equal(controller.snapshot()[0].emoji, 'evergreen_tree');
  assert.notEqual(
    document.querySelector('[data-reaction-row]').dataset.rowId,
    oldRowId,
  );
  assert.match(
    document.getElementById('plan-reaction-status').textContent,
    /Reaction defaults restored/,
  );
});

test('empty state is explicit and keeps Add available when catalog exists', () => {
  const {document} = mountEditor({
    selectedTypeIds: [],
    selectedActivityIds: [],
    savedSnapshot: null,
  });

  assert.match(
    document.getElementById('plan-reaction-empty').textContent,
    /No Plan reactions/,
  );
  assert.equal(document.getElementById('plan-reaction-empty').hidden, false);
  assert.equal(document.getElementById('add-plan-reaction').hidden, false);
});

test('snapshot marks, describes, announces, and focuses the invalid description', () => {
  const {controller, document} = mountEditor();
  const input = document.querySelector('.practice-reaction-label');
  const errorId = input.getAttribute('aria-describedby');
  input.value = '   ';

  assert.throws(() => controller.snapshot(), /required/);
  assert.equal(input.getAttribute('aria-invalid'), 'true');
  assert.equal(document.activeElement, input);
  assert.match(document.getElementById(errorId).textContent, /required/);
  assert.match(
    document.getElementById('plan-reaction-status').textContent,
    /required/,
  );

  input.value = 'Corrected';
  assert.deepEqual(controller.snapshot(), [
    {emoji: 'evergreen_tree', label: 'Corrected'},
  ]);
  assert.equal(input.hasAttribute('aria-invalid'), false);
});

test('unconfigured Activities and blocking conflicts are announced', () => {
  const {controller, document} = mountEditor();

  controller.setSelection([intervals.id], [run.id, strength.id]);
  assert.match(
    document.getElementById('plan-reaction-unconfigured').textContent,
    /Strength/,
  );
  assert.match(
    document.getElementById('plan-reaction-status').textContent,
    /Strength/,
  );

  controller.setSelection(
    [conflictingType.id],
    [run.id, rollerski.id],
  );
  assert.match(
    document.getElementById('plan-reaction-status').textContent,
    /conflict/,
  );
  assert.throws(() => controller.snapshot(), /conflict/);
});

test('labels are assigned as text and values, never interpreted as HTML', () => {
  const attack = '<img src=x onerror="globalThis.pwned=true">';
  const {controller, document} = mountEditor({
    savedSnapshot: [{emoji: 'wheel', label: attack}],
  });

  assert.equal(document.querySelectorAll('img').length, 0);
  assert.equal(document.querySelector('.practice-reaction-label').value, attack);
  document.querySelector('[data-action="remove"]').click();
  assert.equal(document.querySelectorAll('img').length, 0);
  assert.match(document.querySelector('[data-reaction-row]').textContent, /<img/);
  assert.deepEqual(controller.snapshot(), []);
});
