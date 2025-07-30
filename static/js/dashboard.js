document.addEventListener("DOMContentLoaded", function () {
    const navItems = document.querySelectorAll('.sidebar-nav li[data-section]');
    const sections = document.querySelectorAll('.content-section');
    const sidebar = document.getElementById('sidebar');
    let stream = null;

    // Toggle sidebar for mobile
    if (window.innerWidth < 992) {
        sidebar.classList.add('offcanvas', 'offcanvas-start');
        const toggleBtn = document.querySelector('.toggle-btn');
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.add('show');
        });
        const closeBtn = document.getElementById('close-btn');
        closeBtn.classList.remove('d-none');
        closeBtn.addEventListener('click', () => {
            sidebar.classList.remove('show');
        });
    }

    // Navigation
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = item.getAttribute('data-section');
            if (sectionId) {
                navItems.forEach(i => {
                    i.classList.remove('active');
                    i.querySelector('a').classList.remove('active');
                });
                item.classList.add('active');
                item.querySelector('a').classList.add('active');
                sections.forEach(section => section.classList.remove('active'));
                document.getElementById(sectionId).classList.add('active');
                if (window.innerWidth < 992) {
                    sidebar.classList.remove('show');
                }
            }
        });
    });

    // Profile Edit
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const emailInput = document.getElementById('email');
    const positionInput = document.getElementById('position');
    const newFaceImageInput = document.getElementById('new-face-image');
    const profilePic = document.getElementById('profile-pic');
    const emailDisplay = document.getElementById('email-display');

    editProfileBtn.addEventListener('click', () => {
        emailInput.classList.add('active');
        positionInput.classList.add('active');
        newFaceImageInput.style.display = 'block';
        emailDisplay.style.display = 'none';
        editProfileBtn.style.display = 'none';
        saveProfileBtn.style.display = 'block';
    });

    newFaceImageInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            profilePic.src = URL.createObjectURL(file);
        }
    });

    saveProfileBtn.addEventListener('click', () => {
        const formData = new FormData();
        formData.append('email', emailInput.value);
        formData.append('position', positionInput.value);
        if (newFaceImageInput.files[0]) {
            formData.append('face_image', newFaceImageInput.files[0]);
        }
        fetch('/update_profile', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Profile updated successfully!');
                    emailDisplay.textContent = emailInput.value;
                    emailInput.classList.remove('active');
                    positionInput.classList.remove('active');
                    newFaceImageInput.style.display = 'none';
                    emailDisplay.style.display = 'inline';
                    editProfileBtn.style.display = 'block';
                    saveProfileBtn.style.display = 'none';
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error updating profile:', error));
    });

    // Camera Functionality
    const video = document.getElementById('video');
    const startCameraBtn = document.getElementById('start-camera-btn');
    const stopCameraBtn = document.getElementById('stop-camera-btn');
    const captureLoginBtn = document.getElementById('capture-login-btn');
    const captureLogoutBtn = document.getElementById('capture-logout-btn');
    const submitStatusBtn = document.getElementById('submit-status-btn');
    const canvas = document.createElement('canvas');

    function startCamera() {
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(s => {
                stream = s;
                video.srcObject = stream;
                startCameraBtn.style.display = 'none';
                stopCameraBtn.style.display = 'block';
                if (captureLoginBtn) captureLoginBtn.style.display = 'block';
                if (captureLogoutBtn) captureLogoutBtn.style.display = 'block';
            })
            .catch(err => alert('Error accessing camera: ' + err.message));
    }

    if (startCameraBtn) {
        startCameraBtn.addEventListener('click', startCamera);
    }

    if (stopCameraBtn) {
        stopCameraBtn.addEventListener('click', () => {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                video.srcObject = null;
                startCameraBtn.style.display = 'block';
                stopCameraBtn.style.display = 'none';
                if (captureLoginBtn) captureLoginBtn.style.display = 'none';
                if (captureLogoutBtn) captureLogoutBtn.style.display = 'none';
            }
        });
    }

    if (captureLoginBtn) {
        captureLoginBtn.addEventListener('click', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('face_image', blob, 'capture.jpg');
                fetch('/login_photo', { method: 'POST', body: formData })
                    .then(response => response.json())
                    .then(data => {
                        stopCameraBtn.click();
                        if (data.success) {
                            const loginTime = new Date().toLocaleString();
                            alert(`Login Successful! Time: ${loginTime}\nAttendance Submitted\nPhoto: ${data.login_photo}`);
                            location.reload();
                        } else {
                            alert(data.message);
                        }
                    })
                    .catch(error => console.error('Error capturing login:', error));
            }, 'image/jpeg');
        });
    }

    if (submitStatusBtn) {
        submitStatusBtn.addEventListener('click', () => {
            const dailyStatus = document.getElementById('daily-status').value;
            if (!dailyStatus) {
                alert('Please enter your daily status report.');
                return;
            }
            fetch('/submit_daily_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `daily_status=${encodeURIComponent(dailyStatus)}`
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Daily status submitted successfully!');
                        location.reload();
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => console.error('Error submitting status:', error));
        });
    }

    if (captureLogoutBtn) {
        captureLogoutBtn.addEventListener('click', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('face_image', blob, 'capture.jpg');
                fetch('/logout_photo', { method: 'POST', body: formData })
                    .then(response => response.json())
                    .then(data => {
                        stopCameraBtn.click();
                        if (data.success) {
                            const logoutTime = new Date().toLocaleString();
                            alert(`Logout Successful! Time: ${logoutTime}\nAttendance Submitted\nPhoto: ${data.logout_photo}`);
                            location.reload();
                        } else {
                            alert(data.message);
                        }
                    })
                    .catch(error => console.error('Error capturing logout:', error));
            }, 'image/jpeg');
        });
    }

    // Leave Request
    const submitLeaveBtn = document.getElementById('submit-leave-btn');
    submitLeaveBtn.addEventListener('click', () => {
        const startDate = document.getElementById('leave-start').value;
        const endDate = document.getElementById('leave-end').value;
        const leaveType = document.getElementById('leave-type').value;
        alert(`Leave Request Submitted!\nStart: ${startDate}\nEnd: ${endDate}\nType: ${leaveType}`);
    });

    // Notification Polling
    function checkNotifications() {
        fetch('/check_notifications')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.message) {
                    alert(`New Notification: ${data.message}`);
                    location.reload();
                }
            })
            .catch(error => console.error('Error checking notifications:', error));
    }
    setInterval(checkNotifications, 30000);
    checkNotifications();
});
