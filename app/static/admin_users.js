let usersTable;
let usersData = [];
let allSeasons = [];
let allTags = [];
let currentSeason = null;
let selectedSeasonId = null;
let currentView = 'all';
let currentEditUserId = null;

// Default values for tags without metadata
const DEFAULT_EMOJI = '🏷️';
const DEFAULT_GRADIENT = 'linear-gradient(135deg, #868e96 0%, #adb5bd 100%)';

// Helper to get emoji from tag name (looks up in allTags)
function getTagEmoji(tagName) {
    const tag = allTags.find(t => t.name === tagName);
    return tag?.emoji || DEFAULT_EMOJI;
}

// Helper function to generate status badge HTML
function getStatusBadge(status) {
    const classes = {
        'ACTIVE': 'status-badge status-active',
        'PENDING': 'status-badge status-pending',
        'ALUMNI': 'status-badge status-alumni',
        'DROPPED': 'status-badge status-canceled'
    };
    const labels = {
        'ACTIVE': 'Active',
        'PENDING': 'Pending',
        'ALUMNI': 'Alumni',
        'DROPPED': 'Dropped'
    };
    return `<span class="${classes[status] || 'status-badge'}">${labels[status] || status}</span>`;
}

// Helper function to render tag emojis for table cells
function getTagEmojis(tags) {
    if (!tags || tags.length === 0) {
        return '<span class="tag-empty">—</span>';
    }
    return tags.map(tag => {
        const emoji = tag.emoji || DEFAULT_EMOJI;
        const gradient = tag.gradient || DEFAULT_GRADIENT;
        return `<span class="tag-emoji" data-tooltip="${tag.display_name}" data-gradient="${gradient}">${emoji}</span>`;
    }).join('');
}

// Helper function to render full tag badges (for modals)
function getTagBadges(tags) {
    if (!tags || tags.length === 0) {
        return '<span class="tag-empty">—</span>';
    }
    return tags.map(tag => {
        const gradient = tag.gradient || DEFAULT_GRADIENT;
        return `<span class="tag-badge" style="background: ${gradient};" title="${tag.display_name}">${tag.display_name}</span>`;
    }).join(' ');
}

document.addEventListener('DOMContentLoaded', async () => {
    // Fetch user data from API
    const response = await fetch('/admin/users/data');
    const data = await response.json();
    usersData = data.users;
    allSeasons = data.seasons;
    allTags = data.tags || [];
    currentSeason = data.current_season;

    // Initialize Tabulator
    usersTable = new Tabulator("#users-table", {
        data: usersData,
        layout: "fitDataStretch",
        height: "calc(100vh - 320px)",
        responsiveLayout: false,
        movableColumns: true,
        resizableColumns: true,

        columns: [
            // Frozen columns on left (always visible)
            {title: "", formatter: function(cell) {
                const id = cell.getRow().getData().id;
                return `<button class="tbl-btn tbl-btn-primary" onclick="openEditModal(${id}); event.stopPropagation();">Edit</button>`;
            }, headerSort: false, width: 60, hozAlign: "center", frozen: true},
            {title: "Name", field: "full_name", frozen: true, minWidth: 150,
             formatter: function(cell) {
                 const id = cell.getRow().getData().id;
                 return `<a href="/admin/users/${id}">${cell.getValue()}</a>`;
             }
            },
            {title: "Roles", field: "tags", minWidth: 80, frozen: true,
             formatter: function(cell) {
                 const tags = cell.getValue();
                 return `<div class="tags-cell-compact">${getTagEmojis(tags)}</div>`;
             },
             headerSort: false
            },

            // Scrollable columns
            {title: "Email", field: "email", minWidth: 200},
            {title: "Status", field: "status", minWidth: 100,
             formatter: function(cell) {
                 const status = cell.getValue();
                 const classes = {
                     'ACTIVE': 'status-badge status-active',
                     'PENDING': 'status-badge status-pending',
                     'ALUMNI': 'status-badge status-alumni',
                     'DROPPED': 'status-badge status-canceled'
                 };
                 const labels = {
                     'ACTIVE': 'Active',
                     'PENDING': 'Pending',
                     'ALUMNI': 'Alumni',
                     'DROPPED': 'Dropped'
                 };
                 return `<span class="${classes[status] || 'status-badge'}">${labels[status] || status}</span>`;
             }
            },
            {title: "Season", field: "season_status", minWidth: 130,
             formatter: function(cell) {
                 const status = cell.getValue();
                 if (status === 'ACTIVE') return '<span class="status-badge status-active">Active</span>';
                 if (status === 'PENDING_LOTTERY') return '<span class="status-badge status-pending">Pending Lottery</span>';
                 if (status === 'DROPPED_LOTTERY') return '<span class="status-badge status-info">Dropped (Lottery)</span>';
                 if (status === 'DROPPED_VOLUNTARY') return '<span class="status-badge status-draft">Dropped (Voluntary)</span>';
                 if (status === 'DROPPED_CAUSE') return '<span class="status-badge status-canceled">Dropped (Cause)</span>';
                 return '<span class="status-badge status-draft">Not Registered</span>';
             }
            },
            {title: "Type", field: "is_returning", minWidth: 90,
             formatter: cell => cell.getValue() ? "Returning" : "New"
            },
            {title: "Trips", field: "trip_count", minWidth: 60, hozAlign: "center"},
            {title: "Total Paid", field: "total_paid", minWidth: 100,
             formatter: "money", formatterParams: {symbol: "$", precision: 2}
            },
            {title: "Phone", field: "phone", minWidth: 120},
            {title: "Slack UID", field: "slack_uid", minWidth: 110},
            {title: "Address", field: "address", minWidth: 200},
            {title: "Pronouns", field: "pronouns", minWidth: 100},
            {title: "DOB", field: "date_of_birth", minWidth: 110},
            {title: "Technique", field: "preferred_technique", minWidth: 100},
            {title: "T-Shirt", field: "tshirt_size", minWidth: 80},
            {title: "Experience", field: "ski_experience", minWidth: 90},
            {title: "Emergency Name", field: "emergency_contact_name", minWidth: 150},
            {title: "Emergency Phone", field: "emergency_contact_phone", minWidth: 130},
            {title: "Emergency Email", field: "emergency_contact_email", minWidth: 180},
            {title: "Emergency Relation", field: "emergency_contact_relation", minWidth: 120},
        ],

        initialSort: [{column: "full_name", dir: "asc"}],

        dataFiltered: function(filters, rows) {
            updateMemberCount(rows.length);
        }
    });

    updateMemberCount(usersData.length);

    // Populate role filter grid
    const roleGrid = document.getElementById('role-filter-grid');
    if (roleGrid && allTags.length > 0) {
        let html = '';
        allTags.forEach(tag => {
            const emoji = tag.emoji || DEFAULT_EMOJI;
            html += `
                <label class="role-toggle" data-tooltip="${tag.display_name}" data-role="${tag.name}">
                    ${emoji}
                </label>`;
        });
        roleGrid.innerHTML = html;

        // Add click handlers
        roleGrid.querySelectorAll('.role-toggle').forEach(toggle => {
            toggle.addEventListener('click', () => {
                toggle.classList.toggle('selected');
                applyFilters();
                updateRoleFilterLabel();
            });
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('role-filter-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            document.getElementById('role-filter-menu').classList.remove('show');
        }
    });

    // View button handlers
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('global-season-select').value = '';
            currentView = btn.dataset.view;
            selectedSeasonId = null;
            applyGlobalView();
        });
    });

    // Season dropdown handler
    document.getElementById('global-season-select').addEventListener('change', (e) => {
        const seasonId = e.target.value;
        if (seasonId) {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            selectedSeasonId = parseInt(seasonId);
            currentView = 'season';
            applyGlobalView();
        }
    });

    // Search filter
    document.getElementById('users-search').addEventListener('input', () => applyFilters());

    // CSV Export
    document.getElementById('export-csv').addEventListener('click', () => {
        usersTable.download("csv", "tcsc_members.csv");
    });

    // Status filter
    document.getElementById('status-filter').addEventListener('change', () => applyFilters());

    // Season status filter
    document.getElementById('season-filter').addEventListener('change', () => applyFilters());
});

function applyGlobalView() {
    // Update season_status for each user based on selected season
    let seasonIdToUse = selectedSeasonId;
    let title = 'All Members';

    if (currentView === 'current' && currentSeason) {
        seasonIdToUse = currentSeason.id;
        title = `${currentSeason.name} Members`;
    } else if (currentView === 'season' && selectedSeasonId) {
        const season = allSeasons.find(s => s.id === selectedSeasonId);
        title = `${season ? season.name : 'Season'} Members`;
    } else if (currentView === 'alumni') {
        title = 'Alumni Members';
    } else {
        title = 'All Members';
    }

    document.getElementById('view-title').textContent = title;

    // Update the season_status field for each user based on selected season
    usersData.forEach(user => {
        if (seasonIdToUse && user.seasons) {
            user.season_status = user.seasons[seasonIdToUse] || '';
        } else if (currentSeason && user.seasons) {
            user.season_status = user.seasons[currentSeason.id] || '';
        }
    });

    // Refresh table data
    usersTable.replaceData(usersData);

    // Apply filters
    applyFilters();
}

function getSelectedRoles() {
    const selected = document.querySelectorAll('#role-filter-grid .role-toggle.selected');
    return Array.from(selected).map(el => el.dataset.role);
}

function toggleRoleDropdown() {
    document.getElementById('role-filter-menu').classList.toggle('show');
}

function updateRoleFilterLabel() {
    const selected = getSelectedRoles();
    const label = document.getElementById('role-filter-label');
    const btn = document.getElementById('role-filter-btn');

    if (selected.length === 0) {
        label.innerHTML = 'Roles';
        btn.classList.remove('has-selection');
    } else {
        // Show emojis of selected roles (up to 4)
        const emojis = selected.slice(0, 4).map(name => getTagEmoji(name)).join('');
        const extra = selected.length > 4 ? `<span class="role-filter-count">+${selected.length - 4}</span>` : '';
        label.innerHTML = emojis + extra;
        btn.classList.add('has-selection');
    }
}

function clearAllRoles() {
    document.querySelectorAll('#role-filter-grid .role-toggle').forEach(toggle => {
        toggle.classList.remove('selected');
    });
    applyFilters();
    updateRoleFilterLabel();
}

function applyFilters() {
    const searchVal = document.getElementById('users-search').value.toLowerCase();
    const statusVal = document.getElementById('status-filter').value;
    const selectedRoles = getSelectedRoles();
    const seasonVal = document.getElementById('season-filter').value;

    usersTable.setFilter(function(data) {
        // Global view filter
        if (currentView === 'alumni') {
            if (data.status !== 'ALUMNI') {
                return false;
            }
        } else if (currentView === 'current' && currentSeason) {
            // Only show members registered for current season
            if (!data.seasons || !data.seasons[currentSeason.id]) {
                return false;
            }
        } else if (currentView === 'season' && selectedSeasonId) {
            // Only show members registered for selected season
            if (!data.seasons || !data.seasons[selectedSeasonId]) {
                return false;
            }
        }

        // Text search
        const matchesSearch = !searchVal ||
            data.full_name.toLowerCase().includes(searchVal) ||
            data.email.toLowerCase().includes(searchVal) ||
            (data.phone && data.phone.includes(searchVal)) ||
            (data.slack_uid && data.slack_uid.toLowerCase().includes(searchVal));

        // Status filter
        const matchesStatus = !statusVal || data.status === statusVal;

        // Role filter (user must have at least one of the selected roles)
        let matchesRole = true;
        if (selectedRoles.length > 0) {
            const userTagNames = (data.tags || []).map(t => t.name);
            matchesRole = selectedRoles.some(role => userTagNames.includes(role));
        }

        // Season status filter (within selected view)
        let matchesSeason = true;
        if (seasonVal) {
            if (seasonVal === 'registered') {
                matchesSeason = !!data.season_status;
            } else if (seasonVal === 'not_registered') {
                matchesSeason = !data.season_status;
            } else {
                matchesSeason = data.season_status === seasonVal;
            }
        }

        return matchesSearch && matchesStatus && matchesRole && matchesSeason;
    });

    // Update member count after filtering
    setTimeout(() => {
        const rowCount = usersTable.getDataCount("active");
        updateMemberCount(rowCount);
    }, 50);
}

function updateMemberCount(count) {
    document.getElementById('member-count').textContent = `${count} member${count !== 1 ? 's' : ''}`;
}

function openEditModal(userId) {
    const user = usersData.find(u => u.id === userId);
    if (!user) return;

    currentEditUserId = userId;
    document.getElementById('modal-title').textContent = `Edit: ${user.full_name}`;
    document.getElementById('view-details-link').href = `/admin/users/${userId}`;
    document.getElementById('edit-user-form').action = `/admin/users/${userId}/edit`;

    // Build tag checkboxes HTML
    const userTagIds = new Set((user.tags || []).map(t => t.id));
    let tagsHtml = '<div class="edit-modal-tags">';
    for (const tag of allTags) {
        const checked = userTagIds.has(tag.id) ? 'checked' : '';
        const gradient = tag.gradient || DEFAULT_GRADIENT;
        tagsHtml += `
            <label class="tag-checkbox-inline">
                <input type="checkbox" name="tag_ids" value="${tag.id}" ${checked}>
                <span class="tag-badge-small" style="background: ${gradient};">${tag.display_name}</span>
            </label>`;
    }
    tagsHtml += '</div>';

    // Build form fields (status is read-only, derived from season registration)
    const statusBadge = getStatusBadge(user.status);
    document.getElementById('modal-form-fields').innerHTML = `
        <div class="form-group">
            <label>Email</label>
            <input type="email" name="email" value="${user.email || ''}" required>
        </div>
        <div class="form-group">
            <label>Status</label>
            <div style="padding: 8px 0; display: flex; align-items: center; gap: 12px;">
                ${statusBadge}
                <span style="font-size: 12px; color: #667085; font-style: italic;">Derived from season registration</span>
            </div>
        </div>
        <div class="form-group">
            <label>Phone</label>
            <input type="tel" name="phone" value="${user.phone || ''}" placeholder="Optional">
        </div>
        <div class="form-group">
            <label>Roles</label>
            ${tagsHtml}
        </div>
    `;

    document.getElementById('edit-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('edit-modal').style.display = 'none';
    currentEditUserId = null;
}

// Handle edit form submission - save tags via AJAX first
document.addEventListener('DOMContentLoaded', () => {
    const editForm = document.getElementById('edit-user-form');
    if (editForm) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (!currentEditUserId) {
                editForm.submit();
                return;
            }

            // Collect checked tag IDs
            const checkboxes = editForm.querySelectorAll('input[name="tag_ids"]:checked');
            const tagIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

            try {
                // Save tags via AJAX
                const response = await fetch(`/admin/users/${currentEditUserId}/tags`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tag_ids: tagIds })
                });

                const result = await response.json();

                if (result.success) {
                    // Update local data
                    const user = usersData.find(u => u.id === currentEditUserId);
                    if (user) {
                        user.tags = result.tags;
                    }
                }
            } catch (error) {
                console.error('Error saving tags:', error);
            }

            // Now submit the form normally for email/phone updates
            // Remove tag checkboxes before submitting to avoid confusion
            checkboxes.forEach(cb => cb.disabled = true);
            editForm.submit();
        });
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeTagModal();
    }
});

// =============================================================================
// Tag Management
// =============================================================================

let currentTagUserId = null;

function openTagModal(userId) {
    const user = usersData.find(u => u.id === userId);
    if (!user) return;

    currentTagUserId = userId;
    document.getElementById('tag-modal-title').textContent = `Tags: ${user.full_name}`;

    // Build checkbox list for all tags
    const userTagIds = new Set((user.tags || []).map(t => t.id));
    const tagsContainer = document.getElementById('tag-checkboxes');

    // Group tags by category
    const categories = {
        'Leadership': ['PRESIDENT', 'VICE_PRESIDENT', 'TREASURER', 'SECRETARY', 'AUDITOR', 'BOARD_MEMBER', 'FRIEND_OF_BOARD'],
        'Coaching': ['HEAD_COACH', 'ASSISTANT_COACH', 'PRACTICES_DIRECTOR', 'PRACTICES_LEAD', 'WAX_MANAGER'],
        'Activities': ['TRIP_LEAD', 'ADVENTURES', 'SOCIAL', 'SOCIAL_COMMITTEE', 'MARKETING', 'APPAREL']
    };

    let html = '';
    for (const [category, tagNames] of Object.entries(categories)) {
        const categoryTags = allTags.filter(t => tagNames.includes(t.name));
        if (categoryTags.length === 0) continue;

        html += `<div class="tag-category">
            <div class="tag-category-label">${category}</div>
            <div class="tag-category-items">`;

        for (const tag of categoryTags) {
            const checked = userTagIds.has(tag.id) ? 'checked' : '';
            const gradient = tag.gradient || DEFAULT_GRADIENT;
            html += `
                <label class="tag-checkbox-item">
                    <input type="checkbox" value="${tag.id}" ${checked}>
                    <span class="tag-badge-small" style="background: ${gradient};">${tag.display_name}</span>
                </label>`;
        }

        html += '</div></div>';
    }

    // Handle any tags not in categories
    const categorizedNames = Object.values(categories).flat();
    const otherTags = allTags.filter(t => !categorizedNames.includes(t.name));
    if (otherTags.length > 0) {
        html += `<div class="tag-category">
            <div class="tag-category-label">Other</div>
            <div class="tag-category-items">`;
        for (const tag of otherTags) {
            const checked = userTagIds.has(tag.id) ? 'checked' : '';
            const gradient = tag.gradient || DEFAULT_GRADIENT;
            html += `
                <label class="tag-checkbox-item">
                    <input type="checkbox" value="${tag.id}" ${checked}>
                    <span class="tag-badge-small" style="background: ${gradient};">${tag.display_name}</span>
                </label>`;
        }
        html += '</div></div>';
    }

    tagsContainer.innerHTML = html;
    document.getElementById('tag-modal').style.display = 'flex';
}

function closeTagModal() {
    document.getElementById('tag-modal').style.display = 'none';
    currentTagUserId = null;
}

async function saveUserTags() {
    if (!currentTagUserId) return;

    // Collect checked tag IDs
    const checkboxes = document.querySelectorAll('#tag-checkboxes input[type="checkbox"]:checked');
    const tagIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    try {
        const response = await fetch(`/admin/users/${currentTagUserId}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag_ids: tagIds })
        });

        const result = await response.json();

        if (result.success) {
            // Update local data
            const user = usersData.find(u => u.id === currentTagUserId);
            if (user) {
                user.tags = result.tags;
            }

            // Refresh the table to show updated tags
            usersTable.replaceData(usersData);
            applyFilters();

            closeTagModal();
            showToast('Tags updated successfully', 'success');
        } else {
            showToast(result.error || 'Failed to update tags', 'error');
        }
    } catch (error) {
        console.error('Error saving tags:', error);
        showToast('Failed to save tags', 'error');
    }
}

