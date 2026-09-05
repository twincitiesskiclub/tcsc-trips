import {initTripSurvey} from './trip_survey.js';

(function tripRegistrationPage() {
  const dataNode = document.getElementById('trip-registration-data');
  const form = document.getElementById('trip-registration-form');
  if (!dataNode || !form) return;
  const tripData = JSON.parse(dataNode.textContent);
  const scrollBehavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
  let globalError = '';

  // --- email gate -------------------------------------------------------
  const gateButton = document.getElementById('gate-check');
  const gateMessage = document.getElementById('gate-message');
  const emailInput = document.getElementById('member-email');
  const formBody = document.getElementById('form-body');
  let memberConfirmed = false;
  gateButton.addEventListener('click', async function () {
    if (gateButton.disabled) return;
    gateMessage.hidden = true;
    clearFieldError(emailInput);
    if (!emailInput.checkValidity()) {
      showGateError('Enter a valid email address to continue.');
      emailInput.focus();
      return;
    }
    gateButton.disabled = true;
    // Freeze the checked address while the request is in flight.
    emailInput.readOnly = true;
    try {
      const response = await fetch('/api/trips/member-check', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailInput.value }),
      });
      if (!response.ok) throw new Error('Member check failed');
      const result = await response.json();
      if (result.eligible) {
        memberConfirmed = true;
        formBody.hidden = false;
        document.getElementById('gate-entry').hidden = true;
        document.getElementById('confirmed-email').textContent = emailInput.value;
        document.getElementById('gate-confirmed').hidden = false;
        stepLinks.forEach(function (link) { link.removeAttribute('aria-disabled'); });
        const nextSection = formBody.querySelector('[data-step-section]');
        setCurrentStep(nextSection.id);
        focusField(nextSection);
      } else {
        showGateError("We couldn't find a current member with that "
          + 'email. Trips are open to registered members. See tcsc.ski to join.');
      }
    } catch (err) {
      showGateError('We could not check your membership. Please try again.');
    } finally {
      gateButton.disabled = false;
      emailInput.readOnly = memberConfirmed;
    }
  });
  emailInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') { event.preventDefault(); gateButton.click(); }
  });

  function showGateError(message) {
    emailInput.setAttribute('aria-invalid', 'true');
    gateMessage.textContent = message;
    gateMessage.hidden = false;
  }

  // A small scroll indicator also follows keyboard focus within the form.
  const stepLinks = Array.from(form.querySelectorAll('[data-step-link]'));
  const sections = Array.from(form.querySelectorAll('[data-step-section]'));
  function setCurrentStep(id) {
    stepLinks.forEach(function (link) {
      if (link.hash === '#' + id) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
      link.toggleAttribute('data-complete', memberConfirmed && link.hash === '#gate-section');
      link.classList.toggle('progress-step--active', link.hash === '#' + id);
      link.classList.toggle('progress-step--completed', memberConfirmed && link.hash === '#gate-section');
    });
  }
  stepLinks.forEach(function (link) {
    link.addEventListener('click', function (event) {
      event.preventDefault();
      if (link.getAttribute('aria-disabled') === 'true') return;
      const section = document.getElementById(link.hash.slice(1));
      section.scrollIntoView({behavior: scrollBehavior, block: 'start'});
      setCurrentStep(section.id);
    });
  });
  let scrollPending = false;
  window.addEventListener('scroll', function () {
    if (scrollPending || !memberConfirmed) return;
    scrollPending = true;
    window.requestAnimationFrame(function () {
      let current = sections[0];
      sections.forEach(function (section) {
        if (!section.closest('[hidden]') && section.getBoundingClientRect().top <= window.innerHeight * 0.4) current = section;
      });
      setCurrentStep(current.id);
      scrollPending = false;
    });
  }, {passive: true});
  form.addEventListener('focusin', function (event) {
    const section = event.target.closest('[data-step-section]');
    if (section) setCurrentStep(section.id);
  });

  function errorFieldForControl(input) {
    return input.closest('[data-question-key], #dietary-options, fieldset[id]') || input;
  }
  form.addEventListener('input', function (event) {
    clearFieldError(errorFieldForControl(event.target));
    if (event.target === emailInput) {
      gateMessage.hidden = true;
      emailInput.removeAttribute('aria-invalid');
    }
    globalError = '';
    refreshErrorSummary();
  });

  initTripSurvey(form, showError);

  const buttonText = document.getElementById('button-text');
  function updateHoldAmount() {
    const tier = form.querySelector('input[name="price-tier"]:checked');
    const cents = tier && tier.value === 'high' ? tripData.priceHigh : tripData.priceLow;
    buttonText.textContent = 'Place hold for $' + (cents / 100).toFixed(2);
  }
  form.addEventListener('change', function (event) {
    // The survey's change handler has already hidden inapplicable fields.
    form.querySelectorAll('.field-error').forEach(function (field) {
      if (field.closest('[hidden]')) clearFieldError(field);
    });
    refreshErrorSummary();
    if (event.target.name === 'price-tier') updateHoldAmount();
  });
  updateHoldAmount();

  // --- Stripe -----------------------------------------------------------
  let stripe = null;
  let card = null;
  let cardComplete = false;
  async function ensureStripe() {
    if (card) return;
    const keyResponse = await fetch('/get-stripe-key');
    const { publicKey } = await keyResponse.json();
    stripe = window.Stripe(publicKey);
    card = stripe.elements().create('card', {style: {
      base: {fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif', fontSize: '16px', color: '#1c2c44', '::placeholder': {color: '#71717a'}},
      invalid: {color: '#b91c1c'},
    }});
    card.mount('#card-element');
    card.on('change', function (event) {
      cardComplete = event.complete === true;
      const field = document.getElementById('card-element');
      showError(event.error ? event.error.message : '', field);
    });
  }
  ensureStripe().catch(function () {
    showError('The payment form failed to load. Refresh the page to try again.', document.getElementById('card-element'));
  });

  // --- submit -----------------------------------------------------------
  function collectPayload() {
    const drive = form.querySelector('input[name="profile-can-drive"]:checked');
    const tent = form.querySelector('input[name="profile-tent"]:checked');
    const hitch = form.querySelector('input[name="profile-hitch"]:checked');
    const seats = document.getElementById('profile-seats');
    const bikes = document.getElementById('profile-bikes');
    const tier = form.querySelector('input[name="price-tier"]:checked');
    const profile = {};
    if (form.querySelector('#profile-can-drive-group')) {
      Object.assign(profile, {
        can_drive: drive ? drive.value : '',
        seat_capacity: seats && !seats.disabled ? seats.value : '',
        bike_capacity: bikes && !bikes.disabled ? bikes.value : '',
        hitch_size: hitch && !hitch.disabled ? hitch.value : '',
      });
    }
    const region = form.querySelector('#profile-region');
    if (region) profile.region_code = region.value;
    if (form.querySelector('#dietary-options')) {
      profile.dietary_restrictions = Array.from(
        form.querySelectorAll('[data-dietary]:checked')).map(function (i) { return i.value; });
      profile.dietary_other = form.querySelector('#profile-dietary-other').value;
    }
    if (form.querySelector('#profile-tent-group')) profile.has_tent = tent ? tent.value : '';
    const answers = {};
    form.querySelectorAll('[data-question-key]').forEach(function (node) {
      const wrapper = node.closest('[data-question-field]');
      if (wrapper && wrapper.hidden) return;
      const key = node.dataset.questionKey;
      const type = node.dataset.questionType;
      if (type === 'multi_choice') {
        answers[key] = Array.from(
          node.querySelectorAll('input:checked')).map(function (i) { return i.value; });
      } else if (type === 'yes_no' || (type === 'choice' && node.matches('[role="radiogroup"]'))) {
        const checked = node.querySelector('input:checked');
        if (checked) answers[key] = checked.value;
      } else if (node.value) {
        answers[key] = node.value;
      }
    });
    return {
      email: emailInput.value,
      price_tier: tier ? tier.value : 'low',
      profile: profile,
      answers: answers,
    };
  }

  function showError(message, field) {
    if (field) {
      clearFieldError(field);
      if (message) markFieldError(field, message);
    } else {
      globalError = message || '';
    }
    refreshErrorSummary();
  }

  function refreshErrorSummary() {
    const messages = Array.from(form.querySelectorAll('[data-error-for]')).map(function (slot) {
      return slot.textContent;
    }).filter(Boolean);
    const summary = document.getElementById('form-errors');
    summary.textContent = [globalError].concat(messages).filter(Boolean).join(' ');
    summary.hidden = !summary.textContent;
  }

  function errorSlot(field) {
    return form.querySelector('[data-error-for="' + field.id + '"]');
  }

  function clearFieldError(field) {
    field.classList.remove('field-error');
    field.removeAttribute('aria-invalid');
    field.querySelectorAll('[aria-invalid]').forEach(function (input) { input.removeAttribute('aria-invalid'); });
    const slot = errorSlot(field);
    if (slot) { slot.textContent = ''; slot.hidden = true; }
  }

  function markFieldError(field, message) {
    field.classList.add('field-error');
    field.setAttribute('aria-invalid', 'true');
    field.querySelectorAll('input, select').forEach(function (input) { input.setAttribute('aria-invalid', 'true'); });
    const slot = errorSlot(field);
    if (slot) { slot.textContent = message; slot.hidden = false; }
  }

  function focusField(field) {
    const control = field.matches('input, select') ? field : field.querySelector('input:not(:disabled), select:not(:disabled)');
    if (field.id === 'card-element' && card) card.focus();
    else if (control) control.focus({preventScroll: true});
    field.scrollIntoView({behavior: scrollBehavior, block: 'center'});
  }

  function validateFields() {
    form.querySelectorAll('.field-error').forEach(clearFieldError);
    const invalid = new Map();
    form.querySelectorAll('input, select').forEach(function (input) {
      if (!input.disabled && !input.closest('[hidden]') && !input.checkValidity()) {
        invalid.set(errorFieldForControl(input), input.validationMessage);
      }
    });
    form.querySelectorAll('[data-question-type="multi_choice"][data-required], #dietary-options[data-required]').forEach(function (group) {
      if (!group.closest('[hidden]') && !group.querySelector('input:checked')) {
        invalid.set(group, 'Select at least one option.');
      }
    });
    if (!card || !cardComplete) {
      invalid.set(document.getElementById('card-element'), 'Enter your card details.');
    }
    invalid.forEach(function (message, field) { markFieldError(field, message); });
    globalError = '';
    refreshErrorSummary();
    if (invalid.size) focusField(invalid.keys().next().value);
    return invalid.size === 0;
  }

  var PROFILE_ERROR_FIELDS = {
    'profile.can_drive': 'profile-can-drive-group',
    'profile.seat_capacity': 'profile-seats',
    'profile.bike_capacity': 'profile-bikes',
    'profile.hitch_size': 'profile-hitch-group',
    'profile.region_code': 'profile-region',
    'profile.dietary_restrictions': 'dietary-options',
    'profile.dietary_other': 'profile-dietary-other',
    'profile.has_tent': 'profile-tent-group',
    'email': 'member-email',
    'price_tier': 'price-tiers',
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
    form.querySelectorAll('.field-error').forEach(clearFieldError);
    if (typeof errors === 'string') { showError(errors); return; }
    const generalMessages = [];
    var firstField = null;
    Object.keys(errors).forEach(function (key) {
      var field = findErrorField(key);
      if (field) {
        markFieldError(field, errors[key]);
        if (field === emailInput) {
          memberConfirmed = false;
          emailInput.readOnly = false;
          document.getElementById('gate-entry').hidden = false;
          document.getElementById('gate-confirmed').hidden = true;
          formBody.hidden = true;
          stepLinks.slice(1).forEach(function (link) { link.setAttribute('aria-disabled', 'true'); });
          firstField = emailInput;
        }
        if (!firstField) firstField = field;
      } else {
        generalMessages.push(errors[key]);
      }
    });
    showError(generalMessages.join(' '));
    if (firstField) focusField(firstField);
  }

  let isSubmitting = false;
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (isSubmitting) return;
    if (!memberConfirmed) { gateButton.click(); return; }
    if (!validateFields()) return;
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
      if (confirmation.error) { showError(confirmation.error.message, document.getElementById('card-element')); return; }
      form.hidden = true;
      const completed = document.querySelector('.completed-view');
      document.getElementById('confirmation-message').textContent =
        'Your card hold of $' + (result.amountCents / 100).toFixed(2)
        + ' is placed. You will be charged when the roster is confirmed.';
      completed.hidden = false;
      document.getElementById('confirmation-title').focus({preventScroll: true});
      completed.scrollIntoView({behavior: scrollBehavior, block: 'center'});
    } catch (err) {
      showError('Something went wrong placing the hold. You have not been charged. Please try again.');
    } finally {
      isSubmitting = false;
      button.disabled = false;
    }
  });
})();
