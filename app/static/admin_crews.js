// Crews admin: season picker, rule fields, confirms, and live moves/swaps on a draft.
(function () {
  'use strict';

  function toast(message, type) {
    if (window.showToast) window.showToast(message, type);
    else window.alert(message);
  }

  // Post a move or swap; the server answers with a fresh #draft-body.
  async function send(url, data) {
    const body = document.getElementById('draft-body');
    body.classList.add('opacity-60');
    try {
      const response = await fetch(url, {method: 'POST', body: data, headers: {Accept: 'text/html'}});
      const text = await response.text();
      if (!response.ok) {
        toast(text || 'That change did not save. Refresh and try again.', 'error');
        return;
      }
      body.outerHTML = text;
    } catch (_) {
      toast('Could not reach the server. Your change did not save.', 'error');
    } finally {
      const current = document.getElementById('draft-body');
      if (current) current.classList.remove('opacity-60');
    }
  }

  document.addEventListener('change', function (event) {
    const el = event.target;
    if (el.matches('[data-season-picker]')) {
      window.location.href = el.value;
    } else if (el.matches('[data-move]')) {
      const data = new FormData();
      data.append('user_id', el.dataset.userId);
      data.append('crew', el.value);
      send(document.getElementById('draft-body').dataset.moveUrl, data);
    } else if (el.matches('[data-rule-kind]')) {
      const form = el.closest('[data-rule-form]');
      const pin = el.value === 'pin';
      form.querySelector('[data-rule-b]').classList.toggle('hidden', pin);
      form.querySelector('[data-rule-crew]').classList.toggle('hidden', !pin);
    }
  });

  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    } else if (form.matches('[data-swap-form]')) {
      event.preventDefault();
      send(form.action, new FormData(form));
    }
  });
})();
