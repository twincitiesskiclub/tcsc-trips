// script.js
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
  }

  initializeElements() {
    const selectors = {
      form: '.sr-payment-form',
      submit: '#submit',
      nameInput: '#name',
      emailInput: '#email',
      errorDisplay: '.sr-field-error',
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
    return {
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
    this.elements.amountDisplay.textContent = `$${amount.toFixed(2)}`;
    
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
    
    if (!this.validateForm()) return;

    this.toggleLoadingState(true);
    try {
      await this.processPayment();
    } catch (error) {
      console.error('Payment error:', error);
      this.showError('Payment failed. Please try again.');
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        currency: 'usd',
        amount: this.selectedAmount,
        email: this.elements.emailInput.value,
        name: this.elements.nameInput.value
      })
    });
    const data = await response.json();
    this.clientSecret = data.clientSecret;
    this.paymentIntent = data.paymentIntent;
    return this.paymentIntent;
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
  // Email validation for returning member (always runs)
  const emailInput = document.getElementById('email');
  if (emailInput) {
    let emailStatusMsg = document.createElement('div');
    emailStatusMsg.id = 'email-status-msg';
    emailStatusMsg.style.marginTop = '6px';
    emailStatusMsg.style.fontSize = '14px';
    emailInput.parentNode.appendChild(emailStatusMsg);

    emailInput.addEventListener('blur', async function() {
      const email = emailInput.value.trim().toLowerCase();
      emailStatusMsg.textContent = '';
      if (!email) return;
      emailStatusMsg.textContent = 'Checking membership status...';
      try {
        const resp = await fetch('/api/is_returning_member', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email })
        });
        const data = await resp.json();
        if (data.is_returning) {
          emailStatusMsg.textContent = '✅ Returning Member';
          emailStatusMsg.style.color = '#166534';
        } else {
          emailStatusMsg.textContent = '⚠️ We couldn’t find your email in our returning member records. Please register as a new member or try a different email address if you believe this is a mistake.';
          emailStatusMsg.style.color = '#b07b2c';
        }
      } catch (err) {
        emailStatusMsg.textContent = 'Error checking membership status.';
        emailStatusMsg.style.color = '#e44';
      }
    });
  }

  // Get the registration form and price from a data attribute or JS variable
  const registrationForm = document.getElementById('registration-form');
  // You can set this in your template: <form ... data-price-cents="{{ season.price_cents }}">
  const priceCents = parseInt(registrationForm?.dataset.priceCents || 0, 10);
  const priceDollars = priceCents / 100;

  // Only run payment logic if the form and card element exist
  if (registrationForm && document.getElementById('card-element')) {
    let stripe, card, clientSecret;

    async function fetchStripeKey() {
      const response = await fetch('/get-stripe-key');
      return response.json();
    }

    async function createPaymentIntent(name, email) {
      const response = await fetch('/create-season-payment-intent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          season_id: registrationForm.dataset.seasonId,
          email,
          name
        })
      });
      return response.json();
    }

    function showError(message) {
      const errorDisplay = document.getElementById('card-errors');
      if (errorDisplay) {
        errorDisplay.textContent = message;
        errorDisplay.style.display = message ? 'block' : 'none';
      }
    }

    function toggleLoadingState(isLoading) {
      const btn = document.getElementById('register-btn');
      if (btn) btn.disabled = isLoading;
    }

    async function initStripe() {
      const { publicKey } = await fetchStripeKey();
      stripe = Stripe(publicKey);
      const elements = stripe.elements();
      card = elements.create('card', {
        style: {
          base: {
            color: '#32325d',
            fontFamily: 'Helvetica Neue, Helvetica, sans-serif',
            fontSmoothing: 'antialiased',
            fontSize: '16px',
            '::placeholder': { color: '#aab7c4' }
          },
          invalid: { color: '#fa755a', iconColor: '#fa755a' }
        }
      });
      card.mount('#card-element');
      card.on('change', ({error}) => showError(error?.message || ''));
    }

    registrationForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      showError('');
      toggleLoadingState(true);
      try {
        // Get payment info from form
        const name = registrationForm.querySelector('#name').value;
        const email = registrationForm.querySelector('#email').value;
        // Create payment intent
        const paymentIntentData = await createPaymentIntent(name, email);
        if (paymentIntentData.error) {
          showError(paymentIntentData.error);
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
          toggleLoadingState(false);
          return;
        }
        // Payment succeeded, submit the form (remove card details so they aren't sent to backend)
        document.getElementById('card-element').remove();
        registrationForm.submit();
      } catch (err) {
        showError('Payment failed. Please try again.');
        toggleLoadingState(false);
      }
    });

    initStripe();
  }
});

