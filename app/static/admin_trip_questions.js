(function tripQuestionBuilder() {
  'use strict';

  var hidden = document.getElementById('custom_questions_json');
  var container = document.getElementById('trip-question-rows');
  if (!hidden || !container) return;
  var form = hidden.closest('form');
  var addButton = document.getElementById('add-trip-question');
  var templateSelect = document.getElementById('template_key');
  var templatePanel = document.getElementById('trip-template-preview');
  var templateNode = document.getElementById('trip-template-data');
  var appliedTemplate = document.getElementById('applied-trip-template');
  var errorSummary = document.getElementById('trip-question-errors');
  var status = document.getElementById('trip-question-status');
  var templates = templateNode ? JSON.parse(templateNode.textContent) : {};
  var submitted = false;
  var nextId = 0;
  var rows = [];

  var TYPES = {
    text: 'Text', choice: 'Single choice',
    multi_choice: 'Multiple choice', yes_no: 'Yes or no'
  };
  // Keep in sync with RESERVED_QUESTION_KEYS in app/trips/questions.py.
  var RESERVED_KEYS = new Set([
    'id', 'member', 'email', 'status', 'price_tier',
    'can_drive', 'seat_capacity', 'bike_capacity', 'hitch_size',
    'region_code', 'dietary', 'dietary_restrictions', 'dietary_other',
    'has_tent', 'amount_cents', 'payment_status', 'payment_id', 'created_at'
  ]);

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function button(text, className, action) {
    var node = el('button', className, text);
    node.type = 'button';
    node.addEventListener('click', action);
    return node;
  }

  function slugify(label) {
    return label.normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/['\u2019]/g, '').replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'question';
  }

  function uniqueKey(base, used) {
    var key = base;
    var suffix = 2;
    while (used.has(key) || RESERVED_KEYS.has(key)) key = base + '_' + suffix++;
    return key;
  }

  function optionsFor(row) {
    return row.optionsText.split(/\r?\n/).map(function (line) {
      return line.trim();
    }).filter(Boolean);
  }

  function hasOptions(row) {
    return row.data.type === 'choice' || row.data.type === 'multi_choice';
  }

  function makeRow(question, isNew) {
    return {
      id: 'tq-' + nextId++, data: Object.assign({key: '', label: '', type: '', required: false}, question),
      optionsText: (question.options || []).join('\n'),
      capText: question.max_selections == null ? '' : String(question.max_selections),
      autoKey: Boolean(isNew), open: Boolean(isNew),
      advancedOpen: false, previewOpen: false, touched: new Set()
    };
  }

  function questionFor(row) {
    var data = row.data;
    var question = {
      key: data.key.trim(), label: data.label.trim(),
      type: data.type, required: Boolean(data.required)
    };
    if (hasOptions(row)) question.options = optionsFor(row);
    if (data.type === 'multi_choice' && row.capText.trim()
        && Number.isFinite(Number(row.capText))) {
      question.max_selections = Number(row.capText);
    }
    if ((data.help_text || '').trim()) question.help_text = data.help_text.trim();
    if (data.visible_if != null) question.visible_if = data.visible_if;
    return question;
  }

  function sync() {
    // UI state and irrelevant or empty optional fields never enter the payload.
    hidden.value = JSON.stringify(rows.map(questionFor));
  }

  function earlierParents(row, order) {
    return order.slice(0, order.indexOf(row)).filter(function (parent) {
      return parent.data.type === 'yes_no' && parent.data.key;
    });
  }

  function bindParent(row) {
    var condition = row.data.visible_if;
    // Track the parent card while its key is edited, even through a blank or duplicate draft.
    row.parent = condition ? earlierParents(row, rows).find(function (parent) {
      return parent.data.key === condition.question;
    }) : null;
  }

  function validCondition(row, order) {
    var condition = row.data.visible_if;
    return condition && Object.keys(condition).sort().join(',') === 'equals,question'
      && ['yes', 'no'].includes(condition.equals)
      && earlierParents(row, order).some(function (parent) {
        return parent.data.key === condition.question;
      });
  }

  function moveReason(row, offset) {
    var index = rows.indexOf(row);
    var destination = index + offset;
    if (destination < 0 || destination >= rows.length) return 'Already at the end.';
    var order = rows.slice();
    order.splice(index, 1);
    order.splice(destination, 0, row);
    var broken = rows.some(function (item) {
      return validCondition(item, rows) && !validCondition(item, order);
    });
    return broken ? 'Keep follow-up questions after the yes or no question they depend on.' : '';
  }

  function dependents(row) {
    return rows.filter(function (item) {
      return item !== row && (item.parent === row || (!item.parent && item.data.visible_if
        && item.data.visible_if.question === row.data.key));
    });
  }

  function validationErrors() {
    var keys = rows.map(function (row) { return questionFor(row).key; });
    var errors = [];
    rows.forEach(function (row, index) {
      var question = questionFor(row);
      function error(field, message) { errors.push({row: row, field: field, message: message}); }
      if (!question.label) error('label', 'Enter a question for registrants to answer.');
      if (!/^[a-z0-9_]+$/.test(question.key)) {
        error('key', 'Use lowercase letters, numbers and underscores for the key.');
      } else if (RESERVED_KEYS.has(question.key)) {
        error('key', 'This key is used by the system. Choose another key.');
      } else if (keys.some(function (key, i) { return i !== index && key === question.key; })) {
        error('key', 'This key is already used by another question. Choose a unique key.');
      }
      if (!Object.hasOwn(TYPES, question.type)) error('type', 'Choose an answer type.');
      if (hasOptions(row) && !question.options.length) {
        error('options', 'Add at least one option, with one option per line.');
      }
      if (question.type === 'multi_choice' && row.capText.trim()
          && (!Number.isSafeInteger(Number(row.capText)) || Number(row.capText) < 1)) {
        error('max-selections', 'Enter a whole number greater than zero, or leave this blank.');
      }
      if (row.data.visible_if != null && !validCondition(row, rows)) {
        error('visible-if', 'Choose an earlier yes or no question, or choose Always shown.');
      }
    });
    return errors;
  }

  function setOpen(row, open) {
    row.open = open;
    row.refs.body.hidden = !open;
    row.refs.toggle.setAttribute('aria-expanded', String(open));
    row.refs.chevron.textContent = open ? '\u25be' : '\u25b8';
  }

  function focusField(row, field) {
    setOpen(row, true);
    if (field === 'key') row.refs.advanced.open = true;
    row.refs.fields[field].control.focus();
  }

  function showErrors() {
    var errors = validationErrors();
    var visible = errors.filter(function (error) {
      return submitted || error.row.touched.has(error.field);
    });
    rows.forEach(function (row) {
      Object.values(row.refs.fields).forEach(function (field) {
        field.error.textContent = '';
        field.error.hidden = true;
        field.control.removeAttribute('aria-invalid');
      });
      row.refs.invalid.hidden = !visible.some(function (error) { return error.row === row; });
    });
    visible.forEach(function (error) {
      var field = error.row.refs.fields[error.field];
      field.error.textContent = error.message;
      field.error.hidden = false;
      field.control.setAttribute('aria-invalid', 'true');
    });
    errorSummary.replaceChildren();
    errorSummary.hidden = !visible.length;
    if (visible.length) {
      errorSummary.appendChild(el('p', '', 'Fix ' + visible.length
        + (visible.length === 1 ? ' issue' : ' issues') + ' in Trip questions before saving.'));
      var list = el('ul');
      visible.forEach(function (error) {
        var item = el('li');
        item.appendChild(button('Question ' + (rows.indexOf(error.row) + 1) + ': '
          + error.message, 'tq-error-link', function () { focusField(error.row, error.field); }));
        list.appendChild(item);
      });
      errorSummary.appendChild(list);
    }
    return errors;
  }

  function field(row, name, labelText, control, hintText) {
    var wrap = el('div', 'aef-field');
    control.id = row.id + '-' + name;
    control.dataset.field = name;
    var label = el('label', '', labelText);
    label.htmlFor = control.id;
    wrap.append(label, control);
    var describedBy = [];
    if (hintText) {
      var hint = el('p', 'tq-hint', hintText);
      hint.id = control.id + '-hint';
      describedBy.push(hint.id);
      wrap.appendChild(hint);
    }
    var error = el('p', 'tq-error');
    error.id = control.id + '-error';
    error.hidden = true;
    describedBy.push(error.id);
    control.setAttribute('aria-describedby', describedBy.join(' '));
    wrap.appendChild(error);
    row.refs.fields[name] = {wrap: wrap, control: control, error: error};
    return wrap;
  }

  function input(value, type) {
    var node = el('input');
    node.type = type || 'text';
    node.value = value == null ? '' : value;
    return node;
  }

  function option(select, value, label) {
    var node = el('option', '', label);
    node.value = value;
    select.appendChild(node);
  }

  function updateConditionChoices(row) {
    var select = row.refs.fields['visible-if'].control;
    var condition = row.data.visible_if;
    select.replaceChildren();
    option(select, '', 'Always shown');
    var parents = earlierParents(row, rows);
    parents.forEach(function (parent) {
      ['yes', 'no'].forEach(function (answer) {
        option(select, JSON.stringify({question: parent.data.key, equals: answer}),
          (parent.data.label.trim() || 'Untitled question') + ': ' + answer);
      });
    });
    if (condition != null) {
      var value = JSON.stringify({question: condition.question, equals: condition.equals});
      if (!validCondition(row, rows)) {
        value = JSON.stringify(condition);
        option(select, value, 'Unavailable condition. Choose another rule.');
      }
      select.value = value;
    }
    row.refs.fields['visible-if'].wrap.hidden = !parents.length && condition == null;
  }

  function renderPreview(row) {
    var preview = row.refs.previewBody;
    var question = questionFor(row);
    preview.replaceChildren();
    preview.appendChild(el('legend', '', (question.label || 'Your question')
      + (question.required ? ' *' : '')));
    if (question.help_text) preview.appendChild(el('p', 'tq-hint', question.help_text));
    if (question.type === 'multi_choice' && question.max_selections > 0) {
      preview.appendChild(el('p', 'tq-hint', 'Pick up to ' + question.max_selections + '.'));
    }
    if (question.type === 'text') {
      var text = input('');
      text.placeholder = 'Type your answer';
      text.setAttribute('aria-label', question.label || 'Your answer');
      preview.appendChild(text);
    } else {
      var options = question.type === 'yes_no' ? ['Yes', 'No'] : (question.options || []);
      options.forEach(function (label) {
        var choice = el('label', 'tq-check');
        choice.append(input('', question.type === 'multi_choice' ? 'checkbox' : 'radio'),
          document.createTextNode(label));
        preview.appendChild(choice);
      });
    }
  }

  function refresh() {
    rows.forEach(function (row) { if (!row.parent) bindParent(row); });
    rows.forEach(function (row, index) {
      var refs = row.refs;
      var label = row.data.label.trim() || 'Untitled question';
      refs.title.textContent = (index + 1) + '. ' + label;
      refs.title.title = label;
      refs.type.textContent = TYPES[row.data.type] || 'Choose a type';
      refs.required.hidden = !row.data.required;
      var count = optionsFor(row).length;
      refs.count.textContent = count + (count === 1 ? ' option' : ' options');
      refs.count.hidden = !hasOptions(row);
      if (refs.optionCount.textContent !== refs.count.textContent) refs.optionCount.textContent = refs.count.textContent;
      refs.fields.options.wrap.hidden = !hasOptions(row);
      refs.fields['max-selections'].wrap.hidden = row.data.type !== 'multi_choice';
      if (refs.fields.key.control.value.trim() !== row.data.key) refs.fields.key.control.value = row.data.key;
      updateConditionChoices(row);
      var hasDependents = dependents(row).length > 0;
      refs.remove.disabled = hasDependents;
      refs.fields.type.control.disabled = hasDependents;
      refs.dependencyHint.hidden = !hasDependents;
      var orderBlocked = false;
      [-1, 1].forEach(function (offset) {
        var control = offset < 0 ? refs.up : refs.down;
        var reason = moveReason(row, offset);
        control.disabled = Boolean(reason);
        control.setAttribute('aria-label', 'Move question ' + (index + 1)
          + (offset < 0 ? ' up' : ' down'));
        control.title = reason || (offset < 0 ? 'Move up' : 'Move down');
        if (reason && index + offset >= 0 && index + offset < rows.length) orderBlocked = true;
      });
      refs.orderHint.hidden = !orderBlocked;
      if (refs.preview.open) renderPreview(row);
    });
    sync();
    showErrors();
  }

  function updateRow(row, event) {
    var control = event.target;
    var name = control.dataset.field;
    if (!name) return;
    var oldKey = row.data.key;
    row.touched.add(name);
    if (name === 'options') row.optionsText = control.value;
    else if (name === 'max-selections') row.capText = control.value;
    else if (name === 'required') row.data.required = control.checked;
    else if (name === 'visible-if') {
      row.data.visible_if = control.value ? JSON.parse(control.value) : null;
      bindParent(row);
    }
    else if (name === 'help-text') row.data.help_text = control.value;
    else if (name === 'key') {
      row.autoKey = false;
      row.data.key = control.value.trim();
    } else row.data[name] = control.value;
    if (name === 'label' && row.autoKey) {
      row.data.key = uniqueKey(slugify(row.data.label), new Set(rows.filter(function (item) {
        return item !== row;
      }).map(function (item) { return item.data.key; })));
    }
    if (row.data.key !== oldKey) {
      rows.forEach(function (item) {
        if (item.parent === row) {
          item.data.visible_if = Object.assign({}, item.data.visible_if, {question: row.data.key});
        }
      });
    }
    refresh();
  }

  function move(row, offset) {
    if (moveReason(row, offset)) return;
    var index = rows.indexOf(row);
    rows.splice(index, 1);
    rows.splice(index + offset, 0, row);
    render();
    var control = offset < 0 ? row.refs.up : row.refs.down;
    (control.disabled ? row.refs.toggle : control).focus();
    status.textContent = 'Question moved to position ' + (index + offset + 1) + '.';
  }

  function renderCard(row) {
    var card = el('article', 'tq-card');
    var refs = row.refs = {fields: {}};
    var header = el('div', 'tq-card-header');
    refs.toggle = button('', 'tq-toggle', function () { setOpen(row, !row.open); });
    refs.toggle.setAttribute('aria-controls', row.id + '-body');
    refs.chevron = el('span', 'tq-chevron');
    refs.chevron.setAttribute('aria-hidden', 'true');
    var summary = el('span', 'tq-summary');
    refs.title = el('span', 'tq-title');
    refs.type = el('span', 'tq-badge');
    refs.required = el('span', 'tq-badge tq-required', 'Required');
    refs.count = el('span', 'tq-hint');
    refs.invalid = el('span', 'tq-error', 'Needs attention');
    summary.append(refs.title, refs.type, refs.required, refs.count, refs.invalid);
    refs.toggle.append(refs.chevron, summary);
    var moves = el('div', 'tq-moves');
    refs.up = button('\u2191', 'aef-add', function () { move(row, -1); });
    refs.down = button('\u2193', 'aef-add', function () { move(row, 1); });
    moves.append(refs.up, refs.down);
    header.append(refs.toggle, moves);
    refs.orderHint = el('p', 'tq-hint tq-order-hint',
      'Follow-up questions must stay after the yes or no question they depend on.');
    refs.orderHint.id = row.id + '-order-hint';
    refs.up.setAttribute('aria-describedby', refs.orderHint.id);
    refs.down.setAttribute('aria-describedby', refs.orderHint.id);
    refs.body = el('div', 'tq-card-body');
    refs.body.id = row.id + '-body';
    var grid = el('div', 'tq-fields');
    var label = field(row, 'label', 'Question', input(row.data.label));
    label.classList.add('tq-full');
    var type = el('select');
    Object.entries(TYPES).forEach(function (pair) { option(type, pair[0], pair[1]); });
    if (!Object.hasOwn(TYPES, row.data.type)) option(type, row.data.type, 'Choose an answer type');
    type.value = row.data.type;
    grid.append(label, field(row, 'type', 'Answer type', type));
    var required = input('', 'checkbox');
    required.checked = Boolean(row.data.required);
    var requiredWrap = field(row, 'required', 'Required', required);
    requiredWrap.classList.add('tq-check-field');
    grid.appendChild(requiredWrap);
    var options = el('textarea');
    options.rows = 4;
    options.value = row.optionsText;
    options.placeholder = 'Cooking\nCleaning\nNo preference';
    var optionsWrap = field(row, 'options', 'Options', options,
      'Type or paste one option per line. Blank lines are ignored.');
    optionsWrap.classList.add('tq-full');
    refs.optionCount = el('p', 'tq-hint');
    refs.optionCount.setAttribute('aria-live', 'polite');
    optionsWrap.appendChild(refs.optionCount);
    var cap = input(row.capText);
    cap.inputMode = 'numeric';
    grid.append(optionsWrap, field(row, 'max-selections', 'Pick up to', cap,
      'Leave blank to allow any number of options.'));
    var help = field(row, 'help-text', 'Help text (optional)', input(row.data.help_text));
    help.classList.add('tq-full');
    var visible = field(row, 'visible-if', 'Show when', el('select'));
    visible.classList.add('tq-full');
    grid.append(help, visible);
    refs.preview = el('details', 'tq-preview');
    refs.preview.open = row.previewOpen;
    refs.preview.appendChild(el('summary', '', 'Registrant preview'));
    refs.previewBody = el('fieldset');
    refs.previewBody.disabled = true;
    refs.preview.appendChild(refs.previewBody);
    refs.preview.addEventListener('toggle', function () {
      row.previewOpen = refs.preview.open;
      if (row.previewOpen) renderPreview(row);
    });
    refs.advanced = el('details', 'tq-advanced');
    refs.advanced.open = row.advancedOpen;
    refs.advanced.appendChild(el('summary', '', 'Advanced'));
    var key = input(row.data.key);
    key.spellcheck = false;
    key.autocapitalize = 'none';
    refs.advanced.appendChild(field(row, 'key', 'Question key', key,
      'Generated from the question. Saved keys stay the same when you edit the wording. '
      + 'Changing a saved key can disconnect existing answers.'));
    refs.advanced.addEventListener('toggle', function () { row.advancedOpen = refs.advanced.open; });
    refs.remove = button('Remove question', 'aef-remove', function () {
      if (dependents(row).length) return;
      var index = rows.indexOf(row);
      rows.splice(index, 1);
      render();
      (rows[index] ? rows[index].refs.toggle : addButton).focus();
      status.textContent = 'Question removed.';
    });
    refs.dependencyHint = el('p', 'tq-hint',
      'Used by a follow-up question. Change its Show when rule before removing this question '
      + 'or changing its answer type.');
    refs.dependencyHint.id = row.id + '-dependency-hint';
    refs.remove.setAttribute('aria-describedby', refs.dependencyHint.id);
    type.setAttribute('aria-describedby', type.getAttribute('aria-describedby') + ' ' + refs.dependencyHint.id);
    refs.body.append(grid, refs.preview, refs.advanced, refs.remove, refs.dependencyHint);
    card.append(header, refs.orderHint, refs.body);
    card.addEventListener('input', function (event) { updateRow(row, event); });
    card.addEventListener('change', function (event) { updateRow(row, event); });
    setOpen(row, row.open);
    container.appendChild(card);
  }

  function render() {
    // Preserve native details state even if a pending toggle event has not fired.
    rows.forEach(function (row) {
      if (row.refs) {
        row.advancedOpen = row.refs.advanced.open;
        row.previewOpen = row.refs.preview.open;
      }
    });
    container.replaceChildren();
    if (!rows.length) container.appendChild(el('p', 'tq-empty',
      'No trip questions yet. Add a question or choose a template above.'));
    rows.forEach(renderCard);
    refresh();
    showTemplate();
  }

  function applyTemplate(append) {
    var source = templates[templateSelect.value].custom_questions;
    var existing = append ? rows : [];
    var used = new Set(existing.map(function (row) { return row.data.key; }));
    var reserved = new Set(Array.from(used).concat(source.map(function (q) { return q.key; })));
    var renamed = new Map();
    var additions = source.map(function (question) {
      var copy = JSON.parse(JSON.stringify(question));
      if (used.has(copy.key) || RESERVED_KEYS.has(copy.key)) {
        copy.key = uniqueKey(slugify(copy.key), reserved);
      }
      used.add(copy.key);
      reserved.add(copy.key);
      renamed.set(question.key, copy.key);
      return makeRow(copy, false);
    });
    additions.forEach(function (row) {
      if (row.data.visible_if) row.data.visible_if.question = renamed.get(row.data.visible_if.question);
    });
    if (appliedTemplate && (!append || !existing.length)) appliedTemplate.value = templateSelect.value;
    rows = existing.concat(additions);
    additions.forEach(bindParent);
    templateSelect.value = '';
    render();
    (additions.length ? additions[0].refs.toggle : addButton).focus();
    status.textContent = additions.length + ' questions ' + (append ? 'appended.' : 'loaded from the template.');
  }

  function showTemplate() {
    if (!templatePanel || !templateSelect) return;
    templatePanel.replaceChildren();
    var template = templates[templateSelect.value];
    templatePanel.hidden = !template;
    if (!template) return;
    var questions = template.custom_questions;
    templatePanel.appendChild(el('p', 'tq-template-title',
      templateSelect.selectedOptions[0].textContent + ': ' + questions.length + ' questions'));
    var list = el('ol');
    questions.forEach(function (question) { list.appendChild(el('li', '', question.label)); });
    templatePanel.appendChild(list);
    var actions = el('div', 'tq-template-actions');
    if (rows.length) {
      templatePanel.appendChild(el('p', 'tq-hint', 'Replace removes your ' + rows.length
        + ' current questions. Append keeps them and adds ' + questions.length + ' more.'));
      actions.appendChild(button('Replace questions', 'aef-remove', function () { applyTemplate(false); }));
      actions.appendChild(button('Append questions', 'aef-add', function () { applyTemplate(true); }));
    } else {
      actions.appendChild(button('Add ' + questions.length + ' questions', 'aef-add', function () { applyTemplate(false); }));
    }
    actions.appendChild(button('Cancel', 'aef-add', function () {
      templateSelect.value = '';
      showTemplate();
      templateSelect.focus();
    }));
    templatePanel.appendChild(actions);
  }

  try {
    var initial = JSON.parse(hidden.value || '[]');
    if (!Array.isArray(initial) || initial.some(function (q) { return !q || typeof q !== 'object'; })) {
      throw new Error('Invalid question list');
    }
    rows = initial.map(function (question) { return makeRow(question, false); });
    rows.forEach(bindParent);
  } catch (error) {
    errorSummary.hidden = false;
    errorSummary.textContent = 'The saved questions could not be loaded. Reload this page before editing.';
    addButton.disabled = true;
    if (templateSelect) templateSelect.disabled = true;
    form.addEventListener('submit', function (event) { event.preventDefault(); });
    return;
  }

  addButton.addEventListener('click', function () {
    var key = uniqueKey('question', new Set(rows.map(function (row) { return row.data.key; })));
    var row = makeRow({key: key, label: '', type: 'text', required: false}, true);
    rows.push(row);
    render();
    focusField(row, 'label');
    status.textContent = 'Question added.';
  });
  if (templateSelect) templateSelect.addEventListener('change', showTemplate);
  form.addEventListener('submit', function (event) {
    submitted = true;
    sync();
    var errors = showErrors();
    if (errors.length) {
      event.preventDefault();
      focusField(errors[0].row, errors[0].field);
    }
  });
  render();
})();
