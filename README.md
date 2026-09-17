## Tech Stack

### Backend

- **Python 3.12+**: Core language for the application.

- **Flask**: Web framework for routing, templates, and sessions.

- **MySQL**: Database for storing users, attendance, rotas, notifications, and updates.

- **mysql-connector-python**: Python driver for MySQL interactions.

- **Werkzeug**: For password hashing and security utilities.

- **face_recognition & dlib**: For facial recognition during login/logout.

- **numpy & pillow**: For image processing and handling.

- **geocoder**: For capturing GPS location via IP.

- **pandas & openpyxl**: For generating and exporting Excel reports.

- **smtplib**: For sending OTP emails during password reset.

- **dotenv**: For loading environment variables (e.g., DB credentials, SMTP settings).

### Frontend

- **HTML5/CSS3/JavaScript**: Core web technologies for UI.

- **Bootstrap 5**: For responsive design and components (e.g., cards, tables, modals).

- **Font Awesome**: For icons.

- **Custom JS**: Handles camera access, form submissions, and dynamic UI (e.g., editing profiles, capturing photos).

### Other Tools

- **OpenCV (cv2)**: Implicitly used via face_recognition for image capture/processing.

- **Requirements.txt**: Lists all Python dependencies for easy installation via `pip install -r requirements.txt`.

### Deployment Considerations

- **Environment**: Local development (runs on `http://127.0.0.1:5000`).

- **Security**: Uses session-based authentication; store secrets in `.env` file.

- **Browser Compatibility**: Modern browsers with camera access (Chrome, Firefox recommended).

## Installation and Setup

### Prerequisites

- Python 3.12+ installed.

- MySQL server running (e.g., via XAMPP or standalone).

- Webcam for face recognition.

- SMTP server (e.g., Gmail) for password reset emails.

### Steps

1. **Clone the Repository**:

   ```

   git clone <https://github.com/jhaishnagit/HRMS-UPDATED-ATTENDANCE-SYSTEM.git>

   cd <project-directory>

   ```

2. **Install Dependencies**:

   ```

   pip install -r requirements.txt

   ```

   - Note: `face_recognition` and `dlib` may require additional setup (e.g., CMake for dlib on Windows/Mac).

3. **Set Up Environment Variables**:

   Create a `.env` file in the root directory with:

   ```

   FLASK_SECRET_KEY=your_secret_key

   DB_HOST=localhost

   DB_USER=root

   DB_PASSWORD=your_db_password

   DB_NAME=gps_face_db

   DB_PORT=3306

   MAIL_USERNAME=enter the email

   MAIL_PASSWORD=enter the password
   
   MAIL_SERVER=smtp.zoho.com

   ```

   - Generate `FLASK_SECRET_KEY` securely (e.g., via `os.urandom(24)`).

   - For Gmail SMTP, enable "App Passwords" in Google Account settings.
    
     For Zoho SMTP, enable "MFA(Multi Factor Authentication)" in Zoho My Account settings.


4. **Database Initialization**:

   - Start MySQL server.

   - Run the app once: `python app.py` (it auto-initializes the schema via `init_db()`).

5. **Run the Application**:

   ```

   python app.py

   ```

   - Access at `http://localhost:8000`.

   - Register as a user (capture face image during registration).

   - For admin access, manually set `is_admin=1` in the `users` table for a user.

6. **Uploads Directory**:

   - Created automatically at `./static/Uploads` for photos.

### Common Issues

- **Camera Access**: Ensure browser permissions; test on HTTPS for production.

- **Face Recognition Errors**: Requires good lighting; install dlib properly.

- **SMTP Errors**: Verify app password and less secure apps (if using Gmail).

- **Database Connection**: Check `.env` credentials match MySQL setup.

## Database queries

select * from attendance;
describe attendance;
select * from users;
select * from rota;
select * from daily_updates;
select * from notifications;
show tables;
show databases;
use gps_face_db;


-- Checking the Attendance from one date to another date by user_id
SELECT id,user_id,login_time,logout_time,login_photo_path,logout_photo_path,login_latitude,login_longitude,logout_latitude,logout_longitude FROM attendance WHERE user_id = 2 AND login_time BETWEEN '2025-01-01' AND '2025-08-31'ORDER BY login_time ASC;
 
    
-- Date Range with User_id and Username( Attendance Checking)2
SELECT  
@rownum := @rownum + 1 AS serial_number,u.id AS user_id,u.username,DATE_FORMAT(a.login_time, '%Y-%m-%d %H:%i:%s') AS login_time,DATE_FORMAT(a.logout_time, '%Y-%m-%d %H:%i:%s') AS logout_time,a.attendance_status,TIMEDIFF(a.logout_time, a.login_time) AS work_duration
FROM  (SELECT @rownum := 0) r,users u JOIN attendance a ON u.id = a.user_id WHERE u.id = 65 AND a.login_time BETWEEN '2025-08-14' AND '2025-09-30'ORDER BY a.login_time ASC;
    
-- Date filtering  (checking in login and logout)
SELECT @rownum := @rownum + 1 AS s_no, u.id as user_id,a.id as attendance_id,u.username,a.login_time,a.logout_time,a.login_latitude,a.login_longitude,a.logout_latitude,a.logout_longitude
FROM (SELECT @rownum := 0) r,attendance a JOIN users u ON a.user_id = u.id WHERE DATE(a.login_time) = '2025-09-01';


-- Daily Status report with Date 
SELECT u.username,d.user_id,d.update_message,d.submitted_at FROM daily_updates d
JOIN users u ON d.user_id = u.id WHERE DATE(d.submitted_at) = '2025-08-28';

-- Daily Status for excel sheet  
SELECT u.username,d.update_message FROM daily_updates d
JOIN users u ON d.user_id = u.id WHERE DATE(d.submitted_at) = '2025-09-01';

## Application Structure

### Routes and Functionality

#### Public Routes

- `/` (GET): Redirects to login.

- `/login` (GET/POST): Handles user login (email/password, face optional). Supports admin/employee modes.

- `/register` (GET/POST): User registration with username, email, password, and face image.

- `/forgot_password` (GET/POST): Sends OTP to email for reset.

- `/verify_otp` (POST): Verifies OTP.

- `/reset_password` (GET/POST): Resets password after OTP verification.

#### User Routes (Requires Login, Non-Admin)

- `/dashboard` (GET): User dashboard showing attendance, last login/logout, calendar, rota, etc.

- `/login_photo` (POST): Captures login photo, verifies face, records GPS/time.

- `/submit_daily_status` (POST): Submits daily report before logout.

- `/logout_photo` (POST): Captures logout photo, verifies face, records GPS/time.

- `/update_profile` (POST): Updates user email, position, face image.

- `/check_notifications` (GET): Polls for unread notifications.

#### Admin Routes (Requires Login, is_admin=1)

- `/admin` (GET): Admin dashboard with attendance overview, user management, rota upload, notifications.

- `/admin_update_user/<user_id>` (POST): Updates user details (username, email, position, face).

- `/upload_rota` (POST): Uploads weekly rota image.

- `/send_notification` (POST): Sends message to all non-admins.

- `/update_attendance_status/<attendance_id>` (POST): Marks attendance as Present/Absent.

- `/view_excel` (GET): Views attendance in table format.

- `/export` (GET): Downloads attendance as Excel file.

#### Shared Routes

- `/logout` (GET): Clears session and logs out.

### Key Logic

- **Face Recognition**: Uses `face_recognition` to compare captured photo with stored user face encoding.

- **GPS**: Uses `geocoder.ip('me')` for location (IP-based; not precise, for demo).

- **Sessions**: Stores user_id, username, is_admin for authentication.

- **Emails**: SMTP for OTPs (configurable via .env).

- **Exports**: Pandas generates Excel from attendance data.

- **Logging**: Basic logging for debugging.

### Templates

- **login.html**: Login form.

- **register.html**: Registration form with face upload.

- **forgot_password.html**: Email input for OTP.

- **reset_password.html**: New password form.

- **dashboard.html**: User UI with sections (attendance, rota, etc.).

- **admin.html**: Admin UI with management tools.

- **view_excel.html**: Attendance table view.

- **export.html**: Export button page.

### Static Files

- **CSS/JS**: dashboard.css/js, admin.css/js for UI interactions (e.g., camera, edits).

- **Uploads**: Stores photos (login/logout).

## User Guide

### For Employees (Users)

1. **Register**: Visit `/register`, provide details and face photo.

2. **Login**: Use email/password at `/login`.

3. **Dashboard**:

   - Capture login photo (face verification required).

   - Submit daily status before logout.

   - Capture logout photo.

   - View 30-day calendar, rota, notifications, policies.

4. **Profile**: Edit email/position/face.

5. **Logout**: Clears session.

### For Admins

1. **Login**: Use `/login` with admin credentials.

2. **Dashboard**:

   - View/manage attendance (daily/weekly/monthly/yearly).

   - Manage users (edit details).

   - Upload rota images.

   - Send notifications.

   - View read notifications report.

   - Export attendance to Excel.

3. **Search**: Filter users/attendance by username.

### Password Recovery

- Forgot password: Enter email for OTP.

- Verify OTP and reset password.

**

Docker Containerization

The HRMS Attendance Management System can be containerized using Docker. Docker packages the Flask backend, frontend files, Python dependencies, and required system libraries into a portable application image.

Dockerfile

The project uses the following Dockerfile configuration:

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ ./backend/
COPY frontend/ ./frontend/

COPY .env /app/backend/.env

WORKDIR /app/backend

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]

Docker Prerequisites

Docker Desktop installed and running.

The project must contain backend/, frontend/, and Dockerfile.

backend/requirements.txt must contain valid package requirements.

MySQL must be available to the container. If MySQL is running on the host machine, the database host configuration must be adjusted appropriately for the Docker environment.

Build the Docker Image

Open PowerShell in the project root:

cd D:\HRMS-PROJECT\HRMS_AttendanceSystem

Build a fresh image:

docker build --no-cache -t hrms-attendance:latest .

The --no-cache option forces Docker to rebuild the application layers and is useful after source-code or dependency changes.

Run the Docker Container

Start the HRMS application:

docker run -d --name hrms-attendance -p 5000:5000 hrms-attendance:latest

The Flask application listens on port 5000 inside the container and the host port 5000 is mapped to it.

Check running containers:

docker ps

Check all containers, including stopped containers:

docker ps -a

View application logs:

docker logs hrms-attendance

Docker Image Versioning

For testing a new version before replacing the latest tag:

docker build --no-cache -t hrms-attendance:v2 .

Run the test version:

docker run -d --name hrms-attendance-v2 -p 5000:5000 hrms-attendance:v2

Check the available images:

docker images

Docker Hub Deployment

The HRMS Docker image can be tagged for the Docker Hub repository:

docker tag hrms-attendance:latest anil4625/hrms-attendance:latest

Push the image:

docker push anil4625/hrms-attendance:latest

For a versioned Docker Hub image:

docker tag hrms-attendance:v2 anil4625/hrms-attendance:v2
docker push anil4625/hrms-attendance:v2

Updating an Existing HRMS Image

When the HRMS source code is changed, rebuild the image from the project root:

docker build --no-cache -t hrms-attendance:latest .

If an old container exists, remove it before starting the newly built container:

docker rm -f hrms-attendance

Then run the updated image:

docker run -d --name hrms-attendance -p 5000:5000 hrms-attendance:latest

Docker Requirements File

The backend/requirements.txt file must contain package names only. For example:

Flask
Werkzeug
mysql-connector-python
face_recognition
dlib
numpy
Pillow
geocoder
pandas
openpyxl
python-dotenv

Do not write installation commands such as:

pip install Werkzeug

Instead, use:

Werkzeug

Otherwise, Docker will fail at:

RUN pip install --no-cache-dir -r requirements.txt

with an Invalid requirement error.

Environment Variables and Security

The application uses .env values for Flask, MySQL, and SMTP configuration. Do not commit real passwords, SMTP credentials, application passwords, or secret keys to Git.

For production deployments, it is preferable to provide secrets at container runtime rather than permanently copying .env into the Docker image. A runtime example is:

docker run -d `
  --name hrms-attendance `
  -p 5000:5000 `
  --env-file .env `
  hrms-attendance:latest

If the Dockerfile is changed to use runtime environment variables, the line below should not be required:

COPY .env /app/backend/.env

Docker Troubleshooting

Build fails with Invalid requirement:

Check backend/requirements.txt for lines beginning with pip install. Replace them with package names.

Container exits immediately:

Check:

docker ps -a
docker logs hrms-attendance

Port 5000 is already in use:

Use another host port, for example:

docker run -d --name hrms-attendance -p 5001:5000 hrms-attendance:latest

Then access the application through the mapped host port.

Database connection fails:

Check the database host, port, username, password, and database name. When the database is outside the container, localhost refers to the container itself, not the Windows host.

Docker Deployment Workflow

The recommended workflow for an updated HRMS release is:

Update the HRMS source code.

Verify backend/requirements.txt.

Build a fresh Docker image:(docker build --no-cache -t hrms-attendance:latest .)

Run the container locally:(docker run -d --name hrms-attendance -p 5000:5000 hrms-attendance:latest)

Check docker logs:(docker logs hrms-attendance)

Test login, face recognition, attendance, daily status, notifications, rota, and Excel export.

Tag the tested image for Docker Hub.

Push the image to Docker Hub.

Deploy the tested image to the target environment.

Troubleshooting**

- **DB Connection Failed**: Check MySQL running and .env credentials.

- **Face Recognition Issues**: Ensure dlib installed; good lighting/camera.

- **Email Errors**: Verify SMTP settings; check spam/junk for OTPs.

- **Camera Not Working**: Browser permissions; use HTTPS in production.

- **Exports Fail**: Ensure pandas/openpyxl installed.

- **Logs**: Check console for errors (logging set to INFO).