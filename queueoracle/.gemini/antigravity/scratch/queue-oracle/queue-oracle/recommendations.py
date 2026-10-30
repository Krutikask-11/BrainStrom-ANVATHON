"""
QUEUE ORACLE - Recommendations & Administrator Decision Support Module
Implements:
1. Intelligent Doctor Workload Balancing Algorithm (detection, rebalance formulation, wait reduction estimation)
2. Administrator Decision Support System (Approval/Rejection lifecycle, audit trail)
"""

import datetime
from database import get_db_connection
from prediction import recalculate_doctor_queue

def detect_and_generate_doctor_reassignments():
    """
    Scans all departments for workload imbalances between doctors.
    Generates rebalancing recommendations if one doctor has a high waiting queue
    and another in the same department has capacity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()

    for dept in departments:
        dept_name = dept["name"]

        # Fetch doctors in this department with their active waiting counts
        cursor.execute("""
            SELECT d.*,
                   (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status IN ('WAITING', 'CALLED')) as waiting_count,
                   (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor_id = d.id AND p.status = 'IN_CONSULTATION') as active_consults
            FROM doctors d
            WHERE d.department = ? AND d.is_available = 1
            ORDER BY waiting_count DESC
        """, (dept_name,))
        docs = cursor.fetchall()

        if len(docs) >= 2:
            busiest = docs[0]
            lightest = docs[-1]

            busy_q = busiest["waiting_count"]
            light_q = lightest["waiting_count"]
            diff = busy_q - light_q

            # Imbalance condition: busy doctor has at least 8 patients and more than 2x the lightest doctor
            if busy_q >= 8 and (diff >= 5 or busy_q >= 2 * max(1, light_q)):
                # Calculate candidate transfer count (balance them towards parity)
                transfer_count = max(2, diff // 2)

                # Check if an active PENDING recommendation already exists for this pair
                cursor.execute("""
                    SELECT id FROM recommendations
                    WHERE type = 'DOCTOR_REASSIGNMENT'
                      AND doctor_from_id = ?
                      AND doctor_to_id = ?
                      AND status = 'PENDING'
                """, (busiest["id"], lightest["id"]))
                existing = cursor.fetchone()

                if not existing:
                    # Estimate waiting time reduction
                    avg_time = busiest["avg_consult_time"]
                    est_reduction_mins = transfer_count * avg_time
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

                    title = f"Workload Rebalancing: {dept_name}"
                    problem = f"{busiest['name']} is heavily loaded with {busy_q} waiting patients, while {lightest['name']} has only {light_q} waiting."
                    supporting_data = f"{busiest['name']} backlog: {busy_q} patients (~{busy_q * avg_time}m wait). {lightest['name']}: {light_q} patients (~{light_q * lightest['avg_consult_time']}m wait)."
                    impact = f"Average waiting time in Room {busiest['room_no']} will surge to over {busy_q * avg_time} minutes without redistribution."
                    action = f"Reassign {transfer_count} eligible Normal-priority patients from {busiest['name']} to {lightest['name']}."
                    benefit = f"Reduces {busiest['name']}'s queue waiting time by ~{est_reduction_mins} minutes and balances department patient flow."
                    priority = "CRITICAL" if busy_q >= 15 else "HIGH"

                    cursor.execute("""
                        INSERT INTO recommendations (
                            type, title, problem, supporting_data, predicted_impact,
                            recommended_action, expected_benefit, priority, status,
                            doctor_from_id, doctor_to_id, patient_count, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
                    """, (
                        "DOCTOR_REASSIGNMENT", title, problem, supporting_data, impact,
                        action, benefit, priority, busiest["id"], lightest["id"], transfer_count, now_str
                    ))
                    conn.commit()

    conn.close()

def get_all_recommendations():
    """Returns all recommendations with doctor names and details."""
    # Ensure fresh workload recommendations are checked
    detect_and_generate_doctor_reassignments()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*,
               d1.name as from_doctor_name,
               d2.name as to_doctor_name
        FROM recommendations r
        LEFT JOIN doctors d1 ON r.doctor_from_id = d1.id
        LEFT JOIN doctors d2 ON r.doctor_to_id = d2.id
        ORDER BY
            CASE r.status
                WHEN 'PENDING' THEN 1
                WHEN 'APPROVED' THEN 2
                ELSE 3
            END,
            CASE r.priority
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                ELSE 4
            END,
            r.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "type": r["type"],
            "title": r["title"],
            "problem": r["problem"],
            "supporting_data": r["supporting_data"],
            "predicted_impact": r["predicted_impact"],
            "recommended_action": r["recommended_action"],
            "expected_benefit": r["expected_benefit"],
            "priority": r["priority"],
            "status": r["status"],
            "doctor_from_id": r["doctor_from_id"],
            "doctor_to_id": r["doctor_to_id"],
            "from_doctor_name": r["from_doctor_name"],
            "to_doctor_name": r["to_doctor_name"],
            "patient_count": r["patient_count"],
            "created_at": r["created_at"]
        })
    return result

def approve_recommendation(recommendation_id: int):
    """
    Executes approval of a recommendation.
    If it is DOCTOR_REASSIGNMENT, actually reassigns eligible waiting patients in SQLite
    and dynamically recalculates queues for both doctors!
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,))
    rec = cursor.fetchone()

    if not rec:
        conn.close()
        return {"success": False, "message": "Recommendation not found."}

    if rec["status"] != "PENDING":
        conn.close()
        return {"success": False, "message": f"Recommendation is already {rec['status']}."}

    if rec["type"] == "DOCTOR_REASSIGNMENT":
        from_id = rec["doctor_from_id"]
        to_id = rec["doctor_to_id"]
        patient_count = rec["patient_count"]

        # Select candidate Normal priority WAITING patients from from_doctor
        cursor.execute("""
            SELECT id FROM patients
            WHERE assigned_doctor_id = ?
              AND status = 'WAITING'
              AND priority = 'Normal'
            ORDER BY queue_position DESC
            LIMIT ?
        """, (from_id, patient_count))
        candidate_patients = cursor.fetchall()

        reassigned_count = 0
        for pat in candidate_patients:
            cursor.execute("""
                UPDATE patients
                SET assigned_doctor_id = ?
                WHERE id = ?
            """, (to_id, pat["id"]))
            reassigned_count += 1

        cursor.execute("UPDATE recommendations SET status = 'APPROVED' WHERE id = ?", (recommendation_id,))
        conn.commit()
        conn.close()

        # Dynamically recalculate queues for both doctors
        recalculate_doctor_queue(from_id)
        recalculate_doctor_queue(to_id)

        return {
            "success": True,
            "message": f"Approved! Successfully redistributed {reassigned_count} patients and recalculated waiting times."
        }
    else:
        # Non-reassignment recommendations (bed, inventory, staff) marked APPROVED
        cursor.execute("UPDATE recommendations SET status = 'APPROVED' WHERE id = ?", (recommendation_id,))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Recommendation approved by administrator."}

def reject_recommendation(recommendation_id: int):
    """Rejects a recommendation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE recommendations SET status = 'REJECTED' WHERE id = ?", (recommendation_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Recommendation rejected by administrator."}

def complete_recommendation(recommendation_id: int):
    """Marks an approved recommendation as COMPLETED."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE recommendations SET status = 'COMPLETED' WHERE id = ?", (recommendation_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Recommendation marked completed."}
