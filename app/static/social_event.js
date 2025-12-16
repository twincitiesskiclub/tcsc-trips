// social_event.js - Payment handler for social events

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

function generateIdempotencyKey() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

class SocialEventPaymentForm {
  constructor() {
    this.stripe = null;
    this.card = null;
    this.clientSecret = null;
    this.isSubmitting = false;
    this.eventId = document.querySelector('.single-price-display').dataset.eventId;
    this.init();
  }

  async init() {
    try {
      const { publicKey } = await fetch('/get-stripe-key').then(r => r.json());
      this.stripe = Stripe(publicKey);
      this.setupStripeElements();
      this.attachEventListeners();
    } catch (error) {
      this.showError('Failed to initialize payment form. Please refresh the page.');
    }
  }

  setupStripeElements() {
    const elements = this.stripe.elements();
    this.card = elements.create('card', STRIPE_CARD_STYLES);
    this.card.mount('#card-element');
    this.card.on('change', ({error}) => this.showError(error?.message || ''));
  }

  attachEventListeners() {
    document.getElementById('submit').addEventListener('click', this.handleSubmit.bind(this));
  }

  validateForm() {
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;

    if (!name) {
      this.showError('Please enter your name.');
      return false;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      this.showError('Please enter a valid email address.');
      return false;
    }
    return true;
  }

  async handleSubmit(e) {
    e.preventDefault();
    if (this.isSubmitting) return;
    if (!this.validateForm()) return;

    this.isSubmitting = true;
    this.toggleLoadingState(true);

    try {
      const name = document.getElementById('name').value;
      const email = document.getElementById('email').value;

      // Create payment intent for social event
      const response = await fetch('/create-social-event-payment-intent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': generateIdempotencyKey()
        },
        body: JSON.stringify({
          social_event_id: this.eventId,
          email,
          name
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Payment failed');
      }

      const data = await response.json();
      this.clientSecret = data.clientSecret;

      // Confirm payment with Stripe
      const result = await this.stripe.confirmCardPayment(this.clientSecret, {
        payment_method: {
          card: this.card,
          billing_details: { name, email }
        }
      });

      if (result.error) {
        this.showError(result.error.message);
        this.isSubmitting = false;
      } else {
        this.handlePaymentSuccess();
      }
    } catch (error) {
      this.showError(error.message || 'Payment failed. Please try again.');
      this.isSubmitting = false;
    } finally {
      this.toggleLoadingState(false);
    }
  }

  showError(message) {
    const errorDisplay = document.getElementById('card-errors');
    errorDisplay.textContent = message;
    errorDisplay.style.display = message ? 'block' : 'none';
  }

  toggleLoadingState(isLoading) {
    document.getElementById('submit').disabled = isLoading;
    document.getElementById('spinner').classList.toggle('hidden', !isLoading);
    document.getElementById('button-text').classList.toggle('hidden', isLoading);
  }

  handlePaymentSuccess() {
    document.querySelectorAll('.payment-view').forEach(v => v.classList.add('hidden'));
    document.querySelectorAll('.completed-view').forEach(v => v.classList.remove('hidden'));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Initialize for social event registration pages
  if (document.querySelector('.single-price-display[data-event-id]')) {
    new SocialEventPaymentForm();
  }
});
