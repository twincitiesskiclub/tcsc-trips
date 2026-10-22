(function () {
  'use strict';

  var root = document.getElementById('scholarships');
  var members = document.getElementById('ts-members');
  if (!root || !members) return;
  var filter = document.getElementById('ts-filter');
  var amount = document.getElementById('ts-amount');
  var send = document.getElementById('ts-send');
  var error = document.getElementById('ts-error');

  function postJSON(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
      body: JSON.stringify(payload || {})
    }).then(function (response) {
      return response.json().catch(function () { return {}; })
        .then(function (data) {
          if (!response.ok || data.success === false) {
            throw new Error(data.error || 'Request failed (' + response.status + ')');
          }
          return data;
        });
    });
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  function checkedIds() {
    return Array.prototype.map.call(
      members.querySelectorAll('input:checked'),
      function (input) { return Number(input.value); });
  }

  function refreshSend() {
    var count = checkedIds().length;
    send.disabled = count === 0;
    send.textContent = 'Send to ' + count + (count === 1 ? ' member' : ' members');
  }

  filter.addEventListener('input', function () {
    var needle = filter.value.trim().toLowerCase();
    members.querySelectorAll('[data-search]').forEach(function (row) {
      // Checked members stay visible so a narrowed filter never hides a pick.
      var checked = row.querySelector('input').checked;
      row.hidden = !checked && needle !== '' && row.dataset.search.indexOf(needle) === -1;
    });
  });
  members.addEventListener('change', refreshSend);

  send.addEventListener('click', function () {
    var ids = checkedIds();
    if (!ids.length) return;
    var dollars = amount.value;
    if (!window.confirm('Send a $' + dollars + ' scholarship DM to ' + ids.length +
        (ids.length === 1 ? ' member?' : ' members?'))) return;
    send.disabled = true;
    showError('');
    postJSON('/admin/trips/scholarships/send', {user_ids: ids, amount_dollars: dollars})
      .then(function () { window.location.reload(); })
      .catch(function (err) { showError(err.message); refreshSend(); });
  });

  root.addEventListener('click', function (event) {
    var button = event.target.closest('[data-resend]');
    if (!button) return;
    button.disabled = true;
    postJSON('/admin/trips/scholarships/' + button.dataset.resend + '/resend')
      .then(function () { window.location.reload(); })
      .catch(function (err) { showError(err.message); button.disabled = false; });
  });

  refreshSend();
})();
