let paymentsTable;
let paymentsData = [];
let pendingBulkAction = null;
let selectedPaymentIds = [];

document.addEventListener('DOMContentLoaded', async () => {
    // Fetch payment data from API
    const response = await fetch('/admin/payments/data');
    const data = await response.json();
    paymentsData = data.payments;

    // Initialize Tabulator
    paymentsTable = new Tabulator("#payments-table", {
        data: paymentsData,
        layout: "fitDataStretch",
        height: "calc(100vh - 320px)",
        responsiveLayout: false,
        movableColumns: true,
        resizableColumns: true,
        selectable: true,

        columns: [
            {formatter: "rowSelection", titleFormatter: "rowSelection", hozAlign: "center", headerSort: false, width: 40},
            {title: "Name", field: "name", minWidth: 150, frozen: true},
            {title: "Email", field: "email", minWidth: 200},
            {title: "Type", field: "payment_type", minWidth: 80,
                formatter: function(cell) {
                    const type = cell.getValue();
                    return `<span class="type-badge type-${type}">${type ? type.charAt(0).toUpperCase() + type.slice(1) : ''}</span>`;
                }
            },
            {title: "For", field: "for_name", minWidth: 120},
            {title: "Amount", field: "amount", minWidth: 100,
                formatter: "money", formatterParams: {symbol: "$", precision: 2}
            },
            {title: "Status", field: "display_status", minWidth: 100,
                formatter: function(cell) {
                    const status = cell.getValue();
                    const classes = {
                        'success': 'status-badge status-success',
                        'pending': 'status-badge status-pending',
                        'processing': 'status-badge status-pending',
                        'canceled': 'status-badge status-canceled',
                        'refunded': 'status-badge status-refunded',
                        'unknown': 'status-badge status-draft'
                    };
                    const labels = {
                        'success': 'Success',
                        'pending': 'Pending',
                        'processing': 'Processing',
                        'canceled': 'Canceled',
                        'refunded': 'Refunded',
                        'unknown': 'Unknown'
                    };
                    return `<span class="${classes[status] || 'status-badge'}">${labels[status] || status}</span>`;
                }
            },
            {title: "Created", field: "created_at", minWidth: 140},
            {title: "Actions", formatter: function(cell) {
                const data = cell.getRow().getData();
                const status = data.status;
                const acceptDisabled = status !== 'requires_capture' ? 'disabled' : '';
                const refundDisabled = !['requires_capture', 'succeeded'].includes(status) ? 'disabled' : '';
                return `<div class="action-buttons">
                    <button class="button button-small button-success" onclick="capturePayment(${data.id}); event.stopPropagation();" ${acceptDisabled}>Accept</button>
                    <button class="button button-small button-danger" onclick="refundPayment(${data.id}); event.stopPropagation();" ${refundDisabled}>Refund</button>
                </div>`;
            }, headerSort: false, width: 180, hozAlign: "center", frozen: true}
        ],

        initialSort: [{column: "created_at", dir: "desc"}],

        rowSelectionChanged: function(data, rows) {
            updateBulkButtons();
        },

        dataFiltered: function(filters, rows) {
            updatePaymentCount(rows.length);
        }
    });

    updatePaymentCount(paymentsData.length);

    // Search filter
    document.getElementById('payments-search').addEventListener('input', () => applyFilters());

    // Type filter
    document.getElementById('type-filter').addEventListener('change', () => applyFilters());

    // Status filter
    document.getElementById('status-filter').addEventListener('change', () => applyFilters());

    // CSV Export
    document.getElementById('export-csv').addEventListener('click', () => {
        paymentsTable.download("csv", "tcsc_payments.csv");
    });

    // Bulk action buttons
    document.getElementById('bulk-accept').addEventListener('click', () => showBulkConfirmation('accept'));
    document.getElementById('bulk-refund').addEventListener('click', () => showBulkConfirmation('refund'));

    // Modal close handlers
    document.querySelector('.modal-close').addEventListener('click', closeModal);
    document.querySelector('.modal-overlay').addEventListener('click', closeModal);
    document.getElementById('cancel-action').addEventListener('click', closeModal);
    document.getElementById('confirm-action').addEventListener('click', executeBulkAction);
});

function applyFilters() {
    const searchVal = document.getElementById('payments-search').value.toLowerCase();
    const typeVal = document.getElementById('type-filter').value;
    const statusVal = document.getElementById('status-filter').value;

    paymentsTable.setFilter(function(data) {
        // Text search
        const matchesSearch = !searchVal ||
            data.name.toLowerCase().includes(searchVal) ||
            data.email.toLowerCase().includes(searchVal);

        // Type filter
        const matchesType = !typeVal || data.payment_type === typeVal;

        // Status filter
        const matchesStatus = !statusVal || data.display_status === statusVal;

        return matchesSearch && matchesType && matchesStatus;
    });

    // Update count after filtering
    setTimeout(() => {
        const rowCount = paymentsTable.getDataCount("active");
        updatePaymentCount(rowCount);
    }, 50);
}

function updatePaymentCount(count) {
    document.getElementById('payment-count').textContent = `${count} payment${count !== 1 ? 's' : ''}`;
}

function updateBulkButtons() {
    const selectedRows = paymentsTable.getSelectedRows();
    const selectedData = selectedRows.map(row => row.getData());

    // Check if any selected payments can be accepted (status = requires_capture)
    const canAccept = selectedData.some(p => p.status === 'requires_capture');
    // Check if any selected payments can be refunded (status = requires_capture or succeeded)
    const canRefund = selectedData.some(p => ['requires_capture', 'succeeded'].includes(p.status));

    document.getElementById('bulk-accept').disabled = !canAccept || selectedData.length === 0;
    document.getElementById('bulk-refund').disabled = !canRefund || selectedData.length === 0;
}

function showBulkConfirmation(action) {
    const selectedRows = paymentsTable.getSelectedRows();
    const selectedData = selectedRows.map(row => row.getData());

    if (selectedData.length === 0) return;

    // Filter to only actionable payments
    let actionablePayments;
    if (action === 'accept') {
        actionablePayments = selectedData.filter(p => p.status === 'requires_capture');
    } else {
        actionablePayments = selectedData.filter(p => ['requires_capture', 'succeeded'].includes(p.status));
    }

    if (actionablePayments.length === 0) {
        alert(`No selected payments can be ${action === 'accept' ? 'accepted' : 'refunded'}.`);
        return;
    }

    pendingBulkAction = action;
    selectedPaymentIds = actionablePayments.map(p => p.id);

    // Calculate total amount
    const totalAmount = actionablePayments.reduce((sum, p) => sum + p.amount, 0);

    // Build modal content
    const actionText = action === 'accept' ? 'Accept' : 'Refund';
    const actionClass = action === 'accept' ? 'button-success' : 'button-danger';

    document.getElementById('modal-title').textContent = `${actionText} ${actionablePayments.length} Payment${actionablePayments.length > 1 ? 's' : ''}`;
    document.getElementById('confirm-action').textContent = `${actionText} All`;
    document.getElementById('confirm-action').className = `button ${actionClass}`;

    let bodyHtml = `<p>You are about to <strong>${action}</strong> the following payments:</p>`;
    bodyHtml += `<div class="bulk-summary">`;
    bodyHtml += `<div class="summary-stat"><span class="stat-value">${actionablePayments.length}</span><span class="stat-label">Payments</span></div>`;
    bodyHtml += `<div class="summary-stat"><span class="stat-value">$${totalAmount.toFixed(2)}</span><span class="stat-label">Total Amount</span></div>`;
    bodyHtml += `</div>`;
    bodyHtml += `<div class="payment-list">`;
    actionablePayments.forEach(p => {
        bodyHtml += `<div class="payment-item">${p.name} - $${p.amount.toFixed(2)}</div>`;
    });
    bodyHtml += `</div>`;

    document.getElementById('modal-body').innerHTML = bodyHtml;
    document.getElementById('bulk-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('bulk-modal').style.display = 'none';
    pendingBulkAction = null;
    selectedPaymentIds = [];
}

async function executeBulkAction() {
    if (!pendingBulkAction || selectedPaymentIds.length === 0) return;

    const action = pendingBulkAction;
    const endpoint = action === 'accept' ? '/admin/payments/bulk-capture' : '/admin/payments/bulk-refund';

    document.getElementById('confirm-action').disabled = true;
    document.getElementById('confirm-action').textContent = 'Processing...';

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({payment_ids: selectedPaymentIds})
        });

        const result = await response.json();

        if (result.success) {
            // Refresh data
            const dataResponse = await fetch('/admin/payments/data');
            const data = await dataResponse.json();
            paymentsData = data.payments;
            paymentsTable.replaceData(paymentsData);
            paymentsTable.deselectRow();

            closeModal();

            // Show success message
            const successCount = result.results ? result.results.filter(r => r.success).length : selectedPaymentIds.length;
            alert(`Successfully processed ${successCount} payment(s).`);
        } else {
            alert(`Error: ${result.error || 'Unknown error occurred'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        document.getElementById('confirm-action').disabled = false;
        document.getElementById('confirm-action').textContent = action === 'accept' ? 'Accept All' : 'Refund All';
    }
}

async function capturePayment(paymentId) {
    if (!confirm('Are you sure you want to accept this payment?')) return;

    try {
        const response = await fetch(`/admin/payments/${paymentId}/capture`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Refresh data silently on success
            const dataResponse = await fetch('/admin/payments/data');
            const data = await dataResponse.json();
            paymentsData = data.payments;
            paymentsTable.replaceData(paymentsData);
        } else {
            alert(`Error: ${result.error || 'Failed to capture payment'}`);
        }
    } catch (error) {
        // Network error or JSON parse error - refresh anyway in case it succeeded
        console.error('Capture error:', error);
        const dataResponse = await fetch('/admin/payments/data');
        const data = await dataResponse.json();
        paymentsData = data.payments;
        paymentsTable.replaceData(paymentsData);
    }
}

async function refundPayment(paymentId) {
    if (!confirm('Are you sure you want to refund this payment?')) return;

    try {
        const response = await fetch(`/admin/payments/${paymentId}/refund`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Refresh data silently on success
            const dataResponse = await fetch('/admin/payments/data');
            const data = await dataResponse.json();
            paymentsData = data.payments;
            paymentsTable.replaceData(paymentsData);
        } else {
            alert(`Error: ${result.error || 'Failed to refund payment'}`);
        }
    } catch (error) {
        // Network error or JSON parse error - refresh anyway in case it succeeded
        console.error('Refund error:', error);
        const dataResponse = await fetch('/admin/payments/data');
        const data = await dataResponse.json();
        paymentsData = data.payments;
        paymentsTable.replaceData(paymentsData);
    }
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});
