# Kickoff RSVP short link

**Goal:** Serve `https://tcsc.ski/rsvp` so a tap in an SMS attempts to open Augie's kickoff post in the Slack app.

**Architecture:** Add one public Flask route and a self-contained template. An external script attempts one immediate navigation to Slack's own native URI. Keep a direct app link and the original HTTPS post link available when a browser blocks automatic navigation or Slack is unavailable. Do not simulate a trusted click, auto-submit a reaction, or accept a destination from query parameters.

**Scope:** The September 8, 2026 kickoff post in the TCSC workspace. No database, authentication, messaging, registration, or security-policy changes. Existing public CSP must allow the script without being relaxed.

**Evidence:** Slack generated the native URI for the original post. Google documents that app launches may require a user gesture; a desktop browser cannot establish Android or iPhone app acceptance. User requested another phone test before the reminder audience receives anything.

## Implementation and validation

- [x] Add route checks using a minimal Flask app with the real security headers, independent of the database and scheduler. Verify anonymous access, fixed post destination, and script delivery under CSP.
- [x] Add JavaScript behavior checks for one immediate launch, a blocked launch, returning through browser history, and a background document. Exercise the real script with only the external navigation boundary intercepted.
- [x] Implement `/rsvp` and `/rsvp/` in `app/routes/main.py`, `app/templates/rsvp.html`, and `app/static/rsvp.js`. Remove the unshipped marketing-site prototype.
- [ ] Run the focused route and JavaScript checks, existing neighboring route/security checks, and the production CSS build. Inspect narrow mobile layouts and the delivered HTML.
- [ ] Get an independent code review, open a PR, and ship through the repository's PR workflow. Verify the live route and script against the committed files.
- [ ] Text the user one test link through Twilio, verify delivery, and obtain phone behavior before sending member reminders.
