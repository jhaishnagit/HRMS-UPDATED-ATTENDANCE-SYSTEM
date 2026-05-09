
/* ── CSV HELPERS ── */

/**
 * Build CSV string from an array of row objects.
 * headers: array of { label, key } 
 */
function buildCSV(headers, rows) {
    const escape = v => {
        if (v === null || v === undefined) return '';
        const s = String(v).replace(/"/g, '""');
        return /[",\n]/.test(s) ? `"${s}"` : s;
    };
    const headerRow = headers.map(h => escape(h.label)).join(',');
    const dataRows = rows.map(r => headers.map(h => escape(r[h.key])).join(','));
    return [headerRow, ...dataRows].join('\r\n');
}

function downloadCSV(csv, filename) {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/* Collect all row data from the table's data attributes */
function collectAllRows() {
    const rows = document.querySelectorAll('#tableBody tr');
    const data = [];
    rows.forEach(row => {
        data.push({
            username: row.dataset.username || '',
            email: row.dataset.email || '',
            leavetype: row.dataset.leavetype || '',
            from: row.dataset.from || '',
            to: row.dataset.to || '',
            days: row.dataset.days || '',
            paid: row.dataset.paid || '',
            unpaid: row.dataset.unpaid || '',
            reason: row.dataset.reason || '',
            applied: row.dataset.applied || '',
            status: row.dataset.status || '',
        });
    });
    return data;
}

const CSV_HEADERS = [
    { label: 'Employee', key: 'username' },
    { label: 'Email', key: 'email' },
    { label: 'Leave Type', key: 'leavetype' },
    { label: 'From', key: 'from' },
    { label: 'To', key: 'to' },
    { label: 'Total Days', key: 'days' },
    { label: 'Paid Days', key: 'paid' },
    { label: 'Unpaid Days', key: 'unpaid' },
    { label: 'Reason', key: 'reason' },
    { label: 'Applied On', key: 'applied' },
    { label: 'Status', key: 'status' },
];

/* ── EXPORT ALL LEAVES ── */
function exportAllLeaves() {
    const rows = collectAllRows();
    if (!rows.length) {
        showToast('No records to export.', 'info');
        return;
    }
    const csv = buildCSV(CSV_HEADERS, rows);
    const date = new Date().toISOString().slice(0, 10);
    downloadCSV(csv, `all_leaves_${date}.csv`);
    showToast(`Exported ${rows.length} records successfully.`, 'success');
}

/* ── EXPORT SINGLE EMPLOYEE LEAVES ── */
function exportEmployeeLeaves(username, email) {
    const allRows = collectAllRows();
    const empRows = allRows.filter(r =>
        r.username.toLowerCase() === username.toLowerCase() &&
        r.email.toLowerCase() === email.toLowerCase()
    );
    if (!empRows.length) {
        showToast('No records found for this employee.', 'info');
        return;
    }
    const csv = buildCSV(CSV_HEADERS, empRows);
    const safeName = username.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const date = new Date().toISOString().slice(0, 10);
    downloadCSV(csv, `leaves_${safeName}_${date}.csv`);
    showToast(`Downloaded ${empRows.length} record(s) for ${username}.`, 'success');
}

/* ── TOAST ── */
function showToast(msg, type = 'success') {
    const c = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast-msg ${type}`;
    const icon = type === 'success' ? 'check-circle' : (type === 'error' ? 'exclamation-circle' : 'info-circle');
    const color = type === 'success' ? '#16a34a' : (type === 'error' ? '#dc2626' : '#4f46e5');
    t.innerHTML = `<i class="fas fa-${icon}" style="color:${color};font-size:1rem;flex-shrink:0;"></i><span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateX(50px)';
        setTimeout(() => t.remove(), 320);
    }, 3500);
}

/* ── LOADING OVERLAY ── */
function showLoading(msg) {
    document.getElementById('loadingText').textContent = msg;
    document.getElementById('loadingOverlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

/* ── CONFIRM MODAL ── */
let _pendingLeaveId = null;
let _pendingStatus = null;
let _pendingRemarks = '';

function handleLeave(leaveId, status) {
    _pendingLeaveId = leaveId;
    _pendingStatus = status;

    const modal = document.getElementById('confirmModal');
    const titleEl = document.getElementById('confirmTitle');
    const bodyEl = document.getElementById('confirmBody');
    const confirmBtn = document.getElementById('confirmActionBtn');

    if (status === 'Approved') {
        titleEl.innerHTML = '<i class="fas fa-check-circle" style="color:#16a34a;margin-right:8px;"></i>Approve Leave Request';
        bodyEl.textContent = 'Are you sure you want to approve this leave request? The employee will be notified.';
        confirmBtn.className = 'modal-btn modal-btn-approve';
        confirmBtn.innerHTML = '<i class="fas fa-check"></i> Yes, Approve';
    } else {
        titleEl.innerHTML = '<i class="fas fa-times-circle" style="color:#dc2626;margin-right:8px;"></i>Reject Leave Request';
        bodyEl.textContent = 'Are you sure you want to reject this leave request? The employee will be notified.';
        confirmBtn.className = 'modal-btn modal-btn-reject';
        confirmBtn.innerHTML = '<i class="fas fa-times"></i> Yes, Reject';
    }
    const remarks = prompt("Enter remarks:");
    _pendingRemarks = remarks;

    if (remarks === null) {
        return;
    }

    modal.style.display = 'flex';
    requestAnimationFrame(() => modal.classList.add('visible'));
}

function closeConfirm() {
    const modal = document.getElementById('confirmModal');
    modal.classList.remove('visible');
    setTimeout(() => { modal.style.display = 'none'; }, 220);
    _pendingLeaveId = null;
    _pendingStatus = null;
}

function confirmAction() {
    if (!_pendingLeaveId || !_pendingStatus) return;
    const leaveId = _pendingLeaveId;
    const status = _pendingStatus;
    closeConfirm();

    const verb = status === 'Approved' ? 'Approving' : 'Rejecting';
    showLoading(`${verb} leave request…`);

    fetch(`/admin/update_leave_status/${leaveId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `status=${status}&remarks=${encodeURIComponent(_pendingRemarks)}`
    })
        .then(r => r.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                showToast(data.message || `Leave ${status.toLowerCase()} successfully.`, 'success');

                /* Update row in DOM */
                const statusEl = document.getElementById(`status-${leaveId}`);
                const actionsEl = document.getElementById(`actions-${leaveId}`);
                const row = document.getElementById(`row-${leaveId}`);
                const oldStatus = row.dataset.status;

                statusEl.className = `badge-status badge-${status.toLowerCase()}`;
                statusEl.textContent = status;

                /* Keep the CSV download button, remove approve/reject */
                const username = row.dataset.username;
                const email = row.dataset.email;
                actionsEl.innerHTML = `
                    <div class="actions-cell">
                        <span class="no-action-text">No action</span>
                        <button class="btn-emp-dl" onclick="exportEmployeeLeaves('${username}', '${email}')" title="Download ${username}'s leaves">
                            <i class="fas fa-user-download" style="font-size:0.7rem;"></i> CSV
                        </button>
                    </div>`;
                row.dataset.status = status;

                /* Live update stat cards */
                updateStatCards(oldStatus, status);
                updateRowCount();
            } else {
                showToast(data.message || 'Action failed. Please try again.', 'error');
            }
        })
        .catch(() => { hideLoading(); showToast('Network error. Please try again.', 'error'); });
}

/* ── LIVE STAT CARD UPDATE ── */
function updateStatCards(oldStatus, newStatus) {
    const cards = {
        'Pending': document.getElementById('count-pending'),
        'Approved': document.getElementById('count-approved'),
        'Rejected': document.getElementById('count-rejected'),
    };

    if (oldStatus && cards[oldStatus]) {
        const cur = parseInt(cards[oldStatus].textContent) || 0;
        animateCount(cards[oldStatus], cur, Math.max(0, cur - 1));
    }
    if (newStatus && cards[newStatus]) {
        const cur = parseInt(cards[newStatus].textContent) || 0;
        animateCount(cards[newStatus], cur, cur + 1);
    }
}

function animateCount(el, from, to) {
    const duration = 400;
    const start = performance.now();
    function step(now) {
        const progress = Math.min((now - start) / duration, 1);
        el.textContent = Math.round(from + (to - from) * progress);
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

/* ── FILTER ── */
function filterTable() {
    const statusF = document.getElementById('filterStatus').value;
    const typeF = document.getElementById('filterType').value;
    const nameF = document.getElementById('searchUser').value.toLowerCase();
    const rows = document.querySelectorAll('#tableBody tr');
    let visible = 0;
    rows.forEach(row => {
        const show = (statusF === 'all' || row.dataset.status === statusF) &&
            (typeF === 'all' || row.dataset.type === typeF) &&
            row.dataset.name.includes(nameF);
        row.style.display = show ? '' : 'none';
        if (show) visible++;
    });
    updateRowCount(visible);
}

function updateRowCount(n) {
    const count = n !== undefined ? n : document.querySelectorAll('#tableBody tr:not([style*="none"])').length;
    document.getElementById('rowCount').textContent = `${count} record${count !== 1 ? 's' : ''}`;
}

/* Close modal on backdrop click */
document.getElementById('confirmModal').addEventListener('click', function (e) {
    if (e.target === this) closeConfirm();
});

document.addEventListener('DOMContentLoaded', () => updateRowCount());
