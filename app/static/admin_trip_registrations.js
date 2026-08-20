// Admin trip roster: dynamic registration columns and payment actions.
(function () {
  'use strict';

  var root = document.querySelector('[data-page="trip-registrations"]');
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

  var table = document.getElementById('trip-reg-table');
  var head = table.querySelector('thead');
  var body = table.querySelector('tbody');
  var search = document.getElementById('trip-reg-filter');
  var statusFilter = document.getElementById('trip-reg-status');
  var resultCount = document.getElementById('trip-reg-count');
  var selectedCount = document.getElementById('trip-reg-selected-count');
  var bulkCapture = document.getElementById('trip-reg-bulk-capture');
  var bulkRefund = document.getElementById('trip-reg-bulk-refund');
  var dataUrl = '/admin/trips/' + root.dataset.tripId + '/registrations/data';
  var rows = [];
  var columns = [];
  var selectedPaymentIds = new Set();
  var sortKey = 'created_at';
  var sortDirection = -1;

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

  function postJSON(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload || {})
    }).then(function (response) {
      return response.json().catch(function () { return {}; })
        .then(function (data) {
          if (!response.ok || data.success === false) {
            throw new Error(
              data.error || 'Request failed (' + response.status + ')'
            );
          }
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

  function displayCell(key, value) {
    if (key === 'amount_cents') return formatMoney(value);
    if (key === 'created_at') return formatDateTime(value);
    if (key === 'status' || key === 'payment_status') return humanize(value);
    return String(value === null || value === undefined ? '' : value);
  }

  function canCapture(registration) {
    return registration.payment_id !== null &&
      registration.payment_id !== undefined &&
      registration.payment_status === 'requires_capture';
  }

  function canRefund(registration) {
    return registration.payment_id !== null &&
      registration.payment_id !== undefined &&
      (registration.payment_status === 'requires_capture' ||
       registration.payment_status === 'succeeded');
  }

  function selectedRows() {
    return rows.filter(function (registration) {
      return selectedPaymentIds.has(String(registration.payment_id));
    });
  }

  function updateBulkBar() {
    var selected = selectedRows();
    var captureCount = selected.filter(canCapture).length;
    var refundCount = selected.filter(canRefund).length;
    selectedCount.textContent = selected.length + ' selected';
    bulkCapture.disabled = captureCount === 0;
    bulkRefund.disabled = refundCount === 0;
  }

  function renderHead() {
    var row = el('tr');
    row.appendChild(el('th', null, ['Select']));
    columns.forEach(function (column) {
      row.appendChild(el('th', null, [
        el('button', {
          type: 'button',
          class: 'atr-sort',
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
    row.appendChild(el('th', null, ['Actions']));
    head.replaceChildren(row);
  }

  function refresh() {
    return fetchJSON(dataUrl).then(function (data) {
      columns = data.columns || [];
      rows = data.registrations || [];
      selectedPaymentIds.clear();
      renderHead();
      renderBody();
    });
  }

  function runRowMutation(button, url, successMessage) {
    button.disabled = true;
    return postJSON(url).then(function () {
      showSuccess(successMessage);
      return refresh();
    }).catch(showError).finally(function () {
      button.disabled = false;
    });
  }

  function actionButton(label, registration, endpoint, danger) {
    var button = el('button', {
      type: 'button',
      class: 'atr-button' + (danger ? ' atr-button-danger' : ''),
      onclick: function () {
        var question = label + ' payment for ' + registration.member + '?';
        if (!window.confirm(question)) return;
        runRowMutation(
          button,
          '/admin/payments/' + registration.payment_id + '/' + endpoint,
          label === 'Capture' ? 'Payment captured.' : 'Payment released.'
        );
      }
    }, [label]);
    return button;
  }

  function selectionCell(registration) {
    var cell = el('td');
    if (!canRefund(registration)) return cell;
    var paymentId = String(registration.payment_id);
    var checkbox = el('input', {
      type: 'checkbox',
      'aria-label': 'Select payment for ' + registration.member
    });
    checkbox.checked = selectedPaymentIds.has(paymentId);
    checkbox.addEventListener('change', function () {
      if (checkbox.checked) {
        selectedPaymentIds.add(paymentId);
      } else {
        selectedPaymentIds.delete(paymentId);
      }
      updateBulkBar();
    });
    cell.appendChild(checkbox);
    return cell;
  }

  function renderBody() {
    var query = search.value.trim().toLowerCase();
    var status = statusFilter.value;
    var filtered = rows.filter(function (registration) {
      if (status && registration.status !== status) return false;
      if (!query) return true;
      return columns.some(function (column) {
        return String(registration[column.key] || '')
          .toLowerCase()
          .includes(query);
      });
    }).sort(function (a, b) {
      return compareRows(a, b, sortKey, sortDirection);
    });

    resultCount.textContent = filtered.length + (
      filtered.length === 1 ? ' registration' : ' registrations'
    );
    body.replaceChildren();
    if (!filtered.length) {
      body.appendChild(el('tr', null, [
        el('td', {
          colspan: String(columns.length + 2),
          class: 'atr-empty'
        }, [
          rows.length
            ? 'No registrations match these filters.'
            : 'No registrations yet.'
        ])
      ]));
      updateBulkBar();
      return;
    }

    filtered.forEach(function (registration) {
      var row = el('tr');
      row.appendChild(selectionCell(registration));
      columns.forEach(function (column) {
        row.appendChild(el('td', null, [
          displayCell(column.key, registration[column.key])
        ]));
      });

      var actions = el('div', {class: 'atr-actions'});
      if (canCapture(registration)) {
        actions.appendChild(actionButton(
          'Capture', registration, 'capture', false
        ));
      }
      if (canRefund(registration)) {
        actions.appendChild(actionButton(
          'Release', registration, 'refund', true
        ));
      }
      row.appendChild(el('td', null, [actions]));
      body.appendChild(row);
    });
    updateBulkBar();
  }

  function runBulkMutation(button, endpoint, eligible, successMessage) {
    var paymentIds = selectedRows().filter(eligible).map(function (registration) {
      return registration.payment_id;
    });
    if (!paymentIds.length) return;
    if (!window.confirm(
      button.textContent.trim() + ' (' + paymentIds.length + ')?'
    )) return;
    bulkCapture.disabled = true;
    bulkRefund.disabled = true;
    postJSON('/admin/payments/' + endpoint, {payment_ids: paymentIds})
      .then(function () {
        showSuccess(successMessage);
        return refresh();
      }).catch(function (error) {
        showError(error);
        updateBulkBar();
      });
  }

  search.addEventListener('input', renderBody);
  statusFilter.addEventListener('change', renderBody);
  bulkCapture.addEventListener('click', function () {
    runBulkMutation(
      bulkCapture,
      'bulk-capture',
      canCapture,
      'Selected payments captured.'
    );
  });
  bulkRefund.addEventListener('click', function () {
    runBulkMutation(
      bulkRefund,
      'bulk-refund',
      canRefund,
      'Selected payments released.'
    );
  });
  refresh().catch(showError);
})();
