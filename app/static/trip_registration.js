(function tripRegistrationPage() {
  const dataNode = document.getElementById('trip-registration-data');
  const form = document.getElementById('trip-registration-form');
  if (!dataNode || !form) return;
  const tripData = JSON.parse(dataNode.textContent);

  const DIETARY_OPTIONS = [
    'None', 'Vegan', 'Vegetarian', 'Gluten-Free',
    'Dairy Free / Lactose Intolerant', 'Nut allergy', 'Halal', 'Kosher',
    'Pescatarian', 'Other (specify below)',
  ]; // Mirrors DIETARY_OPTIONS in app/trips/service.py - keep in sync.

  const dietaryBox = document.getElementById('dietary-options');
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

  // --- email gate -------------------------------------------------------
  const gateButton = document.getElementById('gate-check');
  const gateMessage = document.getElementById('gate-message');
  const emailInput = document.getElementById('member-email');
  const formBody = document.getElementById('form-body');
  gateButton.addEventListener('click', async function () {
    gateMessage.classList.add('hidden');
    const response = await fetch('/api/trips/member-check', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: emailInput.value }),
    });
    const result = await response.json();
    if (result.eligible) {
      formBody.classList.remove('hidden');
      document.getElementById('gate-section').classList.add('opacity-60');
      emailInput.readOnly = true;
      gateButton.classList.add('hidden');
    } else {
      gateMessage.textContent = "We couldn't find a current member with that "
        + 'email. Trips are open to registered members - see tcsc.ski to join.';
      gateMessage.classList.remove('hidden');
    }
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
    const driverDetails = document.getElementById('driver-details');
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

  // --- Stripe -----------------------------------------------------------
  let stripe = null;
  let card = null;
  async function ensureStripe() {
    if (card) return;
    const keyResponse = await fetch('/get-stripe-key');
    const { publicKey } = await keyResponse.json();
    stripe = window.Stripe(publicKey);
    card = stripe.elements().create('card');
    card.mount('#card-element');
    card.on('change', function (event) {
      showError(event.error ? event.error.message : '');
    });
  }
  ensureStripe().catch(function () {
    showError('The payment form failed to load. Refresh the page to try again.');
  });

  // --- submit -----------------------------------------------------------
  function collectPayload() {
    const drive = form.querySelector('input[name="profile-can-drive"]:checked');
    const tent = form.querySelector('input[name="profile-tent"]:checked');
    const hitch = form.querySelector('input[name="profile-hitch"]:checked');
    const seats = document.getElementById('profile-seats');
    const bikes = document.getElementById('profile-bikes');
    const tier = form.querySelector('input[name="price-tier"]:checked');
    const answers = {};
    form.querySelectorAll('[data-question-key]').forEach(function (node) {
      const wrapper = node.closest('[data-question-field]');
      if (wrapper && wrapper.classList.contains('hidden')) return;
      const key = node.dataset.questionKey;
      const type = node.dataset.questionType;
      if (type === 'multi_choice') {
        answers[key] = Array.from(
          node.querySelectorAll('input:checked')).map(function (i) { return i.value; });
      } else if (type === 'yes_no') {
        const checked = node.querySelector('input:checked');
        if (checked) answers[key] = checked.value;
      } else if (node.value) {
        answers[key] = node.value;
      }
    });
    return {
      email: emailInput.value,
      price_tier: tier ? tier.value : 'low',
      profile: {
        can_drive: drive ? drive.value : '',
        seat_capacity: seats.disabled ? '' : seats.value,
        bike_capacity: bikes.disabled ? '' : bikes.value,
        hitch_size: hitch && !hitch.disabled ? hitch.value : '',
        region_code: document.getElementById('profile-region').value,
        dietary_restrictions: Array.from(
          form.querySelectorAll('[data-dietary]:checked')).map(function (i) { return i.value; }),
        dietary_other: document.getElementById('profile-dietary-other').value,
        has_tent: tent ? tent.value : '',
      },
      answers: answers,
    };
  }

  function showError(message) {
    document.getElementById('form-errors').textContent = message || '';
  }

  var PROFILE_ERROR_FIELDS = {
    'profile.can_drive': 'profile-can-drive-group',
    'profile.seat_capacity': 'profile-seats',
    'profile.bike_capacity': 'profile-bikes',
    'profile.hitch_size': 'profile-hitch-group',
    'profile.region_code': 'profile-region',
    'profile.dietary_restrictions': 'dietary-options',
    'profile.has_tent': 'profile-tent-group',
    'email': 'member-email',
  };

  function findErrorField(key) {
    if (key.indexOf('answers.') === 0) {
      return form.querySelector(
        '[data-question-key="' + key.slice(8) + '"]');
    }
    var id = PROFILE_ERROR_FIELDS[key];
    return id ? document.getElementById(id) : null;
  }

  function showServerErrors(errors) {
    form.querySelectorAll('.field-error').forEach(function (node) {
      node.classList.remove('field-error', 'ring-2', 'ring-red-500');
    });
    if (typeof errors === 'string') { showError(errors); return; }
    var firstField = null;
    Object.keys(errors).forEach(function (key) {
      var field = findErrorField(key);
      if (field) {
        field.classList.add('field-error', 'ring-2', 'ring-red-500');
        if (!firstField) firstField = field;
      }
    });
    showError(Object.values(errors).join(' '));
    if (firstField) {
      firstField.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  let isSubmitting = false;
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (isSubmitting) return;
    if (!form.checkValidity()) { form.reportValidity(); return; }
    isSubmitting = true;
    const button = document.getElementById('submit');
    button.disabled = true;
    try {
      await ensureStripe();
      const response = await fetch(
        '/' + encodeURIComponent(tripData.slug) + '/register', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': (crypto.randomUUID
              ? crypto.randomUUID()
              : Date.now() + '-' + Math.random().toString(36).slice(2)),
          },
          body: JSON.stringify(collectPayload()),
        });
      const result = await response.json();
      if (!response.ok) { showServerErrors(result.error); return; }
      const confirmation = await stripe.confirmCardPayment(result.clientSecret, {
        payment_method: {
          card: card,
          billing_details: { email: emailInput.value },
        },
      });
      if (confirmation.error) { showError(confirmation.error.message); return; }
      form.classList.add('hidden');
      const completed = document.querySelector('.completed-view');
      document.getElementById('confirmation-message').textContent =
        'Your card hold of $' + (result.amountCents / 100).toFixed(2)
        + ' is placed. You will be charged when the roster is confirmed.';
      completed.classList.remove('hidden');
    } catch (err) {
      showError('Something went wrong placing the hold — you have not been charged. Please try again.');
    } finally {
      isSubmitting = false;
      button.disabled = false;
    }
  });
})();
