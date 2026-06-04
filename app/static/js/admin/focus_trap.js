// app/static/js/admin/focus_trap.js
// trapFocus(container) -> release() : cycle Tab within container, restore focus on release.
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  AdminUI.trapFocus = function (container) {
    const previouslyFocused = document.activeElement;

    function focusables() {
      return Array.prototype.slice.call(container.querySelectorAll(FOCUSABLE))
        // getClientRects() is robust to position:fixed focusables (offsetParent is null for those).
        .filter(function (el) { return el.getClientRects().length > 0; });
    }

    function onKeydown(e) {
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (items.length === 0) { e.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    }

    container.addEventListener('keydown', onKeydown);
    const initial = focusables()[0];
    if (initial) initial.focus();

    return function release() {
      container.removeEventListener('keydown', onKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
    };
  };
})();
