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
    const newFaceImageInput = document.getElementById('new-face-image');
    const profilePic = document.getElementById('profile-pic');
    const emailDisplay = document.getElementById('email-display');

    editProfileBtn.addEventListener('click', () => {
        emailInput.classList.add('active');
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

    // Update User
    window.updateUser = function(userId) {
        const formData = new FormData();
        formData.append('username', document.getElementById(`username-${userId}`).value);
        formData.append('email', document.getElementById(`email-${userId}`).value);
        formData.append('position', document.getElementById(`position-${userId}`).value);
        const faceImage = document.getElementById(`face-image-${userId}`).files[0];
        if (faceImage) {
            formData.append('face_image', faceImage);
        }
        fetch(`/admin_update_user/${userId}`, { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('User updated successfully!');
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error updating user:', error));
    };

    // Update Attendance Status
    window.updateStatus = function(attendanceId, status) {
        const formData = new FormData();
        formData.append('status', status);
        fetch(`/update_attendance_status/${attendanceId}`, { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Status updated!');
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error updating status:', error));
    };

    // Rota Form Submit
    const rotaForm = document.getElementById('rota-form');
    rotaForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(rotaForm);
        fetch('/upload_rota', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Rota uploaded!');
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error uploading rota:', error));
    });

    // Notification Form Submit
    const notificationForm = document.getElementById('notification-form');
    notificationForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(notificationForm);
        fetch('/send_notification', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Notification sent!');
                    notificationForm.reset();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error sending notification:', error));
    });
});
