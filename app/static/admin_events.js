// Admin event grids and JSON-backed event form editors.
(function () {
  'use strict';

  var root = document.querySelector('[data-page]');
  if (!root) return;

  var el = window.AdminUI && window.AdminUI.el
    ? window.AdminUI.el
    : function (tag, props, children) {
        var node = document.createElement(tag);
        Object.keys(props || {}).forEach(function (key) {
          if (key === 'class') node.className = props[key];
          else if (key.indexOf('on') === 0) {
            node.addEventListener(key.slice(2).toLowerCase(), props[key]);
          } else {
            node.setAttribute(key, props[key]);
          }
        });
        (children || []).forEach(function (child) {
          node.appendChild(
            typeof child === 'string'
              ? document.createTextNode(child)
              : child
          );
        });
        return node;
      };

  function showError(error) {
    var message = error && error.message
      ? error.message
      : 'Something went wrong.';
    if (window.showToast) {
      window.showToast(message, 'error');
    } else {
      window.alert(message);
    }
  }

  function showSuccess(message) {
    if (window.showToast) window.showToast(message, 'success');
  }

  function fetchJSON(url) {
    return fetch(url, {headers: {'Accept': 'application/json'}})
      .then(function (response) {
        return response.json().catch(function () { return {}; })
          .then(function (data) {
            if (!response.ok) {
              throw new Error(
                data.error || 'Request failed (' + response.status + ')'
              );
            }
            return data;
          });
      });
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json().catch(function () { return {}; })
        .then(function (data) {
          if (!response.ok || data.success === false) {
            throw new Error(
              data.error || 'Request failed (' + response.status + ')'
            );
          }
          if (data.message) showSuccess(data.message);
          return data;
        });
    });
  }

  function formatMoney(cents) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format((Number(cents) || 0) / 100);
  }

  function formatDateTime(value) {
    if (!value) return '';
    var parsed = new Date(value);
    if (isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(parsed);
  }

  function humanize(value) {
    return String(value || '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, function (letter) {
        return letter.toUpperCase();
      });
  }

  function compareRows(a, b, key, direction) {
    var aValue = a[key];
    var bValue = b[key];
    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return (aValue - bValue) * direction;
    }
    return String(aValue || '').localeCompare(
      String(bValue || ''),
      undefined,
      {numeric: true, sensitivity: 'base'}
    ) * direction;
  }

  function initEventsGrid() {
    var body = document.getElementById('event-grid-body');
    var search = document.getElementById('event-search');
    var statusFilter = document.getElementById('event-status-filter');
    var count = document.getElementById('event-result-count');
    var rows = [];
    var sortKey = 'event_date';
    var sortDirection = -1;

    function statusBadge(status) {
      return el('span', {
        class: 'ae-status ae-status-' + status
      }, [humanize(status)]);
    }

    function actionLink(label, href) {
      return el('a', {class: 'ae-action', href: href}, [label]);
    }

    function actionButton(label, handler, danger) {
      var button = el('button', {
        type: 'button',
        class: 'ae-action' + (danger ? ' ae-action-danger' : ''),
        onclick: function () {
          button.disabled = true;
          Promise.resolve(handler()).catch(showError).finally(function () {
            button.disabled = false;
          });
        }
      }, [label]);
      return button;
    }

    function refresh() {
      return fetchJSON(root.dataset.dataUrl).then(function (data) {
        rows = data.events || [];
        render();
      });
    }

    function render() {
      var query = search.value.trim().toLowerCase();
      var status = statusFilter.value;
      var filtered = rows.filter(function (row) {
        if (status && row.status !== status) return false;
        if (!query) return true;
        return (
          String(row.name || '').toLowerCase().includes(query) ||
          String(row.slug || '').toLowerCase().includes(query)
        );
      }).sort(function (a, b) {
        return compareRows(a, b, sortKey, sortDirection);
      });

      count.textContent = filtered.length + (
        filtered.length === 1 ? ' event' : ' events'
      );
      body.replaceChildren();
      if (!filtered.length) {
        body.appendChild(el('tr', null, [
          el('td', {colspan: '8', class: 'ae-empty'}, [
            rows.length
              ? 'No events match these filters.'
              : 'No events yet. Create one to get started.'
          ])
        ]));
        return;
      }

      filtered.forEach(function (row) {
        var actions = el('div', {class: 'ae-actions'}, [
          actionLink('Edit', '/admin/events/' + row.id + '/edit'),
          actionLink(
            'Registrations',
            '/admin/events/' + row.id + '/registrations'
          ),
          actionButton('Duplicate', function () {
            return postJSON(
              '/admin/events/' + row.id + '/duplicate'
            ).then(refresh);
          })
        ]);

        if (row.status === 'active') {
          actions.appendChild(actionButton('Close', function () {
            return postJSON(
              '/admin/events/' + row.id + '/status',
              {status: 'closed'}
            ).then(refresh);
          }));
        } else {
          actions.appendChild(actionButton('Activate', function () {
            return postJSON(
              '/admin/events/' + row.id + '/status',
              {status: 'active'}
            ).then(refresh);
          }));
        }
        if (row.status === 'draft') {
          actions.appendChild(actionButton('Delete', function () {
            if (!window.confirm(
              'Delete "' + row.name + '"? This cannot be undone.'
            )) return Promise.resolve();
            return postJSON(
              '/admin/events/' + row.id + '/delete'
            ).then(refresh);
          }, true));
        }

        body.appendChild(el('tr', null, [
          el('td', null, [
            el('a', {
              href: '/admin/events/' + row.id + '/edit',
              class: 'font-semibold text-tcsc-navy'
            }, [row.name]),
            el('div', {class: 'mt-1 text-xs text-zinc-500'}, [row.slug])
          ]),
          el('td', null, [formatDateTime(row.event_date)]),
          el('td', null, [humanize(row.audience)]),
          el('td', null, [statusBadge(row.status)]),
          el('td', null, [
            String(row.confirmed_count) + ' / ' +
            (row.capacity === null ? 'Unlimited' : row.capacity)
          ]),
          el('td', null, [formatMoney(row.revenue_cents)]),
          el('td', null, [row.template_key || 'Custom']),
          el('td', null, [actions])
        ]));
      });
    }

    search.addEventListener('input', render);
    statusFilter.addEventListener('change', render);
    root.querySelectorAll('[data-sort]').forEach(function (button) {
      button.addEventListener('click', function () {
        var nextKey = button.dataset.sort;
        if (sortKey === nextKey) {
          sortDirection *= -1;
        } else {
          sortKey = nextKey;
          sortDirection = 1;
        }
        render();
      });
    });
    refresh().catch(showError);
  }

  function initRegistrationsGrid() {
    var head = document.getElementById('registration-grid-head');
    var body = document.getElementById('registration-grid-body');
    var search = document.getElementById('registration-search');
    var statusFilter = document.getElementById(
      'registration-status-filter'
    );
    var count = document.getElementById('registration-result-count');
    var rows = [];
    var columns = [];
    var sortKey = 'created_at';
    var sortDirection = -1;

    function displayCell(key, value) {
      if (key === 'amount_cents') return formatMoney(value);
      if (key === 'discount_applied') return value ? 'Yes' : 'No';
      if (key === 'created_at') return formatDateTime(value);
      if (key === 'status') return humanize(value);
      return String(value === null || value === undefined ? '' : value);
    }

    function renderHead() {
      var row = el('tr');
      columns.forEach(function (column) {
        row.appendChild(el('th', null, [
          el('button', {
            type: 'button',
            class: 'aer-sort',
            onclick: function () {
              if (sortKey === column.key) {
                sortDirection *= -1;
              } else {
                sortKey = column.key;
                sortDirection = 1;
              }
              renderBody();
            }
          }, [column.label])
        ]));
      });
      row.appendChild(el('th', null, ['Action']));
      head.replaceChildren(row);
    }

    function refresh() {
      return fetchJSON(root.dataset.dataUrl).then(function (data) {
        columns = data.columns || [];
        rows = data.registrations || [];
        renderHead();
        renderBody();
      });
    }

    function renderBody() {
      var query = search.value.trim().toLowerCase();
      var status = statusFilter.value;
      var filtered = rows.filter(function (row) {
        if (status && row.status !== status) return false;
        if (!query) return true;
        return columns.some(function (column) {
          return String(row[column.key] || '')
            .toLowerCase()
            .includes(query);
        });
      }).sort(function (a, b) {
        return compareRows(a, b, sortKey, sortDirection);
      });

      count.textContent = filtered.length + (
        filtered.length === 1 ? ' registration' : ' registrations'
      );
      body.replaceChildren();
      if (!filtered.length) {
        body.appendChild(el('tr', null, [
          el('td', {
            colspan: String(columns.length + 1),
            class: 'aer-empty'
          }, [
            rows.length
              ? 'No registrations match these filters.'
              : 'No registrations yet.'
          ])
        ]));
        return;
      }

      filtered.forEach(function (registration) {
        var row = el('tr');
        columns.forEach(function (column) {
          row.appendChild(el('td', null, [
            displayCell(column.key, registration[column.key])
          ]));
        });

        var actionCell = el('td');
        if (
          registration.status === 'pending_payment' ||
          registration.status === 'confirmed'
        ) {
          var label = registration.status === 'confirmed'
            ? 'Refund'
            : 'Cancel';
          var button = el('button', {
            type: 'button',
            class: 'aer-action',
            onclick: function () {
              var question = label + ' registration #' +
                registration.id + '?';
              if (!window.confirm(question)) return;
              button.disabled = true;
              postJSON(
                root.dataset.cancelBase + registration.id + '/cancel'
              ).then(refresh).catch(showError).finally(function () {
                button.disabled = false;
              });
            }
          }, [label]);
          actionCell.appendChild(button);
        }
        row.appendChild(actionCell);
        body.appendChild(row);
      });
    }

    search.addEventListener('input', renderBody);
    statusFilter.addEventListener('change', renderBody);
    refresh().catch(showError);
  }

  function initEventForm() {
    var form = document.getElementById('event-editor-form');
    var priceHidden = document.getElementById('price_options_json');
    var questionHidden = document.getElementById(
      'custom_questions_json'
    );
    var priceContainer = document.getElementById('price-option-rows');
    var questionContainer = document.getElementById(
      'custom-question-rows'
    );
    var templateSelect = document.getElementById('template_key');
    var templateDataNode = document.getElementById(
      'event-template-data'
    );
    var templates = JSON.parse(templateDataNode.textContent || '{}');
    var priceRows = parseRows(priceHidden.value);
    var questionRows = parseRows(questionHidden.value);
    var priorNames = priceRows.map(function (item) {
      return (item.name || '').trim();
    });

    function parseRows(rawValue) {
      try {
        var parsed = JSON.parse(rawValue || '[]');
        return Array.isArray(parsed) ? parsed : [];
      } catch (_error) {
        return [];
      }
    }

    function clone(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function field(label, control, wide) {
      return el('div', {
        class: 'aef-field' + (wide ? ' ' + wide : '')
      }, [
        el('label', {for: control.id}, [label]),
        control
      ]);
    }

    function inputControl(id, type, value, required) {
      var input = el('input', {
        id: id,
        type: type,
        value: value === null || value === undefined ? '' : String(value)
      });
      if (required) input.required = true;
      return input;
    }

    function textareaControl(id, value, rows) {
      var textarea = el('textarea', {id: id, rows: String(rows)}, []);
      textarea.value = value || '';
      return textarea;
    }

    function dollars(cents) {
      if (cents === null || cents === undefined) return '';
      return (Number(cents) / 100).toFixed(2);
    }

    function cents(value) {
      return Math.round((Number(value) || 0) * 100);
    }

    function syncPrices() {
      priceRows = Array.from(
        priceContainer.querySelectorAll('.aef-editor-row')
      ).map(function (row) {
        var item = {
          name: row.querySelector('[data-field="name"]').value.trim(),
          description: row.querySelector(
            '[data-field="description"]'
          ).value.trim(),
          price_cents: cents(
            row.querySelector('[data-field="price"]').value
          ),
          member_price_cents: null,
          participant_roles: row.querySelector(
            '[data-field="roles"]'
          ).value.split(',').map(function (role) {
            return role.trim();
          }).filter(Boolean),
          active: row.querySelector('[data-field="active"]').checked
        };
        var memberPrice = row.querySelector(
          '[data-field="member-price"]'
        ).value;
        if (memberPrice !== '') {
          item.member_price_cents = cents(memberPrice);
        }
        if (row.dataset.optionId) {
          item.id = Number(row.dataset.optionId);
        }
        return item;
      });
      priceHidden.value = JSON.stringify(priceRows);
    }

    function syncQuestions() {
      questionRows = Array.from(
        questionContainer.querySelectorAll('.aef-editor-row')
      ).map(function (row) {
        return {
          key: row.querySelector('[data-field="key"]').value.trim(),
          label: row.querySelector('[data-field="label"]').value.trim(),
          type: row.querySelector('[data-field="type"]').value,
          options: row.querySelector('[data-field="options"]')
            .value.split('\n').map(function (option) {
              return option.trim();
            }).filter(Boolean),
          required: row.querySelector(
            '[data-field="required"]'
          ).checked,
          help_text: row.querySelector(
            '[data-field="help-text"]'
          ).value.trim(),
          price_options: Array.from(
            row.querySelectorAll('[data-field="scope"]:checked')
          ).map(function (box) {
            return box.value;
          })
        };
      });
      questionHidden.value = JSON.stringify(questionRows);
    }

    function rawNames() {
      return priceRows.map(function (item) {
        return (item.name || '').trim();
      });
    }

    function optionNames() {
      return rawNames().filter(Boolean);
    }

    // Renaming a price option must carry its question scopes along, or a
    // rename would orphan them and the save would be rejected.
    function renameQuestionScopes(before, after) {
      before.forEach(function (oldName, index) {
        var newName = after[index];
        if (!oldName || newName === undefined || newName === oldName) return;
        dropOrRenameScope(oldName, newName);
      });
    }

    function dropOrRenameScope(oldName, newName) {
      questionRows.forEach(function (question) {
        var scope = question.price_options;
        if (!Array.isArray(scope)) return;
        var at = scope.indexOf(oldName);
        if (at === -1) return;
        if (newName) scope[at] = newName;
        else scope.splice(at, 1);
      });
    }

    function scopeControl(item, index) {
      var names = optionNames();
      var wrapper = el('div', {
        class: 'aef-field aef-field-full aef-scope'
      }, [
        el('span', {class: 'aef-scope-label'}, ['Applies to options'])
      ]);
      if (!names.length) {
        wrapper.appendChild(el('span', {class: 'aef-hint'}, [
          'Add a price option first to limit this question.'
        ]));
        return wrapper;
      }

      var scope = Array.isArray(item.price_options)
        ? item.price_options
        : [];
      wrapper.appendChild(el('span', {class: 'aef-hint'}, [
        scope.length
          ? 'Asked only for the checked options.'
          : 'Nothing checked: asked for every option.'
      ]));
      var boxes = el('div', {class: 'aef-scope-boxes'});
      names.forEach(function (name, nameIndex) {
        var box = el('input', {
          id: 'question-scope-' + index + '-' + nameIndex,
          type: 'checkbox',
          value: name
        });
        box.checked = scope.indexOf(name) !== -1;
        box.dataset.field = 'scope';
        boxes.appendChild(el('label', {class: 'aef-check'}, [box, name]));
      });
      wrapper.appendChild(boxes);
      return wrapper;
    }

    function renderPrices() {
      priceContainer.replaceChildren();
      if (!priceRows.length) {
        priceContainer.appendChild(el('div', {class: 'aef-empty'}, [
          'No price options. Add one before activating a paid event.'
        ]));
        priceHidden.value = '[]';
        return;
      }

      priceRows.forEach(function (item, index) {
        var row = el('div', {
          class: 'aef-editor-row',
          dataset: item.id ? {optionId: String(item.id)} : {}
        });
        if (item.id) row.dataset.optionId = String(item.id);
        var grid = el('div', {class: 'aef-editor-grid'});

        var name = inputControl(
          'price-name-' + index,
          'text',
          item.name,
          true
        );
        name.dataset.field = 'name';
        var description = inputControl(
          'price-description-' + index,
          'text',
          item.description,
          false
        );
        description.dataset.field = 'description';
        var price = inputControl(
          'price-amount-' + index,
          'number',
          dollars(item.price_cents),
          true
        );
        price.step = '0.01';
        price.min = '0';
        price.dataset.field = 'price';
        var memberPrice = inputControl(
          'price-member-' + index,
          'number',
          dollars(item.member_price_cents),
          false
        );
        memberPrice.step = '0.01';
        memberPrice.min = '0';
        memberPrice.dataset.field = 'member-price';
        var roles = inputControl(
          'price-roles-' + index,
          'text',
          (item.participant_roles || []).join(', '),
          true
        );
        roles.dataset.field = 'roles';
        var active = inputControl(
          'price-active-' + index,
          'checkbox',
          '',
          false
        );
        active.checked = item.active !== false;
        active.dataset.field = 'active';

        grid.appendChild(field('Name', name, 'aef-field-wide'));
        grid.appendChild(field('Description', description, 'aef-field-full'));
        grid.appendChild(field('Price ($)', price));
        grid.appendChild(field('Member price ($)', memberPrice));
        grid.appendChild(field('Roles', roles, 'aef-field-wide'));
        grid.appendChild(el('label', {class: 'aef-check'}, [
          active,
          'Active'
        ]));
        row.appendChild(grid);
        row.appendChild(el('button', {
          type: 'button',
          class: 'aef-remove',
          onclick: function () {
            var removed = (priceRows[index] || {}).name;
            priceRows.splice(index, 1);
            if (removed) dropOrRenameScope(removed.trim(), '');
            priorNames = rawNames();
            renderPrices();
            renderQuestions();
          }
        }, ['Remove option']));
        row.addEventListener('input', syncPrices);
        // Scope checkboxes rebuild on blur, not on every keystroke, so
        // renaming an option does not steal focus mid-typing.
        row.addEventListener('change', function () {
          syncPrices();
          var current = rawNames();
          renameQuestionScopes(priorNames, current);
          priorNames = current;
          renderQuestions();
        });
        priceContainer.appendChild(row);
      });
      syncPrices();
    }

    function renderQuestions() {
      questionContainer.replaceChildren();
      if (!questionRows.length) {
        questionContainer.appendChild(el('div', {class: 'aef-empty'}, [
          'No custom questions.'
        ]));
        questionHidden.value = '[]';
        return;
      }

      questionRows.forEach(function (item, index) {
        var row = el('div', {class: 'aef-editor-row'});
        var grid = el('div', {class: 'aef-editor-grid'});
        var key = inputControl(
          'question-key-' + index,
          'text',
          item.key,
          true
        );
        key.pattern = '[a-z0-9_]+';
        key.dataset.field = 'key';
        var label = inputControl(
          'question-label-' + index,
          'text',
          item.label,
          true
        );
        label.dataset.field = 'label';
        var type = el('select', {id: 'question-type-' + index}, [
          el('option', {value: 'text'}, ['Text']),
          el('option', {value: 'choice'}, ['Choice'])
        ]);
        type.value = item.type || 'text';
        type.dataset.field = 'type';
        var options = textareaControl(
          'question-options-' + index,
          (item.options || []).join('\n'),
          4
        );
        options.dataset.field = 'options';
        var helpText = inputControl(
          'question-help-' + index,
          'text',
          item.help_text,
          false
        );
        helpText.dataset.field = 'help-text';
        var required = inputControl(
          'question-required-' + index,
          'checkbox',
          '',
          false
        );
        required.checked = item.required === true;
        required.dataset.field = 'required';

        grid.appendChild(field('Key', key));
        grid.appendChild(field('Label', label, 'aef-field-wide'));
        grid.appendChild(field('Type', type));
        grid.appendChild(field(
          'Options, one per line',
          options,
          'aef-field-wide'
        ));
        grid.appendChild(field(
          'Help text',
          helpText,
          'aef-field-wide'
        ));
        grid.appendChild(el('label', {class: 'aef-check'}, [
          required,
          'Required'
        ]));
        grid.appendChild(scopeControl(item, index));
        row.appendChild(grid);
        row.appendChild(el('button', {
          type: 'button',
          class: 'aef-remove',
          onclick: function () {
            questionRows.splice(index, 1);
            renderQuestions();
          }
        }, ['Remove question']));
        row.addEventListener('input', syncQuestions);
        row.addEventListener('change', syncQuestions);
        questionContainer.appendChild(row);
      });
      syncQuestions();
    }

    document.getElementById('add-price-option')
      .addEventListener('click', function () {
        priceRows.push({
          name: '',
          description: '',
          price_cents: 0,
          member_price_cents: null,
          participant_roles: ['Participant'],
          active: true
        });
        priorNames = rawNames();
        renderPrices();
        renderQuestions();
      });
    document.getElementById('add-question')
      .addEventListener('click', function () {
        questionRows.push({
          key: '',
          label: '',
          type: 'text',
          options: [],
          required: false,
          help_text: ''
        });
        renderQuestions();
      });
    if (templateSelect) {
      var templateKeyBefore = templateSelect.value;
      templateSelect.addEventListener('change', function () {
        // Applying a template replaces price options wholesale, which would
        // discard member prices an existing event depends on.
        var replacesLiveData = priceRows.length || questionRows.length;
        if (replacesLiveData && !window.confirm(
          'Applying this template replaces all price options and custom '
            + 'questions below, including any member prices. Continue?'
        )) {
          templateSelect.value = templateKeyBefore;
          return;
        }

        var selected = templates[templateSelect.value] || {
          price_options: [],
          custom_questions: []
        };
        priceRows = clone(selected.price_options || []);
        questionRows = clone(selected.custom_questions || []);
        priorNames = rawNames();
        templateKeyBefore = templateSelect.value;
        renderPrices();
        renderQuestions();
      });
    }
    form.addEventListener('submit', function () {
      syncPrices();
      syncQuestions();
    });

    renderPrices();
    renderQuestions();
  }

  if (root.dataset.page === 'events') initEventsGrid();
  if (root.dataset.page === 'registrations') initRegistrationsGrid();
  if (root.dataset.page === 'form') initEventForm();
})();
