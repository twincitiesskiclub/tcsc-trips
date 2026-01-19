let eventsTable;
let eventsData = [];

// Format price from cents
function formatPrice(cents) {
    if (!cents) return 'Free';
    return '$' + (cents / 100).toFixed(2);
}

// Status badge HTML
function getStatusBadge(status) {
    const classes = {
        'active': 'admin-badge admin-badge-active',
        'draft': 'admin-badge admin-badge-inactive',
        'closed': 'admin-badge admin-badge-error'
    };
    return `<span class="${classes[status] || 'admin-badge'}">${status}</span>`;
}

document.addEventListener('DOMContentLoaded', async () => {
    // Fetch events data
    const response = await fetch('/admin/social-events/data');
    const data = await response.json();
    eventsData = data.events;

    document.getElementById('event-count').textContent = eventsData.length;

    // Initialize Tabulator
    eventsTable = new Tabulator("#events-table", {
        data: eventsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 320px)",
        placeholder: "No social events found",

        columns: [
            {
                title: "Name",
                field: "name",
                frozen: true,
                minWidth: 180,
                formatter: function(cell) {
                    const id = cell.getRow().getData().id;
                    return `<a href="/admin/social-events/${id}/edit" class="text-tcsc-navy hover:underline font-medium">${cell.getValue()}</a>`;
                }
            },
            {title: "Location", field: "location", minWidth: 150},
            {title: "Date", field: "event_date", minWidth: 130},
            {title: "Time", field: "event_time", minWidth: 90},
            {
                title: "Price",
                field: "price",
                minWidth: 80,
                formatter: function(cell) {
                    return formatPrice(cell.getValue());
                }
            },
            {title: "Capacity", field: "max_participants", minWidth: 80},
            {
                title: "Status",
                field: "status",
                minWidth: 100,
                formatter: function(cell) {
                    return getStatusBadge(cell.getValue());
                }
            },
            {
                title: "Actions",
                frozen: true,
                hozAlign: "right",
                minWidth: 140,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    return `<div class="admin-actions">
                        <a href="/admin/social-events/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteEvent(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                },
                headerSort: false
            }
        ]
    });

    // Search filter
    document.getElementById('events-search').addEventListener('input', function(e) {
        const value = e.target.value.toLowerCase();
        eventsTable.setFilter(function(data) {
            return data.name.toLowerCase().includes(value) ||
                   (data.location && data.location.toLowerCase().includes(value));
        });
        updateCount();
    });

    // Status filter pills
    document.querySelectorAll('.admin-pill[data-status]').forEach(pill => {
        pill.addEventListener('click', function() {
            document.querySelectorAll('.admin-pill[data-status]').forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            const status = this.dataset.status;
            if (status === 'all') {
                eventsTable.clearFilter();
            } else {
                eventsTable.setFilter('status', '=', status);
            }
            updateCount();
        });
    });
});

function updateCount() {
    const count = eventsTable.getDataCount('active');
    document.getElementById('event-count').textContent = count;
}

function confirmDeleteEvent(id, name) {
    if (!confirm(`Delete event "${name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    fetch(`/admin/social-events/${id}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Event deleted', 'success');
            eventsTable.deleteRow(id);
            updateCount();
        } else {
            showToast(data.error || 'Failed to delete event', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
