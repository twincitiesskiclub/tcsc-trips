"""Admin routes for Skipper dashboard and cancellation workflow."""

from flask import Blueprint, render_template, jsonify, request, session
from datetime import datetime
from ..auth import admin_required
from ..models import db, User
from ..practices.models import CancellationRequest, Practice
from ..practices.interfaces import CancellationStatus, PracticeStatus
from ..errors import flash_error, flash_success
from ..agent.decision_engine import evaluate_practice as run_evaluation, load_skipper_config
from ..agent.brain import generate_evaluation_summary
from ..agent.proposals import process_cancellation_decision

admin_skipper_bp = Blueprint('admin_skipper', __name__, url_prefix='/admin/skipper')


@admin_skipper_bp.route('/')
@admin_required
def skipper_dashboard():
    """Render Skipper dashboard."""
    return render_template('admin/skipper.html')


@admin_skipper_bp.route('/data')
@admin_required
def proposals_data():
    """Return cancellation proposals as JSON for grid."""
    proposals = CancellationRequest.query.order_by(
        CancellationRequest.proposed_at.desc()
    ).all()

    proposals_data = []
    for proposal in proposals:
        practice = proposal.practice

        proposals_data.append({
            'id': proposal.id,
            'practice_id': proposal.practice_id,
            'practice_date': practice.date.isoformat(),
            'practice_location': practice.location.name if practice.location else 'No Location',
            'status': proposal.status,
            'reason_type': proposal.reason_type,
            'reason_summary': proposal.reason_summary,
            'proposed_at': proposal.proposed_at.isoformat(),
            'decided_at': proposal.decided_at.isoformat() if proposal.decided_at else None,
            'decided_by': proposal.decided_by_user.full_name if proposal.decided_by_user else None,
            'decision_notes': proposal.decision_notes or '',
            'expires_at': proposal.expires_at.isoformat() if proposal.expires_at else None,
        })

    return jsonify({'proposals': proposals_data})


@admin_skipper_bp.route('/approve/<int:proposal_id>', methods=['POST'])
@admin_required
def approve_proposal(proposal_id):
    """Approve a cancellation proposal."""
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')

        # Get current user from session
        user_email = session.get('user', {}).get('email')
        user_id = None
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                user_id = user.id

        # Use proposals module to process decision
        result = process_cancellation_decision(
            request_id=proposal_id,
            decision='approved',
            decided_by_user_id=user_id,
            notes=notes
        )

        return jsonify({
            'success': True,
            'message': 'Cancellation approved and practice cancelled'
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_skipper_bp.route('/reject/<int:proposal_id>', methods=['POST'])
@admin_required
def reject_proposal(proposal_id):
    """Reject a cancellation proposal."""
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')

        # Get current user from session
        user_email = session.get('user', {}).get('email')
        user_id = None
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                user_id = user.id

        # Use proposals module to process decision
        result = process_cancellation_decision(
            request_id=proposal_id,
            decision='rejected',
            decided_by_user_id=user_id,
            notes=notes
        )

        return jsonify({
            'success': True,
            'message': 'Cancellation rejected - practice will proceed'
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_skipper_bp.route('/evaluate/<int:practice_id>')
@admin_required
def evaluate_practice(practice_id):
    """Manually trigger evaluation for a practice."""
    practice = Practice.query.get_or_404(practice_id)

    try:
        # Run decision engine evaluation
        evaluation = run_evaluation(practice)

        # Generate summary using Claude
        summary = generate_evaluation_summary(evaluation)

        # Serialize evaluation result
        return jsonify({
            'success': True,
            'practice_id': practice_id,
            'is_go': evaluation.is_go,
            'confidence': evaluation.confidence,
            'violations': len(evaluation.violations),
            'critical_violations': len([v for v in evaluation.violations if v.severity == 'critical']),
            'warning_violations': len([v for v in evaluation.violations if v.severity == 'warning']),
            'summary': summary,
            'has_confirmed_lead': evaluation.has_confirmed_lead,
            'has_posted_workout': evaluation.has_posted_workout,
            'weather': {
                'temperature_f': evaluation.weather.temperature_f,
                'feels_like_f': evaluation.weather.feels_like_f,
                'wind_speed_mph': evaluation.weather.wind_speed_mph,
                'precipitation_chance': evaluation.weather.precipitation_chance,
                'conditions_summary': evaluation.weather.conditions_summary,
                'has_lightning_threat': evaluation.weather.has_lightning_threat
            } if evaluation.weather else None,
            'trail_conditions': {
                'location': evaluation.trail_conditions.location,
                'trails_open': evaluation.trail_conditions.trails_open,
                'ski_quality': evaluation.trail_conditions.ski_quality,
                'groomed': evaluation.trail_conditions.groomed,
                'groomed_for': evaluation.trail_conditions.groomed_for
            } if evaluation.trail_conditions else None,
            'violations_detail': [
                {
                    'threshold_name': v.threshold_name,
                    'severity': v.severity,
                    'message': v.message,
                    'threshold_value': v.threshold_value,
                    'actual_value': v.actual_value
                }
                for v in evaluation.violations
            ]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_skipper_bp.route('/config')
@admin_required
def get_config():
    """View current Skipper thresholds and configuration."""
    try:
        # Load actual config from YAML file
        config = load_skipper_config()

        return jsonify({
            'success': True,
            'config': config,
            'message': 'Configuration loaded from config/skipper.yaml'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to load configuration'
        }), 500
