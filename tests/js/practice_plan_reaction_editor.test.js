'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const Editor = require('../../app/static/practice_plan_reaction_editor.js');
const ROOT = path.resolve(__dirname, '../..');
const TOAST_SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/js/toast.js'),
  'utf8',
);

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

function referenceBodies({
  people = {
    coaches: [{
      id: 12,
      name: 'Ada Skier',
      tags: [{name: 'HEAD_COACH', emoji: ':snowflake:'}],
    }],
    leads: [],
    assists: [],
  },
} = {}) {
  return {
    '/admin/practices/locations/data': {
      locations: [{
        id: 7,
        name: 'Wirth',
        spot: null,
        address: null,
        google_maps_url: null,
        latitude: null,
        longitude: null,
        parking_notes: null,
        practice_count: 0,
      }],
    },
    '/admin/practices/activities/data': {
      activities: [{
        ...run,
        plan_reaction_sort_key: 'a run',
        gear_required: [],
        practice_count: 0,
      }],
    },
    '/admin/practices/types/data': {
      types: [{
        ...intervals,
        plan_reaction_sort_key: 'intervals',
        fitness_goals: [],
        has_intervals: true,
        practice_count: 0,
      }],
    },
    '/admin/practices/people/data': people,
  };
}

function mountEditor({
  types = [intervals, conflictingType],
  activities = [run, rollerski, strength],
  selectedTypeIds = [intervals.id],
  selectedActivityIds = [run.id],
  savedSnapshot = null,
  referenceError = null,
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
    <input id="date" value="2026-07-15T18:00">
    <select id="location_id"><option value="7" selected>Wirth</option></select>
    <textarea id="workout_description">Keep this workout</textarea>
    <textarea id="logistics_notes">Keep these logistics</textarea>
    <input id="is_dark_practice" type="checkbox" checked>
    <select id="practice-status"><option value="confirmed" selected>Confirmed</option></select>
    <input id="people-search" value="Ada">
    <button id="activity-selector-pill" aria-pressed="true">Run</button>
    <button id="coach-pill" aria-pressed="true">Coach</button>
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
    referenceError,
  });
  return {dom, controller, document, root};
}

function detailScriptForTest() {
  let source = fs.readFileSync(
    path.join(
      ROOT,
      'app/templates/admin/practices/_detail_script.js',
    ),
    'utf8',
  );
  const values = {
    practiceId: '42',
    selLocationId: '7',
    selActivities: '[1]',
    selTypes: '[10]',
    selCoaches: '[12]',
    selLeads: '[]',
    selAssists: '[]',
    savedPlanReactions: '[{"emoji":"wheel","label":"Protected"}]',
  };
  for (const [name, value] of Object.entries(values)) {
    source = source.replace(
      new RegExp(`^const ${name} = .*;$`, 'm'),
      `const ${name} = ${value};`,
    );
  }
  source = source.replace(
    /document\.addEventListener\('DOMContentLoaded',[\s\S]*?^\}\);\n/m,
    '',
  );
  source = source.replace(
    /\{% if practice %\}[\s\S]*?\{% endif %\}\s*$/,
    '',
  );
  return `${source}\nwindow.readFormReferenceLoadError = () => `
    + 'formReferenceLoadError;';
}

function makeDetailDom() {
  return new JSDOM(`<!doctype html><html><body>
    <form id="practice-form" action="/admin/practices/42">
      <input name="date" value="2026-07-15T18:00">
      <select id="location_id" name="location_id">
        <option value="">Select a location</option>
      </select>
      <select name="social_location_id"><option value=""></option></select>
      <div id="activities-pills"></div>
      <div id="types-pills"></div>
      <input id="people-search">
      <div id="coaches-summary"></div>
      <div id="coaches-pills"></div>
      <div id="leads-summary"></div>
      <div id="leads-pills"></div>
      <button type="button" id="assists-toggle" aria-expanded="false">
        <span class="chevron"></span>
        <span id="assists-toggle-text">Show</span>
      </button>
      <div id="assists-summary"></div>
      <div id="assists-collapsible" class="hidden">
        <div id="assists-pills"></div>
      </div>
      <textarea name="workout_description">Keep workout</textarea>
      <textarea name="logistics_notes">Keep logistics</textarea>
      <input name="is_dark_practice" type="checkbox" checked>
      <select name="status"><option value="scheduled" selected>Scheduled</option></select>
      <section id="plan-reaction-editor">
        <div id="plan-reaction-rows"></div>
        <p id="plan-reaction-empty">No Plan reactions yet.</p>
        <button type="button" id="restore-plan-reactions">Restore defaults</button>
        <button type="button" id="add-plan-reaction"
                aria-controls="plan-reaction-catalog"
                aria-expanded="false">Add reaction</button>
        <select id="plan-reaction-catalog" hidden></select>
        <p id="plan-reaction-unconfigured" hidden></p>
        <span id="plan-reaction-status"></span>
      </section>
      <button type="submit">Save Changes</button>
    </form>
  </body></html>`, {
    url: 'https://example.test/admin/practices/42/edit',
    runScripts: 'outside-only',
  });
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
  assert.equal(
    document.activeElement.getAttribute('aria-label'),
    'Undo removal of :evergreen_tree: reaction',
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
  assert.equal(select.hidden, true);
  assert.equal(
    document.getElementById('add-plan-reaction').getAttribute('aria-expanded'),
    'false',
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

test('Restore and selector reconciliation preserve the invoking control focus', () => {
  const {controller, document} = mountEditor();
  const selectorPill = document.getElementById('activity-selector-pill');
  selectorPill.focus();

  controller.setSelection([intervals.id], [run.id, rollerski.id]);
  assert.equal(document.activeElement, selectorPill);

  const restoreButton = document.getElementById('restore-plan-reactions');
  restoreButton.focus();
  restoreButton.click();
  assert.equal(document.activeElement, restoreButton);
});

test('selection and Restore preserve every unrelated form control by identity and value', () => {
  const {controller, document} = mountEditor();
  const expected = new Map([
    ['date', '2026-07-15T18:00'],
    ['location_id', '7'],
    ['workout_description', 'Keep this workout'],
    ['logistics_notes', 'Keep these logistics'],
    ['practice-status', 'confirmed'],
    ['people-search', 'Ada'],
  ].map(([id, value]) => [document.getElementById(id), value]));
  const dark = document.getElementById('is_dark_practice');
  const activityPill = document.getElementById('activity-selector-pill');
  const coachPill = document.getElementById('coach-pill');

  controller.setSelection([intervals.id], [run.id, rollerski.id]);
  controller.restore();

  for (const [node, value] of expected) {
    assert.strictEqual(document.getElementById(node.id), node);
    assert.equal(node.value, value);
  }
  assert.strictEqual(document.getElementById('is_dark_practice'), dark);
  assert.equal(dark.checked, true);
  assert.strictEqual(document.getElementById('activity-selector-pill'), activityPill);
  assert.strictEqual(document.getElementById('coach-pill'), coachPill);
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

test('globally empty catalog explains Settings while all-reserved does not', () => {
  const empty = mountEditor({
    types: [],
    activities: [],
    selectedTypeIds: [],
    selectedActivityIds: [],
  });
  const guidance = 'Configure reaction pairs in Practices Settings first.';

  assert.equal(empty.document.getElementById('add-plan-reaction').hidden, true);
  assert.equal(
    empty.document.getElementById('plan-reaction-status').textContent,
    guidance,
  );

  const reserved = mountEditor({
    types: [intervals],
    activities: [],
    selectedTypeIds: [],
    selectedActivityIds: [],
    savedSnapshot: [{emoji: 'evergreen_tree', label: 'Protected'}],
  });
  assert.equal(reserved.document.getElementById('add-plan-reaction').hidden, true);
  assert.notEqual(
    reserved.document.getElementById('plan-reaction-status').textContent,
    guidance,
  );
});

test('catalog keeps distinct labels for one emoji and reserves both after choice', () => {
  const first = {
    id: 50,
    name: 'First source',
    plan_reaction_sort_key: 'first source',
    default_plan_reactions: [{emoji: 'wave', label: 'First label'}],
  };
  const second = {
    id: 51,
    name: 'Second source',
    plan_reaction_sort_key: 'second source',
    default_plan_reactions: [{emoji: 'wave', label: 'Second label'}],
  };
  const {document} = mountEditor({
    types: [first, second],
    activities: [],
    selectedTypeIds: [],
    selectedActivityIds: [],
  });
  document.getElementById('add-plan-reaction').click();
  const select = document.getElementById('plan-reaction-catalog');
  const choices = Array.from(select.options).filter(option => option.value);
  assert.deepEqual(
    choices.map(option => option.textContent),
    [':wave: First label', ':wave: Second label'],
  );

  select.value = choices[1].value;
  select.dispatchEvent(new document.defaultView.Event('change', {bubbles: true}));
  assert.equal(document.querySelector('.practice-reaction-label').value, 'Second label');
  assert.equal(document.getElementById('add-plan-reaction').hidden, true);
});

test('repeated Remove and Undo controls name their reaction', () => {
  const {document} = mountEditor({
    selectedTypeIds: [],
    selectedActivityIds: [],
    savedSnapshot: [
      {emoji: 'wheel', label: 'Wheels'},
      {emoji: 'snowflake', label: 'Snow'},
    ],
  });
  const removeButtons = Array.from(document.querySelectorAll(
    '[data-action="remove"]',
  ));
  assert.deepEqual(removeButtons.map(button => button.getAttribute('aria-label')), [
    'Remove :wheel: reaction',
    'Remove :snowflake: reaction',
  ]);

  removeButtons[1].click();
  assert.equal(
    document.querySelector('[data-action="undo"]').getAttribute('aria-label'),
    'Undo removal of :snowflake: reaction',
  );
});

test('picker state closes after reconciliation and Restore', () => {
  const {controller, document} = mountEditor({
    selectedTypeIds: [],
    selectedActivityIds: [],
  });
  const add = document.getElementById('add-plan-reaction');
  const select = document.getElementById('plan-reaction-catalog');

  add.click();
  assert.equal(select.hidden, false);
  controller.setSelection([], []);
  assert.equal(select.hidden, true);
  assert.equal(add.getAttribute('aria-expanded'), 'false');

  add.click();
  controller.restore();
  assert.equal(select.hidden, true);
  assert.equal(add.getAttribute('aria-expanded'), 'false');
});

test('reference error keeps Edit rows protected and blocks unsafe actions', () => {
  const message = 'Could not load reaction Settings. Try again.';
  const {controller, document} = mountEditor({
    types: [],
    activities: [],
    selectedTypeIds: [],
    selectedActivityIds: [],
    savedSnapshot: [{emoji: 'wheel', label: 'Saved protected row'}],
    referenceError: message,
  });
  const before = document.querySelector('[data-reaction-row]').dataset.rowId;

  assert.equal(document.querySelector('.practice-reaction-label').value, 'Saved protected row');
  assert.equal(document.getElementById('plan-reaction-status').textContent, message);
  assert.equal(document.getElementById('restore-plan-reactions').disabled, true);
  assert.equal(document.getElementById('add-plan-reaction').hidden, true);
  assert.throws(() => controller.snapshot(), new RegExp(message.replace('.', '\\.')));
  controller.restore();
  controller.setSelection([], []);
  assert.equal(document.querySelector('[data-reaction-row]').dataset.rowId, before);
});

test('controller mirrors an external server error into the live status', () => {
  const {controller, document} = mountEditor();

  controller.showError('Selected reaction source conflict');

  const status = document.getElementById('plan-reaction-status');
  assert.equal(status.textContent, 'Selected reaction source conflict');
  assert.equal(status.classList.contains('field-error'), true);
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

test('reference loader checks HTTP status and isolates unrelated failures', async () => {
  const bodies = referenceBodies({
    people: {coaches: [], leads: [], assists: []},
  });
  function fetchWith(failures = {}) {
    return async url => {
      if (failures[url] === 'network') throw new Error('network failure');
      const ok = failures[url] !== 'http';
      return {
        ok,
        status: ok ? 200 : 503,
        json: async () => ok ? bodies[url] : {error: 'Unavailable'},
      };
    };
  }

  const peopleFailure = await Editor.loadReferenceData(fetchWith({
    '/admin/practices/people/data': 'network',
  }));
  assert.equal(peopleFailure.reactionSettingsReady, true);
  assert.deepEqual(
    peopleFailure.activities,
    bodies['/admin/practices/activities/data'].activities,
  );
  assert.deepEqual(
    peopleFailure.types,
    bodies['/admin/practices/types/data'].types,
  );
  assert.deepEqual(peopleFailure.failed, ['people']);

  const locationFailure = await Editor.loadReferenceData(fetchWith({
    '/admin/practices/locations/data': 'http',
  }));
  assert.equal(locationFailure.reactionSettingsReady, true);
  assert.deepEqual(locationFailure.locations, []);
  assert.deepEqual(
    locationFailure.activities,
    bodies['/admin/practices/activities/data'].activities,
  );
  assert.deepEqual(locationFailure.failed, ['locations']);

  const activityFailure = await Editor.loadReferenceData(fetchWith({
    '/admin/practices/activities/data': 'http',
  }));
  assert.equal(activityFailure.reactionSettingsReady, false);
  assert.deepEqual(activityFailure.activities, []);
  assert.deepEqual(
    activityFailure.types,
    bodies['/admin/practices/types/data'].types,
  );
  assert.deepEqual(activityFailure.failed, ['activities']);

  const typeFailure = await Editor.loadReferenceData(fetchWith({
    '/admin/practices/types/data': 'network',
  }));
  assert.equal(typeFailure.reactionSettingsReady, false);
  assert.deepEqual(typeFailure.failed, ['types']);

  const malformedPeople = await Editor.loadReferenceData(async url => ({
    ok: true,
    status: 200,
    json: async () => url === '/admin/practices/people/data'
      ? {coaches: {}, leads: [], assists: []}
      : bodies[url],
  }));
  assert.deepEqual(malformedPeople.people, {
    coaches: [],
    leads: [],
    assists: [],
  });
  assert.deepEqual(malformedPeople.failed, ['people']);
});

test('reference loader rejects malformed records before rendering', async t => {
  const valid = referenceBodies();
  const cases = [
    {
      name: 'location name',
      url: '/admin/practices/locations/data',
      key: 'locations',
      body: {locations: [{...valid[
        '/admin/practices/locations/data'
      ].locations[0], name: null}]},
    },
    {
      name: 'Activity id',
      url: '/admin/practices/activities/data',
      key: 'activities',
      body: {activities: [{...valid[
        '/admin/practices/activities/data'
      ].activities[0], id: '1'}]},
    },
    {
      name: 'Workout Type name',
      url: '/admin/practices/types/data',
      key: 'types',
      body: {types: [{...valid[
        '/admin/practices/types/data'
      ].types[0], name: null}]},
    },
    {
      name: 'person name',
      url: '/admin/practices/people/data',
      key: 'people',
      body: {
        coaches: [{id: 12, name: null, tags: []}],
        leads: [],
        assists: [],
      },
    },
    {
      name: 'person tags',
      url: '/admin/practices/people/data',
      key: 'people',
      body: {
        coaches: [{id: 12, name: 'Ada Skier', tags: {}}],
        leads: [],
        assists: [],
      },
    },
    {
      name: 'missing people role array',
      url: '/admin/practices/people/data',
      key: 'people',
      body: {coaches: [], leads: []},
    },
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const result = await Editor.loadReferenceData(async url => ({
        ok: true,
        status: 200,
        json: async () => url === scenario.url
          ? scenario.body
          : valid[url],
      }));

      assert.deepEqual(result.failed, [scenario.key]);
      if (scenario.key === 'people') {
        assert.deepEqual(result.people, {
          coaches: [],
          leads: [],
          assists: [],
        });
      } else {
        assert.deepEqual(result[scenario.key], []);
      }
    });
  }
});

test('detail orchestration blocks POST and renders safe fallbacks for malformed records', async () => {
  const dom = makeDetailDom();
  const {window} = dom;
  const {document} = window;
  const toasts = [];
  let postCount = 0;
  const bodies = referenceBodies({
    people: {
      coaches: [{id: 12, name: null, tags: []}],
      leads: [],
      assists: [],
    },
  });
  window.PracticePlanReactionEditor = Editor;
  window.showToast = (message, kind) => toasts.push([message, kind]);
  window.console.error = () => {};
  window.fetch = async (url, options = {}) => {
    if (options.method === 'POST') {
      postCount += 1;
      return {
        ok: false,
        status: 400,
        json: async () => ({error: 'Unexpected POST'}),
      };
    }
    return {
      ok: true,
      status: 200,
      json: async () => bodies[url],
    };
  };
  window.eval(fs.readFileSync(
    path.join(ROOT, 'app/static/practice_editor.js'),
    'utf8',
  ));
  window.eval(detailScriptForTest());

  let loadError = null;
  try {
    await window.loadFormData();
  } catch (error) {
    loadError = error.message;
  }
  document.getElementById('practice-form').dispatchEvent(
    new window.Event('submit', {bubbles: true, cancelable: true}),
  );
  await new Promise(resolve => setTimeout(resolve, 0));

  assert.deepEqual({
    loadError,
    guard: window.readFormReferenceLoadError(),
    postCount,
    location: document.getElementById('location_id').value,
    activity: document.querySelector('#activities-pills button')?.textContent,
    peopleFallback: document.getElementById('coaches-pills').textContent,
    savedReaction: document.querySelector(
      '.practice-reaction-label',
    )?.value,
    blockedToast: toasts.some(([message, kind]) => (
      message === 'Could not load form options. Refresh and try again.'
      && kind === 'error'
    )),
  }, {
    loadError: null,
    guard: 'Could not load form options. Refresh and try again.',
    postCount: 0,
    location: '7',
    activity: 'A Run',
    peopleFallback: 'No people available',
    savedReaction: 'Protected',
    blockedToast: true,
  });
  dom.window.close();
});

test('hostile reaction conflict reaches the real toast as inert text', async () => {
  const dom = makeDetailDom();
  const {window} = dom;
  const {document} = window;
  const attack = '<img src=x onerror="window.__toastXss = true">';
  const bodies = referenceBodies();
  bodies['/admin/practices/activities/data'].activities.push({
    id: 2,
    name: attack,
    plan_reaction_sort_key: 'hostile',
    default_plan_reactions: [
      {emoji: 'athletic_shoe', label: 'Different runner'},
    ],
    gear_required: [],
    practice_count: 0,
  });
  let postCount = 0;

  window.PracticePlanReactionEditor = Editor;
  window.requestAnimationFrame = callback => callback();
  window.console.error = () => {};
  window.fetch = async (url, options = {}) => {
    if (options.method === 'POST') {
      postCount += 1;
      return {
        ok: false,
        status: 400,
        json: async () => ({error: 'Unexpected POST'}),
      };
    }
    return {
      ok: true,
      status: 200,
      json: async () => bodies[url],
    };
  };
  window.eval(TOAST_SOURCE);
  window.eval(fs.readFileSync(
    path.join(ROOT, 'app/static/practice_editor.js'),
    'utf8',
  ));
  window.eval(detailScriptForTest());
  await window.loadFormData();

  document.querySelector('#activities-pills [data-value="2"]').click();
  document.getElementById('practice-form').dispatchEvent(
    new window.Event('submit', {bubbles: true, cancelable: true}),
  );
  await new Promise(resolve => setTimeout(resolve, 0));

  const toast = document.querySelector('#toast-container > div');
  assert.equal(postCount, 0);
  assert.ok(toast);
  assert.match(toast.querySelector('.flex-1').textContent, /<img/);
  assert.equal(toast.querySelectorAll('img').length, 0);
  assert.equal(window.__toastXss, undefined);
  assert.equal(toast.querySelector('button').getAttribute('onclick'), null);
  toast.querySelector('button').click();
  dom.window.close();
});

test('reaction server fields include snapshot and both selector adapters', () => {
  assert.equal(Editor.isReactionField('plan_reactions'), true);
  assert.equal(Editor.isReactionField('activity_ids'), true);
  assert.equal(Editor.isReactionField('type_ids'), true);
  assert.equal(Editor.isReactionField('workout_description'), false);
});
