(function tripQuestionBuilder() {
  var hidden = document.getElementById('custom_questions_json');
  var container = document.getElementById('trip-question-rows');
  var addButton = document.getElementById('add-trip-question');
  var templateSelect = document.getElementById('template_key');
  var templateNode = document.getElementById('trip-template-data');
  if (!hidden || !container) return;
  var templates = templateNode ? JSON.parse(templateNode.textContent) : {};

  var rows;
  try { rows = JSON.parse(hidden.value) || []; } catch (e) { rows = []; }

  var TYPES = [
    ['text', 'Text'], ['choice', 'Single choice'],
    ['multi_choice', 'Multi choice'], ['yes_no', 'Yes / No'],
  ];

  function field(labelText, control) {
    var wrap = document.createElement('div');
    wrap.className = 'aef-field';
    var label = document.createElement('label');
    label.textContent = labelText;
    if (control.id) label.htmlFor = control.id;
    wrap.appendChild(label);
    wrap.appendChild(control);
    return wrap;
  }

  function input(id, value, type) {
    var node = document.createElement('input');
    node.type = type || 'text';
    node.id = id;
    node.value = value == null ? '' : value;
    return node;
  }

  function yesNoKeys(uptoIndex) {
    return rows.slice(0, uptoIndex)
      .filter(function (r) { return r.type === 'yes_no' && r.key; })
      .map(function (r) { return r.key; });
  }

  function render() {
    container.textContent = '';
    rows.forEach(function (item, index) {
      var row = document.createElement('div');
      row.className = 'aef-editor-row';
      var grid = document.createElement('div');
      grid.className = 'aef-editor-grid';

      var key = input('tq-key-' + index, item.key);
      key.dataset.field = 'key';
      key.pattern = '[a-z0-9_]+';
      key.required = true;
      grid.appendChild(field('Key', key));

      var label = input('tq-label-' + index, item.label);
      label.dataset.field = 'label';
      label.required = true;
      grid.appendChild(field('Label', label));

      var type = document.createElement('select');
      type.id = 'tq-type-' + index;
      type.dataset.field = 'type';
      TYPES.forEach(function (pair) {
        var option = document.createElement('option');
        option.value = pair[0];
        option.textContent = pair[1];
        if (item.type === pair[0]) option.selected = true;
        type.appendChild(option);
      });
      grid.appendChild(field('Type', type));

      var options = document.createElement('textarea');
      options.id = 'tq-options-' + index;
      options.dataset.field = 'options';
      options.rows = 4;
      options.value = (item.options || []).join('\n');
      grid.appendChild(field('Options (one per line)', options));

      var cap = input('tq-cap-' + index, item.max_selections, 'number');
      cap.dataset.field = 'max-selections';
      cap.min = '1';
      grid.appendChild(field('Pick up to (multi choice only)', cap));

      var help = input('tq-help-' + index, item.help_text);
      help.dataset.field = 'help-text';
      grid.appendChild(field('Help text', help));

      var required = input('tq-required-' + index, null, 'checkbox');
      required.dataset.field = 'required';
      required.checked = Boolean(item.required);
      grid.appendChild(field('Required', required));

      var visSelect = document.createElement('select');
      visSelect.id = 'tq-visible-' + index;
      visSelect.dataset.field = 'visible-if';
      var none = document.createElement('option');
      none.value = '';
      none.textContent = 'Always shown';
      visSelect.appendChild(none);
      yesNoKeys(index).forEach(function (parentKey) {
        ['yes', 'no'].forEach(function (answer) {
          var option = document.createElement('option');
          option.value = parentKey + '=' + answer;
          option.textContent = 'Only if "' + parentKey + '" = ' + answer;
          if (item.visible_if
              && item.visible_if.question === parentKey
              && item.visible_if.equals === answer) option.selected = true;
          visSelect.appendChild(option);
        });
      });
      grid.appendChild(field('Show when', visSelect));

      var remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'aef-remove';
      remove.textContent = 'Remove question';
      remove.addEventListener('click', function () {
        rows.splice(index, 1);
        render();
      });

      row.appendChild(grid);
      row.appendChild(remove);
      row.addEventListener('input', sync);
      row.addEventListener('change', function (event) {
        sync();
        if (event.target.dataset.field === 'key'
            || event.target.dataset.field === 'type') render();
      });
      container.appendChild(row);
    });
    sync();
  }

  function sync() {
    rows = Array.from(container.querySelectorAll('.aef-editor-row'))
      .map(function (row) {
        var visible = row.querySelector('[data-field="visible-if"]').value;
        var capValue = row.querySelector('[data-field="max-selections"]').value;
        var item = {
          key: row.querySelector('[data-field="key"]').value.trim(),
          label: row.querySelector('[data-field="label"]').value.trim(),
          type: row.querySelector('[data-field="type"]').value,
          options: row.querySelector('[data-field="options"]').value
            .split('\n').map(function (o) { return o.trim(); }).filter(Boolean),
          required: row.querySelector('[data-field="required"]').checked,
          help_text: row.querySelector('[data-field="help-text"]').value.trim(),
        };
        if (capValue && item.type === 'multi_choice') item.max_selections = Number(capValue);
        if (visible) {
          var parts = visible.split('=');
          item.visible_if = { question: parts[0], equals: parts[1] };
        }
        return item;
      });
    hidden.value = JSON.stringify(rows);
  }

  addButton.addEventListener('click', function () {
    rows.push({ key: '', label: '', type: 'text', options: [],
                required: false, help_text: '' });
    render();
  });

  if (templateSelect) {
    templateSelect.addEventListener('change', function () {
      var template = templates[templateSelect.value];
      if (!template) return;
      if (rows.length
          && !window.confirm('Replace the current questions with this template?')) return;
      rows = JSON.parse(JSON.stringify(template.custom_questions || []));
      render();
    });
  }

  var form = hidden.closest('form');
  if (form) form.addEventListener('submit', sync);
  render();
})();
