"""
QUEUE ORACLE - Prediction & Dynamic Queue Recalculation Engine
Uses the trained Random Forest Regression model to predict patient waiting times
and dynamically recalculates queue wait times whenever delays, early completions,
or status updates occur.
"""

import os
import datetime
import numpy as np
import pandas as pd
import joblib
from database import get_db_connection

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
RF_MODEL_PATH = os.path.join(MODELS_DIR, "wait_time_rf.joblib")

_model = None

DEPT_CODE_MAP = {
    "General Medicine": 0,
    "Pediatrics": 1,
    "Orthopedics": 2,
    "Cardiology": 3,
    "Emergency": 4,
    "General Surgery": 5
}

PRIORITY_CODE_MAP = {
    "Normal": 0,
    "Medium": 1,
    "Emergency": 2
}

def load_prediction_model():
    """Loads and caches the Random Forest model."""
    global _model
    if _model is None:
        if os.path.exists(RF_MODEL_PATH):
            _model = joblib.load(RF_MODEL_PATH)
            print("[PREDICTION] Random Forest model loaded successfully.")
        else:
            print("[PREDICTION] Warning: RF model not found on disk. Falling back to rule-based fallback until trained.")
    return _model

def predict_patient_wait_time(
    patients_ahead: int,
    doctor_workload: int,
    avg_consult_duration: float,
    priority: str,
    department: str,
    doctor_available: int = 1,
    arrival_hour: int = None,
    emergency_interruptions: int = 0
) -> float:
    """
    Predicts waiting time in minutes using Random Forest Regression.
    """
    model = load_prediction_model()
    dept_code = DEPT_CODE_MAP.get(department, 0)
    priority_code = PRIORITY_CODE_MAP.get(priority, 0)

    if arrival_hour is None:
        arrival_hour = datetime.datetime.now().hour

    if model is not None:
        # Prepare feature DataFrame matching training columns to avoid sklearn warnings
        feature_df = pd.DataFrame([{
            "patients_ahead": patients_ahead,
            "doctor_workload": doctor_workload,
            "avg_consult_duration": avg_consult_duration,
            "priority_code": priority_code,
            "dept_code": dept_code,
            "doctor_available": doctor_available,
            "arrival_hour": arrival_hour,
            "emergency_interruptions": emergency_interruptions
        }])
        predicted_mins = model.predict(feature_df)[0]
    else:
        # Fallback if model not trained yet
        if priority == "Emergency":
            predicted_mins = 3.0
        elif priority == "Medium":
            predicted_mins = max(5.0, (patients_ahead * 0.6) * avg_consult_duration)
        else:
            predicted_mins = max(2.0, patients_ahead * avg_consult_duration)

    return max(1.0, round(float(predicted_mins), 1))

def recalculate_doctor_queue(doctor_id: int, delay_offset: int = 0):
    """
    Core Dynamic Waiting Time Recalculation Engine.
    Triggered when:
    - A consultation delay is detected (+X mins)
    - A consultation completes early (-Y mins)
    - A patient's status changes (WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED)
    - An emergency patient arrives and cuts the queue
    - A patient is reassigned
    - Doctor availability changes

    Recalculates waiting times and expected consultation timestamps
    for all active patients in that doctor's queue and updates SQLite.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch doctor details
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        conn.close()
        return

    doc_available = doctor["is_available"]
    doc_avg_consult = doctor["avg_consult_time"]
    dept_name = doctor["department"]

    # Fetch all active patients for this doctor (excluding COMPLETED)
    # Order: IN_CONSULTATION first, CALLED second, then WAITING by priority (Emergency first) then arrival
    cursor.execute("""
        SELECT * FROM patients
        WHERE assigned_doctor_id = ? AND status != 'COMPLETED'
        ORDER BY
            CASE status
                WHEN 'IN_CONSULTATION' THEN 1
                WHEN 'CALLED' THEN 2
                ELSE 3
            END,
            CASE priority
                WHEN 'Emergency' THEN 1
                WHEN 'Medium' THEN 2
                ELSE 3
            END,
            id ASC
    """, (doctor_id,))
    active_patients = cursor.fetchall()
    total_active = len(active_patients)

    now = datetime.datetime.now()
    accumulated_delay = delay_offset

    # Check if there is an in-consultation patient with recorded delay
    for idx, pat in enumerate(active_patients):
        status = pat["status"]
        pat_id = pat["id"]
        pat_priority = pat["priority"]
        pat_delay = pat["delay_minutes"] + delay_offset

        if status == "IN_CONSULTATION":
            patients_ahead = 0
            predicted_wait = 0
            expected_time_str = "Serving Now"
        elif status == "CALLED":
            patients_ahead = 0
            predicted_wait = 2
            expected_time_str = (now + datetime.timedelta(minutes=2)).strftime("%I:%M %p")
        else:
            # WAITING status
            patients_ahead = idx  # Number of patients ahead in sorted queue

            # Model prediction
            base_pred = predict_patient_wait_time(
                patients_ahead=patients_ahead,
                doctor_workload=total_active,
                avg_consult_duration=doc_avg_consult,
                priority=pat_priority,
                department=dept_name,
                doctor_available=doc_available,
                arrival_hour=now.hour,
                emergency_interruptions=1 if pat_priority == "Emergency" else 0
            )

            # Apply accumulated delay/early offset
            adjusted_wait = max(2.0, base_pred + accumulated_delay)
            predicted_wait = int(round(adjusted_wait))

            # Compute clock time for expected consultation
            exp_time_dt = now + datetime.timedelta(minutes=predicted_wait)
            expected_time_str = exp_time_dt.strftime("%I:%M %p")

        # Update patient queue position and predictions in database
        cursor.execute("""
            UPDATE patients
            SET queue_position = ?,
                predicted_wait_time = ?,
                expected_consultation_time = ?,
                delay_minutes = ?
            WHERE id = ?
        """, (idx + 1, predicted_wait, expected_time_str, pat_delay, pat_id))

    conn.commit()
    conn.close()

def recalculate_all_hospital_queues():
    """Recalculates queues for every doctor in the hospital."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM doctors")
    doctors = cursor.fetchall()
    conn.close()

    for doc in doctors:
        recalculate_doctor_queue(doc["id"])
