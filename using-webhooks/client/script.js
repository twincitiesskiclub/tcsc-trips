// script.js
class PaymentForm {
  constructor() {
    this.stripe = null;
    this.card = null;
    this.selectedAmount = 135.00;
    this.clientSecret = null;
    this.paymentIntent = null;
    
    this.elements = {
      form: document.querySelector('.sr-payment-form'),
      submit: document.querySelector('#submit'),
      nameInput: document.querySelector('#name'),
      errorDisplay: document.querySelector('.sr-field-error'),
      amountDisplay: document.querySelector('.order-amount'),
      packageType: document.querySelector('.package-type'),
      spinner: document.querySelector('#spinner'),
      buttonText: document.querySelector('#button-text')
    };
    
    this.init();
  }

  async init() {
    try {
      // Initialize Stripe with just the public key first
      const response = await fetch('/get-stripe-key');
      const data = await response.json();
      this.stripe = Stripe(data.publicKey);
      
      // Set up the card element
      this.setupStripeElements();
      this.attachEventListeners();
    } catch (error) {
      console.error('Initialization error:', error);
      this.showError('Failed to initialize payment form. Please refresh the page.');
    }
  }

  setupStripeElements() {
    const elements = this.stripe.elements();
    
    this.card = elements.create('card', {
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
    });
    
    this.card.mount('#card-element');
    
    // Add card element event listeners
    this.card.on('change', ({error}) => {
      if (error) {
        this.showError(error.message);
      } else {
        this.showError('');
      }
    });
  }

  attachEventListeners() {
    document.querySelectorAll('input[name="price-choice"]')
      .forEach(radio => radio.addEventListener('change', 
        (e) => this.updatePrice(parseFloat(e.target.value))
      ));

    this.elements.submit.addEventListener('click', 
      (e) => this.handleSubmit(e)
    );
  }

  async updatePrice(amount) {
    this.selectedAmount = amount;
    this.elements.amountDisplay.textContent = `$${amount.toFixed(2)}`;
    this.elements.packageType.textContent = amount === 135.00 ? 'Lower' : 'Higher';
    
    // If we already have a payment intent, update it
    if (this.paymentIntent) {
      try {
        const response = await fetch('/update-payment-intent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paymentIntentId: this.paymentIntent.id,
            amount: this.selectedAmount
          })
        });
        const data = await response.json();
        this.clientSecret = data.clientSecret;
        this.paymentIntent = data.paymentIntent;
      } catch (error) {
        console.error('Error updating payment intent:', error);
        this.showError('Failed to update price. Please try again.');
      }
    }
  }

  async createOrUpdatePaymentIntent() {
    if (!this.paymentIntent) {
      // Create new payment intent
      const response = await fetch('/create-payment-intent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          currency: 'usd',
          amount: this.selectedAmount
        })
      });
      const data = await response.json();
      this.clientSecret = data.clientSecret;
      this.paymentIntent = data.paymentIntent;
    }
    return this.paymentIntent;
  }

  async handleSubmit(e) {
    e.preventDefault();
    
    if (!this.elements.nameInput.value) {
      this.showError('Please enter your name.');
      return;
    }

    this.toggleLoadingState(true);

    try {
      // Ensure we have a payment intent before confirming
      await this.createOrUpdatePaymentIntent();

      const result = await this.stripe.confirmCardPayment(this.clientSecret, {
        payment_method: {
          card: this.card,
          billing_details: {
            name: this.elements.nameInput.value
          }
        }
      });

      if (result.error) {
        this.showError(result.error.message);
      } else {
        await this.handlePaymentSuccess(result);
      }
    } catch (error) {
      console.error('Payment error:', error);
      this.showError('Payment failed. Please try again.');
    } finally {
      this.toggleLoadingState(false);
    }
  }

  showError(message) {
    this.elements.errorDisplay.textContent = message;
    if (message) {
      this.elements.errorDisplay.style.display = 'block';
    } else {
      this.elements.errorDisplay.style.display = 'none';
    }
  }

  toggleLoadingState(isLoading) {
    this.elements.submit.disabled = isLoading;
    this.elements.spinner.classList.toggle('hidden', !isLoading);
    this.elements.buttonText.classList.toggle('hidden', isLoading);
  }

  async handlePaymentSuccess(result) {
    document.querySelectorAll('.payment-view')
      .forEach(view => view.classList.add('hidden'));
    document.querySelectorAll('.completed-view')
      .forEach(view => view.classList.remove('hidden'));
    
    const status = result.paymentIntent.status === 'requires_capture' 
      ? 'successfully placed' 
      : 'did not place';
    document.querySelector('.hold-status').textContent = status;
    document.querySelector('pre').textContent = 
      JSON.stringify(result.paymentIntent, null, 2);
  }
}

document.addEventListener('DOMContentLoaded', () => new PaymentForm());
