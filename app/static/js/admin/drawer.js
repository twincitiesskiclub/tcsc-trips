// app/static/js/admin/drawer.js
// drawer({ title, content }) -> { close, body }. Singleton: opening closes any open drawer.
// Right-side panel with inert scrim, focus-trap, Esc + scrim-click to close.
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};
  let current = null;

  AdminUI.drawer = function (opts) {
    opts = opts || {};
    if (current) current.close();

    const scrim = AdminUI.el('div', { class: 'admin-ui-drawer-scrim' }, []);
    const panel = AdminUI.el('aside', {
      class: 'admin-ui-drawer', role: 'dialog', 'aria-modal': 'true',
      'aria-label': opts.title || 'Details'
    }, []);

    const body = AdminUI.el('div', { class: 'admin-ui-drawer__body' }, []);
    if (typeof opts.content === 'string') body.innerHTML = opts.content;
    else if (opts.content) body.appendChild(opts.content);

    const header = AdminUI.el('div', { class: 'admin-ui-drawer__header' }, [
      AdminUI.el('h2', { class: 'admin-ui-drawer__title' }, [opts.title || '']),
      AdminUI.el('button', {
        class: 'admin-ui-drawer__close', type: 'button',
        'aria-label': 'Close', onclick: close
      }, ['×'])
    ]);

    panel.appendChild(header);
    panel.appendChild(body);
    document.body.appendChild(scrim);
    document.body.appendChild(panel);
    document.body.classList.add('admin-ui-no-scroll');
    requestAnimationFrame(function () { panel.classList.add('is-open'); });

    const release = AdminUI.trapFocus(panel);
    scrim.addEventListener('click', close);
    function onEsc(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onEsc);

    function close() {
      if (current !== api) return;
      document.removeEventListener('keydown', onEsc);
      release();
      panel.remove();
      scrim.remove();
      document.body.classList.remove('admin-ui-no-scroll');
      current = null;
    }

    const api = { close: close, body: body };
    current = api;
    return api;
  };
})();
