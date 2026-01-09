"""Admin routes for newsletter prompt management.

Provides a web interface for editing newsletter generation prompts
without requiring code changes.
"""

import os
from flask import Blueprint, render_template, request, jsonify, session
from ..auth import admin_required
from ..models import db
from ..newsletter.models import NewsletterPrompt


admin_newsletter_bp = Blueprint(
    'admin_newsletter',
    __name__,
    url_prefix='/admin/newsletter'
)


# Known prompt names and their descriptions
PROMPT_DEFINITIONS = {
    'main': {
        'display_name': 'Main Newsletter',
        'description': 'Primary generation prompt for weekly newsletters with full content.',
        'file': 'newsletter_main.md'
    },
    'quiet': {
        'display_name': 'Quiet Week',
        'description': 'Shorter prompt for weeks with minimal activity.',
        'file': 'newsletter_quiet.md'
    },
    'final': {
        'display_name': 'Final Review',
        'description': 'Prompt for generating the final polished version before publishing.',
        'file': 'newsletter_final.md'
    }
}


def get_file_prompt_content(name: str) -> str | None:
    """Read prompt content from file."""
    prompt_def = PROMPT_DEFINITIONS.get(name)
    if not prompt_def:
        return None

    filepath = os.path.join('config', 'prompts', prompt_def['file'])
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read()
    return None


@admin_newsletter_bp.route('/prompts')
@admin_required
def prompts_page():
    """Render prompt editor page."""
    return render_template('admin/newsletter_prompts.html')


@admin_newsletter_bp.route('/prompts/definitions')
@admin_required
def get_prompt_definitions():
    """Get prompt definitions (names, descriptions, etc.)."""
    return jsonify({'definitions': PROMPT_DEFINITIONS})


@admin_newsletter_bp.route('/prompts/data')
@admin_required
def get_prompts_data():
    """Get all prompts as JSON, including both database and file-based."""
    # Get database prompts
    db_prompts = NewsletterPrompt.query.filter_by(is_active=True).all()
    db_prompt_map = {p.name: p for p in db_prompts}

    # Build combined prompt data
    prompt_data = []
    for name, definition in PROMPT_DEFINITIONS.items():
        db_prompt = db_prompt_map.get(name)
        file_content = get_file_prompt_content(name)

        if db_prompt:
            # Database prompt exists and is active
            prompt_data.append({
                'id': db_prompt.id,
                'name': name,
                'display_name': definition['display_name'],
                'description': definition['description'],
                'content': db_prompt.content,
                'source': 'database',
                'is_active': True,
                'version': db_prompt.version,
                'updated_at': db_prompt.updated_at.isoformat() if db_prompt.updated_at else None,
                'updated_by': db_prompt.updated_by_email,
                'has_file_default': file_content is not None
            })
        elif file_content:
            # Only file-based prompt exists
            prompt_data.append({
                'id': None,
                'name': name,
                'display_name': definition['display_name'],
                'description': definition['description'],
                'content': file_content,
                'source': 'file',
                'is_active': True,
                'version': None,
                'updated_at': None,
                'updated_by': None,
                'has_file_default': True
            })
        else:
            # No prompt exists yet
            prompt_data.append({
                'id': None,
                'name': name,
                'display_name': definition['display_name'],
                'description': definition['description'],
                'content': '',
                'source': 'none',
                'is_active': False,
                'version': None,
                'updated_at': None,
                'updated_by': None,
                'has_file_default': False
            })

    return jsonify({'prompts': prompt_data})


@admin_newsletter_bp.route('/prompts/<name>/file')
@admin_required
def get_file_prompt(name):
    """Get file-based prompt content."""
    content = get_file_prompt_content(name)
    if content is not None:
        return jsonify({'content': content})
    return jsonify({'error': 'File not found'}), 404


@admin_newsletter_bp.route('/prompts/save', methods=['POST'])
@admin_required
def save_prompt():
    """Save prompt to database."""
    data = request.json
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name', '').strip()
    content = data.get('content', '').strip()

    if not name or name not in PROMPT_DEFINITIONS:
        return jsonify({'error': f'Invalid prompt name: {name}'}), 400

    if not content:
        return jsonify({'error': 'Prompt content is required'}), 400

    user_email = session.get('user', {}).get('email')

    # Find existing active prompt or create new
    prompt = NewsletterPrompt.query.filter_by(name=name, is_active=True).first()

    if prompt:
        # Update existing prompt
        prompt.content = content
        prompt.version += 1
        prompt.updated_by_email = user_email
    else:
        # Create new prompt
        prompt = NewsletterPrompt(
            name=name,
            content=content,
            is_active=True,
            version=1,
            created_by_email=user_email,
            updated_by_email=user_email
        )
        db.session.add(prompt)

    db.session.commit()

    return jsonify({
        'success': True,
        'id': prompt.id,
        'version': prompt.version,
        'updated_at': prompt.updated_at.isoformat()
    })


@admin_newsletter_bp.route('/prompts/<int:prompt_id>/reset', methods=['POST'])
@admin_required
def reset_prompt(prompt_id):
    """Deactivate database prompt to fall back to file default."""
    prompt = NewsletterPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({'error': 'Prompt not found'}), 404

    # Check if file default exists
    file_content = get_file_prompt_content(prompt.name)
    if not file_content:
        return jsonify({
            'error': f'No file default exists for "{prompt.name}". Cannot reset.'
        }), 400

    prompt.is_active = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Prompt "{prompt.name}" reset to file default'
    })


@admin_newsletter_bp.route('/prompts/<name>/history')
@admin_required
def get_prompt_history(name):
    """Get version history for a prompt."""
    if name not in PROMPT_DEFINITIONS:
        return jsonify({'error': f'Invalid prompt name: {name}'}), 400

    prompts = NewsletterPrompt.query.filter_by(name=name).order_by(
        NewsletterPrompt.version.desc()
    ).all()

    history = [{
        'id': p.id,
        'version': p.version,
        'is_active': p.is_active,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
        'created_by': p.created_by_email,
        'updated_by': p.updated_by_email
    } for p in prompts]

    return jsonify({'history': history})
