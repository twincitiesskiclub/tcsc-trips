// Attach Flask-WTF's token to same-origin state-changing fetch requests.
(function installCsrfFetchGuard() {
  const tokenElement = document.querySelector('meta[name="csrf-token"]');
  if (!tokenElement || !window.fetch) return;

  const csrfToken = tokenElement.content;
  const originalFetch = window.fetch.bind(window);
  const safeMethods = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

  window.fetch = function csrfFetch(input, init) {
    const options = Object.assign({}, init || {});
    const existingRequest = input instanceof Request ? input : null;
    const method = String(options.method || (existingRequest && existingRequest.method) || 'GET').toUpperCase();
    const target = new URL(existingRequest ? existingRequest.url : input, window.location.href);

    if (target.origin === window.location.origin && !safeMethods.has(method)) {
      const headers = new Headers(options.headers || (existingRequest && existingRequest.headers) || {});
      if (!headers.has('X-CSRFToken')) headers.set('X-CSRFToken', csrfToken);
      options.headers = headers;
    }

    return originalFetch(input, options);
  };
})();
