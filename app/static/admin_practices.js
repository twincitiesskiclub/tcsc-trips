let practicesTable;
let practicesData = [];
let locationsData = [];
let currentCancelPracticeId = null;

// Load data on page load
document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([
        loadPractices(),
        loadLocations()
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
                    btns += '<button class="tbl-btn tbl-btn-primary" onclick="window.location.href=\'/admin/practices/' + id + '\'">Edit</button>';
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
    document.getElementById('create-practice-btn').addEventListener('click', () => { window.location.href = '/admin/practices/new'; });
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
        closeCancelModal();
    }
});
