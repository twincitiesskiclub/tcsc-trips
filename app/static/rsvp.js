(() => {
  const link = document.getElementById('open-rsvp');
  const navigation = performance.getEntriesByType('navigation')[0];

  // Do not pull someone out of a background tab or trap them when going Back.
  if (!link || document.visibilityState !== 'visible' || navigation?.type === 'back_forward') return;

  try {
    // Try once, immediately. Browsers may require a real tap on the link;
    // a synthetic click or timer cannot guarantee permission to launch Slack.
    window.location.replace(link.href);
  } catch {
    // The app and browser links remain usable if external navigation is blocked.
  }
})();
