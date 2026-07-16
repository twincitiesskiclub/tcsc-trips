# Slack Test App Follow-up

Create a dedicated Slack app in the TCSC workspace for development and live
testing. It must use separate app and bot tokens from production and be scoped
to the test channel (`C07G9RTMRT3`).

This prevents Slack Socket Mode from distributing test interactions between a
local feature branch and the production Render service, which may be running
different code. Until the test app exists, do not run a local Socket Mode
companion with the production Slack app while Render is connected.

The test app must not post to `#announcements-practices`. Give it only the
permissions needed for the preview and authoring workflows, and retain the
test-channel guard as defense in depth.
