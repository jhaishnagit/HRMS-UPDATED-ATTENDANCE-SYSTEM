document.addEventListener("DOMContentLoaded", function () {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const menuToggle = document.querySelector('.menu-toggle');
    const navItems = document.querySelectorAll('.sidebar li[data-section]');
    const sections = document.querySelectorAll('.content-section');
    const errorContainer = document.createElement('div');
    errorContainer.className = 'error-message';
    document.querySelector('.flash-messages').appendChild(errorContainer);

    // Function to display errors
    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
        setTimeout(() => {
            errorContainer.style.display = 'none';
        }, 5000);
    }

    // Sidebar toggle for all screen sizes
    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        mainContent.classList.toggle('expanded', isCollapsed);
        mainContent.style.marginLeft = isCollapsed ? '0' : '280px';
    });

    // Close sidebar if clicked outside on mobile
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && !sidebar.contains(e.target) && !menuToggle.contains(e.target) && !sidebar.classList.contains('collapsed')) {
            sidebar.classList.add('collapsed');
            mainContent.classList.remove('expanded');
            mainContent.style.marginLeft = '0';
        }
    });

    // Initialize sidebar state based on screen size
    if (window.innerWidth > 768) {
        sidebar.classList.remove('collapsed');
        mainContent.classList.remove('expanded');
        mainContent.style.marginLeft = '280px';
    } else {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded');
        mainContent.style.marginLeft = '0';
    }

    // Navigation to show only one section at a time
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const sectionId = item.getAttribute('data-section');
            if (sectionId) {
                e.preventDefault();
                navItems.forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                sections.forEach(section => section.classList.remove('active'));
                const targetSection = document.getElementById(sectionId);
                targetSection.classList.add('active');
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

                if (window.innerWidth <= 768) {
                    sidebar.classList.add('collapsed');
                    mainContent.classList.remove('expanded');
                    mainContent.style.marginLeft = '0';
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
        usernameInput.classList.add('active');
        emailInput.classList.add('active');
        positionInput.classList.add('active');
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
            showError('All fields are required.');
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
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('Profile updated successfully!');
                    usernameDisplay.textContent = usernameInput.value;
                    emailDisplay.textContent = emailInput.value;
                    positionDisplay.textContent = positionInput.value;
                    usernameInput.classList.remove('active');
                    emailInput.classList.remove('active');
                    positionInput.classList.remove('active');
                    newFaceImageInput.style.display = 'none';
                    usernameDisplay.style.display = 'inline';
                    emailDisplay.style.display = 'inline';
                    positionDisplay.style.display = 'inline';
                    editProfileBtn.style.display = 'block';
                    saveProfileBtn.style.display = 'none';
                    location.reload();
                } else {
                    showError(data.message);
                }
            })
            .catch(error => {
                console.error('Error updating profile:', error);
                showError('Failed to update profile. Please try again.');
            });
    });

    // Manage Users Edit
    document.querySelectorAll('.edit-user-btn').forEach(btn => {
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

    document.querySelectorAll('.save-user-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const userId = btn.getAttribute('data-user-id');
            const row = document.getElementById(`user-${userId}`);
            const usernameInput = row.querySelector('.username-input');
            const emailInput = row.querySelector('.email-input');
            const positionInput = row.querySelector('.position-input');
            const faceImageInput = row.querySelector('.face-image-input');
            if (!usernameInput.value || !emailInput.value || !positionInput.value) {
                showError('All fields are required.');
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
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
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
                        showError(data.message);
                    }
                })
                .catch(error => {
                    console.error('Error updating user:', error);
                    showError('Failed to update user. Please try again.');
                });
        });
    });

    // Rota Upload
    document.getElementById('upload-rota-btn').addEventListener('click', () => {
        const fileInput = document.getElementById('rota-image');
        if (!fileInput.files[0]) {
            showError('Please select a file to upload.');
            return;
        }
        const formData = new FormData();
        formData.append('rota_image', fileInput.files[0]);
        fetch('/upload_rota', { method: 'POST', body: formData })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('Rota uploaded successfully!');
                    location.reload();
                } else {
                    showError(data.message);
                }
            })
            .catch(error => {
                console.error('Error uploading rota:', error);
                showError('Failed to upload rota. Please try again.');
            });
    });

    // Send Notification
    document.getElementById('send-notification-btn').addEventListener('click', () => {
        const message = document.getElementById('notification-message').value;
        if (!message.trim()) {
            showError('Please enter a notification message.');
            return;
        }
        fetch('/send_notification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `message=${encodeURIComponent(message)}`
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('Notification sent successfully!');
                    document.getElementById('notification-message').value = '';
                } else {
                    showError(data.message);
                }
            })
            .catch(error => {
                console.error('Error sending notification:', error);
                showError('Failed to send notification. Please try again.');
            });
    });

    // Approve/Reject Attendance
    document.querySelectorAll('.approve-btn, .reject-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const attendanceId = btn.getAttribute('data-attendance-id');
            const status = btn.classList.contains('approve-btn') ? 'Present' : 'Absent';
            fetch(`/update_attendance_status/${attendanceId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `status=${status}`
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        alert('Attendance status updated!');
                        location.reload();
                    } else {
                        showError(data.message);
                    }
                })
                .catch(error => {
                    console.error('Error updating attendance:', error);
                    showError('Failed to update attendance status. Please try again.');
                });
        });
    });

    // Search bar functionality for users and attendance
    const searchInput = document.querySelector('.search-bar input[name="search"]');
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            const query = this.value.toLowerCase().trim();
            const userRows = document.querySelectorAll('#users table tbody tr');
            const attendanceRows = document.querySelectorAll('#attendance table tbody tr');
            const dashboardRows = document.querySelectorAll('#dashboard table tbody tr');

            userRows.forEach(row => {
                const username = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '';
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
    }
});
