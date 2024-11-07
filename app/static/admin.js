document.addEventListener('DOMContentLoaded', () => {
  const actionButtons = document.querySelectorAll('.action-button');
  const singlePriceCheckbox = document.getElementById('single-price');
  const priceHighGroup = document.getElementById('price-high-group');
  const priceLow = document.getElementById('price_low');
  const priceHigh = document.getElementById('price_high');
  const priceLabel = document.getElementById('price-label');

  actionButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      const action = event.target.dataset.action;
      const paymentId = event.target.dataset.paymentId;
      alert(`Action: ${action} for Payment ID: ${paymentId}`);
      // Future: Implement action logic here
    });
  });

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
