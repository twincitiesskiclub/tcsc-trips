'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const Model = require('../../app/static/practice_plan_reactions.js');

const evergreen = {
  emoji: 'evergreen_tree',
  label: 'Endurance instead of intervals',
};
const runOption = {emoji: 'athletic_shoe', label: 'Runner'};
const newRollerskier = {
  emoji: 'hatching_chick',
  label: 'New rollerskier',
};
const experiencedRollerskier = {
  emoji: 'older_adult::skin-tone-4',
  label: 'Experienced rollerskier',
};

const intervals = {
  id: 10,
  name: 'Intervals',
  default_plan_reactions: [evergreen],
};
const run = {
  id: 1,
  name: 'A Run',
  default_plan_reactions: [runOption],
};
const trailRun = {
  id: 4,
  name: 'A Trail Run',
  default_plan_reactions: [runOption],
};
const rollerski = {
  id: 2,
  name: 'B Rollerski',
  default_plan_reactions: [newRollerskier, experiencedRollerskier],
};
const strength = {
  id: 3,
  name: 'Strength',
  default_plan_reactions: [],
};
const conflictingType = {
  id: 11,
  name: 'Conflicting',
  default_plan_reactions: [
    {emoji: 'athletic_shoe', label: 'Type runner'},
  ],
};
const overflowType = {
  id: 12,
  name: 'Overflow',
  default_plan_reactions: [
    {emoji: 'snowflake', label: 'Snow'},
    {emoji: 'zap', label: 'Speed'},
    {emoji: 'turtle', label: 'Easy'},
  ],
};

test('resolver and catalog use server casefold keys with stable ties', () => {
  const scenarios = [
    {
      names: [['Zebra', 'zebra'], ['alpha', 'alpha'], ['Alpha', 'alpha']],
      expected: ['option_2', 'option_3', 'option_1'],
    },
    {
      names: [['Ábc', 'ábc'], ['Zebra', 'zebra']],
      expected: ['option_2', 'option_1'],
    },
    {
      names: [
        ['Zebra', 'zebra'],
        ['Straße', 'strasse'],
        ['STRASSE', 'strasse'],
        ['Kelvin', 'kelvin'],
      ],
      expected: ['option_4', 'option_2', 'option_3', 'option_1'],
    },
  ];

  for (const scenario of scenarios) {
    const sources = scenario.names.map(([name, sortKey], index) => ({
      id: index + 1,
      name,
      plan_reaction_sort_key: sortKey,
      default_plan_reactions: [{
        emoji: `option_${index + 1}`,
        label: `Option ${index + 1}`,
      }],
    }));
    assert.deepEqual(
      Model.resolve(sources, []).rows.map(row => row.emoji),
      scenario.expected,
    );
    assert.deepEqual(
      Model.buildCatalog(sources, []).map(row => row.emoji),
      scenario.expected,
    );
  }
});

test('one activity is ordinary and two activities derive multisport defaults', () => {
  const one = Model.create({
    types: [intervals],
    activities: [run],
    savedSnapshot: null,
  });
  assert.deepEqual(
    Model.activeRows(one).map(row => row.emoji),
    ['evergreen_tree'],
  );

  const two = Model.reconcile(one, {
    types: [intervals],
    activities: [run, rollerski],
  });
  assert.deepEqual(
    Model.activeRows(two).map(row => row.emoji),
    [
      'evergreen_tree',
      'athletic_shoe',
      'hatching_chick',
      'older_adult::skin-tone-4',
    ],
  );
  assert.equal(two.effectiveInheritedCount, 4);
});

test('1 to 2 to 3 to 1 preserves edits only on rows whose origin survives', () => {
  let state = Model.create({
    types: [intervals],
    activities: [run],
    savedSnapshot: null,
  });
  state = Model.reconcile(state, {
    types: [intervals],
    activities: [run, rollerski],
  });
  state = Model.updateLabel(
    state,
    Model.rowByEmoji(state, 'evergreen_tree').rowId,
    'Easy endurance',
  );
  state = Model.reconcile(state, {
    types: [intervals],
    activities: [run, rollerski, strength],
  });
  assert.deepEqual(state.unconfiguredActivityNames, ['Strength']);
  state = Model.reconcile(state, {
    types: [intervals],
    activities: [run],
  });
  assert.deepEqual(
    Model.activeRows(state).map(row => [row.emoji, row.label]),
    [['evergreen_tree', 'Easy endurance']],
  );
});

test('updateLabel clones the full state before changing a nested row', () => {
  const state = Model.create({
    types: [intervals],
    activities: [],
    savedSnapshot: null,
  });
  const originalRow = state.rows[0];
  const returned = Model.updateLabel(state, state.rows[0].rowId, 'Edited');

  assert.notStrictEqual(returned, state);
  assert.notStrictEqual(returned.rows, state.rows);
  assert.notStrictEqual(returned.rows[0], originalRow);
  assert.equal(returned.rows[0].label, 'Edited');
  assert.equal(state.rows[0].label, 'Endurance instead of intervals');
});

test('remove and undo preserve the fixed key, edited description, and slot', () => {
  let state = Model.create({
    types: [intervals],
    activities: [run],
    savedSnapshot: null,
  });
  const row = state.rows[0];
  state = Model.updateLabel(state, row.rowId, 'Edited');

  const removed = Model.remove(state, row.rowId);
  assert.equal(state.rows[0].removed, false);
  assert.equal(removed.rows[0].removed, true);
  assert.equal(Model.reservedSlots(removed), 1);

  const restored = Model.undo(removed, row.rowId);
  assert.equal(removed.rows[0].removed, true);
  assert.deepEqual(
    [restored.rows[0].rowId, restored.rows[0].emoji, restored.rows[0].label],
    [row.rowId, 'evergreen_tree', 'Edited'],
  );
});

test('add uses only an unused Settings pair and removed keys remain reserved', () => {
  const state = Model.create({
    types: [],
    activities: [],
    savedSnapshot: null,
  });
  const catalog = Model.buildCatalog([intervals], [run, rollerski]);
  const option = catalog.find(item => item.emoji === 'athletic_shoe');
  const added = Model.add(state, option);
  const removed = Model.remove(added, added.rows[0].rowId);

  assert.equal(state.rows.length, 0);
  assert.equal(
    Model.availableCatalog(removed, catalog).some(
      item => item.emoji === 'athletic_shoe',
    ),
    false,
  );
});

test('conflict and overflow retain last-valid rows and block add and snapshot', () => {
  const state = Model.create({
    types: [],
    activities: [run, rollerski],
    savedSnapshot: null,
  });
  const invalid = Model.reconcile(state, {
    types: [conflictingType],
    activities: [run, rollerski],
  });

  assert.deepEqual(invalid.rows, state.rows);
  assert.match(invalid.blockingError, /conflict/);
  assert.equal(Model.canAdd(invalid), false);
  assert.throws(() => Model.snapshot(invalid), /conflict/);

  const overflow = Model.reconcile(state, {
    types: [overflowType],
    activities: [run, rollerski],
  });
  assert.deepEqual(overflow.rows, state.rows);
  assert.match(overflow.blockingError, /more than 4/);
});

test('existing snapshot reconstruction preserves protected rows and suppression', () => {
  const state = Model.create({
    types: [intervals],
    activities: [run, rollerski],
    savedSnapshot: [
      {emoji: 'athletic_shoe', label: 'Custom runner'},
      {emoji: 'wheel', label: 'Protected rollerski'},
    ],
  });

  assert.equal(
    Model.rowByEmoji(state, 'athletic_shoe').label,
    'Custom runner',
  );
  assert.equal(Model.rowByEmoji(state, 'wheel').protectedOrder, 1);
  assert.deepEqual(
    state.suppressed.map(item => item.emoji),
    ['evergreen_tree', 'hatching_chick', 'older_adult::skin-tone-4'],
  );
  assert.deepEqual(
    state.suppressed.map(item => item.inheritedOrder),
    [0, 2, 3],
  );
});

test('suppressed inheritedOrder tracks current resolution order explicitly', () => {
  const state = Model.create({
    types: [intervals],
    activities: [run, rollerski],
    savedSnapshot: [],
  });
  assert.deepEqual(
    state.suppressed.map(item => [item.emoji, item.inheritedOrder]),
    [
      ['evergreen_tree', 0],
      ['athletic_shoe', 1],
      ['hatching_chick', 2],
      ['older_adult::skin-tone-4', 3],
    ],
  );

  const reconciled = Model.reconcile(state, {
    types: [],
    activities: [run, rollerski],
  });
  assert.deepEqual(
    reconciled.suppressed.map(item => [item.emoji, item.inheritedOrder]),
    [
      ['athletic_shoe', 0],
      ['hatching_chick', 1],
      ['older_adult::skin-tone-4', 2],
    ],
  );
});

test('suppression survives a partial original-source disappearance', () => {
  const state = Model.create({
    types: [],
    activities: [run, trailRun],
    savedSnapshot: [],
  });
  const partial = Model.reconcile(state, {
    types: [],
    activities: [run, strength],
  });

  assert.deepEqual(partial.suppressed, [
    {
      emoji: 'athletic_shoe',
      sourceKeys: ['activity:1', 'activity:4'],
      inheritedOrder: 0,
    },
  ]);

  const absent = Model.reconcile(partial, {
    types: [],
    activities: [rollerski, strength],
  });
  assert.equal(
    absent.suppressed.some(item => item.emoji === 'athletic_shoe'),
    false,
  );
});

test('suppression expires when one mapping leaves a still-selected source', () => {
  const original = {
    id: 30,
    name: 'Mutable source',
    plan_reaction_sort_key: 'mutable source',
    default_plan_reactions: [
      {emoji: 'snowflake', label: 'Snow'},
      {emoji: 'zap', label: 'Speed'},
    ],
  };
  const withoutSnowflake = {
    ...original,
    default_plan_reactions: [{emoji: 'zap', label: 'Speed'}],
  };
  const state = Model.create({
    types: [original],
    activities: [],
    savedSnapshot: [],
  });

  const expired = Model.reconcile(state, {
    types: [withoutSnowflake],
    activities: [],
  });
  assert.deepEqual(expired.suppressed.map(item => item.emoji), ['zap']);

  const restored = Model.reconcile(expired, {
    types: [original],
    activities: [],
  });
  assert.deepEqual(Model.activeRows(restored).map(row => row.emoji), [
    'snowflake',
  ]);
  assert.deepEqual(restored.suppressed.map(item => item.emoji), ['zap']);
});

test('all Add permutations recover canonical order from reversed tombstones', () => {
  const source = {
    id: 31,
    name: 'Three defaults',
    plan_reaction_sort_key: 'three defaults',
    default_plan_reactions: [
      {emoji: 'a', label: 'A'},
      {emoji: 'b', label: 'B'},
      {emoji: 'c', label: 'C'},
    ],
  };
  const base = Model.create({
    types: [source],
    activities: [],
    savedSnapshot: [],
  });
  base.suppressed.reverse();
  const catalog = Model.buildCatalog([source], []);
  const permutations = [
    ['a', 'b', 'c'],
    ['a', 'c', 'b'],
    ['b', 'a', 'c'],
    ['b', 'c', 'a'],
    ['c', 'a', 'b'],
    ['c', 'b', 'a'],
  ];

  for (const permutation of permutations) {
    let state = structuredClone(base);
    for (const emoji of permutation) {
      state = Model.add(
        state,
        catalog.find(option => option.emoji === emoji),
      );
    }
    assert.deepEqual(state.rows.map(row => row.emoji), ['a', 'b', 'c']);
    assert.deepEqual(Model.snapshot(state).map(row => row.emoji), ['a', 'b', 'c']);
  }
});

test('adding a suppressed applicable option recovers its inherited order', () => {
  const state = Model.create({
    types: [intervals],
    activities: [run, rollerski],
    savedSnapshot: [],
  });
  const catalog = Model.buildCatalog([intervals], [run, rollerski]);
  const added = Model.add(
    state,
    catalog.find(item => item.emoji === 'evergreen_tree'),
  );
  const row = Model.rowByEmoji(added, 'evergreen_tree');

  assert.equal(row.inheritedOrder, 0);
  assert.deepEqual(row.inheritedSourceKeys, ['type:10']);
  assert.equal(row.catalogOrder, 0);
  assert.equal(
    added.suppressed.some(item => item.emoji === 'evergreen_tree'),
    false,
  );
  assert.equal(
    state.suppressed.some(item => item.emoji === 'evergreen_tree'),
    true,
  );
});

test('initially invalid Edit keeps its saved snapshot while blocking submission', () => {
  const edit = Model.create({
    types: [conflictingType],
    activities: [run, rollerski],
    savedSnapshot: [{emoji: 'wheel', label: 'Saved protected row'}],
  });
  assert.match(edit.blockingError, /conflict/);
  assert.deepEqual(
    edit.rows.map(row => [row.emoji, row.label]),
    [['wheel', 'Saved protected row']],
  );
  assert.equal(edit.rows[0].protectedOrder, 0);
  assert.throws(() => Model.snapshot(edit), /conflict/);

  const create = Model.create({
    types: [conflictingType],
    activities: [run, rollerski],
    savedSnapshot: null,
  });
  assert.deepEqual(create.rows, []);
  assert.match(create.blockingError, /conflict/);
});

test('restore is atomic and allocates fresh monotonically increasing row IDs', () => {
  const original = Model.create({
    types: [intervals],
    activities: [run, rollerski],
    savedSnapshot: null,
  });
  const oldIds = new Set(original.rows.map(row => row.rowId));
  const restored = Model.restore(original, {
    types: [intervals],
    activities: [run, rollerski],
  });

  assert.equal(
    restored.rows.some(row => oldIds.has(row.rowId)),
    false,
  );
  assert.equal(
    restored.nextRowNumber,
    original.nextRowNumber + restored.rows.length,
  );
  assert.deepEqual(Model.snapshot(restored), [
    evergreen,
    runOption,
    newRollerskier,
    experiencedRollerskier,
  ]);

  const failed = Model.restore(original, {
    types: [conflictingType],
    activities: [run, rollerski],
  });
  assert.deepEqual(failed.rows, original.rows);
  assert.match(failed.blockingError, /conflict/);
  assert.equal(original.blockingError, null);
});

test('snapshot trims labels and reports the invalid row ID', () => {
  let state = Model.create({
    types: [intervals],
    activities: [],
    savedSnapshot: null,
  });
  const rowId = state.rows[0].rowId;
  state = Model.updateLabel(state, rowId, '  Easy endurance  ');
  assert.deepEqual(Model.snapshot(state), [
    {emoji: 'evergreen_tree', label: 'Easy endurance'},
  ]);

  state = Model.updateLabel(state, rowId, '   ');
  assert.throws(
    () => Model.snapshot(state),
    error => error.rowId === rowId && /required/.test(error.message),
  );

  state = Model.updateLabel(state, rowId, 'x'.repeat(81));
  assert.throws(
    () => Model.snapshot(state),
    error => error.rowId === rowId && /80/.test(error.message),
  );
});

test('saved snapshots reject impossible list, key, and label states', () => {
  const createWith = savedSnapshot => Model.create({
    types: [],
    activities: [],
    savedSnapshot,
  });
  const five = Array.from({length: 5}, (_, index) => ({
    emoji: `option_${index}`,
    label: `Option ${index}`,
  }));

  assert.throws(() => createWith({}), /expected a list/);
  assert.throws(() => createWith(five), /at most 4/);
  assert.throws(() => createWith([
    {emoji: 'snowflake', label: 'One'},
    {emoji: 'snowflake', label: 'Two'},
  ]), /appears more than once/);
  assert.throws(() => createWith([
    {emoji: 'white_check_mark', label: 'Reserved'},
  ]), /reserved for attendance/);
  assert.throws(() => createWith([
    {emoji: 'not:fixed', label: 'Invalid'},
  ]), /Slack emoji shortcode/);
  assert.throws(() => createWith([
    {emoji: 'snowflake', label: '...'},
  ]), /label is required/);
});

test('source pairs use the same normalization boundary as saved snapshots', () => {
  const sourceWith = defaultPlanReactions => ({
    id: 40,
    name: 'Hostile source',
    plan_reaction_sort_key: 'hostile source',
    default_plan_reactions: defaultPlanReactions,
  });

  assert.throws(
    () => Model.buildCatalog([sourceWith({})], []),
    /expected a list/,
  );
  assert.throws(
    () => Model.resolve([sourceWith(Array.from(
      {length: 5},
      (_, index) => ({emoji: `option_${index}`, label: `Option ${index}`}),
    ))], []),
    /at most 4/,
  );
  assert.throws(
    () => Model.resolve([sourceWith([
      {emoji: 'snowflake', label: 'One'},
      {emoji: 'snowflake', label: 'Two'},
    ])], []),
    /appears more than once/,
  );
  assert.throws(
    () => Model.buildCatalog([sourceWith([
      {emoji: 'one', label: 'Reserved'},
    ])], []),
    /reserved for attendance/,
  );

  const normalized = Model.resolve([sourceWith([
    {emoji: '\x1f:SNOWFLAKE:\x1f', label: '  Snow route  '},
  ])], []);
  assert.deepEqual(normalized.rows.map(({emoji, label}) => ({emoji, label})), [
    {emoji: 'snowflake', label: 'Snow route'},
  ]);
  assert.throws(
    () => Model.resolve([sourceWith([
      {emoji: '\ufeffsnowflake\ufeff', label: 'Snow route'},
    ])], []),
    /Slack emoji shortcode/,
  );
});

test('snapshot matches Python line, punctuation, and Unicode length rules', () => {
  const base = Model.create({
    types: [intervals],
    activities: [],
    savedSnapshot: null,
  });
  const rowId = base.rows[0].rowId;
  const lineBreaks = ['\n', '\r', '\v', '\f', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029'];

  for (const separator of lineBreaks) {
    const state = Model.updateLabel(base, rowId, `Before${separator}After`);
    assert.throws(
      () => Model.snapshot(state),
      error => error.rowId === rowId && /single line/.test(error.message),
    );
  }

  const punctuation = Model.updateLabel(base, rowId, '...');
  assert.throws(
    () => Model.snapshot(punctuation),
    error => error.rowId === rowId && /required/.test(error.message),
  );

  const pythonWhitespace = Model.updateLabel(base, rowId, '\x1fSnow route\x1f');
  assert.equal(Model.snapshot(pythonWhitespace)[0].label, 'Snow route');
  const byteOrderMark = Model.updateLabel(base, rowId, '\ufeff');
  assert.equal(Model.snapshot(byteOrderMark)[0].label, '\ufeff');

  const eightyCodePoints = Model.updateLabel(base, rowId, '😀'.repeat(80));
  assert.equal(Model.snapshot(eightyCodePoints)[0].label, '😀'.repeat(80));
  const eightyOneCodePoints = Model.updateLabel(base, rowId, '😀'.repeat(81));
  assert.throws(
    () => Model.snapshot(eightyOneCodePoints),
    error => error.rowId === rowId && /80/.test(error.message),
  );
});

test('picker-open transition is clone-safe and reconcile and Restore close it', () => {
  const state = Model.create({types: [], activities: [], savedSnapshot: null});
  const opened = Model.setAddOpen(state, true);

  assert.notStrictEqual(opened, state);
  assert.equal(state.addOpen, false);
  assert.equal(opened.addOpen, true);
  assert.equal(Model.reconcile(opened, {types: [], activities: []}).addOpen, false);
  assert.equal(Model.restore(opened, {types: [], activities: []}).addOpen, false);
});

test('canAdd follows blocking, slots, inherited, and unconfigured rules', () => {
  const empty = Model.create({types: [], activities: [], savedSnapshot: null});
  assert.equal(Model.canAdd(empty), true);

  const inherited = Model.create({
    types: [intervals],
    activities: [],
    savedSnapshot: null,
  });
  assert.equal(Model.canAdd(inherited), false);

  const unconfigured = Model.create({
    types: [intervals],
    activities: [run, strength],
    savedSnapshot: null,
  });
  assert.deepEqual(unconfigured.unconfiguredActivityNames, ['Strength']);
  assert.equal(Model.canAdd(unconfigured), true);

  const invalid = Model.reconcile(empty, {
    types: [conflictingType],
    activities: [run, rollerski],
  });
  assert.equal(Model.canAdd(invalid), false);
});
