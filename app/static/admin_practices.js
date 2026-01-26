let practicesTable;
let practicesData = [];
let locationsData = [];
let socialLocationsData = [];  // Post-practice social venues
let activitiesData = [];
let typesData = [];
let coachesData = [];  // Users with HEAD_COACH or ASSISTANT_COACH tags
let leadsData = [];    // Users with PRACTICES_LEAD tag
let assistsData = [];  // Combined pool of coaches and leads who can assist
let currentEditPracticeId = null;
let currentCancelPracticeId = null;

// Load data on page load
document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([
        loadPractices(),
        loadLocations(),
        loadSocialLocations(),
        loadActivities(),
        loadTypes(),
        loadPeople()
    ]);

    initTable();
    populateLocationFilter();
    attachEventListeners();
});

async function loadPractices() {
    try {
        const response = await fetch('/admin/practices/data');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        practicesData = data.practices || [];
    } catch (error) {
        console.error('Error loading practices:', error);
        showToast('Failed to load practices', 'error');
    }
}

async function loadLocations() {
    try {
        const response = await fetch('/admin/practices/locations/data');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        locationsData = data.locations;
    } catch (error) {
        console.error('Error loading locations:', error);
        showToast('Failed to load locations', 'error');
    }
}

async function loadSocialLocations() {
    try {
        const response = await fetch('/admin/practices/social-locations/data');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        socialLocationsData = data.social_locations;
    } catch (error) {
        console.error('Error loading social locations:', error);
        showToast('Failed to load social locations', 'error');
    }
}

async function loadActivities() {
    try {
        const response = await fetch('/admin/practices/activities/data');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        activitiesData = data.activities;
    } catch (error) {
        console.error('Error loading activities:', error);
        showToast('Failed to load activities', 'error');
    }
}

async function loadTypes() {
    try {
        const response = await fetch('/admin/practices/types/data');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        typesData = data.types;
    } catch (error) {
        console.error('Error loading types:', error);
        showToast('Failed to load practice types', 'error');
    }
}

async function loadPeople() {
    try {
        const response = await fetch('/admin/practices/people/data');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        coachesData = data.coaches || [];
        leadsData = data.leads || [];
        assistsData = data.assists || [];
    } catch (error) {
        console.error('Error loading people:', error);
        showToast('Failed to load coaches/leads', 'error');
    }
}

function initTable() {
    practicesTable = new Tabulator("#practices-table", {
        data: practicesData,
        layout: "fitDataStretch",
        height: "calc(100vh - 300px)",
        responsiveLayout: false,
        movableColumns: true,
        resizableColumns: true,
        renderVerticalBuffer: 500,
        placeholder: "No practices found",

        columns: [
            {title: "Date", field: "date", minWidth: 150,
             formatter: function(cell) {
                 const val = cell.getValue();
                 if (!val) return '—';
                 const date = new Date(val);
                 if (isNaN(date.getTime())) return '—';
                 return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
             },
             sorter: function(a, b) {
                 return new Date(a) - new Date(b);
             }
            },
            {title: "Day", field: "day_of_week", minWidth: 70,
             formatter: function(cell) { return cell.getValue() || '—'; }
            },
            {title: "Location", field: "location_name", minWidth: 140,
             formatter: function(cell) { return cell.getValue() || 'No Location'; }
            },
            {title: "Activities", field: "activities", minWidth: 120,
             formatter: function(cell) {
                 const activities = cell.getValue();
                 return (activities && activities.length > 0) ? activities.join(', ') : '—';
             }
            },
            {title: "Type", field: "practice_types", minWidth: 100,
             formatter: function(cell) {
                 const types = cell.getValue();
                 return (types && types.length > 0) ? types.join(', ') : '—';
             }
            },
            {title: "Status", field: "status", minWidth: 90,
             formatter: function(cell) {
                 const status = cell.getValue() || 'scheduled';
                 const classes = {
                     'scheduled': 'status-scheduled',
                     'confirmed': 'status-confirmed',
                     'in_progress': 'status-in-progress',
                     'cancelled': 'status-cancelled',
                     'completed': 'status-completed'
                 };
                 return `<span class="status-badge ${classes[status] || ''}">${status}</span>`;
             }
            },
            {title: "Leads", field: "leads", minWidth: 100,
             formatter: function(cell) {
                 const leads = cell.getValue();
                 if (!leads || !Array.isArray(leads) || leads.length === 0) return '—';
                 return leads.map(l => (l.name || 'Unknown') + (l.confirmed ? ' ✓' : '')).join(', ');
             }
            },
            {title: "Coaches", field: "coaches", minWidth: 100,
             formatter: function(cell) {
                 const coaches = cell.getValue();
                 if (!coaches || !Array.isArray(coaches) || coaches.length === 0) return '—';
                 return coaches.map(c => (c.name || 'Unknown') + (c.confirmed ? ' ✓' : '')).join(', ');
             }
            },
            {title: "Assists", field: "assists", minWidth: 100,
             formatter: function(cell) {
                 const assists = cell.getValue();
                 if (!assists || !Array.isArray(assists) || assists.length === 0) return '—';
                 return assists.map(a => (a.name || 'Unknown') + (a.confirmed ? ' ✓' : '')).join(', ');
             }
            },
            {title: "🍺", field: "has_social", width: 40,
             formatter: function(cell) { return cell.getValue() ? '✓' : ''; },
             hozAlign: "center",
             tooltip: "Post-practice social"
            },
            {title: "🔦", field: "is_dark_practice", width: 40,
             formatter: function(cell) { return cell.getValue() ? '✓' : ''; },
             hozAlign: "center",
             tooltip: "Dark practice"
            },
            {
                title: "Actions",
                width: 200,
                minWidth: 200,
                hozAlign: "center",
                vertAlign: "middle",
                headerSort: false,
                frozen: true,
                formatter: function(cell) {
                    const row = cell.getRow();
                    const data = row.getData();
                    const id = data.id;
                    const status = data.status;

                    let btns = '<div class="tbl-actions">';
                    btns += '<button class="tbl-btn tbl-btn-primary" onclick="openEditModal(' + id + ')">Edit</button>';
                    if (status !== 'cancelled') {
                        btns += '<button class="tbl-btn tbl-btn-secondary" onclick="openCancelModal(' + id + ')">Cancel</button>';
                    }
                    btns += '<button class="tbl-btn tbl-btn-danger" onclick="deletePractice(' + id + ')">Delete</button>';
                    btns += '</div>';
                    return btns;
                }
            }
        ],

        initialSort: [{column: "date", dir: "desc"}]
    });

    // Force redraw after table is built to fix rendering issue
    practicesTable.on("tableBuilt", function() {
        setTimeout(() => {
            practicesTable.redraw(true);
        }, 100);
    });
}

function populateLocationFilter() {
    const select = document.getElementById('location-filter');
    for (const loc of locationsData) {
        const option = document.createElement('option');
        option.value = loc.id;
        // Show "Name - Spot" if spot exists
        option.textContent = loc.spot ? `${loc.name} — ${loc.spot}` : loc.name;
        select.appendChild(option);
    }
}

function attachEventListeners() {
    document.getElementById('practices-search').addEventListener('input', applyFilters);
    document.getElementById('status-filter').addEventListener('change', applyFilters);
    document.getElementById('location-filter').addEventListener('change', applyFilters);
    document.getElementById('create-practice-btn').addEventListener('click', openCreateModal);
}

function applyFilters() {
    const searchVal = document.getElementById('practices-search').value.toLowerCase();
    const statusVal = document.getElementById('status-filter').value;
    const locationVal = document.getElementById('location-filter').value;

    practicesTable.setFilter(function(data) {
        const locationName = data.location_name || '';
        const activities = data.activities || [];
        const practiceTypes = data.practice_types || [];

        const matchesSearch = !searchVal ||
            locationName.toLowerCase().includes(searchVal) ||
            activities.some(a => a.toLowerCase().includes(searchVal)) ||
            practiceTypes.some(t => t.toLowerCase().includes(searchVal));

        const matchesStatus = !statusVal || data.status === statusVal;
        const matchesLocation = !locationVal || data.location_id == locationVal;

        return matchesSearch && matchesStatus && matchesLocation;
    });
}

function openCreateModal() {
    currentEditPracticeId = null;
    document.getElementById('modal-title').textContent = 'Create New Practice';

    // Reset form
    document.getElementById('edit-date').value = '';
    document.getElementById('edit-warmup').value = '';
    document.getElementById('edit-workout').value = '';
    document.getElementById('edit-cooldown').value = '';
    document.getElementById('edit-social-location').value = '';
    document.getElementById('edit-is-dark').checked = false;

    populateEditForm();
    document.getElementById('edit-modal').style.display = 'flex';
}

function openEditModal(practiceId) {
    const practice = practicesData.find(p => p.id === practiceId);
    if (!practice) return;

    currentEditPracticeId = practiceId;
    document.getElementById('modal-title').textContent = 'Edit Practice';

    // Populate form
    const date = new Date(practice.date);
    const localDate = new Date(date.getTime() - (date.getTimezoneOffset() * 60000))
        .toISOString().slice(0, 16);
    document.getElementById('edit-date').value = localDate;
    document.getElementById('edit-warmup').value = practice.warmup_description || '';
    document.getElementById('edit-workout').value = practice.workout_description || '';
    document.getElementById('edit-cooldown').value = practice.cooldown_description || '';
    document.getElementById('edit-is-dark').checked = practice.is_dark_practice;

    populateEditForm(practice);
    document.getElementById('edit-modal').style.display = 'flex';
}

function populateEditForm(practice = null) {
    // Populate location dropdown with spot (sub-location) info
    const locationSelect = document.getElementById('edit-location');
    locationSelect.innerHTML = '<option value="">Select Location</option>';
    for (const loc of locationsData) {
        const option = document.createElement('option');
        option.value = loc.id;
        // Show "Name - Spot" if spot exists, otherwise just name
        option.textContent = loc.spot ? `${loc.name} — ${loc.spot}` : loc.name;
        if (practice && practice.location_id === loc.id) {
            option.selected = true;
        }
        locationSelect.appendChild(option);
    }

    // Populate social location dropdown
    const socialLocationSelect = document.getElementById('edit-social-location');
    socialLocationSelect.innerHTML = '<option value="">No Social</option>';
    for (const sl of socialLocationsData) {
        const option = document.createElement('option');
        option.value = sl.id;
        option.textContent = sl.name;
        if (practice && practice.social_location_id === sl.id) {
            option.selected = true;
        }
        socialLocationSelect.appendChild(option);
    }

    // Populate activities as clickable pills
    const activitiesContainer = document.getElementById('edit-activities');
    activitiesContainer.innerHTML = '';
    const practiceActivities = (practice && practice.activities) || [];
    for (const activity of activitiesData) {
        const isSelected = practiceActivities.includes(activity.name);
        const label = document.createElement('label');
        label.className = isSelected ? 'selected' : '';
        label.dataset.value = activity.id;
        label.textContent = activity.name;
        label.onclick = () => label.classList.toggle('selected');
        activitiesContainer.appendChild(label);
    }
    if (activitiesData.length === 0) {
        activitiesContainer.innerHTML = '<span style="color: #9ca3af; font-size: 13px;">No activities defined</span>';
    }

    // Populate types as clickable pills
    const typesContainer = document.getElementById('edit-types');
    typesContainer.innerHTML = '';
    const practiceTypes = (practice && practice.practice_types) || [];
    for (const type of typesData) {
        const isSelected = practiceTypes.includes(type.name);
        const label = document.createElement('label');
        label.className = isSelected ? 'selected' : '';
        label.dataset.value = type.id;
        label.textContent = type.name;
        label.onclick = () => label.classList.toggle('selected');
        typesContainer.appendChild(label);
    }
    if (typesData.length === 0) {
        typesContainer.innerHTML = '<span style="color: #9ca3af; font-size: 13px;">No types defined</span>';
    }

    // Populate coaches as person pills
    renderPersonPills('edit-coaches', 'coaches-summary', coachesData,
        (practice && practice.coaches || []).map(c => c.user_id));

    // Populate leads as person pills
    renderPersonPills('edit-leads', 'leads-summary', leadsData,
        (practice && practice.leads || []).map(l => l.user_id));

    // Populate assists as person pills (collapsible)
    const assistSelectedIds = (practice && practice.assists || []).map(a => a.user_id);
    renderPersonPills('edit-assists', 'assists-summary', assistsData, assistSelectedIds);

    // Auto-expand assists if any are pre-selected, otherwise collapse
    const assistsCollapsible = document.getElementById('assists-collapsible');
    const assistsChevron = document.getElementById('assists-chevron');
    const assistsToggleText = document.getElementById('assists-toggle-text');
    if (assistSelectedIds.length > 0) {
        assistsCollapsible.classList.remove('hidden');
        assistsChevron.classList.add('expanded');
        assistsToggleText.textContent = 'Hide';
    } else {
        assistsCollapsible.classList.add('hidden');
        assistsChevron.classList.remove('expanded');
        assistsToggleText.textContent = 'Show';
    }

    // Reset search input
    const searchInput = document.getElementById('people-search');
    if (searchInput) {
        searchInput.value = '';
        searchInput.oninput = filterPeopleBySearch;
    }
}

function createPersonPill(person, isSelected, containerId, summaryId) {
    const label = document.createElement('label');
    label.className = 'person-pill' + (isSelected ? ' selected' : '');
    label.dataset.value = person.id;
    label.dataset.name = person.name.toLowerCase();

    // Checkmark circle
    const check = document.createElement('span');
    check.className = 'check-icon';
    check.innerHTML = '<svg viewBox="0 0 10 10" fill="none"><path d="M2 5.5L4 7.5L8 3" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    label.appendChild(check);

    // Name
    const nameSpan = document.createElement('span');
    nameSpan.textContent = person.name;
    label.appendChild(nameSpan);

    // Role emoji from tags
    const roleEmoji = getPersonRoleEmoji(person);
    if (roleEmoji) {
        const emojiSpan = document.createElement('span');
        emojiSpan.className = 'role-emoji';
        emojiSpan.textContent = roleEmoji;
        label.appendChild(emojiSpan);
    }

    label.onclick = () => {
        label.classList.toggle('selected');
        updateSelectedSummary(containerId, summaryId);
    };

    return label;
}

function getPersonRoleEmoji(person) {
    if (!person.tags || person.tags.length === 0) return null;
    // Prefer practice-relevant tags
    const preferred = ['HEAD_COACH', 'ASSISTANT_COACH', 'PRACTICES_LEAD', 'PRACTICES_DIRECTOR'];
    for (const tagName of preferred) {
        const tag = person.tags.find(t => t.name === tagName);
        if (tag && tag.emoji) return tag.emoji;
    }
    // Fall back to first tag with emoji
    const withEmoji = person.tags.find(t => t.emoji);
    return withEmoji ? withEmoji.emoji : null;
}

function renderPersonPills(containerId, summaryId, data, selectedIds) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    for (const person of data) {
        const isSelected = selectedIds.includes(person.id);
        container.appendChild(createPersonPill(person, isSelected, containerId, summaryId));
    }
    if (data.length === 0) {
        container.innerHTML = '<span style="color: #9ca3af; font-size: 13px;">No people available</span>';
    }
    updateSelectedSummary(containerId, summaryId);
}

function updateSelectedSummary(containerId, summaryId) {
    const summary = document.getElementById(summaryId);
    if (!summary) return;
    const container = document.getElementById(containerId);
    const selected = container.querySelectorAll('label.selected');

    summary.innerHTML = '';
    if (selected.length === 0) {
        const none = document.createElement('span');
        none.className = 'none-text';
        none.textContent = 'None selected';
        summary.appendChild(none);
        return;
    }

    selected.forEach(label => {
        const chip = document.createElement('span');
        chip.className = 'selected-chip';
        const nameText = label.querySelector('span:nth-child(2)').textContent;
        chip.textContent = nameText;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '&times;';
        removeBtn.onclick = (e) => {
            e.stopPropagation();
            label.classList.remove('selected');
            updateSelectedSummary(containerId, summaryId);
        };
        chip.appendChild(removeBtn);
        summary.appendChild(chip);
    });
}

function deselectPerson(containerId, summaryId, userId) {
    const container = document.getElementById(containerId);
    const label = container.querySelector(`label[data-value="${userId}"]`);
    if (label) {
        label.classList.remove('selected');
        updateSelectedSummary(containerId, summaryId);
    }
}

function filterPeopleBySearch() {
    const query = document.getElementById('people-search').value.toLowerCase().trim();
    const sections = ['edit-coaches', 'edit-leads', 'edit-assists'];
    for (const sectionId of sections) {
        const container = document.getElementById(sectionId);
        if (!container) continue;
        const pills = container.querySelectorAll('.person-pill');
        pills.forEach(pill => {
            const name = pill.dataset.name || '';
            if (!query || name.includes(query)) {
                pill.classList.remove('hidden');
            } else {
                pill.classList.add('hidden');
            }
        });
    }
}

function toggleAssistsSection() {
    const collapsible = document.getElementById('assists-collapsible');
    const chevron = document.getElementById('assists-chevron');
    const toggleText = document.getElementById('assists-toggle-text');
    const isHidden = collapsible.classList.contains('hidden');
    if (isHidden) {
        collapsible.classList.remove('hidden');
        chevron.classList.add('expanded');
        toggleText.textContent = 'Hide';
    } else {
        collapsible.classList.add('hidden');
        chevron.classList.remove('expanded');
        toggleText.textContent = 'Show';
    }
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
    currentEditPracticeId = null;
}

async function savePractice() {
    const date = document.getElementById('edit-date').value;
    const locationId = parseInt(document.getElementById('edit-location').value);
    const socialLocationValue = document.getElementById('edit-social-location').value;
    const socialLocationId = socialLocationValue ? parseInt(socialLocationValue) : null;
    const warmup = document.getElementById('edit-warmup').value;
    const workout = document.getElementById('edit-workout').value;
    const cooldown = document.getElementById('edit-cooldown').value;
    const isDark = document.getElementById('edit-is-dark').checked;

    // Collect selected activities (from pill selections)
    const selectedActivities = document.querySelectorAll('#edit-activities label.selected');
    const activityIds = Array.from(selectedActivities).map(label => parseInt(label.dataset.value));

    // Collect selected types (from pill selections)
    const selectedTypes = document.querySelectorAll('#edit-types label.selected');
    const typeIds = Array.from(selectedTypes).map(label => parseInt(label.dataset.value));

    // Collect selected coaches (from pill selections)
    const selectedCoaches = document.querySelectorAll('#edit-coaches label.selected');
    const coachIds = Array.from(selectedCoaches).map(label => parseInt(label.dataset.value));

    // Collect selected leads (from pill selections)
    const selectedLeads = document.querySelectorAll('#edit-leads label.selected');
    const leadIds = Array.from(selectedLeads).map(label => parseInt(label.dataset.value));

    // Collect selected assists (from pill selections)
    const selectedAssists = document.querySelectorAll('#edit-assists label.selected');
    const assistIds = Array.from(selectedAssists).map(label => parseInt(label.dataset.value));

    if (!date || isNaN(locationId) || !locationId) {
        showToast('Date and Location are required', 'error');
        return;
    }

    const payload = {
        date,
        location_id: locationId,
        social_location_id: socialLocationId,
        activity_ids: activityIds,
        type_ids: typeIds,
        coach_ids: coachIds,
        lead_ids: leadIds,
        assist_ids: assistIds,
        warmup_description: warmup,
        workout_description: workout,
        cooldown_description: cooldown,
        is_dark_practice: isDark,
    };

    try {
        const url = currentEditPracticeId
            ? `/admin/practices/${currentEditPracticeId}/edit`
            : '/admin/practices/create';

        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (result.success) {
            showToast(result.message, 'success');
            closeEditModal();
            await loadPractices();
            practicesTable.setData(practicesData);
        } else {
            showToast(result.error || 'Failed to save practice', 'error');
        }
    } catch (error) {
        console.error('Error saving practice:', error);
        showToast('Failed to save practice', 'error');
    }
}

function openCancelModal(practiceId) {
    currentCancelPracticeId = practiceId;
    document.getElementById('cancel-reason').value = '';
    document.getElementById('cancel-modal').style.display = 'flex';
}

function closeCancelModal() {
    document.getElementById('cancel-modal').style.display = 'none';
    currentCancelPracticeId = null;
}

async function confirmCancel() {
    const reason = document.getElementById('cancel-reason').value.trim();

    if (!reason) {
        showToast('Please provide a cancellation reason', 'error');
        return;
    }

    try {
        const response = await fetch(`/admin/practices/${currentCancelPracticeId}/cancel`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({reason})
        });

        const result = await response.json();

        if (result.success) {
            showToast(result.message, 'success');
            closeCancelModal();
            await loadPractices();
            practicesTable.setData(practicesData);
        } else {
            showToast(result.error || 'Failed to cancel practice', 'error');
        }
    } catch (error) {
        console.error('Error cancelling practice:', error);
        showToast('Failed to cancel practice', 'error');
    }
}

async function deletePractice(practiceId) {
    if (!confirm('Are you sure you want to delete this practice? This cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/admin/practices/${practiceId}/delete`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showToast(result.message, 'success');
            await loadPractices();
            practicesTable.setData(practicesData);
        } else {
            showToast(result.error || 'Failed to delete practice', 'error');
        }
    } catch (error) {
        console.error('Error deleting practice:', error);
        showToast('Failed to delete practice', 'error');
    }
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeEditModal();
        closeCancelModal();
    }
});
