let tripsTable;
let tripsData = [];

// Format price from cents
function formatPrice(cents) {
    if (!cents) return '-';
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
    // Fetch trips data
    const response = await fetch('/admin/trips/data');
    const data = await response.json();
    tripsData = data.trips;

    document.getElementById('trip-count').textContent = tripsData.length;

    // Initialize Tabulator
    tripsTable = new Tabulator("#trips-table", {
        data: tripsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 320px)",
        placeholder: "No trips found",

        columns: [
            {
                title: "Name",
                field: "name",
                frozen: true,
                minWidth: 180,
                formatter: function(cell) {
                    const id = cell.getRow().getData().id;
                    return `<a href="/admin/trips/${id}/edit" class="text-tcsc-navy hover:underline font-medium">${cell.getValue()}</a>`;
                }
            },
            {title: "Destination", field: "destination", minWidth: 150},
            {title: "Dates", field: "date_range", minWidth: 150},
            {
                title: "Capacity",
                minWidth: 100,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    return `${data.capacity_standard}/${data.capacity_extra}`;
                }
            },
            {
                title: "Price",
                minWidth: 120,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (data.price_low === data.price_high) {
                        return formatPrice(data.price_low);
                    }
                    return `${formatPrice(data.price_low)} - ${formatPrice(data.price_high)}`;
                }
            },
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
                        <a href="/admin/trips/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteTrip(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                },
                headerSort: false
            }
        ]
    });

    // Search filter
    document.getElementById('trips-search').addEventListener('input', function(e) {
        const value = e.target.value.toLowerCase();
        tripsTable.setFilter(function(data) {
            return data.name.toLowerCase().includes(value) ||
                   data.destination.toLowerCase().includes(value);
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
                tripsTable.clearFilter();
            } else {
                tripsTable.setFilter('status', '=', status);
            }
            updateCount();
        });
    });
});

function updateCount() {
    const count = tripsTable.getDataCount('active');
    document.getElementById('trip-count').textContent = count;
}

function confirmDeleteTrip(id, name) {
    if (!confirm(`Delete trip "${name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    fetch(`/admin/trips/${id}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Trip deleted', 'success');
            tripsTable.deleteRow(id);
            updateCount();
        } else {
            showToast(data.error || 'Failed to delete trip', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
