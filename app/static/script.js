// script.js

// Shared Stripe card element styles
const STRIPE_CARD_STYLES = {
  style: {
    base: {
      color: '#32325d',
      fontFamily: '"Helvetica Neue", Helvetica, sans-serif',
      fontSmoothing: 'antialiased',
      fontSize: '16px',
      '::placeholder': { color: '#aab7c4' }
    },
    invalid: {
      color: '#fa755a',
      iconColor: '#fa755a'
    }
  }
};

// Generate a unique idempotency key for payment requests
function generateIdempotencyKey() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

class PaymentForm {
  constructor() {
    this.initializeProperties();
    this.initializeElements();
    this.init();
  }

  initializeProperties() {
    this.stripe = null;
    this.card = null;
    this.selectedAmount = null;
    this.clientSecret = null;
    this.paymentIntent = null;
    this.idempotencyKey = null;
    this.isSubmitting = false;
  }

  initializeElements() {
    const selectors = {
      form: '.sr-payment-form',
      submit: '#submit',
      nameInput: '#name',
      emailInput: '#email',
      errorDisplay: '#card-errors',
      amountDisplay: '.order-amount',
      packageType: '.package-type',
      spinner: '#spinner',
      buttonText: '#button-text'
    };

    this.elements = Object.fromEntries(
      Object.entries(selectors).map(([key, selector]) => [
        key, 
        document.querySelector(selector)
      ])
    );
  }

  async init() {
    try {
      const { publicKey } = await this.fetchStripeKey();
      this.stripe = Stripe(publicKey);
      this.setupStripeElements();
      this.attachEventListeners();
    } catch (error) {
      this.handleInitializationError(error);
    }
  }

  async fetchStripeKey() {
    const response = await fetch('/get-stripe-key');
    return response.json();
  }

  setupStripeElements() {
    const elements = this.stripe.elements();
    this.card = elements.create('card', this.getCardElementStyles());
    this.card.mount('#card-element');
    this.card.on('change', ({error}) => this.showError(error?.message || ''));
  }

  getCardElementStyles() {
    return STRIPE_CARD_STYLES;
  }

  attachEventListeners() {
    // Add click handlers for the entire price option containers
    document.querySelectorAll('.price-option-container').forEach(container => {
      container.addEventListener('click', (e) => {
        const radio = container.querySelector('input[type="radio"]');
        radio.checked = true;
        
        const amount = parseFloat(container.dataset.value);
        this.selectedAmount = amount;
        this.updateUI(amount);
      });
    });

    this.elements.submit.addEventListener('click', this.handleSubmit.bind(this));
  }

  updateUI(amount) {
    if (this.elements.amountDisplay) {
      this.elements.amountDisplay.textContent = `$${amount.toFixed(2)}`;
    }

    // Only show package type if there are multiple prices
    const packageTypeElement = this.elements.packageType;
    if (packageTypeElement) {
        const priceInputs = document.querySelectorAll('input[name="price-choice"]');
        packageTypeElement.parentElement.style.display = priceInputs.length > 1 ? 'block' : 'none';

        // Get all price options to determine if this is the lower or higher price
        const priceOptions = Array.from(priceInputs).map(input => parseFloat(input.value));
        const isLowerPrice = amount === Math.min(...priceOptions);
        packageTypeElement.textContent = isLowerPrice ? 'Lower' : 'Higher';
    }
  }

  validateForm() {
    const { nameInput, emailInput } = this.elements;
    
    const selectedPrice = this.getSelectedPrice();
    
    if (!selectedPrice) {
      this.showError('Please select a price.');
      return false;
    }
    this.selectedAmount = selectedPrice;
    
    if (!nameInput.value) {
      this.showError('Please enter your name.');
      return false;
    }
    if (!emailInput.value) {
      this.showError('Please enter your email address.');
      return false;
    }
    if (!this.validateEmail(emailInput.value)) {
      this.showError('Please enter a valid email address.');
      return false;
    }
    return true;
  }

  getSelectedPrice() {
    const priceInputs = document.querySelectorAll('input[name="price-choice"]');
    if (priceInputs.length > 0) {
      const checkedInput = document.querySelector('input[name="price-choice"]:checked');
      return checkedInput ? parseFloat(checkedInput.value) : null;
    }
    
    const priceElement = document.querySelector('.price-amount');
    return priceElement ? parseFloat(priceElement.textContent.replace('$', '')) : null;
  }

  validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  async handleSubmit(e) {
    e.preventDefault();

    // Prevent double submissions
    if (this.isSubmitting) return;

    if (!this.validateForm()) return;

    this.isSubmitting = true;
    // Generate a new idempotency key for this submission attempt
    this.idempotencyKey = generateIdempotencyKey();

    this.toggleLoadingState(true);
    try {
      await this.processPayment();
    } catch (error) {
      console.error('Payment error:', error);
      this.showError(error.message || 'Payment failed. Please try again.');
      // Reset submission state on error to allow retry
      this.isSubmitting = false;
      this.idempotencyKey = null;
    } finally {
      this.toggleLoadingState(false);
    }
  }

  async processPayment() {
    await this.createOrUpdatePaymentIntent();
    const result = await this.confirmPayment();
    
    if (result.error) {
      this.showError(result.error.message);
    } else {
      await this.handlePaymentSuccess(result);
    }
  }

  async confirmPayment() {
    return this.stripe.confirmCardPayment(this.clientSecret, {
      payment_method: {
        card: this.card,
        billing_details: {
          name: this.elements.nameInput.value,
          email: this.elements.emailInput.value
        }
      }
    });
  }

  async createOrUpdatePaymentIntent() {
    const response = await fetch('/create-payment-intent', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': this.idempotencyKey
      },
      body: JSON.stringify({
        currency: 'usd',
        trip_slug: this.elements.form.dataset.tripSlug,
        price_tier: this.getSelectedPriceTier(),
        email: this.elements.emailInput.value,
        name: this.elements.nameInput.value
      })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Server error: ${response.status}`);
    }

    const data = await response.json();
    this.clientSecret = data.clientSecret;
    this.paymentIntent = data.paymentIntent;
    return this.paymentIntent;
  }

  getSelectedPriceTier() {
    const checkedInput = document.querySelector('input[name="price-choice"]:checked');
    return checkedInput ? checkedInput.dataset.tier : 'low';
  }

  showError(message) {
    const { errorDisplay } = this.elements;
    errorDisplay.textContent = message;
    errorDisplay.style.display = message ? 'block' : 'none';
  }

  toggleLoadingState(isLoading) {
    const { submit, spinner, buttonText } = this.elements;
    submit.disabled = isLoading;
    spinner.classList.toggle('hidden', !isLoading);
    buttonText.classList.toggle('hidden', isLoading);
  }

  async handlePaymentSuccess(result) {
    document.querySelectorAll('.payment-view')
      .forEach(view => view.classList.add('hidden'));
    document.querySelectorAll('.completed-view')
      .forEach(view => view.classList.remove('hidden'));
    // Enable registration form if present (season registration flow)
    if (typeof window.enableRegistrationForm === 'function') {
      window.enableRegistrationForm();
    }
  }

  handleInitializationError(error) {
    console.error('Initialization error:', error);
    this.showError('Failed to initialize payment form. Please refresh the page.');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Initialize PaymentForm for trip registration pages (with .sr-payment-form but NOT registration forms)
  if (document.querySelector('.sr-payment-form') && !document.getElementById('registration-form')) {
    new PaymentForm();
  }

  // Get the registration form and price from a data attribute or JS variable
  const registrationForm = document.getElementById('registration-form');
  if (!registrationForm) return;
  // You can set this in your template: <form ... data-price-cents="{{ season.price_cents }}">
  const priceCents = parseInt(registrationForm.dataset.priceCents || 0, 10);
  const priceDollars = priceCents / 100;

  // --- Form State Persistence (sessionStorage, this browser tab only) ---
  // Answers survive a mid-wizard refresh and are cleared on successful
  // submit. Payment fields (name on card, agreement) and hidden control
  // fields are never persisted; card details live in Stripe's iframe and
  // never touch this code.
  const STORAGE_KEY = `tcsc-registration-${registrationForm.dataset.seasonId}`;
  const ENTERED_KEY = `${STORAGE_KEY}-entered`;
  const UNSAVED_FIELDS = new Set(['csrf_token', 'continue_unverified', 'payment_intent_id', 'name', 'agreement']);

  try {
    // Remove data written by versions that persisted form answers in
    // localStorage, which outlives the tab.
    localStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    // Storage may be unavailable; there is nothing else to clean up.
  }

  function saveFormState() {
    const formData = {};
    registrationForm.querySelectorAll('input, select').forEach(field => {
      if (!field.name || UNSAVED_FIELDS.has(field.name)) return;
      if (field.type === 'hidden' || field.type === 'checkbox') return;
      if (field.type === 'radio') {
        if (field.checked) formData[field.name] = field.value;
        return;
      }
      formData[field.name] = field.value;
    });
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(formData));
    } catch (e) {
      // sessionStorage might be full or disabled - silently fail
    }
  }

  function restoreFormState() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      const formData = JSON.parse(saved);
      Object.keys(formData).forEach(fieldName => {
        if (UNSAVED_FIELDS.has(fieldName)) return;
        const field = registrationForm.querySelector(`[name="${fieldName}"]`);
        if (!field || field.readOnly) return;
        if (field.type === 'radio') {
          const radio = registrationForm.querySelector(`[name="${fieldName}"][value="${formData[fieldName]}"]`);
          if (radio) radio.checked = true;
        } else {
          field.value = formData[fieldName];
        }
      });
    } catch (e) {
      // Invalid JSON or other error - silently fail
    }
  }

  function clearFormState() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(ENTERED_KEY);
    } catch (e) {
      // silently fail
    }
  }

  function rememberWizardEntered(continueUnverified) {
    try {
      sessionStorage.setItem(ENTERED_KEY, continueUnverified ? '1' : '0');
    } catch (e) {
      // silently fail
    }
  }

  function storedWizardEntry() {
    try {
      return sessionStorage.getItem(ENTERED_KEY); // null, '0', or '1'
    } catch (e) {
      return null;
    }
  }

  // Debounce helper to avoid excessive sessionStorage writes
  let saveTimeout = null;
  function debouncedSave() {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveFormState, 500);
  }

  // Attach save listeners to all form inputs
  registrationForm.querySelectorAll('input, select').forEach(input => {
    input.addEventListener('input', debouncedSave);
    input.addEventListener('change', debouncedSave);
  });

  // Restore form state on page load (before any verify prefill runs, so
  // restored answers win and prefill only fills fields left empty).
  restoreFormState();
  // --- End Form State Persistence ---

  // --- Step 0: verify phone (email fallback) ahead of the wizard ---
  const verifySection = document.getElementById('section-verify');
  if (verifySection) {
    const progressBar = document.querySelector('.progress-bar');
    let verifyPhone = null;
    let phoneVerified = false; // a phone verification succeeded this session
    let resendTimer = null;

    const byId = id => document.getElementById(id);
    const show = id => { const node = byId(id); if (node) node.hidden = false; };
    const hide = id => { const node = byId(id); if (node) node.hidden = true; };

    function showVerifyError(message) {
      const box = byId('verify-error');
      if (!box) return;
      box.textContent = message || '';
      box.hidden = !message;
    }

    async function postJson(url, payload) {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      return resp.json();
    }

    function setPaymentStatusLine(memberType) {
      const line = byId('payment-status-line');
      if (!line) return;
      line.textContent = memberType === 'returning'
        ? `You're registering as a returning member. Your card will be charged $${priceDollars.toFixed(2)} today.`
        : "You're registering as a new member. We'll place a hold on your card; you're only charged if you get a spot in the lottery.";
      line.hidden = false;
    }

    function setIfEmpty(id, value) {
      const field = byId(id);
      if (!field || !value) return;
      if (field.value.trim() === '') field.value = value;
    }

    function setRadioIfUnset(name, value) {
      if (!value) return;
      if (registrationForm.querySelector(`input[name="${name}"]:checked`)) return;
      const radio = registrationForm.querySelector(`input[name="${name}"][value="${value}"]`);
      if (radio) radio.checked = true;
    }

    function applyPrefill(data) {
      // Restored sessionStorage answers win; prefill only fills empty fields.
      setPaymentStatusLine(data.memberType || 'new');
      const user = data.user;
      if (!user) return;
      setIfEmpty('email', user.email);
      setIfEmpty('firstName', user.firstName);
      setIfEmpty('lastName', user.lastName);
      setIfEmpty('pronouns', user.pronouns);
      setIfEmpty('dob', user.dob);
      setIfEmpty('phone', user.phone);
      setIfEmpty('tshirtSize', user.tshirtSize);
      setRadioIfUnset('technique', user.technique);
      setRadioIfUnset('experience', user.experience);
      setIfEmpty('emergencyName', user.emergencyName);
      setIfEmpty('emergencyRelation', user.emergencyRelation);
      setIfEmpty('emergencyPhone', user.emergencyPhone);
      setIfEmpty('emergencyEmail', user.emergencyEmail);
      // Only collapse to the read-only summary when every emergency field
      // has a value; hidden empty required inputs would block submission.
      const emergencyComplete = ['emergencyName', 'emergencyRelation', 'emergencyPhone', 'emergencyEmail']
        .every(id => byId(id) && byId(id).value.trim() !== '');
      if (emergencyComplete) {
        byId('emergency-summary').textContent =
          `${byId('emergencyName').value} (${byId('emergencyRelation').value}), ${byId('emergencyPhone').value}`;
        show('emergency-confirm');
        hide('emergency-edit');
      }
      saveFormState();
    }

    async function fetchPrefill() {
      const resp = await fetch('/api/verify/prefill');
      return resp.json();
    }

    function enterWizard(opts) {
      const continueUnverified = !!(opts && opts.continueUnverified);
      const cuInput = byId('continue-unverified');
      if (cuInput) cuInput.value = continueUnverified ? '1' : '0';
      verifySection.hidden = true;
      registrationForm.hidden = false;
      if (progressBar) progressBar.hidden = false;
      if (opts && opts.firstName) {
        const welcome = byId('verify-welcome');
        if (welcome) {
          welcome.textContent = `Welcome back, ${opts.firstName}! We filled in what we have on file. Give it a once-over and finish up.`;
          welcome.hidden = false;
        }
      }
      if (continueUnverified) show('unverified-notice'); else hide('unverified-notice');
      rememberWizardEntered(continueUnverified);
      window.scrollTo({ top: 0 });
    }

    function startResendCountdown(seconds) {
      const btn = byId('verify-resend-btn');
      if (!btn) return;
      let remaining = seconds;
      btn.disabled = true;
      btn.textContent = `Resend (${remaining})`;
      clearInterval(resendTimer);
      resendTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(resendTimer);
          btn.disabled = false;
          btn.textContent = 'Resend';
        } else {
          btn.textContent = `Resend (${remaining})`;
        }
      }, 1000);
    }

    async function verifiedPrefillThenEnter(fallbackFirstName) {
      let data = null;
      try {
        data = await fetchPrefill();
      } catch (e) {
        // Prefill is a convenience; verification already succeeded.
      }
      if (data) applyPrefill(data);
      else setPaymentStatusLine('new');
      const firstName = (data && data.user && data.user.firstName) || fallbackFirstName || null;
      enterWizard({ continueUnverified: false, firstName });
    }

    async function sendPhoneCode() {
      showVerifyError('');
      const phoneValue = byId('verify-phone').value.trim();
      const btn = byId('verify-send-btn');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/phone/start', { phone: phoneValue });
        if (!body.ok) {
          showVerifyError(body.error || 'Something went wrong. Please try again.');
          return;
        }
        verifyPhone = phoneValue;
        byId('verify-phone-echo').textContent = phoneValue;
        hide('verify-phone-entry');
        show('verify-code-entry');
        byId('verify-code').focus();
        startResendCountdown(30);
      } catch (e) {
        showVerifyError('Something went wrong sending the code. Please try again.');
      } finally {
        btn.disabled = false;
      }
    }

    async function checkPhoneCode() {
      showVerifyError('');
      const code = byId('verify-code').value.replace(/\s+/g, '');
      if (!code) {
        showVerifyError('Enter the code from the text we sent.');
        return;
      }
      const btn = byId('verify-check-btn');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/phone/check', { phone: verifyPhone, code });
        // On a wrong code the input keeps its value so it can be corrected.
        if (!body.ok) {
          showVerifyError(body.error || 'Something went wrong. Please try again.');
          return;
        }
        phoneVerified = true;
        if (body.match === 'one') {
          await verifiedPrefillThenEnter(body.firstName);
          return;
        }
        // 'none' and 'multiple' both route to the email step; only the copy differs.
        if (body.match === 'multiple') {
          byId('verify-email-msg').textContent =
            "More than one member shares this number, so we'll match you by email " +
            "instead. Enter the email you've used with the club.";
        }
        hide('verify-code-entry');
        show('verify-email-entry');
        byId('verify-email').focus();
      } catch (e) {
        showVerifyError('Something went wrong checking the code. Please try again.');
      } finally {
        btn.disabled = false;
      }
    }

    async function sendEmailCode() {
      showVerifyError('');
      const emailValue = byId('verify-email').value.trim();
      const btn = byId('verify-email-send-btn');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/email/start', { email: emailValue });
        if (!body.ok) {
          showVerifyError(body.error || 'Something went wrong. Please try again.');
          return;
        }
        if (!body.exists) {
          showVerifyError("We don't have that email on file. Double-check the spelling, or use the link below if you no longer have access to it.");
          return;
        }
        byId('verify-email-echo').textContent = emailValue;
        show('verify-email-code-row');
        byId('verify-email-code').focus();
      } catch (e) {
        showVerifyError('Something went wrong sending the code. Please try again.');
      } finally {
        btn.disabled = false;
      }
    }

    async function checkEmailCode() {
      showVerifyError('');
      const emailValue = byId('verify-email').value.trim();
      const code = byId('verify-email-code').value.replace(/\s+/g, '');
      if (!code) {
        showVerifyError('Enter the code from the email we sent.');
        return;
      }
      const btn = byId('verify-email-check-btn');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/email/check', { email: emailValue, code });
        if (!body.ok) {
          showVerifyError(body.error || 'Something went wrong. Please try again.');
          return;
        }
        await verifiedPrefillThenEnter(null);
      } catch (e) {
        showVerifyError('Something went wrong checking the code. Please try again.');
      } finally {
        btn.disabled = false;
      }
    }

    byId('verify-send-btn').addEventListener('click', sendPhoneCode);
    byId('verify-check-btn').addEventListener('click', checkPhoneCode);
    byId('verify-resend-btn').addEventListener('click', sendPhoneCode);
    byId('verify-email-send-btn').addEventListener('click', sendEmailCode);
    byId('verify-email-check-btn').addEventListener('click', checkEmailCode);

    byId('verify-edit-phone').addEventListener('click', e => {
      e.preventDefault();
      clearInterval(resendTimer);
      showVerifyError('');
      hide('verify-code-entry');
      show('verify-phone-entry');
      byId('verify-phone').focus();
    });

    // Escape hatches. continue_unverified stays "0" only when a phone
    // verification succeeded this session; the two skip-verification links
    // always take the flagged path (new-member lottery + admin review).
    byId('verify-skip-link').addEventListener('click', e => {
      e.preventDefault();
      setPaymentStatusLine('new');
      enterWizard({ continueUnverified: !phoneVerified });
    });
    byId('verify-cant-text-link').addEventListener('click', e => {
      e.preventDefault();
      setPaymentStatusLine('new');
      enterWizard({ continueUnverified: true });
    });
    byId('verify-email-dead-link').addEventListener('click', e => {
      e.preventDefault();
      setPaymentStatusLine('new');
      enterWizard({ continueUnverified: true });
    });

    // Enter advances the visible verify step (these inputs sit outside the
    // form, so the browser would otherwise do nothing).
    [['verify-phone', 'verify-send-btn'],
     ['verify-code', 'verify-check-btn'],
     ['verify-email', 'verify-email-send-btn'],
     ['verify-email-code', 'verify-email-check-btn']].forEach(([inputId, btnId]) => {
      byId(inputId).addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          e.preventDefault();
          byId(btnId).click();
        }
      });
    });

    // Emergency contact: keep the summary and move on, or reopen the fields.
    const keepBtn = byId('emergency-keep-btn');
    if (keepBtn) keepBtn.addEventListener('click', () => {
      const target = byId('section-payment');
      if (!target) return;
      const offset = (progressBar ? progressBar.offsetHeight : 0) + 20;
      const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    });
    const updateBtn = byId('emergency-update-btn');
    if (updateBtn) updateBtn.addEventListener('click', () => {
      hide('emergency-confirm');
      show('emergency-edit');
    });

    // Resume after a refresh: a still-verified session skips straight back
    // into the wizard (keeping its recorded continue_unverified choice); an
    // unverified session that had already entered re-enters flagged.
    (async () => {
      try {
        const data = await fetchPrefill();
        if (data.verified) {
          phoneVerified = true;
          applyPrefill(data);
          enterWizard({
            continueUnverified: storedWizardEntry() === '1',
            firstName: data.user ? data.user.firstName : null
          });
          return;
        }
      } catch (e) {
        // Fall through to the sessionStorage check.
      }
      if (storedWizardEntry() !== null) {
        setPaymentStatusLine('new');
        enterWizard({ continueUnverified: true });
      }
    })();
  }
  // --- End Step 0 ---

  // Only run payment logic if the form and card element exist
  if (document.getElementById('card-element')) {
    let stripe, card, clientSecret;
    let isSubmitting = false;
    let idempotencyKey = null;

    async function fetchStripeKey() {
      const response = await fetch('/get-stripe-key');
      return response.json();
    }

    async function createPaymentIntent(name, email) {
      idempotencyKey = generateIdempotencyKey();
      const invite = new URLSearchParams(window.location.search).get('invite');
      const response = await fetch('/create-season-payment-intent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify({
          season_id: registrationForm.dataset.seasonId,
          email,
          name,
          invite
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        return { error: errorData.error || `Server error: ${response.status}` };
      }

      return response.json();
    }

    function showError(message) {
      const errorDisplay = document.getElementById('card-errors');
      if (errorDisplay) {
        errorDisplay.textContent = message;
        errorDisplay.style.display = message ? 'block' : 'none';
      }
    }

    function validateRequiredFields() {
      let valid = true;
      registrationForm.querySelectorAll('.field-error').forEach(el => {
        el.classList.remove('field-error');
      });

      registrationForm.querySelectorAll('input[required], select[required]').forEach(field => {
        if (field.type === 'radio') return;
        if (field.type === 'checkbox') {
          if (!field.checked) {
            field.classList.add('field-error');
            valid = false;
          }
          return;
        }
        if (!field.value.trim()) {
          field.classList.add('field-error');
          valid = false;
        }
      });

      const radioNames = new Set();
      registrationForm.querySelectorAll('input[type="radio"][required]').forEach(r => {
        radioNames.add(r.name);
      });
      radioNames.forEach(name => {
        const checked = registrationForm.querySelector(`input[name="${name}"]:checked`);
        if (!checked) {
          registrationForm.querySelectorAll(`input[name="${name}"]`).forEach(r => {
            r.classList.add('field-error');
          });
          valid = false;
        }
      });

      return valid;
    }

    function toggleLoadingState(isLoading) {
      const btn = document.getElementById('register-btn');
      const text = document.getElementById('button-text');
      const spinner = document.getElementById('button-spinner');
      if (btn) btn.disabled = isLoading;
      if (text) text.style.display = isLoading ? 'none' : 'inline';
      if (spinner) spinner.style.display = isLoading ? 'inline-flex' : 'none';
    }

    async function initStripe() {
      const { publicKey } = await fetchStripeKey();
      stripe = Stripe(publicKey);
      const elements = stripe.elements();
      card = elements.create('card', STRIPE_CARD_STYLES);
      card.mount('#card-element');
      card.on('change', ({error}) => showError(error?.message || ''));
    }

    registrationForm.addEventListener('submit', async function(e) {
      e.preventDefault();

      // Prevent double submissions
      if (isSubmitting) return;

      showError('');
      isSubmitting = true;
      toggleLoadingState(true);

      if (!validateRequiredFields()) {
        showError('Please fill in all required fields before submitting.');
        isSubmitting = false;
        toggleLoadingState(false);
        return;
      }

      try {
        // Get payment info from form
        const name = registrationForm.querySelector('#name').value;
        const email = registrationForm.querySelector('#email').value;
        // Create payment intent
        const paymentIntentData = await createPaymentIntent(name, email);
        if (paymentIntentData.error) {
          showError(paymentIntentData.error);
          isSubmitting = false;
          toggleLoadingState(false);
          return;
        }
        clientSecret = paymentIntentData.clientSecret;
        // Confirm card payment
        const result = await stripe.confirmCardPayment(clientSecret, {
          payment_method: {
            card: card,
            billing_details: { name, email }
          }
        });
        if (result.error) {
          showError(result.error.message);
          isSubmitting = false;
          toggleLoadingState(false);
          return;
        }
        // Payment succeeded, submit the form (remove card details so they aren't sent to backend)
        document.getElementById('card-element').remove();

        // Add payment_intent_id to form for backend coordination with webhook
        const paymentIntentInput = document.createElement('input');
        paymentIntentInput.type = 'hidden';
        paymentIntentInput.name = 'payment_intent_id';
        paymentIntentInput.value = result.paymentIntent.id;
        registrationForm.appendChild(paymentIntentInput);

        // Clear saved form state before submitting
        clearFormState();

        registrationForm.submit();
      } catch (err) {
        showError('Payment failed. Please try again.');
        isSubmitting = false;
        toggleLoadingState(false);
      }
    });

    initStripe();
  }
});
