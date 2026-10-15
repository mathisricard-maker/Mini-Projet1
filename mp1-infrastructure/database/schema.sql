-- Schéma de la base mp1_surveillance (MariaDB)
-- Peut être relancé sans erreur : les tables existantes sont conservées.
CREATE DATABASE IF NOT EXISTS mp1_surveillance;
USE mp1_surveillance;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100),
    role ENUM('admin', 'user', 'viewer') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Événements du capteur PIR (ESP32)
CREATE TABLE IF NOT EXISTS pir_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration INT,
    status ENUM('active', 'inactive'),
    INDEX (timestamp)
);

-- Événements de la caméra (groupe vidéo)
CREATE TABLE IF NOT EXISTS video_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id VARCHAR(50),
    event_type VARCHAR(50),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    image_path VARCHAR(255),
    description TEXT,
    INDEX (timestamp)
);

-- Photos stockées sur le Pi (server/uploads/images)
CREATE TABLE IF NOT EXISTS images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT,
    file_path VARCHAR(255) NOT NULL,
    file_name VARCHAR(255),
    size INT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES video_events(id),
    INDEX (timestamp)
);

-- État actuel de la salle 215 (une seule ligne, id = 1)
CREATE TABLE IF NOT EXISTS room_status (
    id INT AUTO_INCREMENT PRIMARY KEY,
    status ENUM('libre', 'occupee', 'reservee') DEFAULT 'libre',
    last_update DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    reason VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    level ENUM('INFO', 'WARNING', 'ERROR') DEFAULT 'INFO',
    message TEXT,
    source VARCHAR(100),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX (timestamp, level)
);

INSERT INTO room_status (id, status, reason) VALUES (1, 'libre', 'Initial')
ON DUPLICATE KEY UPDATE id = id;
