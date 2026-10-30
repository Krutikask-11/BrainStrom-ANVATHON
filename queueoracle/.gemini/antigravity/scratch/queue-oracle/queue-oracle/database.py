"""
QUEUE ORACLE - Database Layer (SQLite)
Modular, transparent, and easy to explain for evaluation.
Provides SQLite initialization, connection context, and table schemas.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "hospital.db")

def get_db_connection():
    """Returns a connection to the SQLite database with row_factory set for dictionary-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initializes all required database tables for Queue Oracle."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Departments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        total_beds INTEGER DEFAULT 40,
        occupied_beds INTEGER DEFAULT 20,
        avg_consult_time INTEGER DEFAULT 12,
        base_staff INTEGER DEFAULT 8
    )
    """)

    # 2. Doctors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        specialization TEXT NOT NULL,
        is_available INTEGER DEFAULT 1,
        avg_consult_time INTEGER DEFAULT 12,
        room_no TEXT NOT NULL
    )
    """)

    # 3. Patients Table (Queue and status tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        opd_token INTEGER NOT NULL,
        department TEXT NOT NULL,
        arrival_time TEXT NOT NULL,
        assigned_doctor_id INTEGER NOT NULL,
        priority TEXT NOT NULL CHECK(priority IN ('Normal', 'Medium', 'Emergency')),
        estimated_duration INTEGER DEFAULT 12,
        actual_consultation_duration INTEGER DEFAULT 0,
        predicted_wait_time INTEGER DEFAULT 0,
        expected_consultation_time TEXT DEFAULT '',
        status TEXT NOT NULL CHECK(status IN ('WAITING', 'CALLED', 'IN_CONSULTATION', 'COMPLETED')),
        queue_position INTEGER DEFAULT 1,
        delay_minutes INTEGER DEFAULT 0,
        disease_tag TEXT DEFAULT 'General Checkup',
        FOREIGN KEY (assigned_doctor_id) REFERENCES doctors (id)
    )
    """)

    # 4. Hospital Beds Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS beds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT NOT NULL,
        bed_number TEXT NOT NULL,
        status TEXT CHECK(status IN ('AVAILABLE', 'OCCUPIED')) DEFAULT 'AVAILABLE',
        patient_name TEXT DEFAULT NULL,
        admission_time TEXT DEFAULT NULL,
        expected_discharge_hours REAL DEFAULT 24.0
    )
    """)

    # 5. Disease Aggregate Records Table (Epidemiology / Hospital Preparedness)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS disease_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        disease_name TEXT NOT NULL,
        cases_count INTEGER NOT NULL,
        suspected_count INTEGER NOT NULL,
        department TEXT NOT NULL
    )
    """)

    # 6. Inventory & Medicine Preparedness Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        category TEXT NOT NULL,
        available_qty INTEGER NOT NULL,
        min_stock INTEGER NOT NULL,
        daily_usage INTEGER NOT NULL,
        unit TEXT NOT NULL,
        associated_disease TEXT DEFAULT NULL
    )
    """)

    # 7. Consultation History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consultation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        doctor_id INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        scheduled_duration INTEGER,
        actual_duration INTEGER,
        delay_recorded INTEGER DEFAULT 0
    )
    """)

    # 8. Administrator Recommendations & Decision Support Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        problem TEXT NOT NULL,
        supporting_data TEXT NOT NULL,
        predicted_impact TEXT NOT NULL,
        recommended_action TEXT NOT NULL,
        expected_benefit TEXT NOT NULL,
        priority TEXT NOT NULL CHECK(priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
        status TEXT NOT NULL CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED')) DEFAULT 'PENDING',
        doctor_from_id INTEGER DEFAULT NULL,
        doctor_to_id INTEGER DEFAULT NULL,
        patient_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()
    print("[DB] SQLite database initialized successfully.")

if __name__ == "__main__":
    init_db()
