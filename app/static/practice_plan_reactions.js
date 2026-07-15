(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticePlanReactions = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const MAX = 4;

  function clone(state) {
    return structuredClone(state);
  }

  function distinct(items) {
    const seen = new Set();
    return (items || []).filter(item => {
      const key = Number(item.id);
      if (!Number.isInteger(key) || key <= 0 || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function sourceIds(items) {
    return distinct(items).map(item => Number(item.id));
  }

  function resolve(types, activities) {
    const typeSources = distinct(types).sort((left, right) =>
      left.name.localeCompare(right.name)
    );
    const activitySources = distinct(activities).sort((left, right) =>
      left.name.localeCompare(right.name)
    );
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
      for (const pair of source.item.default_plan_reactions || []) {
        const prior = seen.get(pair.emoji);
        if (prior && prior.label !== pair.label) {
          return {
            rows: [],
            unconfiguredActivityNames: [],
            error: `:${pair.emoji}: conflicts between ${prior.sourceName} and ${sourceName}`,
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
      lastValidTypeIds: sourceIds(types),
      lastValidActivityIds: sourceIds(activities),
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
    const resolution = resolve(types, activities);
    const state = emptyState(types, activities);
    if (resolution.error) {
      state.blockingError = resolution.error;
      if (savedSnapshot !== null) {
        (savedSnapshot || []).forEach((pair, protectedOrder) => {
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

    if (savedSnapshot === null) {
      resolution.rows.forEach((row, inheritedOrder) => {
        state.rows.push(newRow(state, {
          emoji: row.emoji,
          label: row.label,
          inheritedSourceKeys: row.sourceKeys,
          inheritedOrder,
        }));
      });
    } else {
      const saved = savedSnapshot || [];
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
    working.lastValidTypeIds = sourceIds(types);
    working.lastValidActivityIds = sourceIds(activities);
    working.unconfiguredActivityNames = [
      ...resolution.unconfiguredActivityNames,
    ];
    working.effectiveInheritedCount = resolution.rows.length;
    working.blockingError = null;
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
    const working = clone(state);
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
    const row = state.rows.find(item => item.rowId === rowId);
    if (!row) throw new Error('Unknown reaction row');
    row.label = label;
    return state;
  }

  function activeRows(state) {
    return state.rows.filter(row => !row.removed);
  }

  function validationError(message, rowId) {
    const error = new Error(message);
    error.rowId = rowId;
    return error;
  }

  function snapshot(state) {
    if (state.blockingError) throw new Error(state.blockingError);
    return activeRows(state).map(row => {
      const label = String(row.label || '').trim();
      if (!label) {
        throw validationError(
          `Description for :${row.emoji}: is required.`,
          row.rowId,
        );
      }
      if (label.length > 80) {
        throw validationError(
          `Description for :${row.emoji}: must be 80 characters or fewer.`,
          row.rowId,
        );
      }
      if (/\r|\n/.test(label)) {
        throw validationError(
          `Description for :${row.emoji}: must be a single line.`,
          row.rowId,
        );
      }
      return {emoji: row.emoji, label};
    });
  }

  function rowByEmoji(state, emoji) {
    return state.rows.find(row => row.emoji === emoji) || null;
  }

  function buildCatalog(types, activities) {
    const sources = [
      ...distinct(types)
        .sort((left, right) => left.name.localeCompare(right.name))
        .map(item => ({kind: 'type', item})),
      ...distinct(activities)
        .sort((left, right) => left.name.localeCompare(right.name))
        .map(item => ({kind: 'activity', item})),
    ];
    const merged = new Map();
    const ordered = [];
    for (const source of sources) {
      const sourceKey = `${source.kind}:${Number(source.item.id)}`;
      for (const pair of source.item.default_plan_reactions || []) {
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
  };
});
