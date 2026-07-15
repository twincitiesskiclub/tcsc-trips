(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticePlanReactions = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const MAX = 4;
  const MAX_LABEL = 80;
  const MAX_NAME = 80;
  const EMOJI_RE = /^([a-z0-9_+\-]+)(?:::skin-tone-[2-6])?$/;
  const LINE_BREAK_RE = /[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/;
  const PYTHON_TRIM_RE =
    /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/g;
  const PYTHON_TRIM_END_RE =
    /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/;
  const RESERVED = new Set([
    'white_check_mark', 'ballot_box_with_check', 'heavy_check_mark',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'keycap_ten',
  ]);

  function clone(state) {
    return structuredClone(state);
  }

  function validationError(message, rowId = null) {
    const error = new Error(message);
    if (rowId !== null) error.rowId = rowId;
    return error;
  }

  function codePointLength(value) {
    return Array.from(value).length;
  }

  function pythonTrim(value) {
    return value.replace(PYTHON_TRIM_RE, '');
  }

  function normalizeEmoji(value, source, rowId) {
    let emoji = pythonTrim(String(value || '')).toLowerCase();
    if (emoji.startsWith(':') && emoji.endsWith(':') && emoji.length > 2) {
      emoji = emoji.slice(1, -1);
    }
    if (codePointLength(emoji) > MAX_NAME) {
      throw validationError(
        `${source}: emoji name must be ${MAX_NAME} characters or fewer`,
        rowId,
      );
    }
    const match = EMOJI_RE.exec(emoji);
    if (!match) {
      throw validationError(
        `${source}: enter a Slack emoji shortcode`,
        rowId,
      );
    }
    if (RESERVED.has(match[1])) {
      throw validationError(
        `${source}: :${emoji}: is reserved for attendance`,
        rowId,
      );
    }
    return emoji;
  }

  function requireDisplayLabel(label, source, rowId) {
    const display = label
      .replace(/[.?!]+$/, '')
      .replace(PYTHON_TRIM_END_RE, '');
    if (!display) {
      throw validationError(`${source}: label is required`, rowId);
    }
  }

  function normalizePairs(value, {
    source = 'Plan reactions',
    rowIds = [],
  } = {}) {
    if (value === null || value === undefined) return [];
    if (!Array.isArray(value)) {
      throw new Error(`${source}: expected a list`);
    }
    if (value.length > MAX) {
      throw new Error(`${source}: use at most ${MAX} reactions`);
    }

    const normalized = [];
    const seen = new Set();
    value.forEach((item, index) => {
      const itemSource = `${source} row ${index + 1}`;
      const rowId = rowIds[index] === undefined ? null : rowIds[index];
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw validationError(
          `${itemSource}: expected emoji and label`,
          rowId,
        );
      }
      const emoji = normalizeEmoji(item.emoji, itemSource, rowId);
      const rawLabel = String(item.label || '');
      if (LINE_BREAK_RE.test(rawLabel)) {
        throw validationError(
          `${itemSource}: label must be a single line`,
          rowId,
        );
      }
      const label = pythonTrim(rawLabel);
      if (!label) {
        throw validationError(`${itemSource}: label is required`, rowId);
      }
      requireDisplayLabel(label, itemSource, rowId);
      if (codePointLength(label) > MAX_LABEL) {
        throw validationError(
          `${itemSource}: label must be ${MAX_LABEL} characters or fewer`,
          rowId,
        );
      }
      if (seen.has(emoji)) {
        throw validationError(
          `${source}: :${emoji}: appears more than once`,
          rowId,
        );
      }
      seen.add(emoji);
      normalized.push({emoji, label});
    });
    return normalized;
  }

  function distinct(items, kind) {
    const seen = new Set();
    return (items || []).filter(item => {
      const key = item && item.id;
      const name = pythonTrim(String((item && item.name) || ''));
      if (
        typeof key !== 'number'
        || !Number.isInteger(key)
        || key <= 0
        || !name
      ) {
        throw new Error(`Invalid ${kind} reaction source`);
      }
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function sourceIds(items, kind) {
    return distinct(items, kind).map(item => item.id);
  }

  function compareCodePoints(left, right) {
    const leftPoints = Array.from(String(left), char => char.codePointAt(0));
    const rightPoints = Array.from(String(right), char => char.codePointAt(0));
    const length = Math.min(leftPoints.length, rightPoints.length);
    for (let index = 0; index < length; index += 1) {
      if (leftPoints[index] !== rightPoints[index]) {
        return leftPoints[index] - rightPoints[index];
      }
    }
    return leftPoints.length - rightPoints.length;
  }

  function sortSources(items, kind) {
    return distinct(items, kind)
      .map((item, inputOrder) => ({item, inputOrder}))
      .sort((left, right) => {
        const leftKey = typeof left.item.plan_reaction_sort_key === 'string'
          ? left.item.plan_reaction_sort_key
          : String(left.item.name || '').toLowerCase();
        const rightKey = typeof right.item.plan_reaction_sort_key === 'string'
          ? right.item.plan_reaction_sort_key
          : String(right.item.name || '').toLowerCase();
        return compareCodePoints(leftKey, rightKey)
          || left.inputOrder - right.inputOrder;
      })
      .map(entry => entry.item);
  }

  function resolve(types, activities) {
    const typeSources = sortSources(types, 'type');
    const activitySources = sortSources(activities, 'activity');
    const sources = typeSources.map(item => ({kind: 'type', item}));
    if (activitySources.length >= 2) {
      sources.push(
        ...activitySources.map(item => ({kind: 'activity', item})),
      );
    }

    const rows = [];
    const seen = new Map();
    for (const source of sources) {
      const sourceKey = `${source.kind}:${Number(source.item.id)}`;
      const sourceName = `${
        source.kind === 'type' ? 'Workout Type' : 'Activity'
      } ${source.item.name}`;
      for (const pair of normalizePairs(
        source.item.default_plan_reactions || [],
        {source: sourceName},
      )) {
        const prior = seen.get(pair.emoji);
        if (prior && prior.label !== pair.label) {
          return {
            rows: [],
            unconfiguredActivityNames: [],
            error: `:${pair.emoji}: has conflicting labels in ${prior.sourceName} and ${sourceName}`,
          };
        }
        if (prior) {
          prior.sourceKeys.push(sourceKey);
        } else {
          const row = {
            emoji: pair.emoji,
            label: pair.label,
            sourceKeys: [sourceKey],
            sourceName,
          };
          seen.set(pair.emoji, row);
          rows.push(row);
        }
      }
    }
    if (rows.length > MAX) {
      return {
        rows: [],
        unconfiguredActivityNames: [],
        error: 'Selected Activities and Workout Types produce more than 4 reactions',
      };
    }
    return {
      rows,
      unconfiguredActivityNames: activitySources.length >= 2
        ? activitySources
          .filter(item => !(item.default_plan_reactions || []).length)
          .map(item => item.name)
        : [],
      error: null,
    };
  }

  function emptyState(types, activities) {
    return {
      rows: [],
      suppressed: [],
      lastValidTypeIds: sourceIds(types, 'type'),
      lastValidActivityIds: sourceIds(activities, 'activity'),
      nextRowNumber: 0,
      blockingError: null,
      unconfiguredActivityNames: [],
      effectiveInheritedCount: 0,
      addOpen: false,
    };
  }

  function newRow(state, {
    emoji,
    label,
    inheritedSourceKeys = [],
    inheritedOrder = null,
    protectedOrder = null,
    catalogOrder = null,
  }) {
    const row = {
      rowId: `r${state.nextRowNumber}`,
      emoji,
      label,
      removed: false,
      inheritedSourceKeys: [...inheritedSourceKeys],
      inheritedOrder,
      protectedOrder,
      catalogOrder,
    };
    state.nextRowNumber += 1;
    return row;
  }

  function rowSortKey(row) {
    if (row.inheritedOrder !== null) return [0, row.inheritedOrder];
    if (row.protectedOrder !== null) return [1, row.protectedOrder];
    return [2, row.catalogOrder === null ? 10000 : row.catalogOrder];
  }

  function sortRows(rows) {
    rows.sort((left, right) => {
      const leftKey = rowSortKey(left);
      const rightKey = rowSortKey(right);
      return leftKey[0] - rightKey[0] || leftKey[1] - rightKey[1];
    });
  }

  function create({types = [], activities = [], savedSnapshot = null}) {
    const saved = savedSnapshot === null
      ? null
      : normalizePairs(savedSnapshot, {source: 'Saved Plan reactions'});
    const resolution = resolve(types, activities);
    const state = emptyState(types, activities);
    if (resolution.error) {
      state.blockingError = resolution.error;
      if (saved !== null) {
        saved.forEach((pair, protectedOrder) => {
          state.rows.push(newRow(state, {
            emoji: pair.emoji,
            label: pair.label,
            protectedOrder,
          }));
        });
      }
      return state;
    }

    state.unconfiguredActivityNames = [
      ...resolution.unconfiguredActivityNames,
    ];
    state.effectiveInheritedCount = resolution.rows.length;
    const current = new Map(
      resolution.rows.map((row, index) => [row.emoji, {index, row}]),
    );

    if (saved === null) {
      resolution.rows.forEach((row, inheritedOrder) => {
        state.rows.push(newRow(state, {
          emoji: row.emoji,
          label: row.label,
          inheritedSourceKeys: row.sourceKeys,
          inheritedOrder,
        }));
      });
    } else {
      saved.forEach((pair, protectedOrder) => {
        const match = current.get(pair.emoji);
        state.rows.push(newRow(state, {
          emoji: pair.emoji,
          label: pair.label,
          inheritedSourceKeys: match ? match.row.sourceKeys : [],
          inheritedOrder: match ? match.index : null,
          protectedOrder: match ? null : protectedOrder,
        }));
      });
      const savedKeys = new Set(saved.map(pair => pair.emoji));
      state.suppressed = resolution.rows
        .map((row, inheritedOrder) => ({
          emoji: row.emoji,
          sourceKeys: [...row.sourceKeys],
          inheritedOrder,
        }))
        .filter(item => !savedKeys.has(item.emoji));
    }
    sortRows(state.rows);
    return state;
  }

  function reconcile(state, {types = [], activities = []}) {
    const original = clone(state);
    const resolution = resolve(types, activities);
    if (resolution.error) {
      original.blockingError = resolution.error;
      original.addOpen = false;
      return original;
    }

    const working = clone(state);
    const desired = new Map(
      resolution.rows.map((row, index) => [row.emoji, {index, row}]),
    );
    const keptSuppression = [];
    for (const item of working.suppressed) {
      const match = desired.get(item.emoji);
      if (
        match
        && item.sourceKeys.some(key => match.row.sourceKeys.includes(key))
      ) {
        keptSuppression.push({
          emoji: item.emoji,
          sourceKeys: [...item.sourceKeys],
          inheritedOrder: match.index,
        });
      }
    }
    keptSuppression.sort(
      (left, right) => left.inheritedOrder - right.inheritedOrder,
    );
    const suppressedKeys = new Set(
      keptSuppression.map(item => item.emoji),
    );

    working.rows = working.rows.filter(row => {
      const match = desired.get(row.emoji);
      if (match) {
        row.inheritedOrder = match.index;
        row.inheritedSourceKeys = [...match.row.sourceKeys];
      } else {
        row.inheritedOrder = null;
        row.inheritedSourceKeys = [];
      }
      return Boolean(
        match || row.protectedOrder !== null || row.catalogOrder !== null
      );
    });

    const byEmoji = new Map(working.rows.map(row => [row.emoji, row]));
    resolution.rows.forEach((resolved, inheritedOrder) => {
      if (!byEmoji.has(resolved.emoji) && !suppressedKeys.has(resolved.emoji)) {
        const row = newRow(working, {
          emoji: resolved.emoji,
          label: resolved.label,
          inheritedSourceKeys: resolved.sourceKeys,
          inheritedOrder,
        });
        working.rows.push(row);
        byEmoji.set(row.emoji, row);
      }
    });
    working.suppressed = keptSuppression;

    if (new Set(working.rows.map(row => row.emoji)).size > MAX) {
      original.blockingError =
        'Selected Activities and Workout Types reserve more than 4 reactions';
      original.addOpen = false;
      return original;
    }

    sortRows(working.rows);
    working.lastValidTypeIds = sourceIds(types, 'type');
    working.lastValidActivityIds = sourceIds(activities, 'activity');
    working.unconfiguredActivityNames = [
      ...resolution.unconfiguredActivityNames,
    ];
    working.effectiveInheritedCount = resolution.rows.length;
    working.blockingError = null;
    working.addOpen = false;
    return working;
  }

  function reservedSlots(state) {
    return new Set(state.rows.map(row => row.emoji)).size;
  }

  function remove(state, rowId) {
    const working = clone(state);
    const row = working.rows.find(item => item.rowId === rowId);
    if (!row) throw new Error('Unknown reaction row');
    row.removed = true;
    return working;
  }

  function undo(state, rowId) {
    const working = clone(state);
    const row = working.rows.find(item => item.rowId === rowId);
    if (!row || !row.removed) {
      throw new Error('Unknown removed reaction row');
    }
    row.removed = false;
    return working;
  }

  function sourceKeyIsApplicable(sourceKey, state) {
    const match = /^(type|activity):([1-9][0-9]*)$/.exec(sourceKey);
    if (!match) return false;
    const sourceId = Number(match[2]);
    if (match[1] === 'type') {
      return state.lastValidTypeIds.includes(sourceId);
    }
    return state.lastValidActivityIds.length >= 2
      && state.lastValidActivityIds.includes(sourceId);
  }

  function add(state, option) {
    if (!option) throw new Error('Choose a Plan reaction');
    const pair = normalizePairs([option])[0];
    option = {...option, ...pair};
    const working = clone(state);
    working.addOpen = false;
    const suppressed = working.suppressed.find(
      item => item.emoji === option.emoji,
    );
    let inheritedSourceKeys = [];
    let inheritedOrder = null;
    if (suppressed) {
      inheritedSourceKeys = suppressed.sourceKeys.filter(key =>
        sourceKeyIsApplicable(key, working)
      );
      if (inheritedSourceKeys.length) {
        inheritedOrder = suppressed.inheritedOrder;
      }
    }
    working.suppressed = working.suppressed.filter(
      item => item.emoji !== option.emoji,
    );

    const existing = working.rows.find(row => row.emoji === option.emoji);
    if (existing) {
      if (existing.catalogOrder === null) {
        existing.catalogOrder = Math.max(
          -1,
          ...working.rows
            .map(row => row.catalogOrder)
            .filter(order => order !== null),
        ) + 1;
      }
      sortRows(working.rows);
      return working;
    }
    if (reservedSlots(working) >= MAX) {
      throw new Error('Plan reactions: use at most 4 reactions');
    }
    const catalogOrder = Math.max(
      -1,
      ...working.rows
        .map(row => row.catalogOrder)
        .filter(order => order !== null),
    ) + 1;
    working.rows.push(newRow(working, {
      emoji: option.emoji,
      label: option.label,
      inheritedSourceKeys,
      inheritedOrder,
      catalogOrder,
    }));
    sortRows(working.rows);
    working.addOpen = false;
    return working;
  }

  function restore(state, {types = [], activities = []}) {
    const restored = create({types, activities, savedSnapshot: null});
    if (restored.blockingError) {
      const working = clone(state);
      working.blockingError = restored.blockingError;
      working.addOpen = false;
      return working;
    }
    let nextRowNumber = state.nextRowNumber;
    for (const row of restored.rows) {
      row.rowId = `r${nextRowNumber}`;
      nextRowNumber += 1;
    }
    restored.nextRowNumber = nextRowNumber;
    return restored;
  }

  function updateLabel(state, rowId, label) {
    const working = clone(state);
    const row = working.rows.find(item => item.rowId === rowId);
    if (!row) throw new Error('Unknown reaction row');
    row.label = label;
    return working;
  }

  function activeRows(state) {
    return state.rows.filter(row => !row.removed);
  }

  function snapshot(state) {
    if (state.blockingError) throw new Error(state.blockingError);
    const rows = activeRows(state);
    return normalizePairs(
      rows.map(row => ({emoji: row.emoji, label: row.label})),
      {
        source: 'Plan reactions',
        rowIds: rows.map(row => row.rowId),
      },
    );
  }

  function rowByEmoji(state, emoji) {
    return state.rows.find(row => row.emoji === emoji) || null;
  }

  function buildCatalog(types, activities) {
    const sources = [
      ...sortSources(types, 'type')
        .map(item => ({kind: 'type', item})),
      ...sortSources(activities, 'activity')
        .map(item => ({kind: 'activity', item})),
    ];
    const merged = new Map();
    const ordered = [];
    for (const source of sources) {
      const sourceKey = `${source.kind}:${Number(source.item.id)}`;
      const sourceName = `${
        source.kind === 'type' ? 'Workout Type' : 'Activity'
      } ${source.item.name}`;
      for (const pair of normalizePairs(
        source.item.default_plan_reactions || [],
        {source: sourceName},
      )) {
        const key = JSON.stringify([pair.emoji, pair.label]);
        if (merged.has(key)) {
          merged.get(key).sourceKeys.push(sourceKey);
        } else {
          const option = {
            optionId: `c${ordered.length}`,
            emoji: pair.emoji,
            label: pair.label,
            sourceKeys: [sourceKey],
          };
          merged.set(key, option);
          ordered.push(option);
        }
      }
    }
    return ordered;
  }

  function availableCatalog(state, catalog) {
    const reserved = new Set(state.rows.map(row => row.emoji));
    return (catalog || []).filter(option => !reserved.has(option.emoji));
  }

  function canAdd(state) {
    return !state.blockingError
      && reservedSlots(state) < MAX
      && (
        state.effectiveInheritedCount === 0
        || state.unconfiguredActivityNames.length > 0
      );
  }

  function setAddOpen(state, isOpen) {
    const working = clone(state);
    working.addOpen = Boolean(isOpen);
    return working;
  }

  return {
    MAX,
    resolve,
    create,
    reconcile,
    restore,
    remove,
    undo,
    add,
    updateLabel,
    activeRows,
    snapshot,
    reservedSlots,
    rowByEmoji,
    buildCatalog,
    availableCatalog,
    canAdd,
    setAddOpen,
  };
});
