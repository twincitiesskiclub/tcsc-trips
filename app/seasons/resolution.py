"""Which registration screen a visitor should see.

One function, one verdict. The client renders it; the client does not
decide it. Keeping the rule here means every edge case is a pytest case
instead of a jsdom case, and a bug surfaces before merge rather than in
a member's browser at noon on opening day.
"""
from app.constants import UserSeasonStatus
from app.models import User, UserSeason

VERIFY_PHONE = 'verify_phone'
NEED_EMAIL = 'need_email'
ALREADY_REGISTERED = 'already_registered'
WINDOW_NOT_YET_OPEN = 'window_not_yet_open'
WINDOW_ENDED = 'window_ended'
WIZARD_RETURNING = 'wizard_returning'
WIZARD_NEW = 'wizard_new'

# A registration in either of these states occupies the member's spot.
# Anything DROPPED_* left the season, so they may register again.
HOLDS_A_SPOT = (UserSeasonStatus.ACTIVE, UserSeasonStatus.PENDING_LOTTERY)


def resolve_registration_step(identity, season, now, invite_payload=None):
    """Return (outcome, context) for this visitor and season.

    identity: the verified-identity session dict from
        app.verify.service.get_verified_identity(), or None.
    season: a Season row.
    now: UTC datetime, compared against the season's window bounds.
    invite_payload: a verified late-link payload, or None. A valid one
        for this season suppresses both window outcomes, matching what
        season_register and create_season_payment_intent already do.

    Outcomes are checked in a deliberate order; see the design doc.
    """
    if not identity:
        return VERIFY_PHONE, {}

    user = None
    if identity.get('user_id'):
        # A stale id (account deleted between steps) resolves to None and
        # falls through to the phone match rather than raising.
        user = User.query.get(identity['user_id'])

    if user is None:
        matches = User.get_by_phone(identity['phone_e164'])
        # Deliberately do not adopt a single match: phone/check would have set
        # user_id if that account had been verified at phone-check time.
        if len(matches) > 1:
            # Households share numbers. The phone cannot say which member
            # this is, so an email code has to. Checked before
            # already_registered so an unresolved visitor can never be
            # shown someone else's registration.
            return NEED_EMAIL, {'reason': 'multiple'}

    if user is not None:
        user_season = UserSeason.get_for_user_season(user.id, season.id)
        if user_season is not None and user_season.status in HOLDS_A_SPOT:
            return ALREADY_REGISTERED, {
                'first_name': user.first_name,
                'season_name': season.name,
                'status': user_season.status,
                'member_type': user_season.registration_type,
            }

    is_returning = bool(user is not None and user.is_returning)
    member_type = 'returning' if is_returning else 'new'

    invite_ok = (invite_payload is not None
                 and invite_payload.get('season_id') == season.id)

    if not invite_ok and not season.is_open_for(member_type, now):
        if is_returning:
            start, end = season.returning_start, season.returning_end
        else:
            start, end = season.new_start, season.new_end
        # is_open_for treats a half-configured window as closed, so an
        # unset bound reads as "not yet", never as "you missed it".
        if start is None or end is None:
            return WINDOW_NOT_YET_OPEN, {'member_type': member_type,
                                         'opens_at': None,
                                         'first_name': (user.first_name
                                                        if user is not None
                                                        else None)}
        if now < start:
            return WINDOW_NOT_YET_OPEN, {'member_type': member_type,
                                         'opens_at': start,
                                         'first_name': (user.first_name
                                                        if user is not None
                                                        else None)}
        return WINDOW_ENDED, {
            'member_type': member_type,
            'closed_at': end,
            'first_name': user.first_name if user is not None else None,
        }

    outcome = WIZARD_RETURNING if is_returning else WIZARD_NEW
    return outcome, {
        'first_name': user.first_name if user is not None else None,
        'member_type': member_type,
    }
