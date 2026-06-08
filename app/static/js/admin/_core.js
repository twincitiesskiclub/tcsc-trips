// app/static/js/admin/_core.js
// AdminUI: thin shared frontend foundation for the admin panel.
// Loaded as a plain <script> (no build step). Each primitive registers onto window.AdminUI.
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  // Escape a value for safe insertion as text/attribute content.
  AdminUI.escapeHtml = function (value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  // el('div', {class:'x', onclick: fn, dataset:{id:1}, unsafeHTML:'<b>x</b>'}, [child, ...])
  // - 'class' sets className; 'dataset' merges data-* attrs.
  // - 'unsafeHTML' sets innerHTML (XSS escape hatch - ONLY for trusted/own markup, never server text).
  //   For server-provided strings, pass them as a child instead: el('span', null, [serverValue]) (auto-escaped).
  // - keys starting with 'on' + a function become event listeners.
  // - any other non-null value becomes an attribute. Boolean attrs: add/omit, do NOT pass false
  //   (el('div',{hidden:false}) would render hidden="false", which is still hidden).
  // children may be DOM nodes or strings (inserted as text nodes).
  AdminUI.el = function (tag, props, children) {
    const node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (key) {
        const val = props[key];
        if (key === 'class') node.className = val;
        else if (key === 'dataset') Object.assign(node.dataset, val);
        else if (key === 'unsafeHTML') node.innerHTML = val;
        else if (/^on[a-zA-Z]/.test(key)) {
          if (typeof val === 'function') {
            node.addEventListener(key.slice(2).toLowerCase(), val);
          } else if (val !== null && val !== undefined) {
            // Reserved event-handler prefix given a non-function value: almost always a bug.
            console.warn('AdminUI.el: ignoring non-function "' + key + '" prop');
          }
        } else if (val !== null && val !== undefined) {
          node.setAttribute(key, val);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  };

  // Run fn once the DOM is ready (now if already past loading).
  AdminUI.onReady = function (fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  };
})();
