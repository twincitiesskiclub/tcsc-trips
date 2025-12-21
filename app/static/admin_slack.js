/**
 * Slack Sync Admin JavaScript
 * Handles Slack user synchronization and linking UI
 */

let usersTable, slackOnlyTable;
let allUsersData = [];
let slackOnlyData = [];
let currentFilter = 'all';
let linkModalData = {};

// Load data on page load
document.addEventListener('DOMContentLoaded', function() {
    loadStatus();
    loadUsers();
    loadSlackOnly();
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLinkModal();
});

async function loadStatus() {
    try {
        const resp = await fetch('/admin/slack/status');
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();

        if (data.error) {
            throw new Error(data.error);
        }

        document.getElementById('stat-slack-users').textContent = data.total_slack_users;
        document.getElementById('stat-db-users').textContent = data.total_db_users;
        document.getElementById('stat-matched').textContent = data.matched_users;
        document.getElementById('stat-unmatched-slack').textContent = data.unmatched_slack_users;
        document.getElementById('stat-unmatched-db').textContent = data.unmatched_db_users;
    } catch (e) {
        console.error('Failed to load status:', e);
        showToast('Failed to load status', 'error');
    }
}

async function loadUsers() {
    try {
        const resp = await fetch('/admin/slack/users');
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();

        if (data.error) {
            throw new Error(data.error);
        }

        allUsersData = data.users;

        if (usersTable) {
            usersTable.replaceData(getFilteredUsers());
        } else {
            usersTable = new Tabulator("#users-table", {
                data: getFilteredUsers(),
                layout: "fitColumns",
                placeholder: "No users found",
                columns: [
                    {title: "ID", field: "id", width: 60},
                    {title: "Name", field: "full_name", minWidth: 150},
                    {title: "Email", field: "email", minWidth: 200},
                    {title: "Status", field: "status", width: 100, formatter: function(cell) {
                        const status = cell.getValue();
                        const classes = {
                            'ACTIVE': 'status-badge status-active',
                            'PENDING': 'status-badge status-pending',
                            'ALUMNI': 'status-badge status-alumni',
                            'DROPPED': 'status-badge status-canceled'
                        };
                        return `<span class="${classes[status] || 'status-badge'}">${status}</span>`;
                    }},
                    {title: "Slack", field: "slack_matched", width: 100, formatter: function(cell) {
                        const matched = cell.getValue();
                        if (matched) {
                            return '<span class="status-badge status-active">Linked</span>';
                        } else {
                            return '<span class="status-badge status-draft">Not Linked</span>';
                        }
                    }},
                    {title: "Slack UID", field: "slack_uid", width: 120},
                    {title: "Slack Name", field: "slack_display_name", minWidth: 120},
                    {title: "Actions", formatter: function(cell) {
                        const row = cell.getData();
                        if (row.slack_matched) {
                            return `<button class="button button-small button-secondary" onclick="unlinkUser(${row.id})">Unlink</button>`;
                        } else {
                            return `<button class="button button-small" onclick="showLinkDbModal(${row.id})">Link</button>` +
                                   ` <button class="button button-small button-danger" onclick="confirmDeleteUser(${row.id})">Delete</button>`;
                        }
                    }, width: 160, hozAlign: "center", headerSort: false}
                ]
            });
        }
    } catch (e) {
        console.error('Failed to load users:', e);
        showToast('Failed to load users', 'error');
    }
}

async function loadSlackOnly() {
    try {
        const resp = await fetch('/admin/slack/unmatched');
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();

        if (data.error) {
            throw new Error(data.error);
        }

        slackOnlyData = data.unmatched_slack_users;

        if (slackOnlyTable) {
            slackOnlyTable.replaceData(slackOnlyData);
        } else {
            slackOnlyTable = new Tabulator("#slack-only-table", {
                data: slackOnlyData,
                layout: "fitColumns",
                placeholder: "No unmatched Slack users",
                columns: [
                    {title: "Slack UID", field: "slack_uid", width: 120},
                    {title: "Email", field: "email", minWidth: 200},
                    {title: "Display Name", field: "display_name", minWidth: 150},
                    {title: "Full Name", field: "full_name", minWidth: 150},
                    {title: "Actions", formatter: function(cell) {
                        const id = cell.getData().id;
                        return `<button class="button button-small" onclick="showLinkSlackModal(${id})">Link</button>` +
                               ` <button class="button button-small button-secondary" onclick="importSlackUser(${id})">Import</button>`;
                    }, width: 180, hozAlign: "center", headerSort: false}
                ]
            });
        }
    } catch (e) {
        console.error('Failed to load Slack users:', e);
        showToast('Failed to load Slack users', 'error');
    }
}

function getFilteredUsers() {
    if (currentFilter === 'all') {
        return allUsersData;
    } else if (currentFilter === 'matched') {
        return allUsersData.filter(u => u.slack_matched);
    } else {
        return allUsersData.filter(u => !u.slack_matched);
    }
}

function setUserFilter(filter, btn) {
    currentFilter = filter;

    // Update button states
    document.querySelectorAll('.btn-group .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Update table
    if (usersTable) {
        usersTable.replaceData(getFilteredUsers());
    }
}

async function runSync() {
    const btn = document.getElementById('sync-btn');
    const icon = document.getElementById('sync-icon');
    const text = document.getElementById('sync-text');
    const status = document.getElementById('sync-status');

    btn.disabled = true;
    icon.classList.add('spinning');
    text.textContent = 'Syncing...';
    status.textContent = '';

    try {
        const resp = await fetch('/admin/slack/sync', {method: 'POST'});
        if (!resp.ok && resp.status !== 200) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();

        if (data.error) {
            showToast('Sync error: ' + data.error, 'error');
            status.textContent = 'Error: ' + data.error;
        } else {
            showToast(`Sync complete! Created: ${data.slack_users_created}, Updated: ${data.slack_users_updated}, Matched: ${data.users_matched}`, 'success');
            status.textContent = `Created: ${data.slack_users_created}, Updated: ${data.slack_users_updated}, Matched: ${data.users_matched}`;
        }

        // Reload data
        loadStatus();
        loadUsers();
        loadSlackOnly();
    } catch (e) {
        showToast('Sync failed: ' + e.message, 'error');
        status.textContent = 'Sync failed: ' + e.message;
    } finally {
        btn.disabled = false;
        icon.classList.remove('spinning');
        text.textContent = 'Sync from Slack';
    }
}

function showLinkSlackModal(slackUserId) {
    linkModalData = {type: 'slack', slackUserId: slackUserId};

    const slackUser = slackOnlyData.find(u => u.id === slackUserId);
    if (!slackUser) return;

    document.getElementById('link-modal-title').textContent = 'Link Slack User to Database User';
    document.getElementById('link-modal-description').textContent =
        `Link "${slackUser.display_name || slackUser.full_name}" (${slackUser.email}) to a database user:`;

    // Populate select with unmatched DB users
    const unmatchedDbUsers = allUsersData.filter(u => !u.slack_matched);
    const select = document.getElementById('link-select');
    select.innerHTML = '<option value="">Select a user...</option>';
    unmatchedDbUsers.forEach(u => {
        const option = document.createElement('option');
        option.value = u.id;
        option.textContent = `${u.full_name} (${u.email})`;
        select.appendChild(option);
    });

    document.getElementById('link-modal').style.display = 'flex';
}

function showLinkDbModal(userId) {
    linkModalData = {type: 'db', userId: userId};

    const dbUser = allUsersData.find(u => u.id === userId);
    if (!dbUser) return;

    document.getElementById('link-modal-title').textContent = 'Link Database User to Slack User';
    document.getElementById('link-modal-description').textContent =
        `Link "${dbUser.full_name}" (${dbUser.email}) to a Slack user:`;

    // Populate select with unmatched Slack users
    const select = document.getElementById('link-select');
    select.innerHTML = '<option value="">Select a Slack user...</option>';
    slackOnlyData.forEach(u => {
        const option = document.createElement('option');
        option.value = u.id;
        option.textContent = `${u.display_name || u.full_name} (${u.email})`;
        select.appendChild(option);
    });

    document.getElementById('link-modal').style.display = 'flex';
}

function closeLinkModal() {
    document.getElementById('link-modal').style.display = 'none';
    linkModalData = {};
}

async function confirmLink() {
    const select = document.getElementById('link-select');
    const selectedId = parseInt(select.value);

    if (!selectedId) {
        showToast('Please select a user to link', 'error');
        return;
    }

    let userId, slackUserId;
    if (linkModalData.type === 'slack') {
        slackUserId = linkModalData.slackUserId;
        userId = selectedId;
    } else {
        userId = linkModalData.userId;
        slackUserId = selectedId;
    }

    try {
        const resp = await fetch('/admin/slack/link', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId, slack_user_id: slackUserId})
        });

        const data = await resp.json();

        if (!resp.ok || data.error) {
            throw new Error(data.error || `HTTP ${resp.status}`);
        }

        closeLinkModal();
        showToast('Users linked successfully', 'success');
        loadStatus();
        loadUsers();
        loadSlackOnly();
    } catch (e) {
        showToast('Failed to link: ' + e.message, 'error');
    }
}

async function unlinkUser(userId) {
    if (!confirm('Are you sure you want to unlink this user from Slack?')) {
        return;
    }

    try {
        const resp = await fetch('/admin/slack/unlink', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        });

        const data = await resp.json();

        if (!resp.ok || data.error) {
            throw new Error(data.error || `HTTP ${resp.status}`);
        }

        showToast('User unlinked from Slack', 'success');
        loadStatus();
        loadUsers();
        loadSlackOnly();
    } catch (e) {
        showToast('Failed to unlink: ' + e.message, 'error');
    }
}

function confirmDeleteUser(userId) {
    const user = allUsersData.find(u => u.id === userId);
    if (!user) return;

    if (!confirm(`Are you sure you want to delete "${user.full_name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    deleteUser(userId);
}

async function deleteUser(userId) {
    try {
        const resp = await fetch('/admin/slack/delete-user', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        });

        const data = await resp.json();

        if (!resp.ok || data.error) {
            throw new Error(data.error || `HTTP ${resp.status}`);
        }

        showToast(data.message || 'User deleted', 'success');
        loadStatus();
        loadUsers();
        loadSlackOnly();
    } catch (e) {
        showToast('Failed to delete: ' + e.message, 'error');
    }
}

async function importSlackUser(slackUserId) {
    const slackUser = slackOnlyData.find(u => u.id === slackUserId);
    if (!slackUser) return;

    if (!confirm(`Import "${slackUser.display_name || slackUser.full_name}" (${slackUser.email}) as a new user with legacy season membership?`)) {
        return;
    }

    try {
        const resp = await fetch('/admin/slack/import', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({slack_user_id: slackUserId})
        });

        const data = await resp.json();

        if (!resp.ok || data.error) {
            throw new Error(data.error || `HTTP ${resp.status}`);
        }

        showToast(data.message || 'User imported successfully', 'success');
        loadStatus();
        loadUsers();
        loadSlackOnly();
    } catch (e) {
        showToast('Failed to import: ' + e.message, 'error');
    }
}

// Simple toast notification
function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast-notification').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
