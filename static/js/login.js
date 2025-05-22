        setTimeout(() => {
            document.getElementById('splash-screen').style.display = 'none';
            document.querySelector('.container').style.display = 'block';
        }, 3000);

        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const email = document.querySelector('input[name="email"]').value;
            fetch('/check_admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            })
            .then(response => response.json())
            .then(data => {
                if (data.is_admin) {
                    const loginType = prompt("Enter 'admin' for Admin login or 'user' for User login:");
                    if (loginType) {
                        document.getElementById('loginType').value = loginType.toLowerCase();
                        this.submit();
                    }
                } else {
                    document.getElementById('loginType').value = 'user';
                    this.submit();
                }
            });
        });
