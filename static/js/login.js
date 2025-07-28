document.addEventListener('DOMContentLoaded', () => {
    // Show splash screen for 3 seconds, then display login form
    setTimeout(() => {
        document.getElementById('splash-screen').style.display = 'none';
        document.querySelector('.container').style.display = 'block';
    }, 3000);

    // Handle form submission
    const loginForm = document.getElementById('loginForm');
    loginForm.addEventListener('submit', function(e) {
        // Log form submission attempt
        console.log('Form submission initiated');

        const email = document.querySelector('input[name="email"]').value;
        const password = document.querySelector('input[name="password"]').value;
        const loginType = document.querySelector('select[name="login_type"]').value;

        // Client-side validation
        if (!email || !password || !loginType) {
            e.preventDefault(); // Prevent submission if validation fails
            alert('Please fill in all fields.');
            console.error('Validation failed: Missing email, password, or login type');
            return;
        }

        // Disable submit button to prevent multiple submissions
        const submitButton = loginForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.textContent = 'Logging in...';
        console.log('Form data:', { email, loginType });

        // Allow native form submission
    });
});
