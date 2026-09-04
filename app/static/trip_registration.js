import {initTripSurvey} from './trip_survey.js';

(function tripRegistrationPage() {
  const dataNode = document.getElementById('trip-registration-data');
  const form = document.getElementById('trip-registration-form');
  if (!dataNode || !form) return;
  const tripData = JSON.parse(dataNode.textContent);

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

  initTripSurvey(form, showError);

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
