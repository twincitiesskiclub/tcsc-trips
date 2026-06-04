// app/static/js/admin/status_badge.js
// statusBadge(text, variant) -> <span> with a color dot + text (color + dot + text for a11y).
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  // Logical variant -> Tailwind color pair (already compiled in tailwind-output.css).
  const VARIANTS = {
    success: 'bg-green-50 text-green-700',
    danger:  'bg-red-50 text-red-700',
    warning: 'bg-amber-50 text-amber-700',
    info:    'bg-blue-50 text-blue-700',
    neutral: 'bg-zinc-100 text-zinc-600'
  };

  AdminUI.statusBadge = function (text, variant) {
    const cls = VARIANTS[variant] || VARIANTS.neutral;
    return AdminUI.el('span', { class: 'admin-ui-badge ' + cls }, [
      AdminUI.el('span', { class: 'admin-ui-badge__dot', 'aria-hidden': 'true' }, []),
      String(text == null ? '' : text)
    ]);
  };
})();
