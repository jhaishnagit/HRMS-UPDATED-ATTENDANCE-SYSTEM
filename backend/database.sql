CREATE DATABASE IF NOT EXISTS gps_face_recognition;
USE gps_face_recognition;

SHOW TABLES;

-- attendance
CREATE TABLE `attendance` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `login_time` datetime DEFAULT NULL,
  `logout_time` datetime DEFAULT NULL,
  `login_photo_path` varchar(255) DEFAULT NULL,
  `logout_photo_path` varchar(255) DEFAULT NULL,
  `login_latitude` float DEFAULT NULL,
  `login_longitude` float DEFAULT NULL,
  `logout_latitude` float DEFAULT NULL,
  `logout_longitude` float DEFAULT NULL,
  `daily_status_submitted` tinyint DEFAULT '0',
  `admin_verified` tinyint DEFAULT '0',
  `attendance_status` enum('Present','Absent') DEFAULT 'Absent',
  `daily_status` text,
  `status` text,
  PRIMARY KEY (`id`)
);

-- daily_updates
CREATE TABLE `daily_updates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `update_message` text,
  `submitted_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `is_verified` tinyint DEFAULT '0',
  `verification_status` enum('Pending','Approved','Rejected') DEFAULT 'Pending',
  `verified_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
);

-- holidays
CREATE TABLE `holidays` (
  `id` int NOT NULL AUTO_INCREMENT,
  `holiday_date` date DEFAULT NULL,
  `holiday_name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
);

-- leave_balance
CREATE TABLE `leave_balance` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `total_annual_leaves` int DEFAULT '12',
  `paid_leaves` int DEFAULT '12',
  `compensation_leaves` int DEFAULT '0',
  `last_updated` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

-- leaves
CREATE TABLE `leaves` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `leave_type` enum('Paid Leave','Sick Leave','Emergency Leave') DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `reason` text,
  `status` enum('Pending','Approved','Rejected') DEFAULT 'Pending',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `total_days` int DEFAULT NULL,
  `used_unpaid_days` int DEFAULT '0',
  `used_paid_days` int DEFAULT '0',
  `used_comp_days` int DEFAULT '0',
  `holiday_days` int DEFAULT '0',
  `remarks` text,
  PRIMARY KEY (`id`)
);

-- notifications
CREATE TABLE `notifications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `message` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_read` tinyint DEFAULT '0',
  `read_at` timestamp NULL DEFAULT NULL,
  `mark_done` tinyint DEFAULT '0',
  `mark_done_at` timestamp NULL DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

-- rota
CREATE TABLE `rota` (
  `id` int NOT NULL AUTO_INCREMENT,
  `rota_image` longblob,
  `uploaded_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `holiday_table` mediumtext,
  PRIMARY KEY (`id`)
);

-- users
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `face_image` longblob,
  `position` varchar(100) DEFAULT 'Employee',
  `is_admin` tinyint DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `dob` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);


CREATE TABLE daily_tasks (

    id INT AUTO_INCREMENT PRIMARY KEY,

    employee_id INT NOT NULL,

    project_name VARCHAR(255) NOT NULL,

    task_name VARCHAR(255) NOT NULL,

    time_period VARCHAR(100),

    status ENUM('Pending','Approved','Rejected')
    DEFAULT 'Pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);