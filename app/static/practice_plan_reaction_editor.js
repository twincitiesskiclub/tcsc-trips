(function (root, factory) {
  const model = typeof module === 'object' && module.exports
    ? require('./practice_plan_reactions.js')
    : root.PracticePlanReactions;
  const api = factory(model);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticePlanReactionEditor = api;
})(typeof window !== 'undefined' ? window : globalThis, function (Model) {
  'use strict';

  const CATALOG_EMPTY =
    'Configure reaction pairs in Practices Settings first.';
  const REACTION_FIELDS = new Set([
    'plan_reactions',
    'activity_ids',
    'type_ids',
  ]);

  function isReactionField(field) {
    return REACTION_FIELDS.has(field);
  }

  async function loadReferenceData(fetchImpl) {
    const specs = [
      ['locations', '/admin/practices/locations/data'],
      ['activities', '/admin/practices/activities/data'],
      ['types', '/admin/practices/types/data'],
      ['people', '/admin/practices/people/data'],
    ];
    const settled = await Promise.allSettled(specs.map(async ([key, url]) => {
      const response = await fetchImpl(url);
      if (!response.ok) {
        throw new Error(`${key} reference request failed (${response.status})`);
      }
      const body = await response.json();
      if (key === 'people') {
        const people = {};
        ['coaches', 'leads', 'assists'].forEach(role => {
          const value = body[role] ?? [];
          if (!Array.isArray(value)) {
            throw new Error(`people ${role} response is invalid`);
          }
          people[role] = value;
        });
        return people;
      }
      const value = body[key];
      if (!Array.isArray(value)) {
        throw new Error(`${key} reference response is invalid`);
      }
      return value;
    }));
    const result = {
      locations: [],
      activities: [],
      types: [],
      people: {coaches: [], leads: [], assists: []},
      failed: [],
      reactionSettingsReady: false,
    };
    settled.forEach((item, index) => {
      const key = specs[index][0];
      if (item.status === 'fulfilled') {
        result[key] = item.value;
      } else {
        result.failed.push(key);
      }
    });
    result.reactionSettingsReady = !result.failed.includes('activities')
      && !result.failed.includes('types');
    return result;
  }

  function mount({
    root,
    types = [],
    activities = [],
    selectedTypeIds = [],
    selectedActivityIds = [],
    savedSnapshot = null,
    referenceError = null,
  }) {
    if (!root) throw new Error('Plan reaction editor root is required');
    if (!Model) throw new Error('Practice plan reaction model is required');

    const document = root.ownerDocument;
    const rowsNode = root.querySelector('#plan-reaction-rows');
    const emptyNode = root.querySelector('#plan-reaction-empty');
    const restoreButton = root.querySelector('#restore-plan-reactions');
    const addButton = root.querySelector('#add-plan-reaction');
    const catalogSelect = root.querySelector('#plan-reaction-catalog');
    const unconfiguredNode = root.querySelector('#plan-reaction-unconfigured');
    const statusNode = root.querySelector('#plan-reaction-status');
    if (
      !rowsNode || !emptyNode || !restoreButton || !addButton
      || !catalogSelect || !unconfiguredNode || !statusNode
    ) {
      throw new Error('Plan reaction editor markup is incomplete');
    }

    const catalog = Model.buildCatalog(types, activities);
    const externalBlockingError = referenceError || null;
    let typeIds = normalizedIds(selectedTypeIds);
    let activityIds = normalizedIds(selectedActivityIds);
    let state = Model.create({
      types: selectedSources(types, typeIds),
      activities: selectedSources(activities, activityIds),
      savedSnapshot,
    });

    function normalizedIds(ids) {
      return (ids || []).map(Number).filter(Number.isInteger);
    }

    function selectedSources(sources, ids) {
      const wanted = new Set(ids);
      return (sources || []).filter(source => wanted.has(Number(source.id)));
    }

    function announce(message, isError = false) {
      statusNode.textContent = message || '';
      statusNode.classList.toggle('field-error', Boolean(isError));
    }

    restoreButton.disabled = Boolean(externalBlockingError);
    restoreButton.setAttribute('aria-describedby', 'plan-reaction-status');

    function syncLabels() {
      rowsNode.querySelectorAll('[data-reaction-row]').forEach(rowNode => {
        const input = rowNode.querySelector('.practice-reaction-label');
        if (input) {
          state = Model.updateLabel(
            state,
            rowNode.dataset.rowId,
            input.value,
          );
        }
      });
    }

    function renderedRow(rowId) {
      return Array.from(
        rowsNode.querySelectorAll('[data-reaction-row]'),
      ).find(rowNode => rowNode.dataset.rowId === rowId) || null;
    }

    function focusRowControl(rowId, selector) {
      const rowNode = renderedRow(rowId);
      const control = rowNode && rowNode.querySelector(selector);
      if (control) control.focus();
    }

    function clearSubmissionErrors() {
      rowsNode.querySelectorAll('.practice-reaction-label').forEach(input => {
        input.removeAttribute('aria-invalid');
        const errorId = input.getAttribute('aria-describedby');
        const errorNode = errorId && document.getElementById(errorId);
        if (errorNode) {
          errorNode.textContent = '';
          errorNode.hidden = true;
        }
      });
    }

    function makeButton(label, action, rowId, ariaLabel) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-secondary practice-reaction-action';
      button.dataset.action = action;
      button.dataset.rowId = rowId;
      button.textContent = label;
      button.setAttribute('aria-label', ariaLabel);
      return button;
    }

    function makeRow(row) {
      const rowNode = document.createElement('div');
      rowNode.className = 'practice-reaction-row';
      rowNode.dataset.reactionRow = '';
      rowNode.dataset.rowId = row.rowId;
      rowNode.dataset.emoji = row.emoji;
      if (row.removed) rowNode.classList.add('is-removed');

      const keyNode = document.createElement('span');
      keyNode.className = 'practice-reaction-key';
      keyNode.textContent = `:${row.emoji}:`;
      rowNode.append(keyNode);

      if (row.removed) {
        const description = document.createElement('span');
        description.className = 'practice-reaction-label-static';
        description.textContent = row.label;
        rowNode.append(description);

        const actions = document.createElement('span');
        const removedLabel = document.createElement('span');
        removedLabel.className = 'practice-reaction-removed-label';
        removedLabel.textContent = 'Removed';
        actions.append(removedLabel, document.createTextNode(' '));
        const undoButton = makeButton(
          'Undo',
          'undo',
          row.rowId,
          `Undo removal of :${row.emoji}: reaction`,
        );
        undoButton.addEventListener('click', () => {
          syncLabels();
          state = Model.undo(state, row.rowId);
          render();
          focusRowControl(row.rowId, '.practice-reaction-label');
          announce(`Restored :${row.emoji}:.`);
        });
        actions.append(undoButton);
        rowNode.append(actions);
        return rowNode;
      }

      const field = document.createElement('span');
      const labelId = `practice-reaction-label-${row.rowId}`;
      const errorId = `practice-reaction-error-${row.rowId}`;
      const input = document.createElement('input');
      input.type = 'text';
      input.id = labelId;
      input.className = 'form-control practice-reaction-label';
      input.maxLength = 80;
      input.value = row.label;
      input.setAttribute('aria-label', `Description for :${row.emoji}:`);
      input.setAttribute('aria-describedby', errorId);
      const errorNode = document.createElement('span');
      errorNode.id = errorId;
      errorNode.className = 'field-error practice-reaction-error';
      errorNode.hidden = true;
      field.append(input, errorNode);
      rowNode.append(field);

      const removeButton = makeButton(
        'Remove',
        'remove',
        row.rowId,
        `Remove :${row.emoji}: reaction`,
      );
      removeButton.addEventListener('click', () => {
        syncLabels();
        state = Model.remove(state, row.rowId);
        render();
        focusRowControl(row.rowId, '[data-action="undo"]');
        announce(`Removed :${row.emoji}:.`);
      });
      rowNode.append(removeButton);
      return rowNode;
    }

    function renderCatalog() {
      const options = Model.availableCatalog(state, catalog);
      catalogSelect.replaceChildren();
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Choose a reaction';
      catalogSelect.append(placeholder);
      options.forEach(option => {
        const optionNode = document.createElement('option');
        optionNode.value = option.optionId;
        optionNode.textContent = `:${option.emoji}: ${option.label}`;
        catalogSelect.append(optionNode);
      });
      const addAvailable = !externalBlockingError
        && Model.canAdd(state)
        && options.length > 0;
      addButton.hidden = !addAvailable;
      const catalogOpen = addAvailable && state.addOpen;
      catalogSelect.hidden = !catalogOpen;
      addButton.setAttribute('aria-expanded', String(catalogOpen));
    }

    function render() {
      const fragment = document.createDocumentFragment();
      state.rows.forEach(row => fragment.append(makeRow(row)));
      rowsNode.replaceChildren(fragment);
      emptyNode.hidden = state.rows.length > 0;
      renderCatalog();

      if (!externalBlockingError && catalog.length === 0) {
        unconfiguredNode.hidden = false;
        unconfiguredNode.textContent = CATALOG_EMPTY;
      } else if (state.unconfiguredActivityNames.length) {
        unconfiguredNode.hidden = false;
        unconfiguredNode.textContent =
          `No configured Activity reactions for: ${state.unconfiguredActivityNames.join(', ')}.`;
      } else {
        unconfiguredNode.hidden = true;
        unconfiguredNode.textContent = '';
      }
    }

    addButton.addEventListener('click', () => {
      syncLabels();
      state = Model.setAddOpen(state, true);
      renderCatalog();
      if (!catalogSelect.hidden) catalogSelect.focus();
    });

    catalogSelect.addEventListener('change', () => {
      syncLabels();
      const option = catalog.find(item => item.optionId === catalogSelect.value);
      if (!option) return;
      state = Model.add(state, option);
      const added = Model.rowByEmoji(state, option.emoji);
      render();
      if (added) focusRowControl(added.rowId, '.practice-reaction-label');
      announce(`Added :${option.emoji}:.`);
    });

    restoreButton.addEventListener('click', () => restore());

    function setSelection(nextTypeIds, nextActivityIds) {
      syncLabels();
      if (externalBlockingError) {
        announce(externalBlockingError, true);
        return;
      }
      typeIds = normalizedIds(nextTypeIds);
      activityIds = normalizedIds(nextActivityIds);
      state = Model.reconcile(state, {
        types: selectedSources(types, typeIds),
        activities: selectedSources(activities, activityIds),
      });
      render();
      if (state.blockingError) {
        announce(state.blockingError, true);
      } else if (state.unconfiguredActivityNames.length) {
        announce(
          `No configured Activity reactions for: ${state.unconfiguredActivityNames.join(', ')}.`,
        );
      } else {
        announce('Plan reactions updated.');
      }
    }

    function restore() {
      syncLabels();
      if (externalBlockingError) {
        announce(externalBlockingError, true);
        return;
      }
      state = Model.restore(state, {
        types: selectedSources(types, typeIds),
        activities: selectedSources(activities, activityIds),
      });
      render();
      if (state.blockingError) {
        announce(state.blockingError, true);
      } else {
        announce('Reaction defaults restored.');
      }
    }

    function snapshot() {
      syncLabels();
      clearSubmissionErrors();
      try {
        if (externalBlockingError) throw new Error(externalBlockingError);
        return Model.snapshot(state);
      } catch (error) {
        if (error.rowId) {
          const rowNode = renderedRow(error.rowId);
          const input = rowNode && rowNode.querySelector(
            '.practice-reaction-label',
          );
          if (input) {
            input.setAttribute('aria-invalid', 'true');
            const errorNode = document.getElementById(
              input.getAttribute('aria-describedby'),
            );
            if (errorNode) {
              errorNode.textContent = error.message;
              errorNode.hidden = false;
            }
            input.focus();
          }
        }
        announce(error.message, true);
        throw error;
      }
    }

    render();
    if (externalBlockingError) {
      announce(externalBlockingError, true);
    } else if (state.blockingError) {
      announce(state.blockingError, true);
    } else if (state.unconfiguredActivityNames.length) {
      announce(
        `No configured Activity reactions for: ${state.unconfiguredActivityNames.join(', ')}.`,
      );
    } else if (catalog.length === 0) {
      announce(CATALOG_EMPTY);
    }

    function showError(message) {
      announce(message, true);
    }

    return {setSelection, restore, snapshot, showError};
  }

  return {mount, loadReferenceData, isReactionField};
});
