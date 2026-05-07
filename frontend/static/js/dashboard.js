// static/js/dashboard.js
document.addEventListener("DOMContentLoaded", function () {
    const today = new Date().toISOString().split("T")[0];

    const startInput = document.getElementById("leave-start");
    const endInput = document.getElementById("leave-end");

    if (startInput && endInput) {
        startInput.setAttribute("min", today);
        endInput.setAttribute("min", today);
    }
    const navItems = document.querySelectorAll('.sidebar-nav li[data-section]');
    const sections = document.querySelectorAll('.content-section');
    const sidebar = document.getElementById('sidebar');
    let stream = null;

    // Toggle sidebar for mobile
    if (window.innerWidth < 992) {
        sidebar.classList.add('offcanvas', 'offcanvas-start');
        const toggleBtn = document.querySelector('.toggle-btn');
        if (toggleBtn) toggleBtn.addEventListener('click', () => sidebar.classList.add('show'));
        const closeBtn = document.getElementById('close-btn');
        if (closeBtn) {
            closeBtn.classList.remove('d-none');
            closeBtn.addEventListener('click', () => sidebar.classList.remove('show'));
        }
    }

    // Navigation
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = item.getAttribute('data-section');
            if (!sectionId) return;
            navItems.forEach(i => {
                i.classList.remove('active');
                i.querySelector('a')?.classList.remove('active');
            });
            item.classList.add('active');
            item.querySelector('a')?.classList.add('active');
            sections.forEach(s => s.classList.remove('active'));
            document.getElementById(sectionId)?.classList.add('active');
            if (window.innerWidth < 992) sidebar.classList.remove('show');
        });
    });

    // ═══════════════════════════════════════════════════════════════════════
    // LIVENESS + FACE CAPTURE  (MediaPipe FaceMesh blink detection)
    // ═══════════════════════════════════════════════════════════════════════
    const RIGHT_EYE = [33, 160, 158, 133, 153, 144];
    const LEFT_EYE = [362, 385, 387, 263, 373, 380];
    const EAR_THRESHOLD = 0.22;
    const BLINK_CONSEC = 2;
    const BLINKS_NEEDED = 2;

    // ── Face presence landmarks (nose tip, chin, etc.) ───────────────────
    // We'll validate that a single face is centred before allowing capture
    const FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361,
        288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149,
        150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109];

    function euclidean(p1, p2) {
        return Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2);
    }
    function eyeAspectRatio(lm, idx) {
        const [p1, p2, p3, p4, p5, p6] = idx.map(i => lm[i]);
        return (euclidean(p2, p6) + euclidean(p3, p5)) / (2.0 * euclidean(p1, p4));
    }

    /**
     * Checks if the detected face is large enough (not too far away) and centred.
     * Returns true if face is acceptable for capture.
     */
    function isFaceAcceptable(lm, videoWidth, videoHeight) {
        // Measure face width using face oval landmarks
        const xs = FACE_OVAL.map(i => lm[i].x);
        const faceWidth = Math.max(...xs) - Math.min(...xs); // normalised 0-1

        // Face must occupy at least 15% of frame width
        if (faceWidth < 0.15) return false;

        // Face centre X should be roughly in the middle third of the frame
        const centerX = (Math.max(...xs) + Math.min(...xs)) / 2;
        if (centerX < 0.2 || centerX > 0.8) return false;

        return true;
    }

    // ── Stop any running stream ──────────────────────────────────────────
    function stopStream() {
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    }

    // ── Main liveness camera function ────────────────────────────────────
    async function startLivenessCamera(videoId, statusId, endpoint, isLogin) {
        const video = document.getElementById(videoId);
        const statusEl = document.getElementById(statusId);
        const startBtn = document.getElementById(isLogin ? 'start-camera-btn' : 'start-camera-logout-btn');
        const stopBtn = document.getElementById(isLogin ? 'stop-camera-btn' : 'stop-camera-logout-btn');
        const captureBtn = document.getElementById(isLogin ? 'capture-login-btn' : 'capture-logout-btn');

        if (!video) { console.error('Video element not found:', videoId); return; }

        if (typeof FaceMesh === 'undefined') {
            setStatus(statusEl, '⚠️ MediaPipe not loaded. Check internet connection.', 'error');
            return;
        }

        stopStream();
        setStatus(statusEl, '📷 Requesting camera access…', 'info');

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
            });
        } catch (err) {
            console.error('Camera error:', err);
            if (err.name === 'NotAllowedError') {
                setStatus(statusEl, '❌ Camera permission denied. Please allow camera access in browser settings.', 'error');
            } else if (err.name === 'NotFoundError') {
                setStatus(statusEl, '❌ No camera found on this device.', 'error');
            } else {
                setStatus(statusEl, `❌ Camera error: ${err.message}`, 'error');
            }
            return;
        }

        video.srcObject = stream;
        video.style.display = 'block';
        video.style.width = '100%';
        video.style.maxWidth = '420px';
        video.style.borderRadius = '10px';
        video.style.marginBottom = '12px';
        video.style.background = '#000';

        try { await video.play(); } catch (e) { console.warn('video.play() warning:', e); }

        if (startBtn) startBtn.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'inline-block';
        if (captureBtn) captureBtn.style.display = 'none';

        setStatus(statusEl, '⏳ Loading face detector…', 'info');

        const faceMesh = new FaceMesh({
            locateFile: f => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4/${f}`
        });
        faceMesh.setOptions({
            maxNumFaces: 1,          // Only detect ONE face
            refineLandmarks: true,
            minDetectionConfidence: 0.7,   // Higher = stricter detection
            minTrackingConfidence: 0.6
        });

        let blinkCount = 0;
        let closedFrames = 0;
        let eyeWasOpen = true;
        let livenessOk = false;
        let animId = null;
        let submitting = false;
        let frameCount = 0;
        let noFaceFrames = 0;       // Track consecutive frames with no/multiple faces

        faceMesh.onResults((results) => {
            if (livenessOk) return;

            frameCount++;

            // ── Show initial prompt ──────────────────────────────────────
            if (frameCount === 5) {
                setStatus(statusEl, '👤 Position your face in the centre of the camera…', 'info');
            }

            const facesFound = results.multiFaceLandmarks ? results.multiFaceLandmarks.length : 0;

            // ── No face detected ─────────────────────────────────────────
            if (facesFound === 0) {
                noFaceFrames++;
                if (frameCount > 5) {
                    setStatus(statusEl, '👤 No face detected. Look directly at the camera.', 'warn');
                }
                return;
            }

            // ── Multiple faces — block immediately ────────────────────────
            if (facesFound > 1) {
                noFaceFrames++;
                setStatus(statusEl, '⚠️ Multiple faces detected! Only YOU should be in frame.', 'error');
                // Reset blink progress if multiple faces appear
                blinkCount = 0;
                closedFrames = 0;
                eyeWasOpen = true;
                return;
            }

            // ── Single face found ─────────────────────────────────────────
            noFaceFrames = 0;
            const lm = results.multiFaceLandmarks[0];

            // Check face is large enough (user isn't too far away)
            if (!isFaceAcceptable(lm, video.videoWidth, video.videoHeight)) {
                setStatus(statusEl, '🔍 Move closer to the camera and centre your face.', 'warn');
                return;
            }

            // ── Blink detection ──────────────────────────────────────────
            const avgEAR = (eyeAspectRatio(lm, RIGHT_EYE) + eyeAspectRatio(lm, LEFT_EYE)) / 2.0;

            if (avgEAR < EAR_THRESHOLD) {
                closedFrames++;
                eyeWasOpen = false;
            } else {
                if (closedFrames >= BLINK_CONSEC && !eyeWasOpen) {
                    blinkCount++;
                    console.log('[liveness] Blink #' + blinkCount);
                }
                closedFrames = 0;
                eyeWasOpen = true;
            }

            const remaining = BLINKS_NEEDED - blinkCount;
            if (remaining > 0) {
                if (frameCount > 5) {
                    setStatus(statusEl, `👁 Blink ${remaining} more time${remaining > 1 ? 's' : ''}… (only your face should be visible)`, 'info');
                }
                return;
            }

            // ── Liveness passed — take final face-only snapshot ───────────
            livenessOk = true;
            cancelAnimationFrame(animId);

            // Final check: still only one face at capture moment
            if (facesFound !== 1) {
                livenessOk = false;
                setStatus(statusEl, '⚠️ Multiple faces detected at capture. Please ensure only you are visible.', 'error');
                blinkCount = 0;
                return;
            }

            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const imageDataUrl = canvas.toDataURL('image/jpeg', 0.85);   // Slightly higher quality for better matching

            setStatus(statusEl, '✅ Liveness confirmed! Click the button below to submit.', 'success');

            if (captureBtn) {
                captureBtn.style.display = 'inline-block';
                captureBtn.disabled = false;
                captureBtn.innerHTML = isLogin ? '&#10003; Confirm Login' : '&#10003; Confirm Logout';

                const newBtn = captureBtn.cloneNode(true);
                captureBtn.parentNode.replaceChild(newBtn, captureBtn);
                newBtn.style.display = 'inline-block';
                newBtn.disabled = false;

                newBtn.addEventListener('click', function handler() {
                    if (submitting) return;
                    submitting = true;
                    newBtn.disabled = true;
                    newBtn.innerHTML = '⏳ Verifying face…';
                    newBtn.removeEventListener('click', handler);
                    submitCapture(imageDataUrl, endpoint, isLogin, statusEl,
                        document.getElementById(isLogin ? 'stop-camera-btn' : 'stop-camera-logout-btn'),
                        startBtn, newBtn);
                }, { once: true });
            }
        });

        // ── Frame loop ───────────────────────────────────────────────────
        async function processFrame() {
            if (!livenessOk && video.readyState >= 2 && !video.paused) {
                try { await faceMesh.send({ image: video }); } catch (e) { /* ignore */ }
            }
            animId = requestAnimationFrame(processFrame);
        }
        animId = requestAnimationFrame(processFrame);

        // ── Stop button ──────────────────────────────────────────────────
        if (stopBtn) {
            stopBtn.onclick = () => {
                cancelAnimationFrame(animId);
                stopStream();
                video.srcObject = null;
                video.style.display = 'none';
                if (startBtn) startBtn.style.display = 'inline-block';
                if (stopBtn) stopBtn.style.display = 'none';
                const cb = document.getElementById(isLogin ? 'capture-login-btn' : 'capture-logout-btn');
                if (cb) cb.style.display = 'none';
                setStatus(statusEl, '', 'info');
                livenessOk = false;
                submitting = false;
                blinkCount = 0;
                closedFrames = 0;
            };
        }
    }

    // ── Submit base64 image + geolocation as JSON ─────────────────────────
    function submitCapture(imageDataUrl, endpoint, isLogin, statusEl, stopBtn, startBtn, captureBtn) {
        setStatus(statusEl, '🔍 Verifying your face on server… please wait.', 'info');

        function doSubmit(lat, lng) {
            const payload = { image: imageDataUrl };
            if (lat !== null) { payload.latitude = lat; payload.longitude = lng; }

            fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(res => {
                    if (!res.ok) {
                        return res.json().catch(() => ({
                            success: false,
                            message: `Server error (HTTP ${res.status}). Please try again.`
                        }));
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.success) {
                        if (stopBtn) stopBtn.click();
                        setStatus(statusEl, '✅ ' + (data.message || 'Success!'), 'success');
                        setTimeout(() => window.location.reload(), 1800);
                    } else {
                        // Show the server rejection reason clearly
                        const reason = data.message || 'Face verification failed. Please try again.';
                        setStatus(statusEl,
                            '❌ ' + reason,
                            'error');
                        if (captureBtn) {
                            captureBtn.disabled = false;
                            captureBtn.innerHTML = isLogin ? '&#10003; Retry Login' : '&#10003; Retry Logout';
                        }
                    }
                })
                .catch(err => {
                    console.error('[submitCapture] fetch failed:', err);
                    setStatus(statusEl, '❌ Network error. Check your connection and try again.', 'error');
                    if (captureBtn) {
                        captureBtn.disabled = false;
                        captureBtn.innerHTML = isLogin ? 'Confirm Login' : 'Retry Logout';

                        captureBtn.onclick = () => {
                            // Restart camera again
                            if (isLogin) {
                                startLivenessCamera('video', 'liveness-status-login', '/mark_login', true);
                            } else {
                                startLivenessCamera('video-logout', 'liveness-status-logout', '/mark_logout', false);
                            }
                        };
                    }
                });
        }

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                pos => doSubmit(pos.coords.latitude, pos.coords.longitude),
                _err => { console.warn('Geolocation failed, proceeding without.'); doSubmit(null, null); },
                { timeout: 8000, maximumAge: 60000 }
            );
        } else {
            doSubmit(null, null);
        }
    }

    // ── Status helper ──────────────────────────────────────────────────────
    function setStatus(el, msg, type) {
        if (!el) return;
        el.textContent = msg;
        el.className = 'mt-2';
        if (type === 'success') el.classList.add('alert', 'alert-success');
        else if (type === 'error') el.classList.add('alert', 'alert-danger');
        else if (type === 'warn') el.classList.add('alert', 'alert-warning');
        else el.classList.add('alert', 'alert-info');
        el.style.display = msg ? 'block' : 'none';
    }

    // ── Wire up Start Camera buttons ───────────────────────────────────────
    document.addEventListener('click', function (e) {
        if (e.target.closest('#start-camera-btn')) {
            e.preventDefault();
            startLivenessCamera('video', 'liveness-status-login', '/mark_login', true);
        }
        if (e.target.closest('#start-camera-logout-btn')) {
            e.preventDefault();
            startLivenessCamera('video-logout', 'liveness-status-logout', '/mark_logout', false);
        }
    });

    // ═══════════════════════════════════════════════════════════════════════
    // DAILY STATUS
    // ═══════════════════════════════════════════════════════════════════════
    const submitStatusBtn = document.getElementById('submit-status-btn');
    if (submitStatusBtn) {
        submitStatusBtn.addEventListener('click', () => {
            const dailyStatus = document.getElementById('daily-status').value;
            if (!dailyStatus.trim()) { alert('Please enter your daily status report.'); return; }
            fetch('/submit_daily_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `daily_status=${encodeURIComponent(dailyStatus)}`
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) { alert('Daily status submitted!'); location.reload(); }
                    else alert(data.message || 'Submission failed.');
                })
                .catch(err => console.error('Status submit error:', err));
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // NOTIFICATION POLLING
    // ═══════════════════════════════════════════════════════════════════════
    function checkNotifications() {
        fetch('/check_notifications')
            .then(r => r.json())
            .then(data => {
                if (data.success && data.message) { alert(`New Notification: ${data.message}`); location.reload(); }
            })
            .catch(e => console.error('Notification poll error:', e));
    }
    setInterval(checkNotifications, 30000);
    checkNotifications();
});


/* ══════════════════════════════════════════════════════════════════════════
LEAVES JS
══════════════════════════════════════════════════════════════════════════ */

document.getElementById('submit-leave-btn')?.addEventListener('click', async function () {
    const spinner = this.querySelector('.spinner-border');
    const leaveType = document.getElementById('leave-type').value;
    const startDate = document.getElementById('leave-start').value;
    const endDate = document.getElementById('leave-end').value;
    const reason = document.getElementById('leave-reason').value;

    if (!leaveType || !startDate || !endDate || !reason) { showToast('Please fill in all fields', 'error'); return; }
    if (new Date(startDate) > new Date(endDate)) { showToast('End date cannot be before start date', 'error'); return; }

    spinner.classList.remove('d-none');
    this.disabled = true;
    try {
        const fd = new FormData();
        fd.append('leave_type', leaveType); fd.append('start_date', startDate);
        fd.append('end_date', endDate); fd.append('reason', reason);
        const res = await fetch('/leave/apply_leave', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.success) {
            showToast('✅ ' + data.message + ' — Confirmation email sent!', 'success');
            document.getElementById('leave-form').reset();
            setTimeout(() => window.location.reload(), 1800);
        } else { showToast('❌ ' + data.message, 'error'); }
    } catch { showToast('Network error. Please try again.', 'error'); }
    finally { spinner.classList.add('d-none'); this.disabled = false; }
});

function showToast(msg, type = 'success') {
    document.getElementById('leave-toast')?.remove();
    const t = document.createElement('div');
    t.id = 'leave-toast';
    Object.assign(t.style, {
        position: 'fixed', bottom: '28px', right: '28px', padding: '13px 20px',
        borderRadius: '12px', background: type === 'success' ? '#10b981' : '#ef4444',
        color: '#fff', fontSize: '0.9rem', fontWeight: '600', zIndex: '99999',
        boxShadow: '0 8px 24px rgba(0,0,0,0.18)', maxWidth: '340px', lineHeight: '1.4'
    });
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(() => t.remove(), 300); }, 4000);
}

let pieChartInst = null, barChartInst = null;
let historyLoaded = false, allLeavesData = [];

function openLeaveHistoryModal() {
    new bootstrap.Modal(document.getElementById('leaveHistoryModal')).show();
    if (historyLoaded) return;
    document.getElementById('historyLoading').style.display = 'block';
    document.getElementById('historyContent').style.display = 'none';
    document.getElementById('historyError').style.display = 'none';
    fetch('/leave/leave_history')
        .then(r => r.json())
        .then(data => {
            if (!data.success) throw new Error(data.message);
            allLeavesData = data.leaves;
            renderHistoryModal(data.leaves);
            historyLoaded = true;
        })
        .catch(err => {
            console.error(err);
            document.getElementById('historyLoading').style.display = 'none';
            document.getElementById('historyError').style.display = 'block';
        });
}

function renderHistoryModal(leaves) {
    document.getElementById('historyLoading').style.display = 'none';
    document.getElementById('historyContent').style.display = 'block';
    const approved = leaves.filter(l => l.status === 'Approved');
    const pending = leaves.filter(l => l.status === 'Pending');
    const rejected = leaves.filter(l => l.status === 'Rejected');
    const totalUsed = approved.reduce((s, l) => s + (l.total_days || 0), 0);
    const pillDefs = [
        { label: 'Total Requests', val: leaves.length, color: '#3b82f6' },
        { label: 'Approved', val: approved.length, color: '#10b981' },
        { label: 'Pending', val: pending.length, color: '#f59e0b' },
        { label: 'Rejected', val: rejected.length, color: '#ef4444' },
        { label: 'Days Used', val: totalUsed + ' days', color: '#6366f1' },
    ];
    document.getElementById('summaryPills').innerHTML = pillDefs.map(p => `
                <div style="background:${p.color}18;border:1.5px solid ${p.color}45;border-radius:20px;
                            padding:5px 16px;font-size:.83rem;display:inline-flex;align-items:center;gap:6px;">
                    <span style="color:${p.color};font-weight:700;">${p.val}</span>
                    <span style="color:#555;">${p.label}</span>
                </div>`).join('');

    const tbody = document.getElementById('fullHistoryBody');
    if (!leaves.length) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:40px;color:#9ca3af;">No leave history found.</td></tr>`;
    } else {
        tbody.innerHTML = leaves.map((l, i) => {
            const sc = l.status === 'Approved' ? 'background:#d1fae5;color:#065f46;' : l.status === 'Rejected' ? 'background:#fee2e2;color:#991b1b;' : 'background:#fef3c7;color:#92400e;';
            const ic = l.status === 'Approved' ? 'check-circle' : l.status === 'Rejected' ? 'times-circle' : 'clock';
            return `<tr>
                        <td style="color:#9ca3af;">${i + 1}</td>
                        <td><strong>${l.leave_type}</strong></td>
                        <td>${l.start_date}</td><td>${l.end_date}</td>
                        <td><strong>${l.total_days}</strong></td>
                        <td><span style="background:#d1fae5;color:#065f46;padding:3px 8px;border-radius:6px;font-size:.8rem;font-weight:600;">
    ${l.used_paid_days || 0}
</span></td>

<td><span style="background:#e0e7ff;color:#3730a3;padding:3px 8px;border-radius:6px;font-size:.8rem;font-weight:600;">
    ${l.used_comp_days || 0}
</span></td>

<td><span style="background:#fee2e2;color:#991b1b;padding:3px 8px;border-radius:6px;font-size:.8rem;font-weight:600;">
    ${l.used_unpaid_days || 0}
</span></td>
                        <td style="max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${l.reason}">${l.reason}</td>
                        <td style="color:#9ca3af;font-size:.8rem;">${l.created_at}</td>
                        <td><span style="${sc}padding:4px 12px;border-radius:20px;font-size:.78rem;font-weight:700;display:inline-flex;align-items:center;gap:5px;">
                            <i class="fas fa-${ic}"></i>${l.status}</span></td>
                    </tr>`;
        }).join('');
    }

    if (pieChartInst) pieChartInst.destroy();
    pieChartInst = new Chart(document.getElementById('statusPieChart'), {
        type: 'doughnut',
        data: { labels: ['Approved', 'Pending', 'Rejected'], datasets: [{ data: [approved.length, pending.length, rejected.length], backgroundColor: ['#10b981', '#f59e0b', '#ef4444'], borderWidth: 3, borderColor: '#fff', hoverOffset: 8 }] },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { padding: 16, font: { size: 12 }, usePointStyle: true } } }, cutout: '65%' }
    });

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const paidM = new Array(12).fill(0),compM = new Array(12).fill(0), unpaidM = new Array(12).fill(0);
    const yr = new Date().getFullYear();
    leaves.filter(l => l.status === 'Approved').forEach(l => {
        const d = new Date(l.start_date);
        if (d.getFullYear() === yr) { paidM[d.getMonth()] += (l.used_paid_days || 0); compM[d.getMonth()] += (l.used_comp_days || 0); unpaidM[d.getMonth()] += (l.used_unpaid_days || 0); }
    });
    if (barChartInst) barChartInst.destroy();
    barChartInst = new Chart(document.getElementById('monthlyBarChart'), {
        type: 'bar',
        data: { labels: months, datasets: [{ label: 'Paid Days', data: paidM, backgroundColor: '#10b981bb', borderRadius: 6 }, { label: 'Comp Days', data: compM, backgroundColor: '#e0e7ffbb', borderRadius: 6 }, { label: 'Unpaid Days', data: unpaidM, backgroundColor: '#ef4444bb', borderRadius: 6 }] },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { padding: 16, font: { size: 12 }, usePointStyle: true } } }, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } } } }
    });
}

function exportLeaveHistory() {
    if (!allLeavesData.length) { showToast('No data to export', 'error'); return; }
    const btn = document.getElementById('exportLeaveBtn');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting…'; btn.disabled = true;
    try {
        const headers = ['#', 'Leave Type', 'From', 'To', 'Total Days', 'Paid Days', 'Comp Days', 'Unpaid Days', 'Reason', 'Applied On', 'Status'];
        const csvRows = [headers.join(','), ...allLeavesData.map((l, i) => [i + 1, `"${l.leave_type}"`, l.start_date, l.end_date, l.total_days, l.used_paid_days || 0, l.used_comp_days || 0, l.used_unpaid_days || 0, `"${(l.reason || '').replace(/"/g, '""')}"`, l.created_at, l.status].join(','))];
        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url; link.download = `leave_history_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(link); link.click(); document.body.removeChild(link);
        URL.revokeObjectURL(url);
        showToast('✅ Exported successfully!', 'success');
    } catch { showToast('Export failed.', 'error'); }
    finally { btn.innerHTML = '<i class="fas fa-download"></i> Export'; btn.disabled = false; }
}