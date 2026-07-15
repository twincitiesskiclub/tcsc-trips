(function (root, factory) {
  const model = typeof module === 'object' && module.exports
    ? require('./practice_plan_reactions.js')
    : root.PracticePlanReactions;
  const api = factory(model);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticePlanReactionEditor = api;
})(typeof window !== 'undefined' ? window : globalThis, function (Model) {
  'use strict';

  function mount({
    root,
    types = [],
    activities = [],
    selectedTypeIds = [],
    selectedActivityIds = [],
    savedSnapshot = null,
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

    function syncLabels() {
      rowsNode.querySelectorAll('[data-reaction-row]').forEach(rowNode => {
        const input = rowNode.querySelector('.practice-reaction-label');
        if (input) {
          Model.updateLabel(state, rowNode.dataset.rowId, input.value);
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

    function makeButton(label, action, rowId) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-secondary practice-reaction-action';
      button.dataset.action = action;
      button.dataset.rowId = rowId;
      button.textContent = label;
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
        const undoButton = makeButton('Undo', 'undo', row.rowId);
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

      const removeButton = makeButton('Remove', 'remove', row.rowId);
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
      const addAvailable = Model.canAdd(state) && options.length > 0;
      addButton.hidden = !addAvailable;
      if (!addAvailable) {
        catalogSelect.hidden = true;
        addButton.setAttribute('aria-expanded', 'false');
      }
    }

    function render() {
      const fragment = document.createDocumentFragment();
      state.rows.forEach(row => fragment.append(makeRow(row)));
      rowsNode.replaceChildren(fragment);
      emptyNode.hidden = state.rows.length > 0;
      renderCatalog();

      if (state.unconfiguredActivityNames.length) {
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
      renderCatalog();
      catalogSelect.hidden = false;
      addButton.setAttribute('aria-expanded', 'true');
      catalogSelect.focus();
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
    if (state.blockingError) {
      announce(state.blockingError, true);
    } else if (state.unconfiguredActivityNames.length) {
      announce(
        `No configured Activity reactions for: ${state.unconfiguredActivityNames.join(', ')}.`,
      );
    }

    return {setSelection, restore, snapshot};
  }

  return {mount};
});
