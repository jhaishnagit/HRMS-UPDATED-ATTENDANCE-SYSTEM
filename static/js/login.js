document.addEventListener('DOMContentLoaded', () => {
    // Show splash screen for 3 seconds, then display login form
    setTimeout(() => {
        document.getElementById('splash-screen').style.display = 'none';
        document.querySelector('.container').style.display = 'block';
    }, 3000);

    // Handle form submission
    const loginForm = document.getElementById('loginForm');
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        // Log form submission attempt
        console.log('Form submission initiated');

        const email = document.querySelector('input[name="email"]').value;
        const password = document.querySelector('input[name="password"]').value;

        // Client-side validation
        if (!email || !password) {
            alert('Please fill in all fields.');
            console.error('Validation failed: Missing email or password');
            return;
        }

        // Disable submit button to prevent multiple submissions
        const submitButton = loginForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.textContent = 'Logging in...';
        console.log('Form data:', { email });

        const formData = new FormData(loginForm);
        fetch('/login', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            submitButton.disabled = false;
            submitButton.textContent = 'Login';
            if (data.success) {
                if (data.is_admin) {
                    document.getElementById('adminModal').style.display = 'flex';
                    document.getElementById('userDashBtn').onclick = () => {
                        window.location.href = '/dashboard';
                    };
                    document.getElementById('adminDashBtn').onclick = () => {
                        window.location.href = '/admin';
                    };
                } else {
                    window.location.href = '/dashboard';
                }
            } else {
                alert(data.message);
            }
        })
        .catch(error => {
            submitButton.disabled = false;
            submitButton.textContent = 'Login';
            console.error('Error during login:', error);
            alert('An error occurred during login.');
        });
    });
});
