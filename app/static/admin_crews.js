// Crews admin: season picker, rule fields, confirm prompts.
(function () {
  'use strict';

  document.addEventListener('change', function (event) {
    const el = event.target;
    if (el.matches('[data-season-picker]')) {
      window.location.href = el.value;
    } else if (el.matches('[data-rule-kind]')) {
      const form = el.closest('[data-rule-form]');
      const pin = el.value === 'pin';
      form.querySelector('[data-rule-b]').classList.toggle('hidden', pin);
      form.querySelector('[data-rule-crew]').classList.toggle('hidden', !pin);
    }
  });

  document.addEventListener('submit', function (event) {
    const message = event.target.dataset.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });
})();
