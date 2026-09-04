// Shared by trip registration and the admin survey preview.
export function initTripSurvey(form, showError) {
  const document = form.ownerDocument;
  const DIETARY_OPTIONS = [
    'None', 'Vegan', 'Vegetarian', 'Gluten-Free',
    'Dairy Free / Lactose Intolerant', 'Nut allergy', 'Halal', 'Kosher',
    'Pescatarian', 'Other (specify below)',
  ]; // Mirrors DIETARY_OPTIONS in app/trips/service.py - keep in sync.

  const dietaryBox = form.querySelector('#dietary-options');
  DIETARY_OPTIONS.forEach(function (option) {
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.value = option;
    box.dataset.dietary = 'true';
    label.appendChild(box);
    label.appendChild(document.createTextNode(' ' + option));
    dietaryBox.appendChild(label);
  });

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
      } else if (type === 'yes_no') {
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
      wrapper.classList.toggle('hidden', !applies);
      wrapper.querySelectorAll('input, select').forEach(function (input) {
        input.disabled = !applies;
      });
    });
    const driver = form.querySelector('input[name="profile-can-drive"]:checked');
    const driverDetails = form.querySelector('#driver-details');
    const driverDetailsHidden = !driver || driver.value !== 'yes';
    driverDetails.classList.toggle('hidden', driverDetailsHidden);
    driverDetails.querySelectorAll('input').forEach(function (input) {
      input.disabled = driverDetailsHidden;
    });
  }
  form.addEventListener('change', applyVisibility);
  applyVisibility();

  // multi-choice caps
  form.addEventListener('change', function (event) {
    const group = event.target.closest('[data-max-selections]');
    if (!group) return;
    const cap = Number(group.dataset.maxSelections);
    const checked = group.querySelectorAll('input:checked');
    if (checked.length > cap) {
      event.target.checked = false;
      showError('Pick at most ' + cap + ' options.');
    }
  });
}
