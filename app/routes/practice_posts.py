from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, g
from ..auth import admin_required
import requests
import os
from datetime import datetime

practice_posts_bp = Blueprint('practice_posts', __name__)

# Import the cache from admin routes
from .admin import practice_post_cache

# API endpoint to receive practice post from announcer service (webhook)
@practice_posts_bp.route('/api/practice-post', methods=['POST'])
def receive_practice_post():
    """
    Webhook endpoint for announcer service to notify us of new announcements.
    Expected payload (based on announcer API spec):
    {
        "id": "uuid-string",
        "date": "2025-07-25",
        "content": "Announcement content...",
        "slack_message_ts": "1234567890.123456",
        "slack_channel": "C1234567890",
        "created_at": "2025-07-25T10:00:00",
        "posted_at": "2025-07-25T10:05:00",
        "secret": "shared_secret"
    }
    """
    # Verify the request is from our announcer service
    secret = request.json.get('secret')
    expected_secret = os.getenv('ANNOUNCER_WEBHOOK_SECRET')
    
    if not expected_secret or secret != expected_secret:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    post_date = data.get('date')
    announcement_id = data.get('id')
    
    if not post_date or not announcement_id:
        return jsonify({'error': 'Missing required fields (date, id)'}), 400
    
    # Cache the announcement data
    practice_post_cache[post_date] = {
        'id': announcement_id,
        'date': post_date,
        'slack_message_ts': data.get('slack_message_ts'),
        'slack_channel': data.get('slack_channel'),
        'content': data.get('content'),
        'original_content': data.get('content'),  # Keep original for comparison
        'created_at': data.get('created_at'),
        'posted_at': data.get('posted_at'),
        'received_at': datetime.utcnow()
    }
    
    return jsonify({'status': 'success', 'message': 'Announcement received'}), 200

# Admin interface to edit practice posts
@practice_posts_bp.route('/admin/practice-posts/edit')
@admin_required
def edit_practice_post():
    """Edit today's practice post."""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Check cache first
    post_data = practice_post_cache.get(today)
    
    if not post_data:
        # Try to fetch from announcer service if not in cache
        announcer_url = os.getenv('ANNOUNCER_SERVICE_URL')
        api_key = os.getenv('ANNOUNCER_API_KEY')
        
        if not announcer_url or not api_key:
            flash('Announcer service not configured.', 'error')
            return redirect(url_for('admin.get_admin_page'))
        
        try:
            response = requests.get(
                f"{announcer_url}/api/announcements/today",
                headers={'X-API-Key': api_key},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                post_data = {
                    'id': data.get('id'),
                    'date': data.get('date'),
                    'slack_message_ts': data.get('slack_message_ts'),
                    'slack_channel': data.get('slack_channel'),
                    'content': data.get('content'),
                    'original_content': data.get('content'),
                    'created_at': data.get('created_at'),
                    'posted_at': data.get('posted_at')
                }
                practice_post_cache[today] = post_data
            elif response.status_code == 404:
                flash('No practice post found for today.', 'info')
                return redirect(url_for('admin.get_admin_page'))
            else:
                flash(f'Error fetching practice post: {response.status_code}', 'error')
                return redirect(url_for('admin.get_admin_page'))
        except requests.RequestException as e:
            flash(f'Error connecting to announcer service: {str(e)}', 'error')
            return redirect(url_for('admin.get_admin_page'))
    
    return render_template('admin/practice_post_edit.html', post=post_data)

@practice_posts_bp.route('/admin/practice-posts/edit', methods=['POST'])
@admin_required
def save_practice_post():
    """Save edited practice post and send update to announcer service."""
    today = datetime.now().strftime('%Y-%m-%d')
    content = request.form.get('content')
    
    if not content:
        flash('Content cannot be empty.', 'error')
        return redirect(url_for('practice_posts.edit_practice_post'))
    
    # Get the cached post data
    post_data = practice_post_cache.get(today)
    if not post_data:
        flash('Practice post data not found. Please try again.', 'error')
        return redirect(url_for('practice_posts.edit_practice_post'))
    
    # Update the announcer service
    announcer_url = os.getenv('ANNOUNCER_SERVICE_URL')
    api_key = os.getenv('ANNOUNCER_API_KEY')
    
    if not announcer_url or not api_key:
        flash('Announcer service not configured.', 'error')
        return redirect(url_for('practice_posts.edit_practice_post'))
    
    try:
        announcement_id = post_data.get('id')
        if not announcement_id:
            flash('Missing announcement ID. Cannot update.', 'error')
            return redirect(url_for('practice_posts.edit_practice_post'))
        
        response = requests.post(
            f"{announcer_url}/api/announcements/{announcement_id}/update",
            json={
                'content': content,
                'updated_by': g.user.email,
                'slack_channel': post_data.get('slack_channel'),
                'slack_message_ts': post_data.get('slack_message_ts')
            },
            headers={'X-API-Key': api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            # Update cache
            post_data['content'] = content
            flash('Practice post updated successfully!', 'success')
        else:
            flash(f'Error updating practice post: {response.text}', 'error')
            
    except requests.RequestException as e:
        flash(f'Error communicating with announcer service: {str(e)}', 'error')
    
    return redirect(url_for('practice_posts.edit_practice_post'))