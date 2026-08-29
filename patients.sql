-- 1. Create and select database
CREATE DATABASE IF NOT EXISTS hospital_db;
USE hospital_db;

-- 2. Create Patients Table
CREATE TABLE IF NOT EXISTS patients (
    bed_id INT PRIMARY KEY,
    patient_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    hr VARCHAR(20),
    bp VARCHAR(20),
    spo2 VARCHAR(20),
    temp VARCHAR(20)
);

-- 3. Seed Initial Dummy Data
INSERT INTO patients (bed_id, patient_name, status, hr, bp, spo2, temp) VALUES
(1, 'M. Owusu', 'normal', '76 bpm', '118/76', '98%', '36.8°C'),
(2, 'S. Krishnan', 'normal', '68 bpm', '122/80', '99%', '36.6°C'),
(3, 'R. Fernandez', 'critical', '104 bpm', '168/104', '94%', '37.9°C'),
(4, 'A. Lindqvist', 'normal', '80 bpm', '116/74', '97%', '36.7°C'),
(5, 'J. Achebe', 'warning', '92 bpm', '138/88', '96%', '37.1°C'),
(6, 'Empty Bed', 'empty', '-', 'No patient assigned', '-', '-')
ON DUPLICATE KEY UPDATE patient_name=VALUES(patient_name);