// app/static/js/admin/pills.js
// pills(mountEl, items, opts) -> { getSelected }
// items = [{ id, label }]; opts = { multi:true, selected:[ids] }
// Selection is held in a Set and read at submit time (no hidden inputs).
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  AdminUI.pills = function (mountEl, items, opts) {
    opts = opts || {};
    const multi = opts.multi !== false;
    const selected = new Set(opts.selected || []);

    // dataset values are strings; coerce back to number when the id was numeric.
    function coerce(v) {
      const asNum = Number(v);
      return (v !== '' && String(asNum) === v) ? asNum : v;
    }

    items.forEach(function (item) {
      const isOn = selected.has(item.id);
      const btn = AdminUI.el('button', {
        type: 'button',
        class: 'admin-ui-pill' + (isOn ? ' is-active' : ''),
        'aria-pressed': isOn ? 'true' : 'false',
        dataset: { id: item.id },
        onclick: function () {
          if (selected.has(item.id)) selected.delete(item.id);
          else { if (!multi) selected.clear(); selected.add(item.id); }
          syncAll();
        }
      }, [item.label]);
      mountEl.appendChild(btn);
    });

    function syncAll() {
      Array.prototype.forEach.call(mountEl.querySelectorAll('.admin-ui-pill'), function (btn) {
        const on = selected.has(coerce(btn.dataset.id));
        btn.classList.toggle('is-active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    return { getSelected: function () { return Array.from(selected); } };
  };
})();
