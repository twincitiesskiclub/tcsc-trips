"""Block Kit builders for newsletter dispatch section."""


def build_dispatch_submission_section() -> list[dict]:
    """Build the Submit to Dispatch section for App Home.

    Creates a section with information about the Weekly Dispatch newsletter
    and a button to open the submission modal.

    Returns:
        List of Slack Block Kit blocks for the dispatch section.
    """
    return [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Weekly Dispatch",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":newspaper: *Share your story with the club!*\n\n"
                    "Submit member spotlights, event announcements, stories, "
                    "or tips for the Weekly Dispatch newsletter."
                )
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":memo: Submit to Dispatch",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "open_dispatch_modal",
                    "value": "submit_dispatch"
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_You can also use `/dispatch` from any channel._"
                }
            ]
        }
    ]
