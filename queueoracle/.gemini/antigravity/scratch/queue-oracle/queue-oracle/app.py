"""
QUEUE ORACLE - Flask Backend Application
AI-Powered Smart Hospital Queue and Resource Prediction System
Full-stack REST API and Dashboard Router.
"""

import os
import json
import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from database import init_db, get_db_connection
from data_generator import seed_database, generate_patient_name
from train_model import train_and_evaluate, METRICS_PATH, RF_MODEL_PATH
from prediction import (
    predict_patient_wait_time,
    recalculate_doctor_queue,
    recalculate_all_hospital_queues,
    load_prediction_model
)
from disease_forecasting import analyze_disease_trends
from resource_management import (
    get_bed_occupancy_analysis,
    get_inventory_status,
    get_staffing_requirements
)
from recommendations import (
    get_all_recommendations,
    approve_recommendation,
    reject_recommendation,
    complete_recommendation,
    detect_and_generate_doctor_reassignments
)
from forecasting import get_hourly_arrival_forecast

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Ensure database and ML models exist on startup
def bootstrap_system():
    db_file = os.path.join(os.path.dirname(__file__), "hospital.db")
    if not os.path.exists(db_file):
        print("[INIT] Hospital database not found. Initializing and seeding...")
        init_db()
        seed_database()

    if not os.path.exists(RF_MODEL_PATH):
        print("[INIT] Trained Random Forest model not found. Training model...")
        train_and_evaluate()
    else:
        load_prediction_model()

    # Recalculate queues on start to ensure live sync
    try:
        recalculate_all_hospital_queues()
    except Exception as e:
        print(f"[INIT] Note on initial queue recalculation: {e}")

bootstrap_system()

# ----------------------------------------------------
# 1. FRONTEND ROUTE
# ----------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# ----------------------------------------------------
# 2. OVERVIEW & KPI API
# ----------------------------------------------------
@app.route("/api/overview", methods=["GET"])
def get_overview():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Patient counts
    cursor.execute("SELECT COUNT(*) AS total FROM patients")
    total_registered = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS waiting FROM patients WHERE status = 'WAITING'")
    waiting_count = cursor.fetchone()["waiting"]

    cursor.execute("SELECT COUNT(*) AS in_consult FROM patients WHERE status = 'IN_CONSULTATION'")
    in_consult_count = cursor.fetchone()["in_consult"]

    cursor.execute("SELECT COUNT(*) AS called FROM patients WHERE status = 'CALLED'")
    called_count = cursor.fetchone()["called"]

    cursor.execute("SELECT AVG(predicted_wait_time) AS avg_wait FROM patients WHERE status = 'WAITING'")
    avg_wait_val = cursor.fetchone()["avg_wait"]
    avg_wait = round(float(avg_wait_val), 1) if avg_wait_val is not None else 0.0

    # Doctor counts
    cursor.execute("SELECT COUNT(*) AS total FROM doctors WHERE is_available = 1")
    available_doctors = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM doctors WHERE is_available = 0")
    busy_doctors = cursor.fetchone()["total"]

    # Bed counts
    cursor.execute("SELECT SUM(total_beds) as tot, SUM(occupied_beds) as occ FROM departments")
    bed_row = cursor.fetchone()
    total_beds = bed_row["tot"] or 0
    occupied_beds = bed_row["occ"] or 0
    available_beds = max(0, total_beds - occupied_beds)
    occupancy_pct = round((occupied_beds / max(1, total_beds)) * 100, 1)

    # Department stats
    cursor.execute("""
        SELECT d.id, d.name, d.code, d.total_beds, d.occupied_beds,
               (SELECT COUNT(*) FROM patients p WHERE p.department = d.name AND p.status IN ('WAITING', 'CALLED')) as active_waiting,
               (SELECT COUNT(*) FROM doctors doc WHERE doc.department = d.name AND doc.is_available = 1) as available_docs
        FROM departments d
    """)
    departments_summary = []
    overcrowded_depts = []

    for dept in cursor.fetchall():
        d_tot_beds = dept["total_beds"]
        d_occ_beds = dept["occupied_beds"]
        d_occ_pct = round((d_occ_beds / max(1, d_tot_beds)) * 100, 1)
        wait_load = dept["active_waiting"]

        # Alert level
        if d_occ_pct >= 90.0 or wait_load >= 14:
            status_badge = "CRITICAL"
            overcrowded_depts.append(dept["name"])
        elif d_occ_pct >= 75.0 or wait_load >= 8:
            status_badge = "WARNING"
        else:
            status_badge = "NORMAL"

        departments_summary.append({
            "id": dept["id"],
            "name": dept["name"],
            "code": dept["code"],
            "total_beds": d_tot_beds,
            "occupied_beds": d_occ_beds,
            "occupancy_rate": d_occ_pct,
            "waiting_patients": wait_load,
            "available_doctors": dept["available_docs"],
            "status": status_badge
        })

    # Recent patients in queue
    cursor.execute("""
        SELECT p.*, d.name as doctor_name, d.room_no
        FROM patients p
        JOIN doctors d ON p.assigned_doctor_id = d.id
        WHERE p.status != 'COMPLETED'
        ORDER BY
            CASE p.status
                WHEN 'IN_CONSULTATION' THEN 1
                WHEN 'CALLED' THEN 2
                ELSE 3
            END,
            CASE p.priority
                WHEN 'Emergency' THEN 1
                WHEN 'Medium' THEN 2
                ELSE 3
            END,
            p.predicted_wait_time ASC
        LIMIT 10
    """)
    recent_queue = [dict(r) for r in cursor.fetchall()]

    conn.close()

    # Predicted shortages from resource module
    bed_analysis = get_bed_occupancy_analysis()
    inventory_summary = get_inventory_status()

    shortages = []
    if bed_analysis["overall"]["occupancy_rate"] >= 85.0:
        shortages.append(f"Bed capacity tight ({bed_analysis['overall']['occupancy_rate']}% occupied)")
    if inventory_summary["critical_count"] > 0:
        shortages.append(f"{inventory_summary['critical_count']} critical inventory stockouts")

    return jsonify({
        "total_registered": total_registered,
        "waiting_patients": waiting_count,
        "in_consultation": in_consult_count,
        "called_patients": called_count,
        "avg_predicted_wait_time": avg_wait,
        "available_doctors": available_doctors,
        "busy_doctors": busy_doctors,
        "total_beds": total_beds,
        "occupied_beds": occupied_beds,
        "available_beds": available_beds,
        "overall_occupancy_rate": occupancy_pct,
        "overcrowded_departments": overcrowded_depts,
        "predicted_shortages": shortages,
        "departments": departments_summary,
        "recent_queue": recent_queue
    })

# ----------------------------------------------------
# 3. PATIENTS & QUEUE MANAGEMENT API
# ----------------------------------------------------
@app.route("/api/patients", methods=["GET"])
def list_patients():
    conn = get_db_connection()
    cursor = conn.cursor()

    dept_filter = request.args.get("department")
    status_filter = request.args.get("status")
    doc_filter = request.args.get("doctor_id")

    query = """
        SELECT p.*, d.name as doctor_name, d.room_no
        FROM patients p
        JOIN doctors d ON p.assigned_doctor_id = d.id
        WHERE 1=1
    """
    params = []

    if dept_filter:
        query += " AND p.department = ?"
        params.append(dept_filter)
    if status_filter:
        query += " AND p.status = ?"
        params.append(status_filter)
    if doc_filter:
        query += " AND p.assigned_doctor_id = ?"
        params.append(doc_filter)

    query += """
        ORDER BY
            CASE p.status
                WHEN 'IN_CONSULTATION' THEN 1
                WHEN 'CALLED' THEN 2
                WHEN 'WAITING' THEN 3
                ELSE 4
            END,
            CASE p.priority
                WHEN 'Emergency' THEN 1
                WHEN 'Medium' THEN 2
                ELSE 3
            END,
            p.queue_position ASC,
            p.id ASC
    """

    cursor.execute(query, params)
    patients = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(patients)

@app.route("/api/patients", methods=["POST"])
def register_patient():
    """Registers a new patient and runs ML prediction for wait time."""
    data = request.json or {}
    name = data.get("name", "").strip() or generate_patient_name()
    department = data.get("department", "General Medicine")
    priority = data.get("priority", "Normal")
    doctor_id = data.get("doctor_id")
    disease_tag = data.get("disease_tag", "Routine Checkup")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine assigned doctor if not provided: pick least busy doctor in department
    if not doctor_id:
        cursor.execute("""
            SELECT d.id FROM doctors d
            WHERE d.department = ? AND d.is_available = 1
            ORDER BY (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status != 'COMPLETED') ASC
            LIMIT 1
        """, (department,))
        doc_row = cursor.fetchone()
        if doc_row:
            doctor_id = doc_row["id"]
        else:
            cursor.execute("SELECT id FROM doctors WHERE department = ? LIMIT 1", (department,))
            doctor_id = cursor.fetchone()["id"]
    else:
        doctor_id = int(doctor_id)

    # Next OPD token
    cursor.execute("SELECT MAX(opd_token) as max_token, COUNT(*) as cnt FROM patients")
    token_row = cursor.fetchone()
    next_token = (token_row["max_token"] or 100) + 1
    patient_code = f"PAT-{3000 + (token_row['cnt'] or 0) + 1}"

    # Query doctor details
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    avg_consult = doctor["avg_consult_time"] if doctor else 12

    # Query current queue for this doctor
    cursor.execute("""
        SELECT COUNT(*) as q_len FROM patients
        WHERE assigned_doctor_id = ? AND status IN ('WAITING', 'CALLED', 'IN_CONSULTATION')
    """, (doctor_id,))
    q_len = cursor.fetchone()["q_len"]
    patients_ahead = max(0, q_len)

    # ML Prediction
    now = datetime.datetime.now()
    pred_wait = predict_patient_wait_time(
        patients_ahead=patients_ahead,
        doctor_workload=patients_ahead + 1,
        avg_consult_duration=avg_consult,
        priority=priority,
        department=department,
        doctor_available=doctor["is_available"] if doctor else 1,
        arrival_hour=now.hour,
        emergency_interruptions=1 if priority == "Emergency" else 0
    )

    exp_time_dt = now + datetime.timedelta(minutes=int(pred_wait))
    exp_time_str = exp_time_dt.strftime("%I:%M %p")
    arrival_time_str = now.strftime("%I:%M %p")

    cursor.execute("""
        INSERT INTO patients (
            patient_id, name, opd_token, department, arrival_time,
            assigned_doctor_id, priority, estimated_duration,
            actual_consultation_duration, predicted_wait_time,
            expected_consultation_time, status, queue_position, delay_minutes, disease_tag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'WAITING', ?, 0, ?)
    """, (
        patient_code, name, next_token, department, arrival_time_str,
        doctor_id, priority, avg_consult, int(pred_wait), exp_time_str,
        patients_ahead + 1, disease_tag
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Recalculate doctor queue to update exact sorted positions
    recalculate_doctor_queue(doctor_id)

    return jsonify({
        "success": True,
        "patient": {
            "id": new_id,
            "patient_id": patient_code,
            "name": name,
            "opd_token": next_token,
            "department": department,
            "doctor_name": doctor["name"] if doctor else "Assigned Doctor",
            "priority": priority,
            "predicted_wait_time": int(pred_wait),
            "expected_consultation_time": exp_time_str,
            "status": "WAITING"
        }
    }), 201

@app.route("/api/patients/<token_or_id>", methods=["GET"])
def get_patient_detail(token_or_id):
    """
    Patient Waiting Time Prediction Query.
    Can query by OPD token (e.g., 143) or patient_id (PAT-2015).
    Returns rich explainable prediction breakdown.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if str(token_or_id).isdigit():
        cursor.execute("""
            SELECT p.*, d.name as doctor_name, d.room_no, d.avg_consult_time, d.is_available as doc_available
            FROM patients p
            JOIN doctors d ON p.assigned_doctor_id = d.id
            WHERE p.opd_token = ?
        """, (int(token_or_id),))
    else:
        cursor.execute("""
            SELECT p.*, d.name as doctor_name, d.room_no, d.avg_consult_time, d.is_available as doc_available
            FROM patients p
            JOIN doctors d ON p.assigned_doctor_id = d.id
            WHERE p.patient_id = ?
        """, (token_or_id,))

    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return jsonify({"success": False, "message": "Patient token not found."}), 404

    # Recalculate live patients ahead for this doctor
    cursor.execute("""
        SELECT COUNT(*) as ahead FROM patients
        WHERE assigned_doctor_id = ?
          AND status IN ('WAITING', 'CALLED')
          AND (
            CASE priority WHEN 'Emergency' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END <
            CASE ? WHEN 'Emergency' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
            OR (
                CASE priority WHEN 'Emergency' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END =
                CASE ? WHEN 'Emergency' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
                AND id < ?
            )
          )
    """, (patient["assigned_doctor_id"], patient["priority"], patient["priority"], patient["id"]))
    patients_ahead = cursor.fetchone()["ahead"]

    conn.close()

    return jsonify({
        "success": True,
        "patient": {
            "id": patient["id"],
            "patient_id": patient["patient_id"],
            "name": patient["name"],
            "opd_token": patient["opd_token"],
            "department": patient["department"],
            "assigned_doctor": patient["doctor_name"],
            "room_no": patient["room_no"],
            "doctor_available": bool(patient["doc_available"]),
            "arrival_time": patient["arrival_time"],
            "patients_ahead": patients_ahead,
            "priority": patient["priority"],
            "estimated_duration": patient["estimated_duration"],
            "predicted_wait_time": patient["predicted_wait_time"],
            "expected_consultation": patient["expected_consultation_time"],
            "status": patient["status"],
            "delay_minutes": patient["delay_minutes"],
            "disease_tag": patient["disease_tag"]
        }
    })

# ----------------------------------------------------
# 4. STATUS UPDATES & DYNAMIC RECALCULATION (Section 5 & 6)
# ----------------------------------------------------
@app.route("/api/patients/<int:patient_id>/status", methods=["POST"])
def update_patient_status(patient_id):
    """
    Staff-operated consultation status tracking:
    WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED
    When COMPLETED:
    - Removes from active queue
    - Records consultation duration
    - Recalculates remaining waiting times dynamically!
    - Refreshes doctor availability and dashboard
    """
    data = request.json or {}
    new_status = data.get("status")

    if new_status not in ["WAITING", "CALLED", "IN_CONSULTATION", "COMPLETED"]:
        return jsonify({"success": False, "message": "Invalid status."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return jsonify({"success": False, "message": "Patient not found."}), 404

    doc_id = patient["assigned_doctor_id"]
    sched_dur = patient["estimated_duration"]
    actual_dur = data.get("actual_duration", sched_dur)

    now_str = datetime.datetime.now().strftime("%I:%M %p")

    if new_status == "COMPLETED":
        # Record into consultation_history
        delay_recorded = max(0, actual_dur - sched_dur)
        cursor.execute("""
            INSERT INTO consultation_history (patient_id, doctor_id, start_time, end_time, scheduled_duration, actual_duration, delay_recorded)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (patient["patient_id"], doc_id, patient["arrival_time"], now_str, sched_dur, actual_dur, delay_recorded))

        cursor.execute("""
            UPDATE patients
            SET status = 'COMPLETED',
                actual_consultation_duration = ?,
                predicted_wait_time = 0,
                expected_consultation_time = 'Completed'
            WHERE id = ?
        """, (actual_dur, patient_id))

    elif new_status == "IN_CONSULTATION":
        cursor.execute("""
            UPDATE patients
            SET status = 'IN_CONSULTATION',
                predicted_wait_time = 0,
                expected_consultation_time = 'Serving Now'
            WHERE id = ?
        """, (patient_id,))

    elif new_status == "CALLED":
        cursor.execute("""
            UPDATE patients
            SET status = 'CALLED',
                predicted_wait_time = 2,
                expected_consultation_time = ?
            WHERE id = ?
        """, (now_str, patient_id))

    else:
        cursor.execute("UPDATE patients SET status = 'WAITING' WHERE id = ?", (patient_id,))

    conn.commit()
    conn.close()

    # Recalculate remaining waiting times for this doctor
    recalculate_doctor_queue(doc_id)

    return jsonify({
        "success": True,
        "message": f"Patient status updated to {new_status}.",
        "patient_id": patient_id,
        "new_status": new_status
    })

@app.route("/api/patients/<int:patient_id>/delay", methods=["POST"])
def simulate_consultation_delay(patient_id):
    """
    DYNAMIC WAITING TIME RECALCULATION (Section 5):
    Detects consultation delay or early completion.
    Example: Patient's consultation takes 25 minutes longer than expected.
    Recalculates waiting times for all subsequent patients in that doctor's queue!
    """
    data = request.json or {}
    delay_minutes = int(data.get("delay_minutes", 15))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return jsonify({"success": False, "message": "Patient not found."}), 404

    doc_id = patient["assigned_doctor_id"]

    # Record delay on the patient
    cursor.execute("""
        UPDATE patients
        SET delay_minutes = delay_minutes + ?
        WHERE id = ?
    """, (delay_minutes, patient_id))
    conn.commit()
    conn.close()

    # Cascade recalculation to all subsequent patients in this doctor's queue!
    recalculate_doctor_queue(doc_id, delay_offset=delay_minutes)

    return jsonify({
        "success": True,
        "message": f"Delay of {delay_minutes:+d} minutes recorded. Subsequent queue recalculation completed successfully.",
        "doctor_id": doc_id,
        "delay_minutes": delay_minutes
    })

@app.route("/api/patients/<int:patient_id>/priority", methods=["POST"])
def update_patient_priority(patient_id):
    """Changes priority and reprioritizes queue dynamically."""
    data = request.json or {}
    new_priority = data.get("priority")
    if new_priority not in ["Normal", "Medium", "Emergency"]:
        return jsonify({"success": False, "message": "Invalid priority level."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT assigned_doctor_id FROM patients WHERE id = ?", (patient_id,))
    p = cursor.fetchone()
    if not p:
        conn.close()
        return jsonify({"success": False, "message": "Patient not found."}), 404

    doc_id = p["assigned_doctor_id"]
    cursor.execute("UPDATE patients SET priority = ? WHERE id = ?", (new_priority, patient_id))
    conn.commit()
    conn.close()

    recalculate_doctor_queue(doc_id)
    return jsonify({"success": True, "message": f"Priority updated to {new_priority}."})

# ----------------------------------------------------
# 5. DOCTORS & WORKLOAD BALANCING API (Section 8)
# ----------------------------------------------------
@app.route("/api/doctors", methods=["GET"])
def list_doctors():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.*,
               (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status IN ('WAITING', 'CALLED')) as waiting_count,
               (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status = 'IN_CONSULTATION') as active_consults,
               (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status = 'COMPLETED') as completed_today,
               (SELECT AVG(predicted_wait_time) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status = 'WAITING') as avg_wait
        FROM doctors d
        ORDER BY d.department ASC, waiting_count DESC
    """)
    doctors = []
    for doc in cursor.fetchall():
        w_cnt = doc["waiting_count"]
        avg_w = round(float(doc["avg_wait"]), 1) if doc["avg_wait"] else 0.0

        # Workload status badge
        if w_cnt >= 12:
            status = "OVERLOADED"
            badge = "danger"
        elif w_cnt >= 6:
            status = "MODERATE"
            badge = "warning"
        else:
            status = "OPTIMAL"
            badge = "success"

        doctors.append({
            "id": doc["id"],
            "name": doc["name"],
            "department": doc["department"],
            "specialization": doc["specialization"],
            "room_no": doc["room_no"],
            "is_available": bool(doc["is_available"]),
            "avg_consult_time": doc["avg_consult_time"],
            "waiting_count": w_cnt,
            "active_consults": doc["active_consults"],
            "completed_today": doc["completed_today"],
            "avg_wait_time": avg_w,
            "workload_status": status,
            "workload_badge": badge
        })

    conn.close()
    return jsonify(doctors)

@app.route("/api/doctors/<int:doctor_id>/availability", methods=["POST"])
def toggle_doctor_availability(doctor_id):
    """Toggles doctor availability and triggers queue recalculation."""
    data = request.json or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_available, name FROM doctors WHERE id = ?", (doctor_id,))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        return jsonify({"success": False, "message": "Doctor not found."}), 404

    new_avail = 1 if not doc["is_available"] else 0
    if "is_available" in data:
        new_avail = 1 if data["is_available"] else 0

    cursor.execute("UPDATE doctors SET is_available = ? WHERE id = ?", (new_avail, doctor_id))
    conn.commit()
    conn.close()

    recalculate_doctor_queue(doctor_id)
    status_label = "Available" if new_avail else "On Break / Emergency"
    return jsonify({
        "success": True,
        "message": f"{doc['name']} is now marked {status_label}.",
        "is_available": bool(new_avail)
    })

# ----------------------------------------------------
# 6. BED OCCUPANCY API (Section 9)
# ----------------------------------------------------
@app.route("/api/beds", methods=["GET"])
def bed_analysis_route():
    analysis = get_bed_occupancy_analysis()
    return jsonify(analysis)

@app.route("/api/beds/simulate-admit", methods=["POST"])
def simulate_bed_admit():
    data = request.json or {}
    dept_name = data.get("department", "Cardiology")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find available bed in department
    cursor.execute("""
        SELECT id, bed_number FROM beds
        WHERE department = ? AND status = 'AVAILABLE'
        LIMIT 1
    """, (dept_name,))
    bed = cursor.fetchone()

    if not bed:
        conn.close()
        return jsonify({"success": False, "message": f"No beds available in {dept_name}!"}), 400

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    patient_name = data.get("patient_name", generate_patient_name())

    cursor.execute("""
        UPDATE beds
        SET status = 'OCCUPIED',
            patient_name = ?,
            admission_time = ?,
            expected_discharge_hours = 24.0
        WHERE id = ?
    """, (patient_name, now_str, bed["id"]))

    cursor.execute("""
        UPDATE departments
        SET occupied_beds = occupied_beds + 1
        WHERE name = ?
    """, (dept_name,))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Simulated admission of {patient_name} to {bed['bed_number']} ({dept_name})."
    })

@app.route("/api/beds/simulate-discharge", methods=["POST"])
def simulate_bed_discharge():
    data = request.json or {}
    dept_name = data.get("department", "Cardiology")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, bed_number, patient_name FROM beds
        WHERE department = ? AND status = 'OCCUPIED'
        LIMIT 1
    """, (dept_name,))
    bed = cursor.fetchone()

    if not bed:
        conn.close()
        return jsonify({"success": False, "message": f"No occupied beds found to discharge in {dept_name}."}), 400

    cursor.execute("""
        UPDATE beds
        SET status = 'AVAILABLE',
            patient_name = NULL,
            admission_time = NULL,
            expected_discharge_hours = 0.0
        WHERE id = ?
    """, (bed["id"],))

    cursor.execute("""
        UPDATE departments
        SET occupied_beds = MAX(0, occupied_beds - 1)
        WHERE name = ?
    """, (dept_name,))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Simulated discharge of patient from {bed['bed_number']} ({dept_name})."
    })

# ----------------------------------------------------
# 7. DISEASE TRENDS & PREPAREDNESS API (Section 7 & 10)
# ----------------------------------------------------
@app.route("/api/disease-trends", methods=["GET"])
def disease_trends_route():
    analysis = analyze_disease_trends()
    return jsonify(analysis)

@app.route("/api/disease-trends/simulate-surge", methods=["POST"])
def simulate_disease_surge():
    """Simulates an outbreak surge (e.g. Dengue +15 cases today)."""
    data = request.json or {}
    disease = data.get("disease", "Dengue")
    additional_cases = int(data.get("additional_cases", 12))
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE disease_records
        SET cases_count = cases_count + ?,
            suspected_count = suspected_count + ?
        WHERE date = ? AND disease_name = ?
    """, (additional_cases, int(additional_cases * 1.6), today_str, disease))

    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO disease_records (date, disease_name, cases_count, suspected_count, department)
            VALUES (?, ?, ?, ?, 'General Medicine')
        """, (today_str, disease, additional_cases, int(additional_cases * 1.6)))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Simulated surge: Added {additional_cases} verified and {int(additional_cases * 1.6)} suspected cases of {disease}."
    })

# ----------------------------------------------------
# 8. INVENTORY API (Section 10)
# ----------------------------------------------------
@app.route("/api/inventory", methods=["GET"])
def inventory_route():
    return jsonify(get_inventory_status())

@app.route("/api/inventory/<int:item_id>/restock", methods=["POST"])
def restock_inventory(item_id):
    data = request.json or {}
    add_qty = int(data.get("quantity", 100))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET available_qty = available_qty + ? WHERE id = ?", (add_qty, item_id))
    cursor.execute("SELECT item_name, available_qty, unit FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Successfully replenished {item['item_name']}. New stock: {item['available_qty']} {item['unit']}."
    })

@app.route("/api/inventory/<int:item_id>/adjust", methods=["POST"])
def adjust_inventory(item_id):
    data = request.json or {}
    new_qty = int(data.get("available_qty", 20))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET available_qty = ? WHERE id = ?", (max(0, new_qty), item_id))
    cursor.execute("SELECT item_name, available_qty, unit FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Adjusted stock of {item['item_name']} to {item['available_qty']} {item['unit']}."
    })

# ----------------------------------------------------
# 9. STAFFING API (Section 11)
# ----------------------------------------------------
@app.route("/api/staffing", methods=["GET"])
def staffing_route():
    return jsonify(get_staffing_requirements())

# ----------------------------------------------------
# 10. RECOMMENDATIONS & DECISION SUPPORT API (Section 8 & 12)
# ----------------------------------------------------
@app.route("/api/recommendations", methods=["GET"])
def list_recommendations():
    return jsonify(get_all_recommendations())

@app.route("/api/recommendations/<int:rec_id>/approve", methods=["POST"])
def approve_rec_route(rec_id):
    result = approve_recommendation(rec_id)
    return jsonify(result)

@app.route("/api/recommendations/<int:rec_id>/reject", methods=["POST"])
def reject_rec_route(rec_id):
    result = reject_recommendation(rec_id)
    return jsonify(result)

@app.route("/api/recommendations/<int:rec_id>/complete", methods=["POST"])
def complete_rec_route(rec_id):
    result = complete_recommendation(rec_id)
    return jsonify(result)

# ----------------------------------------------------
# 11. FORECASTING API (Section 14)
# ----------------------------------------------------
@app.route("/api/forecast/arrivals", methods=["GET"])
def arrivals_forecast_route():
    return jsonify(get_hourly_arrival_forecast())

# ----------------------------------------------------
# 12. MACHINE LEARNING MODEL PERFORMANCE (Section 16)
# ----------------------------------------------------
@app.route("/api/model-performance", methods=["GET"])
def model_performance_route():
    if not os.path.exists(METRICS_PATH):
        metrics = train_and_evaluate()
    else:
        with open(METRICS_PATH, "r") as f:
            metrics = json.load(f)
    return jsonify(metrics)

# ----------------------------------------------------
# 13. INTERACTIVE SIMULATION ENGINE (Section 13)
# ----------------------------------------------------
@app.route("/api/simulation/reset", methods=["POST"])
def reset_simulation():
    """Resets entire hospital state back to baseline seed for demonstrations."""
    seed_database()
    recalculate_all_hospital_queues()
    return jsonify({
        "success": True,
        "message": "Hospital operational database successfully reset to clean demonstration baseline."
    })

@app.route("/api/simulation/burst-patients", methods=["POST"])
def simulate_burst_patients():
    """Adds a burst of N patients to a specific department or doctor."""
    data = request.json or {}
    count = int(data.get("count", 5))
    dept_name = data.get("department", "General Medicine")
    priority = data.get("priority", "Normal")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get doctor
    doc_id = data.get("doctor_id")
    if not doc_id:
        cursor.execute("SELECT id FROM doctors WHERE department = ? LIMIT 1", (dept_name,))
        doc_id = cursor.fetchone()["id"]
    else:
        doc_id = int(doc_id)

    cursor.execute("SELECT MAX(opd_token) as max_tok, COUNT(*) as cnt FROM patients")
    row = cursor.fetchone()
    base_tok = (row["max_tok"] or 100) + 1
    base_id = (row["cnt"] or 0) + 3000

    now = datetime.datetime.now()
    now_str = now.strftime("%I:%M %p")

    for i in range(count):
        p_name = generate_patient_name()
        tok = base_tok + i
        p_code = f"PAT-{base_id + i + 1}"

        cursor.execute("""
            INSERT INTO patients (
                patient_id, name, opd_token, department, arrival_time,
                assigned_doctor_id, priority, estimated_duration,
                actual_consultation_duration, predicted_wait_time,
                expected_consultation_time, status, queue_position, delay_minutes, disease_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 10, 0, 30, ?, 'WAITING', 99, 0, 'General Checkup')
        """, (p_code, p_name, tok, dept_name, now_str, doc_id, priority, now_str))

    conn.commit()
    conn.close()

    # Recalculate doctor queue
    recalculate_doctor_queue(doc_id)

    return jsonify({
        "success": True,
        "message": f"Successfully registered a burst of {count} {priority} patients to doctor #{doc_id} in {dept_name}."
    })

if __name__ == "__main__":
    print("\n=======================================================")
    print("  QUEUE ORACLE - Hospital Queue & Resource Prediction  ")
    print("  Server running on http://127.0.0.1:5000              ")
    print("=======================================================\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
