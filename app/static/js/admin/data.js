// app/static/js/admin/data.js
// fetchJSON(url): GET -> parsed JSON (rejects on non-2xx).
// mutate(url, body): POST JSON; toasts success/error via global showToast (js/toast.js).
(function () {
  const AdminUI = window.AdminUI = window.AdminUI || {};

  AdminUI.fetchJSON = function (url) {
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      });
  };

  AdminUI.mutate = function (url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok || data.success === false) {
          const msg = (data && (data.error || data.message)) ||
            ('Request failed (' + res.status + ')');
          if (window.showToast) showToast(msg, 'error');
          throw new Error(msg);
        }
        if (data.message && window.showToast) showToast(data.message, 'success');
        return data;
      });
    });
  };
})();
