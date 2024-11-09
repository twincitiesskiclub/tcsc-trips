document.addEventListener('DOMContentLoaded', () => {
  // Status mapping for UI display
  const STATUS_DISPLAY = {
    'requires_payment_method': 'Pending',
    'requires_confirmation': 'Pending',
    'requires_action': 'Pending',
    'requires_capture': 'Pending',
    'processing': 'Processing',
    'succeeded': 'Success',
    'canceled': 'Canceled',
    'refunded': 'Refunded',
    'default': 'Unknown'  // Fallback for unexpected values
  };

  // CSS class mapping for status badges
  const STATUS_CLASSES = {
    'requires_payment_method': 'pending',
    'requires_confirmation': 'pending',
    'requires_action': 'pending',
    'requires_capture': 'pending',
    'processing': 'processing',
    'succeeded': 'success',
    'canceled': 'canceled',
    'refunded': 'refunded',
    'default': 'unknown'  // Fallback for unexpected values
  };

  const actionButtons = document.querySelectorAll('[data-action]');
  const singlePriceCheckbox = document.getElementById('single-price');
  const priceHighGroup = document.getElementById('price-high-group');
  const priceLow = document.getElementById('price_low');
  const priceHigh = document.getElementById('price_high');
  const priceLabel = document.getElementById('price-label');

  actionButtons.forEach(button => {
    button.addEventListener('click', async (event) => {
      const action = event.target.dataset.action;
      const paymentId = event.target.dataset.paymentId;
      
      if (!confirm(`Are you sure you want to ${action} this payment?`)) {
        return;
      }
      
      try {
        button.disabled = true;
        const row = button.closest('tr');
        
        let endpoint;
        switch(action) {
          case 'accept':
            endpoint = `/admin/payments/${paymentId}/capture`;
            break;
          case 'refund':
            endpoint = `/admin/payments/${paymentId}/refund`;
            break;
          default:
            return; // Exit for unhandled actions
        }
        
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.error || 'An error occurred');
        }
        
        // Update the status badge display
        const statusBadge = row.querySelector('.status-badge');
        const newStatus = data.payment.status;
        statusBadge.className = `status-badge status-${STATUS_CLASSES[newStatus]}`;
        statusBadge.textContent = STATUS_DISPLAY[newStatus];
        
        // Disable relevant buttons based on new status
        updateButtonStates(row, data.payment.status);
        
        // Show success message
        showMessage('success', `Payment ${action}ed successfully`);
        
      } catch (error) {
        console.error('Error:', error);
        showMessage('error', error.message);
        button.disabled = false;
      }
    });
  });
  
  function updateButtonStates(row, status) {
    const acceptBtn = row.querySelector('[data-action="accept"]');
    const refundBtn = row.querySelector('[data-action="refund"]');
    
    switch(status) {
      case 'succeeded':
        acceptBtn.disabled = true;
        refundBtn.disabled = false;
        break;
      case 'refunded':
        acceptBtn.disabled = true;
        refundBtn.disabled = true;
        break;
      default:
        acceptBtn.disabled = false;
        refundBtn.disabled = true;
    }
  }
  
  function showMessage(type, message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `flash-message ${type}`;
    messageDiv.textContent = message;
    
    const container = document.querySelector('.admin-content');
    container.insertBefore(messageDiv, container.firstChild);
    
    // Remove message after 5 seconds
    setTimeout(() => {
      messageDiv.remove();
    }, 5000);
  }

  // Set initial state
  if (trip && priceLow.value === priceHigh.value) {
    singlePriceCheckbox.checked = true;
    priceHighGroup.style.display = 'none';
    priceLabel.textContent = 'Price ($)';
  }

  singlePriceCheckbox.addEventListener('change', (e) => {
    if (e.target.checked) {
      priceHighGroup.style.display = 'none';
      priceLabel.textContent = 'Price ($)';
      priceHigh.value = priceLow.value;
      priceLow.addEventListener('input', syncPrices);
    } else {
      priceHighGroup.style.display = 'block';
      priceLabel.textContent = 'Lower Price ($)';
      priceLow.removeEventListener('input', syncPrices);
    }
  });

  function syncPrices(e) {
    priceHigh.value = e.target.value;
  }
});
