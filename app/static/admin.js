document.addEventListener('DOMContentLoaded', () => {
  const actionButtons = document.querySelectorAll('.action-button');

  actionButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      const action = event.target.dataset.action;
      const paymentId = event.target.dataset.paymentId;
      alert(`Action: ${action} for Payment ID: ${paymentId}`);
      // Future: Implement action logic here
    });
  });
});
