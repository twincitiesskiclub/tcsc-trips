// app/static/js/admin/filter_bar.js
// filterBar(mountEl, config, onChange) renders the shared filter UI and emits a state object.
// config = {
//   search:  { placeholder },                                    // optional
//   selects: [ { key, label, options:[{value,label}] } ],        // optional
//   pills:   [ { key, label, multi, options:[{value,label}] } ]  // optional
// }
// onChange(state): state = { search:'', <selectKey>:'', <pillKey>:[...] }
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  AdminUI.filterBar = function (mountEl, config, onChange) {
    config = config || {};
    const state = { search: '' };
    const root = AdminUI.el('div', { class: 'admin-ui-filterbar' }, []);

    if (config.search) {
      const input = AdminUI.el('input', {
        type: 'search', class: 'admin-ui-filterbar__search',
        placeholder: config.search.placeholder || 'Search...',
        oninput: function () { state.search = input.value; emit(); }
      }, []);
      root.appendChild(input);
    }

    (config.selects || []).forEach(function (sel) {
      state[sel.key] = '';
      const node = AdminUI.el('select', {
        class: 'admin-ui-filterbar__select', 'aria-label': sel.label,
        onchange: function () { state[sel.key] = node.value; emit(); }
      }, [AdminUI.el('option', { value: '' }, [sel.label])].concat(
        sel.options.map(function (o) {
          return AdminUI.el('option', { value: o.value }, [o.label]);
        })
      ));
      root.appendChild(node);
    });

    (config.pills || []).forEach(function (group) {
      state[group.key] = [];
      const wrap = AdminUI.el('div', {
        class: 'admin-ui-filterbar__pills', role: 'group', 'aria-label': group.label
      }, []);
      group.options.forEach(function (o) {
        const btn = AdminUI.el('button', {
          type: 'button', class: 'admin-ui-pill', 'aria-pressed': 'false',
          onclick: function () { togglePill(group, o.value, btn); }
        }, [o.label]);
        wrap.appendChild(btn);
      });
      root.appendChild(wrap);
    });

    function togglePill(group, value, btn) {
      const arr = state[group.key];
      const idx = arr.indexOf(value);
      if (group.multi) {
        if (idx === -1) arr.push(value); else arr.splice(idx, 1);
      } else {
        state[group.key] = (idx === -1) ? [value] : [];
        Array.prototype.forEach.call(btn.parentNode.children, function (b) {
          b.classList.remove('is-active'); b.setAttribute('aria-pressed', 'false');
        });
      }
      const active = state[group.key].indexOf(value) !== -1;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      emit();
    }

    function emit() { onChange(Object.assign({}, state)); }

    mountEl.appendChild(root);
    return { state: state, emit: emit };
  };
})();
