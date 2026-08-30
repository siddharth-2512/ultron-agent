import sqlite3

conn = sqlite3.connect("hospital.db")
cursor = conn.cursor()

# 1. Patient Telemetry Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS patients (
    bed_id INTEGER PRIMARY KEY,
    patient_name TEXT,
    status TEXT,
    hr TEXT,
    bp TEXT,
    spo2 TEXT,
    temp TEXT
)
""")

patients = [
    (1, 'M. Owusu', 'normal', '76 bpm', '118/76', '98%', '36.8°C'),
    (2, 'S. Krishnan', 'normal', '68 bpm', '122/80', '99%', '36.6°C'),
    (3, 'R. Fernandez', 'critical', '104 bpm', '168/104', '94%', '37.9°C'),
    (4, 'A. Lindqvist', 'normal', '80 bpm', '116/74', '97%', '36.7°C'),
    (5, 'J. Achebe', 'warning', '92 bpm', '138/88', '96%', '37.1°C'),
    (6, 'Empty Bed', 'empty', '-', 'No patient assigned', '-', '-')
]

cursor.executemany("INSERT OR REPLACE INTO patients VALUES (?, ?, ?, ?, ?, ?, ?)", patients)

# 2. Analytics: Fall Alerts Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS fall_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bed_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence_score REAL,
    status TEXT DEFAULT 'UNACKNOWLEDGED'
)
""")

# 3. Analytics: LLM Query Logs Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_prompt TEXT NOT NULL,
    llm_response TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
print("hospital.db updated with analytics tables successfully!")