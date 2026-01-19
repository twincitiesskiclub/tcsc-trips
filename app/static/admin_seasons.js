let seasonsTable;
let seasonsData = [];

function formatPrice(cents) {
    if (!cents) return '-';
    return '$' + (cents / 100).toFixed(2);
}

document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch('/admin/seasons/data');
    const data = await response.json();
    seasonsData = data.seasons;

    document.getElementById('season-count').textContent = seasonsData.length;

    seasonsTable = new Tabulator("#seasons-table", {
        data: seasonsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 280px)",
        placeholder: "No seasons found",

        columns: [
            {
                title: "Name",
                field: "name",
                frozen: true,
                minWidth: 150,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    const badge = data.is_current ? ' <span class="admin-badge admin-badge-active">Current</span>' : '';
                    return `<span class="font-medium">${cell.getValue()}</span>${badge}`;
                }
            },
            {title: "Type", field: "season_type", minWidth: 80},
            {title: "Year", field: "year", minWidth: 60},
            {
                title: "Dates",
                minWidth: 180,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (!data.start_date) return '-';
                    return `${data.start_date} to ${data.end_date}`;
                }
            },
            {
                title: "Returning Reg",
                minWidth: 150,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (!data.returning_start) return '-';
                    return `${data.returning_start}<br>to ${data.returning_end}`;
                }
            },
            {
                title: "New Reg",
                minWidth: 150,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    if (!data.new_start) return '-';
                    return `${data.new_start}<br>to ${data.new_end}`;
                }
            },
            {
                title: "Price",
                field: "price_cents",
                minWidth: 80,
                formatter: function(cell) {
                    return formatPrice(cell.getValue());
                }
            },
            {title: "Limit", field: "registration_limit", minWidth: 60},
            {
                title: "Actions",
                frozen: true,
                hozAlign: "right",
                minWidth: 260,
                formatter: function(cell) {
                    const data = cell.getRow().getData();
                    let html = `<div class="admin-actions">
                        <a href="/admin/seasons/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <a href="/admin/seasons/${data.id}/export" class="admin-btn admin-btn-sm admin-btn-secondary">Export</a>`;

                    if (!data.is_current) {
                        html += `<button class="admin-btn admin-btn-sm admin-btn-success" onclick="activateSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Activate</button>`;
                    }

                    html += `<button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                    return html;
                },
                headerSort: false
            }
        ]
    });
});

function activateSeason(id, name) {
    if (!confirm(`Activate season "${name}"?\n\nThis will:\n- Set this as the current season\n- Update all user statuses based on their registration\n- Recalculate seasons_since_active counters\n\nContinue?`)) {
        return;
    }

    fetch(`/admin/seasons/${id}/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Season activated', 'success');
            location.reload();
        } else {
            showToast(data.error || 'Failed to activate season', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}

function confirmDeleteSeason(id, name) {
    if (!confirm(`Delete season "${name}"?\n\nThis cannot be undone.`)) {
        return;
    }

    fetch(`/admin/seasons/${id}/delete-json`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Season deleted', 'success');
            seasonsTable.deleteRow(id);
            document.getElementById('season-count').textContent = seasonsTable.getDataCount();
        } else {
            showToast(data.error || 'Failed to delete season', 'error');
        }
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
