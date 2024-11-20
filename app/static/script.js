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
    document.querySelectorAll('input[name="price-choice"]')
        .forEach(radio => radio.addEventListener('change', (e) => {
            const amount = parseFloat(e.target.value);
            this.selectedAmount = amount;
            this.updateUI(amount);
        }));

    this.elements.submit.addEventListener('click', this.handleSubmit.bind(this));
  }

  updateUI(amount) {
    this.elements.amountDisplay.textContent = `$${amount.toFixed(2)}`;
    
    // Only show package type if there are multiple prices
    const packageTypeElement = this.elements.packageType;
    if (packageTypeElement) {
        const priceInputs = document.querySelectorAll('input[name="price-choice"]');
        packageTypeElement.parentElement.style.display = priceInputs.length > 1 ? 'block' : 'none';
        packageTypeElement.textContent = amount === this.selectedAmount ? 'Lower' : 'Higher';
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
  }

  handleInitializationError(error) {
    console.error('Initialization error:', error);
    this.showError('Failed to initialize payment form. Please refresh the page.');
  }
}

document.addEventListener('DOMContentLoaded', () => new PaymentForm());

