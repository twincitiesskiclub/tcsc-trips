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

// Submit button label for season registration. The verb matches the
// capture method: a returning member is charged, a new member's card is
// held for the lottery. Unknown stays neutral rather than promising either.
function paymentButtonLabel(memberType, priceDollars) {
  if (!(priceDollars > 0)) return 'Register';
  const amount = `$${priceDollars.toFixed(2)}`;
  if (memberType === 'returning') return `Register & Pay ${amount}`;
  if (memberType === 'new') return `Register & Hold ${amount}`;
  return 'Register';
}

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
      this.showError(error.message || "We couldn't process that payment. Try again.");
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

  // Registration success page: the submission went through, so this
  // season's saved answers are no longer needed and must not leak into a
  // future registration. CSP blocks inline scripts on that page, so the
  // cleanup lives here, keyed off the success marker element.
  const successMarker = document.getElementById('registration-success');
  if (successMarker && successMarker.dataset.seasonId) {
    const successKey = `tcsc-registration-${successMarker.dataset.seasonId}`;
    try {
      sessionStorage.removeItem(successKey);
      sessionStorage.removeItem(`${successKey}-entered`);
    } catch (e) {
      // silently fail
    }
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
      if (field.type === 'hidden') return;
      if (field.type === 'checkbox') {
        // Checkbox groups (volunteer interests/committees) persist as arrays.
        if (!Array.isArray(formData[field.name])) formData[field.name] = [];
        if (field.checked) formData[field.name].push(field.value);
        return;
      }
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
        if (Array.isArray(formData[fieldName])) {
          registrationForm.querySelectorAll(`input[name="${fieldName}"]`).forEach(cb => {
            cb.checked = formData[fieldName].includes(cb.value);
          });
          return;
        }
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

  // --- Get Involved: committee reveal + pick-at-least-one gate ---
  const committeeToggle = document.getElementById('volunteer-committee-toggle');
  const committeePicker = document.getElementById('committee-picker');
  const volunteerError = document.getElementById('volunteer-error');

  function updateCommitteeReveal() {
    if (committeeToggle && committeePicker) {
      committeePicker.hidden = !committeeToggle.checked;
    }
  }

  function showVolunteerError(message) {
    if (!volunteerError) return;
    volunteerError.textContent = message || '';
    volunteerError.hidden = !message;
  }

  function validateVolunteerSection() {
    if (!document.getElementById('volunteer-interests')) return true;
    const interests = registrationForm.querySelectorAll('input[name="volunteerInterests"]:checked');
    if (interests.length === 0) {
      showVolunteerError('Pick at least one way to help this season.');
      return false;
    }
    if (committeeToggle && committeeToggle.checked) {
      const committees = registrationForm.querySelectorAll('input[name="volunteerCommittees"]:checked');
      if (committees.length === 0) {
        showVolunteerError('You picked Join a committee. Which one(s)?');
        return false;
      }
    }
    showVolunteerError('');
    return true;
  }

  if (committeeToggle) {
    committeeToggle.addEventListener('change', updateCommitteeReveal);
    updateCommitteeReveal(); // restored answers may have re-checked it
  }
  // A visible error re-validates live, so it disappears as soon as the
  // member fixes their pick instead of waiting for the next submit.
  registrationForm.querySelectorAll('input[name="volunteerInterests"], input[name="volunteerCommittees"]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (volunteerError && !volunteerError.hidden) validateVolunteerSection();
    });
  });
  // --- End Get Involved ---

  // --- Step 0: verify phone (email fallback) ahead of the wizard ---
  const verifySection = document.getElementById('section-verify');
  if (verifySection) {
    const progressBar = document.querySelector('.progress-bar');
    let verifyPhone = null;
    let reverifying = false;   // "Not [name]?" re-verification in progress
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

    function showCollisionError(message, lookupPath = false) {
      const box = byId('email-collision-error');
      if (!box) return;
      box.textContent = message || '';
      box.hidden = !message;
      if (message && lookupPath) {
        show('email-collision');
        hide('email-collision-send');
        hide('email-collision-code-row');
      }
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
      const buttonText = byId('button-text');
      if (buttonText) buttonText.textContent = paymentButtonLabel(memberType, priceDollars);
      const line = byId('payment-status-line');
      if (!line) return;
      if (memberType === 'returning') {
        line.textContent = `We'll charge your card $${priceDollars.toFixed(2)} today.`;
      } else if (memberType === 'new') {
        line.textContent = `New members enter a lottery. We'll hold $${priceDollars.toFixed(2)} on your card and charge it only if you get a spot.`;
      } else {
        // Membership type unknown (prefill fetch failed); don't guess.
        line.textContent = "We'll confirm your membership type at checkout. We hold the amount until then.";
      }
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

    function resetWizardFields() {
      // Drop answers derived from the wrong identity: saved state plus every
      // step 1-3 field. Payment fields (excluded from persistence) and
      // readonly fields (invite email) are left alone.
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (e) {
        // silently fail
      }
      registrationForm.querySelectorAll('input, select').forEach(field => {
        if (!field.name || UNSAVED_FIELDS.has(field.name)) return;
        if (field.type === 'hidden' || field.readOnly) return;
        if (field.type === 'radio' || field.type === 'checkbox') {
          field.checked = false;
        } else {
          field.value = '';
        }
      });
      show('emergency-edit');
      hide('emergency-confirm');
    }

    function enterWizard(opts) {
      const continueUnverified = !!(opts && opts.continueUnverified);
      const cuInput = byId('continue-unverified');
      if (cuInput) cuInput.value = continueUnverified ? '1' : '0';
      verifySection.hidden = true;
      registrationForm.hidden = false;
      if (progressBar) progressBar.hidden = false;
      const welcome = byId('verify-welcome');
      if (welcome) {
        if (opts && opts.firstName) {
          const welcomeText = byId('verify-welcome-text');
          if (welcomeText) {
            welcomeText.textContent = `Welcome back, ${opts.firstName}. We filled in what we have, so give it a once-over.`;
          }
          const notMeLink = byId('verify-not-me-link');
          if (notMeLink) {
            notMeLink.textContent = `Not ${opts.firstName}? Verify with your email instead.`;
          }
          welcome.hidden = false;
        } else {
          welcome.hidden = true;
        }
      }
      if (continueUnverified) show('unverified-notice'); else hide('unverified-notice');
      rememberWizardEntered(continueUnverified);
      window.scrollTo({ top: 0 });
    }

    const VERIFY_PANELS = [
      'verify-phone-entry', 'verify-code-entry', 'verify-email-entry',
      'verify-already-registered', 'verify-window-wait', 'verify-window-ended'
    ];

    function showOnlyVerifyPanel(id) {
      VERIFY_PANELS.forEach(panel => { if (panel !== id) hide(panel); });
      if (id) show(id);
      verifySection.hidden = false;
      registrationForm.hidden = true;
      if (progressBar) progressBar.hidden = true;
    }

    function formatWindowDate(iso) {
      if (!iso) return null;
      return new Date(iso).toLocaleString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'
      });
    }

    function setVerdictNotMeLink(id, firstName) {
      const link = byId(id);
      if (!link) return;
      link.textContent = firstName
        ? `Not ${firstName}? Verify with your email instead.`
        : '';
      link.hidden = !firstName;
    }

    // The server decided. This only renders.
    function applyVerdict(body) {
      const ctx = body.context || {};
      switch (body.outcome) {
        case 'verify_phone':
          showOnlyVerifyPanel('verify-phone-entry');
          return;

        case 'need_email':
          byId('verify-email-msg').textContent =
            "More than one member shares this number. Enter the email you use with the club.";
          showOnlyVerifyPanel('verify-email-entry');
          byId('verify-email').focus();
          return;

        case 'already_registered': {
          byId('already-registered-title').textContent =
            `You're already registered for ${ctx.season_name}.`;
          byId('already-registered-detail').textContent =
            ctx.status === 'ACTIVE'
              ? "We charged your card. See you out there."
              : "Your card has a hold. You pay only if you get a lottery spot.";
          setVerdictNotMeLink('already-registered-not-me-link', ctx.first_name);
          showOnlyVerifyPanel('verify-already-registered');
          return;
        }

        case 'window_not_yet_open': {
          const who = ctx.member_type === 'returning' ? 'Returning member' : 'New member';
          const when = formatWindowDate(ctx.opens_at);
          byId('window-wait-title').textContent = when
            ? `${who} registration opens ${when}.`
            : `${who} registration isn't open yet.`;
          setVerdictNotMeLink('window-wait-not-me-link', ctx.first_name);
          showOnlyVerifyPanel('verify-window-wait');
          return;
        }

        case 'window_ended': {
          const who = ctx.member_type === 'returning' ? 'Returning member' : 'New member';
          const when = formatWindowDate(ctx.closed_at);
          byId('window-ended-title').textContent = when
            ? `${who} registration closed ${when}.`
            : `${who} registration is closed.`;
          setVerdictNotMeLink('window-ended-not-me-link', ctx.first_name);
          showOnlyVerifyPanel('verify-window-ended');
          return;
        }

        case 'wizard_returning':
        case 'wizard_new':
          if (body.user) applyPrefill({ memberType: ctx.member_type, user: body.user });
          else setPaymentStatusLine(ctx.member_type);
          phoneResolvedMember = !!ctx.first_name;
          enterWizard({ continueUnverified: false, firstName: ctx.first_name });
          return;

        default:
          showOnlyVerifyPanel('verify-phone-entry');
      }
    }

    // Email correlation inside the wizard. Only fires when the phone
    // matched nobody: a resolved member owns their email outright and can
    // change it freely, which is the phone-is-primary rule.
    let phoneResolvedMember = false;
    let phoneVerifiedThisSession = false;
    let lastLookupEmail = null;
    let collisionCodeEmail = null;

    async function checkEmailCollision() {
      if (phoneResolvedMember || !phoneVerifiedThisSession) return;
      const emailField = byId('email');
      const value = emailField.value.trim();
      if (value === lastLookupEmail) return;
      if (!value || !value.includes('@')) return;
      showCollisionError('');
      let body;
      try {
        body = await postJson('/api/verify/email/lookup', { email: value });
      } catch (e) {
        if (byId('email').value.trim() === value) {
          showCollisionError("We couldn't check that email just now. Keep going, or try it again in a minute.", true);
        }
        return;
      }
      if (byId('email').value.trim() !== value) return;
      if (!body.ok) {
        showCollisionError(body.error || "We couldn't check that email just now. Keep going, or try it again in a minute.", true);
        return;
      }
      lastLookupEmail = value;
      if (!body.exists) {
        hide('email-collision');
        return;
      }
      collisionCodeEmail = null;
      hide('email-collision-code-row');
      show('email-collision-send');
      show('email-collision');
    }

    byId('email').addEventListener('blur', checkEmailCollision);

    byId('email-collision-send').addEventListener('click', async () => {
      const btn = byId('email-collision-send');
      const email = byId('email').value.trim();
      showCollisionError('');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/email/start',
                                    { email });
        if (!body.ok) {
          showCollisionError(body.error || "We can't email you a code right now. Try again in a minute.");
          return;
        }
        if (!body.exists) {
          hide('email-collision-code-row');
          showCollisionError("That email doesn't match an account.");
          return;
        }
        collisionCodeEmail = email;
        show('email-collision-code-row');
        byId('email-collision-code').focus();
      } catch (e) {
        showCollisionError("We can't email you a code right now. Try again in a minute.");
      } finally {
        btn.disabled = false;
      }
    });

    byId('email-collision-check').addEventListener('click', async () => {
      const btn = byId('email-collision-check');
      showCollisionError('');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/email/check', {
          email: collisionCodeEmail,
          code: byId('email-collision-code').value.replace(/\s+/g, '')
        });
        if (!body.ok) {
          showCollisionError(body.error || "That code doesn't match. Check your email and try again.");
          return;
        }
        hide('email-collision');
        // Linking may flip them to returning, or reveal a registration
        // they already have, or a window that isn't open. Re-ask.
        applyVerdict(await resolveAndRender());
      } catch (e) {
        showCollisionError("That code doesn't match. Check your email and try again.");
      } finally {
        btn.disabled = false;
      }
    });

    byId('email-collision-code').addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        byId('email-collision-check').click();
      }
    });

    // Last resort, not an opt-out. Someone who cannot reach the inbox on
    // a matched account still gets to register; an organizer links the
    // history afterward.
    byId('email-collision-dead').addEventListener('click', e => {
      e.preventDefault();
      hide('email-collision');
      byId('continue-unverified').value = '1';
      show('unverified-notice');
      rememberWizardEntered(true);
      setPaymentStatusLine('new');
    });

    async function resolveAndRender() {
      const invite = new URLSearchParams(window.location.search).get('invite');
      const seasonId = registrationForm.dataset.seasonId;
      let url = `/api/verify/resolve?season_id=${encodeURIComponent(seasonId)}`;
      if (invite) url += `&invite=${encodeURIComponent(invite)}`;
      const resp = await fetch(url);
      return resp.json();
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

    async function sendPhoneCode() {
      showVerifyError('');
      const phoneValue = byId('verify-phone').value.trim();
      const btn = byId('verify-send-btn');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/phone/start', { phone: phoneValue });
        if (!body.ok) {
          showVerifyError(body.error || 'We hit a snag. Try again.');
          return;
        }
        verifyPhone = phoneValue;
        byId('verify-phone-echo').textContent = phoneValue;
        hide('verify-phone-entry');
        show('verify-code-entry');
        byId('verify-code').focus();
        startResendCountdown(30);
      } catch (e) {
        showVerifyError("We couldn't send that code. Try again.");
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
          showVerifyError(body.error || 'We hit a snag. Try again.');
          return;
        }
        phoneVerifiedThisSession = true;
        applyVerdict(await resolveAndRender());
      } catch (e) {
        showVerifyError("We couldn't check that code. Try again.");
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
          showVerifyError(body.error || 'We hit a snag. Try again.');
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
        showVerifyError("We couldn't send that code. Try again.");
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
          showVerifyError(body.error || 'We hit a snag. Try again.');
          return;
        }
        if (reverifying) {
          // The previous identity's prefill no longer applies.
          resetWizardFields();
          reverifying = false;
        }
        applyVerdict(await resolveAndRender());
      } catch (e) {
        showVerifyError("We couldn't check that code. Try again.");
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

    // Escape hatches. Verification is mandatory, but registration never
    // hard-blocks. Both links take the flagged path: new-member lottery,
    // manual capture, admin review.
    byId('verify-cant-text-link').addEventListener('click', e => {
      e.preventDefault();
      phoneResolvedMember = false;
      setPaymentStatusLine('new');
      enterWizard({ continueUnverified: true });
    });
    byId('verify-email-dead-link').addEventListener('click', e => {
      e.preventDefault();
      phoneResolvedMember = false;
      if (reverifying) {
        // They said "Not [name]", so the old identity's answers must not
        // ride along into the flagged path.
        resetWizardFields();
        reverifying = false;
      }
      setPaymentStatusLine('new');
      enterWizard({ continueUnverified: true });
    });

    // Every "Not [name]?" exit returns to email entry so the session can be
    // re-pointed at the right account. The backend re-links user_id on a
    // successful email check for a phone-verified session.
    async function handleNotMe(e) {
      phoneResolvedMember = false;
      e.preventDefault();
      // Tell the server before showing the email step. Until this lands,
      // /create-season-payment-intent still sees the old account and would
      // auto-capture a full charge for someone who belongs in the lottery
      // on a hold.
      let body = null;
      try {
        body = await postJson('/api/verify/disclaim', {});
      } catch (e) {
        // A failed request cannot confirm that the old identity was dropped.
      }
      if (!body || body.ok !== true) {
        hide('verify-welcome');
        showOnlyVerifyPanel('verify-phone-entry');
        show('verify-expired-notice');
        return;
      }
      reverifying = true;
      showVerifyError('');
      hide('verify-welcome');
      hide('unverified-notice');
      hide('verify-expired-notice');
      hide('verify-email-code-row');
      byId('verify-email-msg').textContent =
        "Enter the email you use with the club to find your account.";
      showOnlyVerifyPanel('verify-email-entry');
      byId('verify-email').focus();
      window.scrollTo({ top: 0 });
    }

    [
      'verify-not-me-link',
      'already-registered-not-me-link',
      'window-wait-not-me-link',
      'window-ended-not-me-link'
    ].forEach(id => byId(id).addEventListener('click', handleNotMe));

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

    // Resume after a refresh. The server re-decides; the client never
    // guesses. An expired identity lands back on step 0 with an
    // explanation, never a silent downgrade to the flagged path.
    (async () => {
      let entry = null;
      try {
        entry = storedWizardEntry();
        const body = await resolveAndRender();
        if (body.outcome !== 'verify_phone') phoneVerifiedThisSession = true;
        const isWizardVerdict =
          body.outcome === 'wizard_new' || body.outcome === 'wizard_returning';
        if (entry === '1' && isWizardVerdict) {
          // A hatch choice wins over a wizard verdict after refresh or a
          // redirected POST. Keep the flagged new-member path they chose.
          //
          // The session may have been resolved in another tab since the
          // hatch was taken. If the verdict names someone, drop that link
          // first: /create-season-payment-intent never sees
          // continue_unverified and would otherwise price and capture the
          // intent as that member while this POST files a new one.
          const ctx = body.context || {};
          if (body.user || ctx.first_name) {
            let disclaimed = null;
            try {
              disclaimed = await postJson('/api/verify/disclaim', {});
            } catch (e) {
              // A failed request cannot confirm that the identity was dropped.
            }
            if (!disclaimed || disclaimed.ok !== true) {
              hide('verify-welcome');
              showOnlyVerifyPanel('verify-phone-entry');
              show('verify-expired-notice');
              return;
            }
          }
          phoneResolvedMember = false;
          setPaymentStatusLine('new');
          enterWizard({ continueUnverified: true });
          return;
        }
        applyVerdict(body);
        if (body.outcome === 'verify_phone' && entry === '0') {
          show('verify-expired-notice');
        }
        return;
      } catch (e) {
        entry = storedWizardEntry();
      }
      if (entry === '1') {
        // They took an escape hatch earlier; keep them on that path.
        phoneResolvedMember = false;
        setPaymentStatusLine('new');
        enterWizard({ continueUnverified: true });
        return;
      }
      if (entry === '0') show('verify-expired-notice');
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

      const fieldsOk = validateRequiredFields();
      const volunteerOk = validateVolunteerSection();
      if (!fieldsOk || !volunteerOk) {
        if (!fieldsOk) {
          showError('Please fill in all required fields before submitting.');
        } else {
          const volunteerSection = document.getElementById('section-volunteer');
          if (volunteerSection) {
            volunteerSection.scrollIntoView({behavior: 'smooth', block: 'center'});
          }
        }
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

        // Saved answers are NOT cleared here: the server can still reject
        // this POST (expired identity, email collision, closed window) and
        // redirect back promising "your answers are saved". The success
        // page clears the keys instead.
        registrationForm.submit();
      } catch (err) {
        showError("We couldn't process that payment. Try again.");
        isSubmitting = false;
        toggleLoadingState(false);
      }
    });

    initStripe();
  }
});
