// Shared by trip registration and the admin survey preview.
export function initTripSurvey(form, showError) {
  // --- conditional visibility ------------------------------------------
  // Mirrors visible_questions() in app/trips/service.py - keep in sync.
  function currentAnswers() {
    const answers = {};
    form.querySelectorAll('[data-question-key]').forEach(function (node) {
      const key = node.dataset.questionKey;
      const type = node.dataset.questionType;
      if (type === 'multi_choice') {
        answers[key] = Array.from(
          node.querySelectorAll('input:checked')).map(function (i) { return i.value; });
      } else if (type === 'yes_no' || (type === 'choice' && node.matches('[role="radiogroup"]'))) {
        const checked = node.querySelector('input:checked');
        answers[key] = checked ? checked.value : '';
      } else {
        answers[key] = node.value;
      }
    });
    return answers;
  }

  function applyVisibility() {
    const answers = currentAnswers();
    form.querySelectorAll('[data-question-field]').forEach(function (wrapper) {
      const raw = wrapper.dataset.visibleIf;
      if (!raw) return;
      const condition = JSON.parse(raw);
      const applies = answers[condition.question] === condition.equals;
      wrapper.hidden = !applies;
      wrapper.querySelectorAll('input, select').forEach(function (input) {
        input.disabled = !applies;
      });
    });
    const driver = form.querySelector('input[name="profile-can-drive"]:checked');
    const driverDetails = form.querySelector('#driver-details');
    const driverDetailsHidden = !driver || driver.value !== 'yes';
    if (driverDetails) {
      driverDetails.hidden = driverDetailsHidden;
      driverDetails.querySelectorAll('input').forEach(function (input) {
        input.disabled = driverDetailsHidden;
      });
    }
  }
  // Count after enforcing the cap, so the count always matches the payload.
  function updateCounter(group) {
    const counter = group.querySelector('[data-selection-counter]');
    if (counter) {
      counter.textContent = group.querySelectorAll('input:checked').length
        + ' of ' + group.dataset.maxSelections + ' selected';
    }
  }
  form.querySelectorAll('[data-max-selections]').forEach(updateCounter);
  form.addEventListener('change', function (event) {
    const group = event.target.closest('[data-max-selections]');
    if (group) {
      const cap = Number(group.dataset.maxSelections);
      if (group.querySelectorAll('input:checked').length > cap) {
        event.target.checked = false;
        showError('Pick at most ' + cap + ' options.', group);
      }
      updateCounter(group);
    }
    applyVisibility();
  });
  applyVisibility();
}
