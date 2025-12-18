let usersTable;
let usersData = [];
let allSeasons = [];
let currentSeason = null;
let selectedSeasonId = null;
let currentView = 'all';

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

document.addEventListener('DOMContentLoaded', async () => {
    // Fetch user data from API
    const response = await fetch('/admin/users/data');
    const data = await response.json();
    usersData = data.users;
    allSeasons = data.seasons;
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
                return `<button class="button button-small" onclick="openEditModal(${id}); event.stopPropagation();">Edit</button>`;
            }, headerSort: false, width: 60, hozAlign: "center", frozen: true},
            {title: "Name", field: "full_name", frozen: true, minWidth: 150,
             formatter: function(cell) {
                 const id = cell.getRow().getData().id;
                 return `<a href="/admin/users/${id}">${cell.getValue()}</a>`;
             }
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

    // View button handlers
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
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
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
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

function applyFilters() {
    const searchVal = document.getElementById('users-search').value.toLowerCase();
    const statusVal = document.getElementById('status-filter').value;
    const seasonVal = document.getElementById('season-filter').value;

    usersTable.setFilter(function(data) {
        // Global view filter
        if (currentView === 'alumni') {
            if (data.status !== 'ALUMNI' && data.status !== 'DROPPED') {
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

        return matchesSearch && matchesStatus && matchesSeason;
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

    document.getElementById('modal-title').textContent = `Edit: ${user.full_name}`;
    document.getElementById('view-details-link').href = `/admin/users/${userId}`;
    document.getElementById('edit-user-form').action = `/admin/users/${userId}/edit`;

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
    `;

    document.getElementById('edit-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});
