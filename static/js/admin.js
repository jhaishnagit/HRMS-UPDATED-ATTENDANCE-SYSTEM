document.addEventListener("DOMContentLoaded", function () {
    const navItems = document.querySelectorAll('.sidebar-nav li[data-section]');
    const sections = document.querySelectorAll('.content-section');
    const sidebar = document.getElementById('sidebar');

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

    // Admin Profile Edit
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const positionInput = document.getElementById('position');
    const newFaceImageInput = document.getElementById('new-face-image');
    const profilePic = document.getElementById('profile-pic');
    const usernameDisplay = document.getElementById('username-display');
    const emailDisplay = document.getElementById('email-display');
    const positionDisplay = document.getElementById('position-display');

    editProfileBtn.addEventListener('click', () => {
        usernameInput.style.display = 'block';
        emailInput.style.display = 'block';
        positionInput.style.display = 'block';
        newFaceImageInput.style.display = 'block';
        usernameDisplay.style.display = 'none';
        emailDisplay.style.display = 'none';
        positionDisplay.style.display = 'none';
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
        if (!usernameInput.value || !emailInput.value || !positionInput.value) {
            alert('All fields are required.');
            return;
        }
        const formData = new FormData();
        formData.append('username', usernameInput.value);
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
                    usernameDisplay.textContent = usernameInput.value;
                    emailDisplay.textContent = emailInput.value;
                    positionDisplay.textContent = positionInput.value;
                    usernameInput.style.display = 'none';
                    emailInput.style.display = 'none';
                    positionInput.style.display = 'none';
                    newFaceImageInput.style.display = 'none';
                    usernameDisplay.style.display = 'inline';
                    emailDisplay.style.display = 'inline';
                    positionDisplay.style.display = 'inline';
                    editProfileBtn.style.display = 'block';
                    saveProfileBtn.style.display = 'none';
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => {
                console.error('Error updating profile:', error);
                alert('Failed to update profile. Please try again.');
            });
    });

    // Update Attendance Status
    const updateForms = document.querySelectorAll('.update-status-form');
    updateForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const attendanceId = form.getAttribute('data-attendance-id');
            const status = form.querySelector('select[name="status"]').value;
            const formData = new FormData();
            formData.append('status', status);
            fetch(`/update_attendance_status/${attendanceId}`, { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Attendance status updated successfully!');
                        location.reload();
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => console.error('Error updating status:', error));
        });
    });

    // Update User
    const editUserBtns = document.querySelectorAll('.edit-user-btn');
    editUserBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const userId = btn.getAttribute('data-user-id');
            const row = document.getElementById(`user-${userId}`);
            row.querySelector('.username-display').style.display = 'none';
            row.querySelector('.email-display').style.display = 'none';
            row.querySelector('.position-display').style.display = 'none';
            row.querySelector('.username-input').style.display = 'block';
            row.querySelector('.email-input').style.display = 'block';
            row.querySelector('.position-input').style.display = 'block';
            row.querySelector('.face-image-input').style.display = 'block';
            btn.style.display = 'none';
            row.querySelector('.save-user-btn').style.display = 'block';
        });
    });

    const saveUserBtns = document.querySelectorAll('.save-user-btn');
    saveUserBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const userId = btn.getAttribute('data-user-id');
            const row = document.getElementById(`user-${userId}`);
            const usernameInput = row.querySelector('.username-input');
            const emailInput = row.querySelector('.email-input');
            const positionInput = row.querySelector('.position-input');
            const faceImageInput = row.querySelector('.face-image-input');
            if (!usernameInput.value || !emailInput.value || !positionInput.value) {
                alert('All fields are required.');
                return;
            }
            const formData = new FormData();
            formData.append('username', usernameInput.value);
            formData.append('email', emailInput.value);
            formData.append('position', positionInput.value);
            if (faceImageInput.files[0]) {
                formData.append('face_image', faceImageInput.files[0]);
            }
            fetch(`/admin_update_user/${userId}`, { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('User updated successfully!');
                        row.querySelector('.username-display').textContent = usernameInput.value;
                        row.querySelector('.email-display').textContent = emailInput.value;
                        row.querySelector('.position-display').textContent = positionInput.value;
                        if (faceImageInput.files[0]) {
                            row.querySelector('.user-pic').src = URL.createObjectURL(faceImageInput.files[0]);
                        }
                        row.querySelector('.username-display').style.display = 'block';
                        row.querySelector('.email-display').style.display = 'block';
                        row.querySelector('.position-display').style.display = 'block';
                        row.querySelector('.username-input').style.display = 'none';
                        row.querySelector('.email-input').style.display = 'none';
                        row.querySelector('.position-input').style.display = 'none';
                        row.querySelector('.face-image-input').style.display = 'none';
                        btn.style.display = 'none';
                        row.querySelector('.edit-user-btn').style.display = 'block';
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => {
                    console.error('Error updating user:', error);
                    alert('Failed to update user. Please try again.');
                });
        });
    });

    // Upload Rota
    const uploadRotaForm = document.getElementById('upload-rota-form');
    if (uploadRotaForm) {
        uploadRotaForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(uploadRotaForm);
            fetch('/upload_rota', { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Rota uploaded successfully!');
                        location.reload();
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => console.error('Error uploading rota:', error));
        });
    }

    // Send Notification
    const sendNotificationForm = document.getElementById('send-notification-form');
    if (sendNotificationForm) {
        sendNotificationForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(sendNotificationForm);
            fetch('/send_notification', { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Notification sent successfully!');
                        sendNotificationForm.reset();
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => console.error('Error sending notification:', error));
        });
    }

    // Search Functionality
    const searchInputs = document.querySelectorAll('.search-form input[name="search"]');
    searchInputs.forEach(input => {
        input.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            const userRows = document.querySelectorAll('#users table tbody tr');
            const attendanceRows = document.querySelectorAll('#attendance table tbody tr');
            const dashboardRows = document.querySelectorAll('#dashboard table tbody tr');

            userRows.forEach(row => {
                const username = row.querySelector('td:nth-child(2) .username-display')?.textContent.toLowerCase() || '';
                row.style.display = username.includes(query) ? '' : 'none';
            });

            attendanceRows.forEach(row => {
                const username = row.querySelector('td:nth-child(1)')?.textContent.toLowerCase() || '';
                row.style.display = username.includes(query) ? '' : 'none';
            });

            dashboardRows.forEach(row => {
                const username = row.querySelector('td:nth-child(1)')?.textContent.toLowerCase() || '';
                row.style.display = username.includes(query) ? '' : 'none';
            });
        });
    });
});
