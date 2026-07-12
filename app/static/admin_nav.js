(function installAdminMobileNavigation() {
  document.addEventListener('DOMContentLoaded', function () {
    const openButton = document.getElementById('mobile-sidebar-open');
    const closeButton = document.getElementById('mobile-sidebar-close');
    const overlay = document.getElementById('mobile-sidebar-overlay');
    const panel = document.getElementById('mobile-sidebar-panel');
    if (!openButton || !closeButton || !overlay || !panel) return;

    function setOpen(isOpen) {
      overlay.classList.toggle('hidden', !isOpen);
      panel.classList.toggle('hidden', !isOpen);
      openButton.setAttribute('aria-expanded', String(isOpen));
      if (isOpen) closeButton.focus();
    }

    openButton.addEventListener('click', function () { setOpen(true); });
    closeButton.addEventListener('click', function () {
      setOpen(false);
      openButton.focus();
    });
    overlay.addEventListener('click', function () { setOpen(false); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !panel.classList.contains('hidden')) {
        setOpen(false);
        openButton.focus();
      }
    });
  });
})();
