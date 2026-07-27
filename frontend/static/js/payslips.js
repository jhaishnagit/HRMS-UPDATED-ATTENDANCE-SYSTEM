async function loadPayslips() {
    try {
        const response = await fetch("/payslip/list");

        if (!response.ok) {
            throw new Error("Failed to load payslips");
        }

        const data = await response.json();

        const tbody = document.getElementById("payslipTable");

        if (!tbody) {
            console.error("payslipTable element not found");
            return;
        }

        tbody.innerHTML = "";

        if (data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="text-center">
                        No payslips available.
                    </td>
                </tr>
            `;
            return;
        }

        data.forEach((p) => {
            tbody.innerHTML += `
                <tr>
                    <td>${p.month}</td>
                    <td>${p.year}</td>
                    <td>
                        <a href="/payslip/download/${p.id}" class="btn btn-primary btn-sm">
                            Download
                        </a>
                    </td>
                </tr>
            `;
        });

    } catch (err) {
        console.error(err);

        const tbody = document.getElementById("payslipTable");

        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="text-danger text-center">
                        Failed to load payslips.
                    </td>
                </tr>
            `;
        }
    }
}

document.addEventListener("DOMContentLoaded", loadPayslips);