"""Admin routes for Practice Management CRUD."""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from datetime import datetime
from ..auth import admin_required
from ..models import db, User, Tag
from ..practices.models import (
    Practice, PracticeLocation, PracticeActivity, PracticeType,
    PracticeLead, SocialLocation, practice_activities_junction,
    practice_types_junction
)
from ..practices.interfaces import PracticeStatus, LeadRole, RSVPStatus, CancellationStatus
from ..errors import flash_error, flash_success

admin_practices_bp = Blueprint('admin_practices', __name__, url_prefix='/admin/practices')


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
    """Return all practices as JSON for Tabulator grid."""
    practices = Practice.query.order_by(Practice.date.desc()).all()

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
            'id': lead.user_id,
            'name': lead.display_name,
            'confirmed': lead.confirmed
        } for lead in practice.leads if lead.role == 'lead']

        # Build coaches list (role='coach')
        coaches = [{
            'id': lead.user_id,
            'name': lead.display_name,
            'confirmed': lead.confirmed
        } for lead in practice.leads if lead.role == 'coach']

        practices_data.append({
            'id': practice.id,
            'date': practice.date.isoformat(),
            'day_of_week': practice.day_of_week,
            'location_name': location_name,
            'location_id': practice.location_id,
            'activities': activities,
            'practice_types': practice_types,
            'status': practice.status,
            'has_social': practice.has_social,
            'is_dark_practice': practice.is_dark_practice,
            'leads': leads,
            'coaches': coaches,
            'cancellation_reason': practice.cancellation_reason or '',
            'warmup_description': practice.warmup_description or '',
            'workout_description': practice.workout_description or '',
            'cooldown_description': practice.cooldown_description or '',
        })

    return jsonify({'practices': practices_data})


@admin_practices_bp.route('/<int:practice_id>')
@admin_required
def practice_detail(practice_id):
    """Display single practice detail."""
    practice = Practice.query.get_or_404(practice_id)
    return render_template('admin/practices/detail.html', practice=practice)


@admin_practices_bp.route('/create', methods=['POST'])
@admin_required
def create_practice():
    """Create a new practice."""
    try:
        data = request.get_json()

        # Parse date
        date = datetime.fromisoformat(data['date'])

        # Create practice
        practice = Practice(
            date=date,
            day_of_week=date.strftime('%A'),
            location_id=data['location_id'],
            status=PracticeStatus.SCHEDULED.value,
            warmup_description=data.get('warmup_description'),
            workout_description=data.get('workout_description'),
            cooldown_description=data.get('cooldown_description'),
            has_social=data.get('has_social', False),
            is_dark_practice=data.get('is_dark_practice', False),
        )
        db.session.add(practice)
        db.session.flush()

        # Add activities (many-to-many)
        if data.get('activity_ids'):
            activities = PracticeActivity.query.filter(
                PracticeActivity.id.in_(data['activity_ids'])
            ).all()
            practice.activities.extend(activities)

        # Add practice types (many-to-many)
        if data.get('type_ids'):
            types = PracticeType.query.filter(
                PracticeType.id.in_(data['type_ids'])
            ).all()
            practice.practice_types.extend(types)

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

    try:
        data = request.get_json()

        # Update fields if provided
        if 'date' in data:
            date = datetime.fromisoformat(data['date'])
            practice.date = date
            practice.day_of_week = date.strftime('%A')

        if 'location_id' in data:
            practice.location_id = data['location_id']

        if 'warmup_description' in data:
            practice.warmup_description = data['warmup_description']

        if 'workout_description' in data:
            practice.workout_description = data['workout_description']

        if 'cooldown_description' in data:
            practice.cooldown_description = data['cooldown_description']

        if 'has_social' in data:
            practice.has_social = data['has_social']

        if 'is_dark_practice' in data:
            practice.is_dark_practice = data['is_dark_practice']

        if 'status' in data:
            practice.status = data['status']

        # Update activities if provided
        if 'activity_ids' in data:
            practice.activities = []
            if data['activity_ids']:
                activities = PracticeActivity.query.filter(
                    PracticeActivity.id.in_(data['activity_ids'])
                ).all()
                practice.activities = activities

        # Update types if provided
        if 'type_ids' in data:
            practice.practice_types = []
            if data['type_ids']:
                types = PracticeType.query.filter(
                    PracticeType.id.in_(data['type_ids'])
                ).all()
                practice.practice_types = types

        # Update coaches and leads if provided (now using user_id)
        if 'coach_ids' in data or 'lead_ids' in data:
            # Remove existing leads/coaches
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

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Practice updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_practices_bp.route('/<int:practice_id>/delete', methods=['POST'])
@admin_required
def delete_practice(practice_id):
    """Delete a practice."""
    practice = Practice.query.get_or_404(practice_id)

    try:
        db.session.delete(practice)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Practice deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_practices_bp.route('/<int:practice_id>/cancel', methods=['POST'])
@admin_required
def cancel_practice(practice_id):
    """Cancel a practice with a reason."""
    practice = Practice.query.get_or_404(practice_id)

    try:
        data = request.get_json()

        practice.status = PracticeStatus.CANCELLED.value
        practice.cancellation_reason = data.get('reason', 'Cancelled by admin')

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Practice cancelled successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


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
            'social_location_id': loc.social_location_id,
            'social_location_name': loc.social_location.name if loc.social_location else None,
            'practice_count': len(loc.practices)
        } for loc in locations]
    })


@admin_practices_bp.route('/types/data')
@admin_required
def types_data():
    """Return all practice types as JSON with practice counts."""
    types = PracticeType.query.order_by(PracticeType.name).all()

    return jsonify({
        'types': [{
            'id': t.id,
            'name': t.name,
            'fitness_goals': t.fitness_goals or [],
            'has_intervals': t.has_intervals,
            'practice_count': len(t.practices)
        } for t in types]
    })


@admin_practices_bp.route('/activities/data')
@admin_required
def activities_data():
    """Return all practice activities as JSON with practice counts."""
    activities = PracticeActivity.query.order_by(PracticeActivity.name).all()

    return jsonify({
        'activities': [{
            'id': a.id,
            'name': a.name,
            'gear_required': a.gear_required or [],
            'practice_count': len(a.practices)
        } for a in activities]
    })


@admin_practices_bp.route('/people/data')
@admin_required
def people_data():
    """Return coaches and leads from Users with appropriate tags."""
    # Get coach tags (HEAD_COACH, ASSISTANT_COACH)
    coach_tags = Tag.query.filter(Tag.name.in_(['HEAD_COACH', 'ASSISTANT_COACH'])).all()
    coach_tag_ids = [t.id for t in coach_tags]

    # Get lead tag (PRACTICE_LEAD)
    lead_tags = Tag.query.filter(Tag.name.in_(['PRACTICE_LEAD'])).all()
    lead_tag_ids = [t.id for t in lead_tags]

    # Query users with coach tags
    coaches = User.query.filter(
        User.tags.any(Tag.id.in_(coach_tag_ids))
    ).order_by(User.first_name).all()

    # Query users with lead tags
    leads = User.query.filter(
        User.tags.any(Tag.id.in_(lead_tag_ids))
    ).order_by(User.first_name).all()

    return jsonify({
        'coaches': [{
            'id': u.id,
            'name': f"{u.first_name} {u.last_name}",
        } for u in coaches],
        'leads': [{
            'id': u.id,
            'name': f"{u.first_name} {u.last_name}",
        } for u in leads]
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
            'practice_location_count': len(loc.practice_locations)
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
            'practice_location_count': 0
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
        location.address = request.json['address'].strip() or None
    if 'google_maps_url' in request.json:
        location.google_maps_url = request.json['google_maps_url'].strip() or None

    db.session.commit()

    return jsonify({
        'success': True,
        'social_location': {
            'id': location.id,
            'name': location.name,
            'address': location.address,
            'google_maps_url': location.google_maps_url,
            'practice_location_count': len(location.practice_locations)
        }
    })


@admin_practices_bp.route('/social-locations/<int:loc_id>/delete', methods=['POST'])
@admin_required
def delete_social_location(loc_id):
    """Delete a social location (only if no practice locations reference it)."""
    location = SocialLocation.query.get_or_404(loc_id)

    if location.practice_locations:
        return jsonify({
            'error': f'Cannot delete "{location.name}" - {len(location.practice_locations)} practice location(s) reference it'
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
        parking_notes=request.json.get('parking_notes', '').strip() or None,
        social_location_id=request.json.get('social_location_id')
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
            'social_location_id': location.social_location_id,
            'social_location_name': location.social_location.name if location.social_location else None,
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
        location.spot = request.json['spot'].strip() or None
    if 'address' in request.json:
        location.address = request.json['address'].strip() or None
    if 'google_maps_url' in request.json:
        location.google_maps_url = request.json['google_maps_url'].strip() or None
    if 'latitude' in request.json:
        location.latitude = request.json['latitude']
    if 'longitude' in request.json:
        location.longitude = request.json['longitude']
    if 'parking_notes' in request.json:
        location.parking_notes = request.json['parking_notes'].strip() or None
    if 'social_location_id' in request.json:
        location.social_location_id = request.json['social_location_id']

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
            'social_location_id': location.social_location_id,
            'social_location_name': location.social_location.name if location.social_location else None,
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

    # Handle gear_required - can be string (comma-separated) or array
    gear_required = request.json.get('gear_required')
    if isinstance(gear_required, str):
        gear_required = [s.strip() for s in gear_required.split(',') if s.strip()]
    elif not isinstance(gear_required, list):
        gear_required = None

    activity = PracticeActivity(
        name=name,
        gear_required=gear_required or None
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({
        'success': True,
        'activity': {
            'id': activity.id,
            'name': activity.name,
            'gear_required': activity.gear_required or [],
            'practice_count': 0
        }
    })


@admin_practices_bp.route('/activities/<int:activity_id>/edit', methods=['POST'])
@admin_required
def edit_activity(activity_id):
    """Update a practice activity."""
    activity = PracticeActivity.query.get_or_404(activity_id)

    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

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

    db.session.commit()

    return jsonify({
        'success': True,
        'activity': {
            'id': activity.id,
            'name': activity.name,
            'gear_required': activity.gear_required or [],
            'practice_count': len(activity.practices)
        }
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

    # Handle fitness_goals - can be string (comma-separated) or array
    fitness_goals = request.json.get('fitness_goals')
    if isinstance(fitness_goals, str):
        fitness_goals = [s.strip() for s in fitness_goals.split(',') if s.strip()]
    elif not isinstance(fitness_goals, list):
        fitness_goals = None

    practice_type = PracticeType(
        name=name,
        fitness_goals=fitness_goals or None,
        has_intervals=request.json.get('has_intervals', False)
    )
    db.session.add(practice_type)
    db.session.commit()

    return jsonify({
        'success': True,
        'type': {
            'id': practice_type.id,
            'name': practice_type.name,
            'fitness_goals': practice_type.fitness_goals or [],
            'has_intervals': practice_type.has_intervals,
            'practice_count': 0
        }
    })


@admin_practices_bp.route('/types/<int:type_id>/edit', methods=['POST'])
@admin_required
def edit_type(type_id):
    """Update a practice type."""
    practice_type = PracticeType.query.get_or_404(type_id)

    if not request.json:
        return jsonify({'error': 'JSON body required'}), 400

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

    db.session.commit()

    return jsonify({
        'success': True,
        'type': {
            'id': practice_type.id,
            'name': practice_type.name,
            'fitness_goals': practice_type.fitness_goals or [],
            'has_intervals': practice_type.has_intervals,
            'practice_count': len(practice_type.practices)
        }
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
