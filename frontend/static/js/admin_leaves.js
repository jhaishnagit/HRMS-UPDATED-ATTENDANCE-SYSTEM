/* ============================================================
   ADMIN LEAVE MANAGEMENT
   ============================================================ */

document.addEventListener("DOMContentLoaded", function () {
    console.log("admin_leaves.js loaded successfully");

    initializeLeaveManagement();
});


/* ============================================================
   GLOBAL VARIABLES
   ============================================================ */

let pendingLeaveId = null;
let pendingLeaveStatus = null;
let pendingLeaveRemarks = "";


/* ============================================================
   INITIALIZE
   ============================================================ */

function initializeLeaveManagement() {

    // Approve / Reject buttons
    document.addEventListener("click", function (event) {

        const button = event.target.closest(".leave-action-btn");

        if (!button) {
            return;
        }

        const leaveId = button.dataset.leaveId;
        const status = button.dataset.leaveStatus;

        if (!leaveId || !status) {
            console.error("Leave ID or status missing");
            return;
        }

        handleLeave(leaveId, status);
    });


    // Confirmation modal background click
    const confirmModal = document.getElementById("confirmModal");

    if (confirmModal) {
        confirmModal.addEventListener("click", function (event) {

            if (event.target === confirmModal) {
                closeConfirm();
            }

        });
    }


    // Initial row count
    updateRowCount();
}


/* ============================================================
   HANDLE APPROVE / REJECT
   ============================================================ */

function handleLeave(leaveId, status) {

    console.log("handleLeave called:", leaveId, status);

    pendingLeaveId = String(leaveId);
    pendingLeaveStatus = status;
    pendingLeaveRemarks = "";


    // Validate status
    if (status !== "Approved" && status !== "Rejected") {

        console.error("Invalid leave status:", status);

        showToast(
            "Invalid leave status.",
            "error"
        );

        return;
    }


    // Ask for remarks
    const remarks = window.prompt(
        status === "Approved"
            ? "Enter remarks for approving this leave:"
            : "Enter remarks for rejecting this leave:"
    );


    // User clicked Cancel
    if (remarks === null) {

        pendingLeaveId = null;
        pendingLeaveStatus = null;
        pendingLeaveRemarks = "";

        return;
    }


    // Save remarks
    pendingLeaveRemarks = remarks.trim();


    // Show confirmation modal
    const modal = document.getElementById("confirmModal");
    const title = document.getElementById("confirmTitle");
    const body = document.getElementById("confirmBody");
    const confirmButton = document.getElementById("confirmActionBtn");


    if (!modal || !title || !body || !confirmButton) {

        console.error("Confirmation modal elements are missing.");

        showToast(
            "Confirmation modal is not configured correctly.",
            "error"
        );

        return;
    }


    if (status === "Approved") {

        title.innerHTML = `
            <i class="fas fa-check-circle"></i>
            Approve Leave
        `;

        body.innerHTML = `
            Are you sure you want to approve this leave request?
            <br><br>
            <strong>Remarks:</strong>
            <span>${escapeHtml(pendingLeaveRemarks || "No remarks")}</span>
        `;

        confirmButton.innerHTML = `
            <i class="fas fa-check"></i>
            Yes, Approve
        `;

        confirmButton.className =
            "modal-btn modal-btn-approve";

    } else {

        title.innerHTML = `
            <i class="fas fa-times-circle"></i>
            Reject Leave
        `;

        body.innerHTML = `
            Are you sure you want to reject this leave request?
            <br><br>
            <strong>Remarks:</strong>
            <span>${escapeHtml(pendingLeaveRemarks || "No remarks")}</span>
        `;

        confirmButton.innerHTML = `
            <i class="fas fa-times"></i>
            Yes, Reject
        `;

        confirmButton.className =
            "modal-btn modal-btn-reject";
    }


    // Show modal
    modal.style.display = "flex";

    // Small delay for CSS transition
    setTimeout(function () {
        modal.classList.add("visible");
    }, 10);
}


/* ============================================================
   CLOSE CONFIRMATION MODAL
   ============================================================ */

function closeConfirm() {

    const modal = document.getElementById("confirmModal");

    if (modal) {

        modal.classList.remove("visible");

        setTimeout(function () {
            modal.style.display = "none";
        }, 200);
    }


    pendingLeaveId = null;
    pendingLeaveStatus = null;
    pendingLeaveRemarks = "";
}


/* ============================================================
   CONFIRM ACTION
   ============================================================ */

async function confirmAction() {

    console.log(
        "confirmAction called:",
        pendingLeaveId,
        pendingLeaveStatus,
        pendingLeaveRemarks
    );


    // Validate pending data
    if (!pendingLeaveId || !pendingLeaveStatus) {

        console.error("No pending leave action.");

        showToast(
            "No leave action is pending.",
            "error"
        );

        return;
    }


    // IMPORTANT:
    // Copy values BEFORE closing the modal because closeConfirm()
    // clears the global variables.
    const leaveId = pendingLeaveId;
    const status = pendingLeaveStatus;
    const remarks = pendingLeaveRemarks;


    // Get button
    const confirmButton =
        document.getElementById("confirmActionBtn");


    // Disable button to prevent double-click
    if (confirmButton) {

        confirmButton.disabled = true;

        confirmButton.innerHTML = `
            <i class="fas fa-spinner fa-spin"></i>
            Processing...
        `;
    }


    // Show loading
    showLoading(
        status === "Approved"
            ? "Approving leave request..."
            : "Rejecting leave request..."
    );


    try {

        console.log("Sending leave update:", {
            leaveId: leaveId,
            status: status,
            remarks: remarks
        });


        /*
         * Use URLSearchParams instead of manually creating
         * the encoded request body.
         */
        const formData = new URLSearchParams();

        formData.append("status", status);
        formData.append("remarks", remarks);


        const response = await fetch(
            `/admin/update_leave_status/${encodeURIComponent(leaveId)}`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest"
                },

                body: formData.toString(),

                credentials: "same-origin"
            }
        );


        console.log(
            "Leave update HTTP status:",
            response.status
        );


        /*
         * Read response as text first.
         * This prevents JSON parsing errors from hiding the
         * actual Flask error response.
         */
        const responseText = await response.text();

        console.log(
            "Leave update server response:",
            responseText
        );


        let data;

        try {

            data = JSON.parse(responseText);

        } catch (jsonError) {

            console.error(
                "Server did not return JSON:",
                jsonError
            );

            throw new Error(
                `Server returned HTTP ${response.status}. ` +
                `Response: ${responseText.substring(0, 300)}`
            );
        }


        /*
         * HTTP error
         */
        if (!response.ok) {

            throw new Error(
                data.message ||
                `Request failed with HTTP ${response.status}`
            );
        }


        /*
         * Backend returned success:false
         */
        if (!data.success) {

            throw new Error(
                data.message ||
                "Leave update failed."
            );
        }


        /* ====================================================
           SUCCESS
           ==================================================== */

        console.log(
            "Leave updated successfully:",
            data
        );


        hideLoading();
        closeConfirm();


        showToast(
            data.message ||
            `Leave ${status.toLowerCase()} successfully.`,
            "success"
        );


        /*
         * Update the table immediately
         */
        updateLeaveRow(
            leaveId,
            status,
            remarks
        );


        /*
         * Update statistics
         */
        updateStatistics();


        /*
         * Update visible row count
         */
        updateRowCount();


    } catch (error) {

        console.error(
            "Leave update error:",
            error
        );


        hideLoading();


        if (confirmButton) {

            confirmButton.disabled = false;

            confirmButton.innerHTML =
                status === "Approved"
                    ? `<i class="fas fa-check"></i> Yes, Approve`
                    : `<i class="fas fa-times"></i> Yes, Reject`;
        }


        showToast(
            error.message ||
            "Unable to update leave request.",
            "error"
        );


        /*
         * IMPORTANT:
         * Keep the modal open when there is an error so the user
         * can try again.
         */
        const modal =
            document.getElementById("confirmModal");

        if (modal) {
            modal.style.display = "flex";
            modal.classList.add("visible");
        }
    }
}


/* ============================================================
   UPDATE LEAVE ROW
   ============================================================ */

function updateLeaveRow(leaveId, newStatus, remarks) {

    const row =
        document.getElementById(`row-${leaveId}`);


    if (!row) {

        console.error(
            `Row row-${leaveId} not found`
        );

        return;
    }


    /* ========================================================
       UPDATE STATUS
       ======================================================== */

    const statusElement =
        document.getElementById(`status-${leaveId}`);


    if (statusElement) {

        statusElement.textContent = newStatus;

        statusElement.className =
            `badge-status badge-${newStatus.toLowerCase()}`;
    }


    /* ========================================================
       UPDATE REMARKS
       ======================================================== */

    const remarksElement =
        document.getElementById(`remarks-${leaveId}`);


    if (remarksElement) {

        remarksElement.textContent =
            remarks || "—";
    }


    /* ========================================================
       UPDATE DATA ATTRIBUTE
       ======================================================== */

    row.dataset.status = newStatus;


    /* ========================================================
       REMOVE APPROVE / REJECT BUTTONS
       ======================================================== */

    const actionsElement =
        document.getElementById(`actions-${leaveId}`);


    if (actionsElement) {

        const username =
            row.dataset.username || "";

        const email =
            row.dataset.email || "";


        const actionCell =
            actionsElement.querySelector(".actions-cell");


        if (actionCell) {

            /*
             * Keep CSV button if it exists.
             */
            const csvButton =
                actionCell.querySelector(".btn-emp-dl");


            actionCell.innerHTML = `
                <span class="no-action-text">
                    No action
                </span>
            `;


            if (csvButton) {

                actionCell.appendChild(
                    csvButton
                );
            }
        }
    }


    /*
     * Disable action buttons if any remain.
     */
    const buttons =
        row.querySelectorAll(".leave-action-btn");


    buttons.forEach(function (button) {

        button.disabled = true;
        button.remove();

    });


    console.log(
        `Leave ${leaveId} UI updated to ${newStatus}`
    );
}


/* ============================================================
   UPDATE STATISTICS
   ============================================================ */

function updateStatistics() {

    const rows =
        document.querySelectorAll(
            "#tableBody tr[id^='row-']"
        );


    let pending = 0;
    let approved = 0;
    let rejected = 0;


    rows.forEach(function (row) {

        const status =
            row.dataset.status;


        if (status === "Pending") {
            pending++;
        }

        else if (status === "Approved") {
            approved++;
        }

        else if (status === "Rejected") {
            rejected++;
        }
    });


    const pendingElement =
        document.getElementById("count-pending");

    const approvedElement =
        document.getElementById("count-approved");

    const rejectedElement =
        document.getElementById("count-rejected");


    if (pendingElement) {
        pendingElement.textContent = pending;
    }

    if (approvedElement) {
        approvedElement.textContent = approved;
    }

    if (rejectedElement) {
        rejectedElement.textContent = rejected;
    }
}


/* ============================================================
   FILTER TABLE
   ============================================================ */

function filterTable() {

    const statusFilter =
        document.getElementById("filterStatus");

    const typeFilter =
        document.getElementById("filterType");

    const searchInput =
        document.getElementById("searchUser");


    const selectedStatus =
        statusFilter
            ? statusFilter.value
            : "all";


    const selectedType =
        typeFilter
            ? typeFilter.value
            : "all";


    const searchText =
        searchInput
            ? searchInput.value.trim().toLowerCase()
            : "";


    const rows =
        document.querySelectorAll(
            "#tableBody tr[id^='row-']"
        );


    rows.forEach(function (row) {

        const rowStatus =
            row.dataset.status || "";

        const rowType =
            row.dataset.type || "";

        const rowName =
            row.dataset.name || "";


        const statusMatch =
            selectedStatus === "all" ||
            rowStatus === selectedStatus;


        const typeMatch =
            selectedType === "all" ||
            rowType === selectedType;


        const searchMatch =
            !searchText ||
            rowName.includes(searchText);


        if (
            statusMatch &&
            typeMatch &&
            searchMatch
        ) {

            row.style.display = "";

        } else {

            row.style.display = "none";
        }
    });


    updateRowCount();
}


/* ============================================================
   UPDATE ROW COUNT
   ============================================================ */

function updateRowCount() {

    const rowCountElement =
        document.getElementById("rowCount");


    if (!rowCountElement) {
        return;
    }


    const rows =
        document.querySelectorAll(
            "#tableBody tr[id^='row-']"
        );


    let visibleCount = 0;


    rows.forEach(function (row) {

        if (row.style.display !== "none") {
            visibleCount++;
        }
    });


    rowCountElement.textContent =
        `${visibleCount} record${visibleCount === 1 ? "" : "s"}`;
}


/* ============================================================
   LOADING OVERLAY
   ============================================================ */

function showLoading(message) {

    const loadingOverlay =
        document.getElementById("loadingOverlay");

    const loadingText =
        document.getElementById("loadingText");


    if (loadingText) {

        loadingText.textContent =
            message || "Processing...";
    }


    if (loadingOverlay) {

        loadingOverlay.style.display =
            "flex";
    }
}


function hideLoading() {

    const loadingOverlay =
        document.getElementById("loadingOverlay");


    if (loadingOverlay) {

        loadingOverlay.style.display =
            "none";
    }
}


/* ============================================================
   TOAST MESSAGE
   ============================================================ */

function showToast(message, type = "success") {

    let toastContainer =
        document.getElementById("toastContainer");


    /*
     * Create toast container automatically if it doesn't exist.
     */
    if (!toastContainer) {

        toastContainer =
            document.createElement("div");

        toastContainer.id =
            "toastContainer";

        toastContainer.style.position =
            "fixed";

        toastContainer.style.top =
            "20px";

        toastContainer.style.right =
            "20px";

        toastContainer.style.zIndex =
            "10000";

        document.body.appendChild(
            toastContainer
        );
    }


    const toast =
        document.createElement("div");


    toast.className =
        `leave-toast leave-toast-${type}`;


    toast.style.padding =
        "12px 18px";

    toast.style.marginBottom =
        "10px";

    toast.style.borderRadius =
        "8px";

    toast.style.fontWeight =
        "600";

    toast.style.boxShadow =
        "0 4px 15px rgba(0,0,0,0.15)";

    toast.style.background =
        type === "success"
            ? "#d1fae5"
            : "#fee2e2";

    toast.style.color =
        type === "success"
            ? "#065f46"
            : "#991b1b";


    toast.textContent =
        message;


    toastContainer.appendChild(
        toast
    );


    setTimeout(function () {

        toast.style.opacity = "0";

        toast.style.transition =
            "opacity 0.3s";

        setTimeout(function () {

            toast.remove();

        }, 300);

    }, 3500);
}


/* ============================================================
   HTML ESCAPE
   ============================================================ */

function escapeHtml(value) {

    const div =
        document.createElement("div");

    div.textContent =
        value || "";

    return div.innerHTML;
}


/* ============================================================
   CSV EXPORT
   ============================================================ */

function exportEmployeeLeaves(username, email) {

    const rows =
        document.querySelectorAll(
            "#tableBody tr[id^='row-']"
        );


    const employeeRows = [];


    rows.forEach(function (row) {

        const rowUsername =
            row.dataset.username || "";

        const rowEmail =
            row.dataset.email || "";


        if (
            rowUsername === username ||
            rowEmail === email
        ) {

            employeeRows.push(row);
        }
    });


    if (employeeRows.length === 0) {

        showToast(
            "No leave records found for this employee.",
            "error"
        );

        return;
    }


    const headers = [
        "Employee",
        "Email",
        "Leave Type",
        "From",
        "To",
        "Days",
        "Status",
        "Remarks",
        "Reason",
        "Applied Date"
    ];


    const csvRows = [
        headers
    ];


    employeeRows.forEach(function (row) {

        const usernameValue =
            row.dataset.username || "";

        const emailValue =
            row.dataset.email || "";

        const leaveType =
            row.dataset.leavetype || "";

        const from =
            row.dataset.from || "";

        const to =
            row.dataset.to || "";

        const days =
            row.dataset.days || "0";

        const status =
            row.dataset.status || "";

        const remarksElement =
            row.querySelector(
                ".leave-remarks"
            );

        const remarks =
            remarksElement
                ? remarksElement.textContent.trim()
                : "";

        const reason =
            row.dataset.reason || "";

        const applied =
            row.dataset.applied || "";


        csvRows.push([
            usernameValue,
            emailValue,
            leaveType,
            from,
            to,
            days,
            status,
            remarks,
            reason,
            applied
        ]);
    });


    const csvContent =
        csvRows
            .map(function (row) {

                return row
                    .map(function (value) {

                        return `"${String(value)
                            .replace(/"/g, '""')}"`;

                    })
                    .join(",");

            })
            .join("\n");


    const blob =
        new Blob(
            [csvContent],
            {
                type: "text/csv;charset=utf-8;"
            }
        );


    const url =
        URL.createObjectURL(blob);


    const link =
        document.createElement("a");


    link.href = url;


    link.download =
        `${username}_leave_records.csv`;


    document.body.appendChild(
        link
    );


    link.click();


    document.body.removeChild(
        link
    );


    URL.revokeObjectURL(url);
}


/* ============================================================
   EXPOSE FUNCTIONS GLOBALLY
   ============================================================ */

window.handleLeave = handleLeave;
window.confirmAction = confirmAction;
window.closeConfirm = closeConfirm;
window.filterTable = filterTable;
window.exportEmployeeLeaves = exportEmployeeLeaves;
window.showToast = showToast;