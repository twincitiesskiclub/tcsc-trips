"""Admin routes for Practice Management CRUD."""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from datetime import datetime, timedelta
from ..auth import admin_required
from ..models import db, User, Tag, AppConfig
from ..practices.models import (
    Practice, PracticeLocation, PracticeActivity, PracticeType,
    PracticeLead, SocialLocation, practice_activities_junction,
    practice_types_junction
)
from ..practices.interfaces import PracticeStatus, LeadRole, RSVPStatus, CancellationStatus
from ..practices.plan_reaction_queries import (
    PlanReactionSourceSelectionError,
    load_all_plan_reaction_sources,
    load_selected_plan_reaction_sources,
)
from ..practices.plan_reactions import (
    PlanReactionValidationError,
    build_plan_reaction_catalog,
    normalize_plan_reactions,
    resolve_plan_reaction_defaults,
    validate_authorized_plan_reactions,
)
from sqlalchemy.orm import joinedload

admin_practices_bp = Blueprint('admin_practices', __name__, url_prefix='/admin/practices')
_EDIT_UNSYNCED_ERROR = (
    'Practice was updated, but its Slack announcement did not update. '
    'Retry the edit to refresh the announcement.'
)


def _activity_json(activity):
    return {
        'id': activity.id,
        'name': activity.name,
        'gear_required': activity.gear_required or [],
        'default_plan_reactions': activity.default_plan_reactions or [],
        'practice_count': len(activity.practices),
    }


def _type_json(practice_type):
    return {
        'id': practice_type.id,
        'name': practice_type.name,
        'fitness_goals': practice_type.fitness_goals or [],
        'has_intervals': practice_type.has_intervals,
        'default_plan_reactions': practice_type.default_plan_reactions or [],
        'practice_count': len(practice_type.practices),
    }


def _prepare_plan_reaction_submission(data, *, existing_practice=None):
    activity_ids = (
        data['activity_ids']
        if 'activity_ids' in data
        else (
            [item.id for item in existing_practice.activities]
            if existing_practice is not None
            else []
        )
    )
    type_ids = (
        data['type_ids']
        if 'type_ids' in data
        else (
            [item.id for item in existing_practice.practice_types]
            if existing_practice is not None
            else []
        )
    )
    selected = load_selected_plan_reaction_sources(
        db.session,
        activity_ids=activity_ids,
        type_ids=type_ids,
    )
    resolution = resolve_plan_reaction_defaults(
        selected.practice_types,
        selected.activities,
    )
    all_sources = load_all_plan_reaction_sources(db.session)
    catalog = build_plan_reaction_catalog(
        all_sources.practice_types,
        all_sources.activities,
    )
    protected = (
        existing_practice.plan_reactions or []
        if existing_practice
        else []
    )
    if data.get('restore_plan_reaction_defaults') is True:
        plan_reactions = resolution.snapshot
    elif 'plan_reactions' in data:
        plan_reactions = validate_authorized_plan_reactions(
            data['plan_reactions'],
            catalog=catalog,
            protected_snapshot=protected,
        )
    elif existing_practice is None:
        plan_reactions = resolution.snapshot
    else:
        plan_reactions = None
    return selected, plan_reactions


def _week_coach_summary_ts(practice_date, exclude_id=None):
    """Return the Coach Review post ts already linked to this practice's week.

    The weekly Coach Review summary is one Slack post per week, and the
    refresh dispatcher updates it via each practice's slack_coach_summary_ts.
    A practice created out-of-band (admin UI) after the summary was posted has
    no ts of its own, so editing it silently skips the refresh. Copying a
    sibling's ts at create time keeps the whole week linked to the same post.
    """
    days_since_monday = practice_date.weekday()
    week_start = (practice_date - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = week_start + timedelta(days=7)

    query = Practice.query.filter(
        Practice.date >= week_start,
        Practice.date < week_end,
        Practice.slack_coach_summary_ts.isnot(None),
    )
    if exclude_id is not None:
        query = query.filter(Practice.id != exclude_id)

    sibling = query.first()
    return sibling.slack_coach_summary_ts if sibling else None


@admin_practices_bp.route('/')
@admin_required
def practices_list():
    """Render practice list view."""
    return render_template('admin/practices/list.html')


@admin_practices_bp.route('/calendar')
@admin_required
def practices_calendar():
    """Render practice calendar view."""
    return render_template('admin/practices/calendar.html')


@admin_practices_bp.route('/data')
@admin_required
def practices_data():
    """Return all practices as JSON for the admin grid."""
    # Eager load relationships to avoid N+1 queries
    practices = Practice.query.options(
        joinedload(Practice.location),
        joinedload(Practice.social_location),
        joinedload(Practice.activities),
        joinedload(Practice.practice_types),
        joinedload(Practice.leads).joinedload(PracticeLead.user)
    ).order_by(Practice.date.desc()).all()

    practices_data = []
    for practice in practices:
        # Build location name
        location_name = practice.location.name if practice.location else 'No Location'

        # Build activities list
        activities = [a.name for a in practice.activities]

        # Build types list
        practice_types = [t.name for t in practice.practice_types]

        # Build leads list (role='lead')
        leads = [{
            'id': lead.id,
            'user_id': lead.user_id,
            'name': lead.display_name,
            'confirmed': lead.confirmed
        } for lead in practice.leads if lead.role == 'lead']

        # Build coaches list (role='coach')
        coaches = [{
            'id': lead.id,
            'user_id': lead.user_id,
            'name': lead.display_name,
            'confirmed': lead.confirmed
        } for lead in practice.leads if lead.role == 'coach']

        # Build assists list (role='assist')
        assists = [{
            'id': lead.id,
            'user_id': lead.user_id,
            'name': lead.display_name,
            'confirmed': lead.confirmed
        } for lead in practice.leads if lead.role == 'assist']

        practices_data.append({
            'id': practice.id,
            'date': practice.date.isoformat(),
            'day_of_week': practice.day_of_week,
            'location_name': location_name,
            'location_id': practice.location_id,
            'social_location_id': practice.social_location_id,
            'social_location_name': practice.social_location.name if practice.social_location else None,
            'activities': activities,
            'practice_types': practice_types,
            'status': practice.status,
            'has_social': practice.has_social,
            'is_dark_practice': practice.is_dark_practice,
            'leads': leads,
            'coaches': coaches,
            'assists': assists,
            'cancellation_reason': practice.cancellation_reason or '',
            'workout_description': practice.workout_description or '',
            'logistics_notes': practice.logistics_notes or '',
        })

    return jsonify({'practices': practices_data})


@admin_practices_bp.route('/<int:practice_id>')
@admin_required
def practice_detail(practice_id):
    """Display single practice detail."""
    practice = Practice.query.get_or_404(practice_id)
    social_locations = SocialLocation.query.order_by(SocialLocation.name).all()
    return render_template('admin/practices/detail.html', practice=practice, social_locations=social_locations)


@admin_practices_bp.route('/new')
@admin_required
def practice_new():
    """Render the editor in create mode (no practice)."""
    social_locations = SocialLocation.query.order_by(SocialLocation.name).all()
    return render_template(
        'admin/practices/detail.html',
        practice=None,
        social_locations=social_locations,
    )


@admin_practices_bp.route('/create', methods=['POST'])
@admin_required
def create_practice():
    """Create a new practice."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # Validate required fields
    if not data.get('date'):
        return jsonify({'error': 'Date is required'}), 400
    if not data.get('location_id'):
        return jsonify({'error': 'Location is required'}), 400

    for field, label in (
        ('workout_description', 'Workout'),
        ('logistics_notes', 'Notes / Logistics'),
    ):
        value = data.get(field)
        if value is not None and len(value) > 2500:
            return jsonify({
                'error': f'{label} must be 2,500 characters or fewer',
                'field': field,
            }), 400

    try:
        selected, plan_reactions = _prepare_plan_reaction_submission(data)
    except PlanReactionSourceSelectionError as exc:
        field = {
            'activities': 'activity_ids',
            'types': 'type_ids',
        }[exc.field]
        return jsonify({'error': str(exc), 'field': field}), 400
    except PlanReactionValidationError as exc:
        return jsonify({
            'error': str(exc),
            'field': 'plan_reactions',
        }), 400

    try:
        # Parse date
        date = datetime.fromisoformat(data['date'])

        # Create practice
        practice = Practice(
            date=date,
            day_of_week=date.strftime('%A'),
            location_id=data['location_id'],
            social_location_id=data.get('social_location_id'),
            status=PracticeStatus.SCHEDULED.value,
            workout_description=data.get('workout_description'),
            logistics_notes=data.get('logistics_notes') or None,
            plan_reactions=plan_reactions,
            is_dark_practice=data.get('is_dark_practice', False),
        )
        practice.activities = list(selected.activities)
        practice.practice_types = list(selected.practice_types)
        db.session.add(practice)
        db.session.flush()

        # Link to the week's existing Coach Review post (if one was already
        # posted) so later edits refresh that post instead of silently skipping.
        practice.slack_coach_summary_ts = _week_coach_summary_ts(
            practice.date, exclude_id=practice.id
        )

        # Add coaches (now using user_id)
        if data.get('coach_ids'):
            for user_id in data['coach_ids']:
                coach = PracticeLead(
                    practice_id=practice.id,
                    user_id=user_id,
                    role='coach'
                )
                db.session.add(coach)

        # Add leads (now using user_id)
        if data.get('lead_ids'):
            for user_id in data['lead_ids']:
                lead = PracticeLead(
                    practice_id=practice.id,
                    user_id=user_id,
                    role='lead'
                )
                db.session.add(lead)

        # Add assists
        if data.get('assist_ids'):
            for user_id in data['assist_ids']:
                assist = PracticeLead(
                    practice_id=practice.id,
                    user_id=user_id,
                    role='assist'
                )
                db.session.add(assist)

        db.session.commit()

        return jsonify({
            'success': True,
            'practice_id': practice.id,
            'message': 'Practice created successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_practices_bp.route('/<int:practice_id>/edit', methods=['POST'])
@admin_required
def edit_practice(practice_id):
    """Update an existing practice."""
    practice = Practice.query.get_or_404(practice_id)
    had_root = bool(practice.slack_message_ts)
    practice_updated = False

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        previous_date = practice.date
        previous_location_id = practice.location_id
        previous_plan_reactions = [
            dict(item) for item in (practice.plan_reactions or [])
        ]

        for field, label in (
            ('workout_description', 'Workout'),
            ('logistics_notes', 'Notes / Logistics'),
        ):
            value = data.get(field)
            if value is not None and len(value) > 2500:
                return jsonify({
                    'error': f'{label} must be 2,500 characters or fewer',
                    'field': field,
                }), 400

        try:
            selected, plan_reactions = _prepare_plan_reaction_submission(
                data,
                existing_practice=practice,
            )
        except PlanReactionSourceSelectionError as exc:
            field = {
                'activities': 'activity_ids',
                'types': 'type_ids',
            }[exc.field]
            return jsonify({'error': str(exc), 'field': field}), 400
        except PlanReactionValidationError as exc:
            field = {
                'activities': 'activity_ids',
                'types': 'type_ids',
            }.get(exc.field, 'plan_reactions')
            return jsonify({
                'error': str(exc),
                'field': field,
            }), 400

        if plan_reactions is not None:
            practice.plan_reactions = plan_reactions

        # Update fields if provided
        if 'date' in data:
            date = datetime.fromisoformat(data['date'])
            practice.date = date
            practice.day_of_week = date.strftime('%A')

        if 'location_id' in data:
            practice.location_id = data['location_id']

        if 'workout_description' in data:
            practice.workout_description = data['workout_description']

        if 'logistics_notes' in data:
            practice.logistics_notes = data['logistics_notes'] or None

        if 'social_location_id' in data:
            practice.social_location_id = data['social_location_id']

        if 'is_dark_practice' in data:
            practice.is_dark_practice = data['is_dark_practice']

        if 'status' in data:
            practice.status = data['status']

        # Update activities if provided
        if 'activity_ids' in data:
            practice.activities = list(selected.activities)

        # Update types if provided
        if 'type_ids' in data:
            practice.practice_types = list(selected.practice_types)

        # Update coaches, leads, and assistants if provided (now using user_id)
        if 'coach_ids' in data or 'lead_ids' in data or 'assist_ids' in data:
            # Remove existing leads/coaches/assistants
            PracticeLead.query.filter_by(practice_id=practice.id).delete()

            # Add coaches
            if data.get('coach_ids'):
                for user_id in data['coach_ids']:
                    coach = PracticeLead(
                        practice_id=practice.id,
                        user_id=user_id,
                        role='coach'
                    )
                    db.session.add(coach)

            # Add leads
            if data.get('lead_ids'):
                for user_id in data['lead_ids']:
                    lead = PracticeLead(
                        practice_id=practice.id,
                        user_id=user_id,
                        role='lead'
                    )
                    db.session.add(lead)

            # Add assists
            if data.get('assist_ids'):
                for user_id in data['assist_ids']:
                    assist = PracticeLead(
                        practice_id=practice.id,
                        user_id=user_id,
                        role='assist'
                    )
                    db.session.add(assist)

        db.session.commit()
        practice_updated = True

        # Update all Slack posts
        from app.slack.practices import refresh_practice_posts
        from app.slack.practices.announcements import (
            build_announcement_change_notice,
        )
        announcement_notice = build_announcement_change_notice(
            previous_date=previous_date,
            previous_location_id=previous_location_id,
            practice=practice,
        )
        results = refresh_practice_posts(
            practice,
            change_type='edit',
            announcement_notice=announcement_notice,
            previous_plan_reactions=previous_plan_reactions,
        )
        announcement = (results or {}).get('announcement') or {}
        if had_root and announcement.get('success') is not True:
            return jsonify({
                'success': False,
                'practice_updated': True,
                'error': _EDIT_UNSYNCED_ERROR,
            }), 502

        return jsonify({
            'success': True,
            'message': 'Practice updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        if practice_updated:
            if had_root:
                return jsonify({
                    'success': False,
                    'practice_updated': True,
                    'error': _EDIT_UNSYNCED_ERROR,
                }), 502
            return jsonify({
                'success': True,
                'message': 'Practice updated successfully',
            })
        return jsonify({'error': str(e)}), 500


@admin_practices_bp.route('/<int:practice_id>/delete', methods=['POST'])
@admin_required
def delete_practice(practice_id):
    """Delete a practice."""
    practice = Practice.query.get_or_404(practice_id)
    had_root = bool(practice.slack_message_ts)

    try:
        # Clean up Slack posts before deleting DB record
        from app.slack.practices import refresh_practice_posts
        results = refresh_practice_posts(practice, change_type='delete')
        announcement = results.get('announcement') or {}
        safe = announcement.get('success') is True
        if not had_root:
            safe = safe or announcement.get('skipped') in {True, 'absent'}
        if not safe:
            return jsonify({
                'success': False,
                'error': (
                    'Slack announcement could not be updated; '
                    'practice was not deleted'
                ),
            }), 502

        db.session.delete(practice)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Practice deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_practices_bp.route('/<int:practice_id>/cancel', methods=['POST'])
@admin_required
def cancel_practice(practice_id):
    """Cancel a practice with a reason."""
    practice = Practice.query.get_or_404(practice_id)
    data = request.get_json() or {}
    had_root = bool(practice.slack_message_ts)

    try:
        practice.status = PracticeStatus.CANCELLED.value
        practice.cancellation_reason = (
            data.get('reason') or 'Cancelled by admin'
        )

        db.session.commit()

        # Update all Slack posts to show cancelled status
        from app.slack.practices import refresh_practice_posts
        results = refresh_practice_posts(practice, change_type='cancel')
        announcement = results.get('announcement') or {}
        if had_root and announcement.get('success') is not True:
            return jsonify({
                'success': False,
                'practice_cancelled': True,
                'error': (
                    'Practice was cancelled, but its Slack announcement '
                    'did not update'
                ),
            }), 502

        return jsonify({
            'success': True,
            'message': 'Practice cancelled successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_practices_bp.route('/config')
@admin_required
def practices_config():
    """Render practices configuration page with tabs for locations, activities, types."""
    return render_template('admin/practices/config.html')


@admin_practices_bp.route('/locations/data')
@admin_required
def locations_data():
    """Return all practice locations as JSON with practice counts."""
    locations = PracticeLocation.query.order_by(PracticeLocation.name).all()

    return jsonify({
        'locations': [{
            'id': loc.id,
            'name': loc.name,
            'spot': loc.spot,
            'address': loc.address,
            'google_maps_url': loc.google_maps_url,
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'parking_notes': loc.parking_notes,
            'practice_count': len(loc.practices)
        } for loc in locations]
    })


@admin_practices_bp.route('/types/data')
@admin_required
def types_data():
    """Return all practice types as JSON with practice counts."""
    types = PracticeType.query.order_by(PracticeType.name).all()

    return jsonify({
        'types': [_type_json(practice_type) for practice_type in types]
    })


@admin_practices_bp.route('/activities/data')
@admin_required
def activities_data():
    """Return all practice activities as JSON with practice counts."""
    activities = PracticeActivity.query.order_by(PracticeActivity.name).all()

    return jsonify({
        'activities': [_activity_json(activity) for activity in activities]
    })


@admin_practices_bp.route('/people/data')
@admin_required
def people_data():
    """Return coaches, leads, and assistants from Users with appropriate tags."""
    # Get coach tags (HEAD_COACH, ASSISTANT_COACH)
    coach_tags = Tag.query.filter(Tag.name.in_(['HEAD_COACH', 'ASSISTANT_COACH'])).all()
    coach_tag_ids = [t.id for t in coach_tags]

    # Get lead tag (PRACTICES_LEAD)
    lead_tags = Tag.query.filter(Tag.name.in_(['PRACTICES_LEAD'])).all()
    lead_tag_ids = [t.id for t in lead_tags]

    # Get assistant tag (PRACTICES_LEAD can also be assistants, or any active member)
    # For assistants, we include all users with PRACTICES_LEAD tag since they can assist
    # as well as coaches who might help as assistants

    # Query users with coach tags (eager-load tags to avoid N+1)
    coaches = User.query.options(joinedload(User.tags)).filter(
        User.tags.any(Tag.id.in_(coach_tag_ids))
    ).order_by(User.first_name).all()

    # Query users with lead tags (eager-load tags to avoid N+1)
    leads = User.query.options(joinedload(User.tags)).filter(
        User.tags.any(Tag.id.in_(lead_tag_ids))
    ).order_by(User.first_name).all()

    # Assists can be any coach or lead (combined pool)
    assist_ids = set()
    assists = []
    for u in coaches + leads:
        if u.id not in assist_ids:
            assist_ids.add(u.id)
            assists.append(u)
    assists.sort(key=lambda u: u.first_name)

    def serialize_person(u):
        return {
            'id': u.id,
            'name': f"{u.first_name} {u.last_name}",
            'tags': [{'name': t.name, 'emoji': t.emoji} for t in u.tags],
        }

    return jsonify({
        'coaches': [serialize_person(u) for u in coaches],
        'leads': [serialize_person(u) for u in leads],
        'assists': [serialize_person(u) for u in assists],
    })


# ============================================================================
# Social Locations CRUD
# ============================================================================

@admin_practices_bp.route('/social-locations/data')
@admin_required
def social_locations_data():
    """Return all social locations as JSON."""
    locations = SocialLocation.query.order_by(SocialLocation.name).all()

    return jsonify({
        'social_locations': [{
            'id': loc.id,
            'name': loc.name,
            'address': loc.address,
            'google_maps_url': loc.google_maps_url,
            'practice_count': len(loc.practices)
        } for loc in locations]
    })


@admin_practices_bp.route('/social-locations/create', methods=['POST'])
@admin_required
def create_social_location():
    """Create a new social location."""
    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Check for duplicate name
    if SocialLocation.query.filter_by(name=name).first():
        return jsonify({'error': f'Social location "{name}" already exists'}), 400

    location = SocialLocation(
        name=name,
        address=request.json.get('address', '').strip() or None,
        google_maps_url=request.json.get('google_maps_url', '').strip() or None
    )
    db.session.add(location)
    db.session.commit()

    return jsonify({
        'success': True,
        'social_location': {
            'id': location.id,
            'name': location.name,
            'address': location.address,
            'google_maps_url': location.google_maps_url,
            'practice_count': 0
        }
    })


@admin_practices_bp.route('/social-locations/<int:loc_id>/edit', methods=['POST'])
@admin_required
def edit_social_location(loc_id):
    """Update a social location."""
    location = SocialLocation.query.get_or_404(loc_id)

    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    # Update name with duplicate check
    if 'name' in request.json:
        new_name = request.json['name'].strip()
        if new_name != location.name:
            if SocialLocation.query.filter_by(name=new_name).first():
                return jsonify({'error': f'Social location "{new_name}" already exists'}), 400
            location.name = new_name

    if 'address' in request.json:
        location.address = (request.json['address'] or '').strip() or None
    if 'google_maps_url' in request.json:
        location.google_maps_url = (request.json['google_maps_url'] or '').strip() or None

    db.session.commit()

    return jsonify({
        'success': True,
        'social_location': {
            'id': location.id,
            'name': location.name,
            'address': location.address,
            'google_maps_url': location.google_maps_url,
            'practice_count': len(location.practices)
        }
    })


@admin_practices_bp.route('/social-locations/<int:loc_id>/delete', methods=['POST'])
@admin_required
def delete_social_location(loc_id):
    """Delete a social location (only if no practices reference it)."""
    location = SocialLocation.query.get_or_404(loc_id)

    if location.practices:
        return jsonify({
            'error': f'Cannot delete "{location.name}" - {len(location.practices)} practice(s) reference it'
        }), 400

    location_name = location.name
    db.session.delete(location)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Social location "{location_name}" deleted successfully'
    })


# ============================================================================
# Practice Locations CRUD
# ============================================================================

@admin_practices_bp.route('/locations/create', methods=['POST'])
@admin_required
def create_location():
    """Create a new practice location."""
    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Check for duplicate name
    if PracticeLocation.query.filter_by(name=name).first():
        return jsonify({'error': f'Location "{name}" already exists'}), 400

    location = PracticeLocation(
        name=name,
        spot=request.json.get('spot', '').strip() or None,
        address=request.json.get('address', '').strip() or None,
        google_maps_url=request.json.get('google_maps_url', '').strip() or None,
        latitude=request.json.get('latitude'),
        longitude=request.json.get('longitude'),
        parking_notes=request.json.get('parking_notes', '').strip() or None
    )
    db.session.add(location)
    db.session.commit()

    return jsonify({
        'success': True,
        'location': {
            'id': location.id,
            'name': location.name,
            'spot': location.spot,
            'address': location.address,
            'google_maps_url': location.google_maps_url,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'parking_notes': location.parking_notes,
            'practice_count': 0
        }
    })


@admin_practices_bp.route('/locations/<int:loc_id>/edit', methods=['POST'])
@admin_required
def edit_location(loc_id):
    """Update a practice location."""
    location = PracticeLocation.query.get_or_404(loc_id)

    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    # Update name with duplicate check
    if 'name' in request.json:
        new_name = request.json['name'].strip()
        if new_name != location.name:
            if PracticeLocation.query.filter_by(name=new_name).first():
                return jsonify({'error': f'Location "{new_name}" already exists'}), 400
            location.name = new_name

    if 'spot' in request.json:
        location.spot = (request.json['spot'] or '').strip() or None
    if 'address' in request.json:
        location.address = (request.json['address'] or '').strip() or None
    if 'google_maps_url' in request.json:
        location.google_maps_url = (request.json['google_maps_url'] or '').strip() or None
    if 'latitude' in request.json:
        location.latitude = request.json['latitude']
    if 'longitude' in request.json:
        location.longitude = request.json['longitude']
    if 'parking_notes' in request.json:
        location.parking_notes = (request.json['parking_notes'] or '').strip() or None

    db.session.commit()

    return jsonify({
        'success': True,
        'location': {
            'id': location.id,
            'name': location.name,
            'spot': location.spot,
            'address': location.address,
            'google_maps_url': location.google_maps_url,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'parking_notes': location.parking_notes,
            'practice_count': len(location.practices)
        }
    })


@admin_practices_bp.route('/locations/<int:loc_id>/delete', methods=['POST'])
@admin_required
def delete_location(loc_id):
    """Delete a practice location (only if no practices reference it)."""
    location = PracticeLocation.query.get_or_404(loc_id)

    if location.practices:
        return jsonify({
            'error': f'Cannot delete "{location.name}" - {len(location.practices)} practice(s) use this location'
        }), 400

    location_name = location.name
    db.session.delete(location)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Location "{location_name}" deleted successfully'
    })


# ============================================================================
# Practice Activities CRUD
# ============================================================================

@admin_practices_bp.route('/activities/create', methods=['POST'])
@admin_required
def create_activity():
    """Create a new practice activity."""
    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Check for duplicate name
    if PracticeActivity.query.filter_by(name=name).first():
        return jsonify({'error': f'Activity "{name}" already exists'}), 400

    try:
        if 'default_plan_reactions' in request.json:
            defaults = normalize_plan_reactions(
                request.json['default_plan_reactions'], source='Plan reactions'
            )
        else:
            defaults = []
    except PlanReactionValidationError as exc:
        return jsonify({
            'error': str(exc),
            'field': 'default_plan_reactions',
        }), 400

    # Handle gear_required - can be string (comma-separated) or array
    gear_required = request.json.get('gear_required')
    if isinstance(gear_required, str):
        gear_required = [s.strip() for s in gear_required.split(',') if s.strip()]
    elif not isinstance(gear_required, list):
        gear_required = None

    activity = PracticeActivity(
        name=name,
        gear_required=gear_required or None,
        default_plan_reactions=defaults,
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({
        'success': True,
        'activity': _activity_json(activity),
    })


@admin_practices_bp.route('/activities/<int:activity_id>/edit', methods=['POST'])
@admin_required
def edit_activity(activity_id):
    """Update a practice activity."""
    activity = PracticeActivity.query.get_or_404(activity_id)

    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    try:
        defaults = None
        if 'default_plan_reactions' in request.json:
            defaults = normalize_plan_reactions(
                request.json['default_plan_reactions'], source='Plan reactions'
            )
    except PlanReactionValidationError as exc:
        return jsonify({
            'error': str(exc),
            'field': 'default_plan_reactions',
        }), 400

    # Update name with duplicate check
    if 'name' in request.json:
        new_name = request.json['name'].strip()
        if new_name != activity.name:
            if PracticeActivity.query.filter_by(name=new_name).first():
                return jsonify({'error': f'Activity "{new_name}" already exists'}), 400
            activity.name = new_name

    if 'gear_required' in request.json:
        gear_required = request.json['gear_required']
        if isinstance(gear_required, str):
            gear_required = [s.strip() for s in gear_required.split(',') if s.strip()]
        elif not isinstance(gear_required, list):
            gear_required = None
        activity.gear_required = gear_required or None

    if defaults is not None:
        activity.default_plan_reactions = defaults

    db.session.commit()

    return jsonify({
        'success': True,
        'activity': _activity_json(activity),
    })


@admin_practices_bp.route('/activities/<int:activity_id>/delete', methods=['POST'])
@admin_required
def delete_activity(activity_id):
    """Delete a practice activity (only if no practices reference it)."""
    activity = PracticeActivity.query.get_or_404(activity_id)

    if activity.practices:
        return jsonify({
            'error': f'Cannot delete "{activity.name}" - {len(activity.practices)} practice(s) use this activity'
        }), 400

    activity_name = activity.name
    db.session.delete(activity)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Activity "{activity_name}" deleted successfully'
    })


# ============================================================================
# Practice Types CRUD
# ============================================================================

@admin_practices_bp.route('/types/create', methods=['POST'])
@admin_required
def create_type():
    """Create a new practice type."""
    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Check for duplicate name
    if PracticeType.query.filter_by(name=name).first():
        return jsonify({'error': f'Type "{name}" already exists'}), 400

    try:
        if 'default_plan_reactions' in request.json:
            defaults = normalize_plan_reactions(
                request.json['default_plan_reactions'], source='Plan reactions'
            )
        else:
            defaults = []
    except PlanReactionValidationError as exc:
        return jsonify({
            'error': str(exc),
            'field': 'default_plan_reactions',
        }), 400

    # Handle fitness_goals - can be string (comma-separated) or array
    fitness_goals = request.json.get('fitness_goals')
    if isinstance(fitness_goals, str):
        fitness_goals = [s.strip() for s in fitness_goals.split(',') if s.strip()]
    elif not isinstance(fitness_goals, list):
        fitness_goals = None

    practice_type = PracticeType(
        name=name,
        fitness_goals=fitness_goals or None,
        has_intervals=request.json.get('has_intervals', False),
        default_plan_reactions=defaults,
    )
    db.session.add(practice_type)
    db.session.commit()

    return jsonify({
        'success': True,
        'type': _type_json(practice_type),
    })


@admin_practices_bp.route('/types/<int:type_id>/edit', methods=['POST'])
@admin_required
def edit_type(type_id):
    """Update a practice type."""
    practice_type = PracticeType.query.get_or_404(type_id)

    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    try:
        defaults = None
        if 'default_plan_reactions' in request.json:
            defaults = normalize_plan_reactions(
                request.json['default_plan_reactions'], source='Plan reactions'
            )
    except PlanReactionValidationError as exc:
        return jsonify({
            'error': str(exc),
            'field': 'default_plan_reactions',
        }), 400

    # Update name with duplicate check
    if 'name' in request.json:
        new_name = request.json['name'].strip()
        if new_name != practice_type.name:
            if PracticeType.query.filter_by(name=new_name).first():
                return jsonify({'error': f'Type "{new_name}" already exists'}), 400
            practice_type.name = new_name

    if 'fitness_goals' in request.json:
        fitness_goals = request.json['fitness_goals']
        if isinstance(fitness_goals, str):
            fitness_goals = [s.strip() for s in fitness_goals.split(',') if s.strip()]
        elif not isinstance(fitness_goals, list):
            fitness_goals = None
        practice_type.fitness_goals = fitness_goals or None

    if 'has_intervals' in request.json:
        practice_type.has_intervals = request.json['has_intervals']

    if defaults is not None:
        practice_type.default_plan_reactions = defaults

    db.session.commit()

    return jsonify({
        'success': True,
        'type': _type_json(practice_type),
    })


@admin_practices_bp.route('/types/<int:type_id>/delete', methods=['POST'])
@admin_required
def delete_type(type_id):
    """Delete a practice type (only if no practices reference it)."""
    practice_type = PracticeType.query.get_or_404(type_id)

    if practice_type.practices:
        return jsonify({
            'error': f'Cannot delete "{practice_type.name}" - {len(practice_type.practices)} practice(s) use this type'
        }), 400

    type_name = practice_type.name
    db.session.delete(practice_type)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Type "{type_name}" deleted successfully'
    })


# ============================================================================
# Status Reference (Read-Only)
# ============================================================================

@admin_practices_bp.route('/statuses/data')
@admin_required
def statuses_data():
    """Return all practice-related status enums as JSON for reference display."""
    return jsonify({
        'practice_status': [{'value': s.value, 'name': s.name} for s in PracticeStatus],
        'lead_role': [{'value': r.value, 'name': r.name} for r in LeadRole],
        'rsvp_status': [{'value': s.value, 'name': s.name} for s in RSVPStatus],
        'cancellation_status': [{'value': s.value, 'name': s.name} for s in CancellationStatus],
    })


# ============================================================================
# RSVP Management
# ============================================================================

@admin_practices_bp.route('/<int:practice_id>/rsvps')
@admin_required
def practice_rsvps(practice_id):
    """Return RSVPs for a practice."""
    from ..practices.models import PracticeRSVP

    practice = Practice.query.get_or_404(practice_id)
    rsvps = PracticeRSVP.query.filter_by(practice_id=practice_id).all()

    return jsonify({
        'rsvps': [{
            'id': rsvp.id,
            'user_id': rsvp.user_id,
            'user_name': f"{rsvp.user.first_name} {rsvp.user.last_name}" if rsvp.user else 'Unknown',
            'status': rsvp.status,
            'notes': rsvp.notes,
            'responded_at': rsvp.responded_at.isoformat() if rsvp.responded_at else None
        } for rsvp in rsvps],
        'summary': {
            'going': len([r for r in rsvps if r.status == RSVPStatus.GOING.value]),
            'not_going': len([r for r in rsvps if r.status == RSVPStatus.NOT_GOING.value]),
            'maybe': len([r for r in rsvps if r.status == RSVPStatus.MAYBE.value])
        }
    })


# ============================================================================
# Lead Confirmation Management
# ============================================================================

@admin_practices_bp.route('/<int:practice_id>/leads/<int:lead_id>/toggle-confirm', methods=['POST'])
@admin_required
def toggle_lead_confirmation(practice_id, lead_id):
    """Toggle the confirmation status of a practice lead."""
    lead = PracticeLead.query.filter_by(
        id=lead_id,
        practice_id=practice_id
    ).first_or_404()

    try:
        lead.confirmed = not lead.confirmed
        lead.confirmed_at = datetime.utcnow() if lead.confirmed else None
        db.session.commit()

        # Keep Slack surfaces (announcement / collab / coach summary) in sync.
        # Local import matches the existing edit/cancel/delete routes in this file.
        from app.slack.practices import refresh_practice_posts
        from flask import current_app
        practice = Practice.query.get(practice_id)
        if practice:
            try:
                refresh_practice_posts(practice, change_type='edit')
            except Exception as refresh_err:
                current_app.logger.warning(
                    f"Lead toggle saved but Slack refresh failed for practice "
                    f"#{practice_id}: {refresh_err}"
                )

        return jsonify({
            'success': True,
            'confirmed': lead.confirmed,
            'confirmed_at': lead.confirmed_at.isoformat() if lead.confirmed_at else None,
            'message': f"Lead {'confirmed' if lead.confirmed else 'unconfirmed'} successfully"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_practices_bp.route('/<int:practice_id>/leads/data')
@admin_required
def practice_leads_data(practice_id):
    """Return all leads/coaches/assistants for a practice with confirmation status."""
    practice = Practice.query.get_or_404(practice_id)

    leads_data = []
    for lead in practice.leads:
        leads_data.append({
            'id': lead.id,
            'user_id': lead.user_id,
            'name': lead.display_name,
            'role': lead.role,
            'confirmed': lead.confirmed,
            'confirmed_at': lead.confirmed_at.isoformat() if lead.confirmed_at else None
        })

    return jsonify({'leads': leads_data})


# ============================================================================
# Skipper Evaluation (Inline Display)
# ============================================================================

@admin_practices_bp.route('/<int:practice_id>/evaluation')
@admin_required
def practice_evaluation(practice_id):
    """Get Skipper evaluation for a practice."""
    from ..agent.decision_engine import evaluate_practice

    practice = Practice.query.get_or_404(practice_id)

    try:
        evaluation = evaluate_practice(practice)

        return jsonify({
            'success': True,
            'evaluation': {
                'is_go': evaluation.is_go,
                'confidence': evaluation.confidence,
                'has_confirmed_lead': evaluation.has_confirmed_lead,
                'has_posted_workout': evaluation.has_posted_workout,
                'weather': {
                    'temperature_f': evaluation.weather.temperature_f if evaluation.weather else None,
                    'feels_like_f': evaluation.weather.feels_like_f if evaluation.weather else None,
                    'wind_speed_mph': evaluation.weather.wind_speed_mph if evaluation.weather else None,
                    'conditions_summary': evaluation.weather.conditions_summary if evaluation.weather else None,
                    'precipitation_chance': evaluation.weather.precipitation_chance if evaluation.weather else None,
                } if evaluation.weather else None,
                'trail_conditions': {
                    'ski_quality': evaluation.trail_conditions.ski_quality if evaluation.trail_conditions else None,
                    'trails_open': evaluation.trail_conditions.trails_open if evaluation.trail_conditions else None,
                    'groomed': evaluation.trail_conditions.groomed if evaluation.trail_conditions else None,
                } if evaluation.trail_conditions else None,
                'air_quality': evaluation.air_quality,
                'violations': [{
                    'threshold_name': v.threshold_name,
                    'severity': v.severity,
                    'message': v.message
                } for v in evaluation.violations]
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Weekly Summary Trigger
# ============================================================================

@admin_practices_bp.route('/weekly-summary/trigger', methods=['POST'])
@admin_required
def trigger_weekly_summary():
    """Manually trigger the weekly practice summary post."""
    from flask import current_app
    from ..agent.routines.weekly_summary import run_weekly_summary

    try:
        result = run_weekly_summary()

        return jsonify({
            'success': True,
            'practice_count': result.get('practice_count', 0),
            'week_start': result.get('week_start'),
            'slack_posted': result.get('slack_posted', False),
            'slack_error': result.get('slack_error'),
            'dry_run': result.get('dry_run', False)
        })

    except Exception as e:
        current_app.logger.error(f"Error triggering weekly summary: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# App Config (Global Settings)
# ============================================================================

@admin_practices_bp.route('/settings/data')
@admin_required
def settings_data():
    """Return practice-related settings from AppConfig."""
    # Get practice_days config
    practice_days = AppConfig.get('practice_days', [
        {"day": "tuesday", "time": "18:00", "active": True},
        {"day": "thursday", "time": "18:00", "active": True},
        {"day": "saturday", "time": "09:00", "active": True}
    ])

    return jsonify({
        'practice_days': practice_days
    })


@admin_practices_bp.route('/settings/practice-days', methods=['POST'])
@admin_required
def update_practice_days():
    """Update the practice_days configuration."""
    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

    practice_days = request.json.get('practice_days')
    if practice_days is None:
        return jsonify({'error': 'practice_days is required'}), 400

    # Validate the structure
    if not isinstance(practice_days, list):
        return jsonify({'error': 'practice_days must be an array'}), 400

    for entry in practice_days:
        if not isinstance(entry, dict):
            return jsonify({'error': 'Each entry must be an object'}), 400
        if 'day' not in entry:
            return jsonify({'error': 'Each entry must have a day field'}), 400
        if entry['day'].lower() not in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            return jsonify({'error': f'Invalid day: {entry["day"]}'}), 400
        defaults = entry.get('defaults')
        if defaults is not None and not isinstance(defaults, dict):
            return jsonify({'error': 'defaults must be an object or null'}), 400

    try:
        AppConfig.set(
            key='practice_days',
            value=practice_days,
            description='Expected practice days and default times for weekly coach summary',
            category='practices'
        )
        db.session.commit()

        return jsonify({
            'success': True,
            'practice_days': practice_days
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
