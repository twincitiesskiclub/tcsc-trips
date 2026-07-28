// Generic event registration and Stripe Elements checkout.

(function eventRegistrationPage() {
  const dataNode = document.getElementById('event-registration-data');
  const form = document.getElementById('event-registration-form');
  if (!dataNode || !form) return;

  const eventData = JSON.parse(dataNode.textContent);
  const optionsById = new Map(
    eventData.priceOptions.map(option => [String(option.id), option])
  );
  const knownOptionNames = new Set(
    eventData.priceOptions.map(option => option.name)
  );

  // Mirrors questions_for_option() on the server: an empty scope applies to
  // every option, and a scope naming no surviving option falls open to
  // applying rather than silently dropping a required question.
  function questionAppliesTo(scope, optionName) {
    if (!Array.isArray(scope) || scope.length === 0) return true;
    if (scope.includes(optionName)) return true;
    return !scope.some(name => knownOptionNames.has(name));
  }

  const stripeCardStyles = {
    style: {
      base: {
        color: '#1c2c44',
        fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
        fontSmoothing: 'antialiased',
        fontSize: '16px',
        '::placeholder': { color: '#94a3b8' }
      },
      invalid: {
        color: '#c53030',
        iconColor: '#c53030'
      }
    }
  };

  function createInputField(labelText, type, field, value, autocomplete) {
    const fieldWrapper = document.createElement('div');
    fieldWrapper.className = 'form-field';

    const label = document.createElement('label');
    label.className = 'form-field__label';
    label.htmlFor = field;
    label.textContent = labelText;

    const input = document.createElement('input');
    input.className = 'form-input';
    input.id = field;
    input.type = type;
    input.required = true;
    input.dataset.participantField = field.split('-').pop();
    input.value = value || '';
    if (autocomplete) input.autocomplete = autocomplete;

    fieldWrapper.append(label, input);
    return fieldWrapper;
  }

  class EventRegistrationForm {
    constructor() {
      this.stripe = null;
      this.card = null;
      this.stripePromise = null;
      this.isSubmitting = false;
      this.participantValues = [];
      this.attachEventListeners();
      this.renderSelectedOption();
    }

    get selectedOption() {
      const selected = form.querySelector(
        'input[name="price_option_id"]:checked'
      );
      return selected ? optionsById.get(selected.value) : null;
    }

    attachEventListeners() {
      form.addEventListener('submit', event => this.handleSubmit(event));
      form.querySelectorAll('input[name="price_option_id"]').forEach(input => {
        input.addEventListener('change', () => this.renderSelectedOption());
      });
    }

    snapshotParticipants() {
      const participantGroups = form.querySelectorAll('[data-participant]');
      this.participantValues = Array.from(participantGroups).map(group => {
        const values = {};
        group.querySelectorAll('[data-participant-field]').forEach(input => {
          values[input.dataset.participantField] = input.value;
        });
        return values;
      });
    }

    renderSelectedOption() {
      this.snapshotParticipants();
      const option = this.selectedOption;
      if (!option) return;

      form.querySelectorAll('.price-option-container').forEach(card => {
        const radio = card.querySelector('input[type="radio"]');
        card.classList.toggle(
          'price-option-container--selected',
          radio.checked
        );
      });

      const description = document.getElementById('option-description');
      description.textContent = option.description || '';
      this.renderParticipants(option.participantRoles);

      const teamNameField = document.getElementById('team-name-field');
      const teamName = document.getElementById('team-name');
      const isTeam = option.participantRoles.length > 1;
      teamNameField.classList.toggle('hidden', !isTeam);
      teamName.required = isTeam;
      teamName.disabled = !isTeam;

      this.applyQuestionScopes(option.name);

      const isFree = option.priceCents === 0;
      document.getElementById('card-field').classList.toggle('hidden', isFree);
      document.getElementById('button-text').textContent = isFree
        ? 'Complete registration'
        : `Pay ${this.formatCurrency(option.priceCents)}`;

      if (!isFree) {
        this.ensureStripe().catch(() => {
          this.showError(
            'The payment form could not be initialized. Refresh and try again.'
          );
        });
      }
    }

    applyQuestionScopes(optionName) {
      let visibleCount = 0;
      form.querySelectorAll('[data-question-field]').forEach(field => {
        let scope = [];
        try {
          scope = JSON.parse(field.dataset.questionScope || '[]');
        } catch (error) {
          scope = [];
        }

        const applies = questionAppliesTo(scope, optionName);
        if (applies) visibleCount += 1;
        field.classList.toggle('hidden', !applies);
        // Disabling keeps out-of-scope answers out of validation and out of
        // the payload while preserving what was typed if the option changes
        // back.
        field.querySelectorAll('[data-question-key]').forEach(input => {
          input.disabled = !applies;
        });
      });

      // Don't leave the heading stranded over an empty section.
      const section = document.getElementById('event-questions');
      if (section) section.classList.toggle('hidden', visibleCount === 0);
    }

    renderParticipants(roles) {
      const container = document.getElementById('participants-container');
      container.replaceChildren();

      roles.forEach((role, index) => {
        const participantNumber = index + 1;
        const saved = this.participantValues[index] || {};
        const group = document.createElement('div');
        group.dataset.participant = String(index);
        group.style.marginBottom = index === roles.length - 1 ? '0' : '32px';

        const title = document.createElement('h3');
        title.className = 'form-section__title';
        title.style.marginBottom = '16px';
        title.textContent = `${role} details`;

        const identityRow = document.createElement('div');
        identityRow.className = 'form-row form-row--pair';
        identityRow.append(
          createInputField(
            'Full name',
            'text',
            `participant-${participantNumber}-name`,
            saved.name,
            'name'
          ),
          createInputField(
            'Date of birth',
            'date',
            `participant-${participantNumber}-date_of_birth`,
            saved.date_of_birth,
            'bday'
          )
        );

        const contactRow = document.createElement('div');
        contactRow.className = 'form-row form-row--pair';
        contactRow.append(
          createInputField(
            'Email address',
            'email',
            `participant-${participantNumber}-email`,
            saved.email,
            'email'
          ),
          createInputField(
            'Phone number',
            'tel',
            `participant-${participantNumber}-phone`,
            saved.phone,
            'tel'
          )
        );

        group.append(title, identityRow, contactRow);
        container.append(group);
      });
    }

    async ensureStripe() {
      if (this.card) return;
      if (this.stripePromise) return this.stripePromise;

      this.stripePromise = (async () => {
        const response = await fetch('/get-stripe-key');
        if (!response.ok) throw new Error('Payment configuration unavailable');
        const { publicKey } = await response.json();
        if (!publicKey || !window.Stripe) {
          throw new Error('Payment configuration unavailable');
        }

        this.stripe = window.Stripe(publicKey);
        this.card = this.stripe
          .elements()
          .create('card', stripeCardStyles);
        this.card.mount('#card-element');
        this.card.on('change', ({ error }) => {
          this.showError(error ? error.message : '');
        });
      })();

      try {
        await this.stripePromise;
      } finally {
        this.stripePromise = null;
      }
    }

    collectPayload() {
      const answers = {};
      form
        .querySelectorAll('[data-question-key]:not([disabled])')
        .forEach(input => {
          answers[input.dataset.questionKey] = input.value;
        });

      const participants = Array.from(
        form.querySelectorAll('[data-participant]')
      ).map(group => {
        const participant = {};
        group.querySelectorAll('[data-participant-field]').forEach(input => {
          participant[input.dataset.participantField] = input.value;
        });
        return participant;
      });

      // Only teams have a team name; don't ship a stale one left behind by a
      // registrant who switched away from a team option.
      const isTeam = this.selectedOption.participantRoles.length > 1;

      return {
        price_option_id: this.selectedOption.id,
        team_name: isTeam
          ? document.getElementById('team-name').value
          : null,
        emergency_contact_name: document.getElementById(
          'emergency-contact-name'
        ).value,
        emergency_contact_phone: document.getElementById(
          'emergency-contact-phone'
        ).value,
        participants,
        answers,
        discount_code: document.getElementById('discount-code').value
      };
    }

    async handleSubmit(event) {
      event.preventDefault();
      if (this.isSubmitting || !this.selectedOption) return;
      this.clearFieldErrors();

      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      this.isSubmitting = true;
      this.toggleLoading(true);

      try {
        if (this.selectedOption.priceCents > 0) {
          await this.ensureStripe();
        }

        const payload = this.collectPayload();
        const response = await fetch(
          `/events/${encodeURIComponent(eventData.slug)}/register`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Idempotency-Key': this.generateIdempotencyKey()
            },
            body: JSON.stringify(payload)
          }
        );
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          this.showServerErrors(result.error);
          return;
        }

        if (result.free) {
          this.showCompleted(
            'Your registration is confirmed. No payment was required.'
          );
          return;
        }

        const confirmation = await this.stripe.confirmCardPayment(
          result.clientSecret,
          {
            payment_method: {
              card: this.card,
              billing_details: {
                name: payload.participants[0].name,
                email: payload.participants[0].email,
                phone: payload.participants[0].phone
              }
            }
          }
        );

        if (confirmation.error) {
          this.showError(confirmation.error.message);
          return;
        }

        this.showCompleted(
          `Your registration is confirmed. ${this.formatCurrency(
            result.amountCents
          )} was charged to your card. Stripe will email your receipt.`
        );
      } catch (error) {
        this.showError(
          error.message || 'Registration failed. Please try again.'
        );
      } finally {
        this.isSubmitting = false;
        this.toggleLoading(false);
      }
    }

    // A key can repeat across scopes, so match the one currently in play.
    findQuestionInput(questionKey) {
      const inputs = Array.from(
        form.querySelectorAll('[data-question-key]:not([disabled])')
      );
      return (
        inputs.find(input => input.dataset.questionKey === questionKey) || null
      );
    }

    showServerErrors(errors) {
      if (!errors || typeof errors !== 'object') {
        this.showError(errors || 'Registration failed. Please try again.');
        return;
      }

      const messages = Object.values(errors);
      Object.keys(errors).forEach(key => {
        const fieldId = {
          team_name: 'team-name',
          emergency_contact_name: 'emergency-contact-name',
          emergency_contact_phone: 'emergency-contact-phone'
        }[key];
        const questionKey = key.startsWith('answers.')
          ? key.slice('answers.'.length)
          : null;
        const field = fieldId
          ? document.getElementById(fieldId)
          : questionKey
            ? this.findQuestionInput(questionKey)
            : null;
        if (field) field.classList.add('field-error');
      });
      this.showError(messages.join(' '));
    }

    clearFieldErrors() {
      form.querySelectorAll('.field-error').forEach(field => {
        field.classList.remove('field-error');
      });
      this.showError('');
    }

    showError(message) {
      const errorDisplay = document.getElementById('form-errors');
      errorDisplay.textContent = message || '';
      errorDisplay.style.display = message ? 'block' : 'none';
    }

    toggleLoading(isLoading) {
      document.getElementById('submit').disabled = isLoading;
      document.getElementById('spinner').classList.toggle(
        'hidden',
        !isLoading
      );
      document.getElementById('button-text').classList.toggle(
        'hidden',
        isLoading
      );
    }

    showCompleted(message) {
      document.getElementById('confirmation-message').textContent = message;
      document.querySelectorAll('.payment-view').forEach(view => {
        view.classList.add('hidden');
      });
      document.querySelectorAll('.completed-view').forEach(view => {
        view.classList.remove('hidden');
      });
      document.querySelector('.completed-view h1').focus?.();
      window.scrollTo({ top: 0 });
    }

    formatCurrency(cents) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
      }).format(cents / 100);
    }

    generateIdempotencyKey() {
      if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
      }
      return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
    }
  }

  new EventRegistrationForm();
})();
