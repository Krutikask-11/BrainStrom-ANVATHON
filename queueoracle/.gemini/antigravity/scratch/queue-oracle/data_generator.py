"""
QUEUE ORACLE - Synthetic Dataset & Database Seeding
Generates >1000 realistic historical patient training records and
seeds SQLite with realistic initial hospital operations data.
"""

import os
import random
import datetime
import pandas as pd
import numpy as np
from database import get_db_connection, init_db

DATASET_DIR = os.path.join(os.path.dirname(__file__), "dataset")
os.makedirs(DATASET_DIR, exist_ok=True)
CSV_PATH = os.path.join(DATASET_DIR, "synthetic_patients.csv")
DISEASE_CSV_PATH = os.path.join(DATASET_DIR, "historical_disease.csv")

DEPARTMENTS = [
    {"name": "General Medicine", "code": "GM", "total_beds": 60, "occupied_beds": 52, "avg_consult": 10, "staff": 12},
    {"name": "Pediatrics", "code": "PED", "total_beds": 40, "occupied_beds": 28, "avg_consult": 12, "staff": 8},
    {"name": "Orthopedics", "code": "ORTH", "total_beds": 35, "occupied_beds": 22, "avg_consult": 15, "staff": 6},
    {"name": "Cardiology", "code": "CARD", "total_beds": 50, "occupied_beds": 46, "avg_consult": 18, "staff": 10},
    {"name": "Emergency", "code": "EMER", "total_beds": 25, "occupied_beds": 19, "avg_consult": 8, "staff": 14},
    {"name": "General Surgery", "code": "SURG", "total_beds": 30, "occupied_beds": 16, "avg_consult": 20, "staff": 8}
]

DOCTORS = [
    {"name": "Dr. Rajesh Sharma", "department": "General Medicine", "specialization": "Internal Medicine", "room": "101", "avg_consult": 10},
    {"name": "Dr. Priya Nair", "department": "General Medicine", "specialization": "Family Physician", "room": "102", "avg_consult": 10},
    {"name": "Dr. Amit Verma", "department": "Pediatrics", "specialization": "Child Specialist", "room": "103", "avg_consult": 12},
    {"name": "Dr. Sunita Rao", "department": "Pediatrics", "specialization": "Neonatologist", "room": "104", "avg_consult": 12},
    {"name": "Dr. Vikram Singh", "department": "Orthopedics", "specialization": "Joint Replacement", "room": "105", "avg_consult": 15},
    {"name": "Dr. Neha Kapoor", "department": "Orthopedics", "specialization": "Spine & Trauma", "room": "106", "avg_consult": 15},
    {"name": "Dr. Arun Mehta", "department": "Cardiology", "specialization": "Interventional Cardiology", "room": "107", "avg_consult": 18},
    {"name": "Dr. Sneha Patel", "department": "Cardiology", "specialization": "Clinical Cardiology", "room": "108", "avg_consult": 18},
    {"name": "Dr. Rohan Joshi", "department": "Emergency", "specialization": "Trauma & Critical Care", "room": "ER-1", "avg_consult": 8},
    {"name": "Dr. Kavita Desai", "department": "Emergency", "specialization": "Emergency Physician", "room": "ER-2", "avg_consult": 8},
    {"name": "Dr. Manoj Kulkarni", "department": "General Surgery", "specialization": "Laparoscopic Surgery", "room": "201", "avg_consult": 20},
    {"name": "Dr. Ananya Iyer", "department": "General Surgery", "specialization": "General Surgeon", "room": "202", "avg_consult": 20}
]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
               "Diya", "Saanvi", "Aanya", "Aadhya", "Pari", "Ananya", "Riya", "Navya", "Avani", "Myra",
               "Rahul", "Rohan", "Kunal", "Meera", "Pooja", "Suresh", "Ramesh", "Deepak", "Sunil", "Anil",
               "Geeta", "Sunita", "Anita", "Kavita", "Rekha", "Lakshmi", "Preeti", "Sanjay", "Vikram", "Gaurav"]

LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Bhatia", "Saxena", "Patel", "Shah", "Mehta", "Deshmukh",
              "Kulkarni", "Joshi", "Iyer", "Nair", "Reddy", "Rao", "Kumar", "Singh", "Yadav", "Mishra"]

DISEASE_CATEGORIES = [
    "Dengue", "Malaria", "Seasonal Influenza", "Fever-related", "Gastroenteritis", "Respiratory Infection", "Hypertension", "Routine Checkup"
]

def generate_patient_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def generate_training_dataset(num_records=1500):
    """
    Generates realistic synthetic patient historical dataset for training ML models.
    Features:
    - patients_ahead (int)
    - doctor_workload (int: total queue size)
    - avg_consult_duration (float: doctor's average speed)
    - priority (Normal: 0, Medium: 1, Emergency: 2)
    - department (Categorical code: 0-5)
    - doctor_available (1 = Active, 0 = Delay/Break)
    - arrival_hour (int: 8 to 20)
    - emergency_interruptions (int: 0, 1, 2)
    Target:
    - actual_wait_time (float: in minutes)
    """
    np.random.seed(42)
    random.seed(42)

    records = []
    dept_names = [d["name"] for d in DEPARTMENTS]
    dept_codes = {d["name"]: idx for idx, d in enumerate(DEPARTMENTS)}

    for i in range(1, num_records + 1):
        dept = random.choice(DEPARTMENTS)
        dept_name = dept["name"]
        dept_code = dept_codes[dept_name]
        avg_consult = dept["avg_consult"]

        # Priority distribution: 75% Normal, 18% Medium, 7% Emergency
        p_rand = random.random()
        if p_rand < 0.75:
            priority = "Normal"
            priority_code = 0
        elif p_rand < 0.93:
            priority = "Medium"
            priority_code = 1
        else:
            priority = "Emergency"
            priority_code = 2

        patients_ahead = random.randint(0, 35)
        # Total workload is patients ahead + some remaining
        doctor_workload = patients_ahead + random.randint(0, 15)
        doctor_available = 1 if random.random() > 0.08 else 0
        arrival_hour = random.randint(8, 19)
        emergency_interruptions = np.random.choice([0, 1, 2], p=[0.75, 0.20, 0.05])

        # Base wait time model calculation
        if priority == "Emergency":
            # Emergency patients bypass normal queue or wait <= 5 mins
            wait_time = max(0.0, np.random.normal(3.5, 1.5))
        elif priority == "Medium":
            # Medium priority gets prioritized ahead of normal
            effective_ahead = max(0, int(patients_ahead * 0.55))
            wait_time = effective_ahead * avg_consult
            wait_time += emergency_interruptions * 12.0
            wait_time += (1 - doctor_available) * 15.0
            # Overload fatigue penalty
            if doctor_workload > 20:
                wait_time *= 1.15
            wait_time += np.random.normal(0, 3.0)
            wait_time = max(2.0, wait_time)
        else:
            # Normal priority
            wait_time = patients_ahead * avg_consult
            wait_time += emergency_interruptions * 14.0
            wait_time += (1 - doctor_available) * 18.0
            if doctor_workload > 20:
                wait_time *= 1.20
            # Slight arrival hour rush at 10-12 and 16-18
            if arrival_hour in [10, 11, 16, 17]:
                wait_time += 4.0
            wait_time += np.random.normal(0, 4.0)
            wait_time = max(3.0, wait_time)

        records.append({
            "patient_id": f"PAT-{1000 + i}",
            "name": generate_patient_name(),
            "department": dept_name,
            "dept_code": dept_code,
            "patients_ahead": patients_ahead,
            "doctor_workload": doctor_workload,
            "avg_consult_duration": avg_consult,
            "priority": priority,
            "priority_code": priority_code,
            "doctor_available": doctor_available,
            "arrival_hour": arrival_hour,
            "emergency_interruptions": emergency_interruptions,
            "actual_wait_time": round(float(wait_time), 1)
        })

    df = pd.DataFrame(records)
    df.to_csv(CSV_PATH, index=False)
    print(f"[DATA] Generated {len(df)} synthetic patient training records saved to {CSV_PATH}")
    return df

def seed_database():
    """Initializes tables and seeds live operational data for demonstration."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing tables to ensure a clean state
    cursor.execute("DELETE FROM recommendations")
    cursor.execute("DELETE FROM consultation_history")
    cursor.execute("DELETE FROM inventory")
    cursor.execute("DELETE FROM disease_records")
    cursor.execute("DELETE FROM beds")
    cursor.execute("DELETE FROM patients")
    cursor.execute("DELETE FROM doctors")
    cursor.execute("DELETE FROM departments")

    # 1. Seed Departments
    for dept in DEPARTMENTS:
        cursor.execute("""
            INSERT INTO departments (name, code, total_beds, occupied_beds, avg_consult_time, base_staff)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (dept["name"], dept["code"], dept["total_beds"], dept["occupied_beds"], dept["avg_consult"], dept["staff"]))

    # 2. Seed Doctors
    doctor_id_map = {}
    for doc in DOCTORS:
        cursor.execute("""
            INSERT INTO doctors (name, department, specialization, is_available, avg_consult_time, room_no)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (doc["name"], doc["department"], doc["specialization"], doc["avg_consult"], doc["room"]))
        doctor_id_map[doc["name"]] = cursor.lastrowid

    # 3. Seed Live Patients with intentional workload imbalances for demonstration
    # Dr. Rajesh Sharma (Gen Med) will have 16 waiting patients (High load!)
    # Dr. Priya Nair (Gen Med) will have only 3 waiting patients (Low load!)
    # Dr. Arun Mehta (Cardiology) will have 12 waiting patients
    # Dr. Sneha Patel (Cardiology) will have only 3 waiting patients
    # Other doctors will have moderate balanced queues (4 to 8 patients)

    doctor_queue_targets = {
        "Dr. Rajesh Sharma": 16,
        "Dr. Priya Nair": 3,
        "Dr. Amit Verma": 9,
        "Dr. Sunita Rao": 7,
        "Dr. Vikram Singh": 8,
        "Dr. Neha Kapoor": 4,
        "Dr. Arun Mehta": 12,
        "Dr. Sneha Patel": 3,
        "Dr. Rohan Joshi": 6,
        "Dr. Kavita Desai": 5,
        "Dr. Manoj Kulkarni": 4,
        "Dr. Ananya Iyer": 3
    }

    base_time = datetime.datetime.now().replace(minute=0, second=0, microsecond=0) - datetime.timedelta(hours=2)
    token_counter = 101
    patient_id_counter = 2001

    for doc in DOCTORS:
        doc_id = doctor_id_map[doc["name"]]
        target_count = doctor_queue_targets.get(doc["name"], 5)

        for q_pos in range(1, target_count + 1):
            name = generate_patient_name()
            # Randomize arrival times over past 2 hours
            arr_time_dt = base_time + datetime.timedelta(minutes=q_pos * 6 + random.randint(0, 5))
            arrival_time_str = arr_time_dt.strftime("%I:%M %p")

            # Determine status:
            if q_pos == 1:
                status = "IN_CONSULTATION"
            elif q_pos == 2 and random.random() > 0.5:
                status = "CALLED"
            else:
                status = "WAITING"

            # Assign priority: 1 emergency if queue is large, some medium, rest normal
            if q_pos == 4 and target_count >= 8 and doc["department"] in ["General Medicine", "Emergency"]:
                priority = "Emergency"
            elif q_pos in [3, 7]:
                priority = "Medium"
            else:
                priority = "Normal"

            disease_tag = random.choice(DISEASE_CATEGORIES)
            patients_ahead = max(0, q_pos - 1)
            # Rough initial wait estimation (will be refined dynamically by prediction engine)
            predicted_wait = patients_ahead * doc["avg_consult"]
            if priority == "Emergency":
                predicted_wait = min(predicted_wait, 4)
            elif priority == "Medium":
                predicted_wait = int(predicted_wait * 0.7)

            expected_dt = arr_time_dt + datetime.timedelta(minutes=predicted_wait)
            expected_time_str = expected_dt.strftime("%I:%M %p")

            cursor.execute("""
                INSERT INTO patients (
                    patient_id, name, opd_token, department, arrival_time,
                    assigned_doctor_id, priority, estimated_duration,
                    actual_consultation_duration, predicted_wait_time,
                    expected_consultation_time, status, queue_position, delay_minutes, disease_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, ?)
            """, (
                f"PAT-{patient_id_counter}",
                name,
                token_counter,
                doc["department"],
                arrival_time_str,
                doc_id,
                priority,
                doc["avg_consult"],
                predicted_wait,
                expected_time_str,
                status,
                q_pos,
                disease_tag
            ))
            token_counter += 1
            patient_id_counter += 1

    # Also seed a few COMPLETED consultation records for history
    for i in range(15):
        pat_id = f"PAT-{1900 + i}"
        doc = random.choice(DOCTORS)
        doc_id = doctor_id_map[doc["name"]]
        sched_dur = doc["avg_consult"]
        act_dur = sched_dur + random.choice([-2, 0, 3, 5, -1])
        start_t = (datetime.datetime.now() - datetime.timedelta(minutes=90 - i * 5)).strftime("%I:%M %p")
        end_t = (datetime.datetime.now() - datetime.timedelta(minutes=90 - i * 5 - act_dur)).strftime("%I:%M %p")
        delay = max(0, act_dur - sched_dur)

        cursor.execute("""
            INSERT INTO consultation_history (patient_id, doctor_id, start_time, end_time, scheduled_duration, actual_duration, delay_recorded)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pat_id, doc_id, start_t, end_t, sched_dur, act_dur, delay))

    # 4. Seed Beds for each department
    for dept in DEPARTMENTS:
        total = dept["total_beds"]
        occupied = dept["occupied_beds"]
        for b in range(1, total + 1):
            bed_num = f"{dept['code']}-B{b:02d}"
            if b <= occupied:
                bed_status = "OCCUPIED"
                pat_name = generate_patient_name()
                adm_time = (datetime.datetime.now() - datetime.timedelta(hours=random.randint(2, 48))).strftime("%Y-%m-%d %H:%M")
                exp_disc = round(random.uniform(1.5, 36.0), 1)
            else:
                bed_status = "AVAILABLE"
                pat_name = None
                adm_time = None
                exp_disc = 0.0

            cursor.execute("""
                INSERT INTO beds (department, bed_number, status, patient_name, admission_time, expected_discharge_hours)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (dept["name"], bed_num, bed_status, pat_name, adm_time, exp_disc))

    # 5. Seed Historical Disease Trends (Past 30 days)
    # Intentionally model a rising Dengue and Fever outbreak in the past 7 days!
    today = datetime.date.today()
    disease_rows = []

    for day_offset in range(30, -1, -1):
        record_date = (today - datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
        # Dengue: baseline 2-4, but sharp spike in last 7 days up to 22 cases
        if day_offset > 7:
            dengue_cases = random.randint(2, 6)
        else:
            # Escalating surge
            dengue_cases = int(6 + (7 - day_offset) * 2.8 + random.randint(0, 3))
        dengue_suspected = int(dengue_cases * 1.6 + random.randint(1, 4))

        # Malaria: steady 4-8 cases
        malaria_cases = random.randint(3, 8)
        malaria_suspected = int(malaria_cases * 1.4 + random.randint(1, 3))

        # Seasonal Flu: fluctuating 12-25
        flu_cases = random.randint(12, 24)
        flu_suspected = int(flu_cases * 1.3)

        # Fever-related (general OPD): rising trend 22-48
        if day_offset > 7:
            fever_cases = random.randint(20, 28)
        else:
            fever_cases = int(28 + (7 - day_offset) * 3.2 + random.randint(0, 4))
        fever_suspected = int(fever_cases * 1.5)

        # Gastro
        gastro_cases = random.randint(5, 11)
        gastro_suspected = int(gastro_cases * 1.3)

        # Insert records
        for d_name, c_cnt, s_cnt, dept_name in [
            ("Dengue", dengue_cases, dengue_suspected, "General Medicine"),
            ("Malaria", malaria_cases, malaria_suspected, "General Medicine"),
            ("Seasonal Influenza", flu_cases, flu_suspected, "General Medicine"),
            ("Fever-related", fever_cases, fever_suspected, "Pediatrics"),
            ("Gastroenteritis", gastro_cases, gastro_suspected, "General Medicine")
        ]:
            cursor.execute("""
                INSERT INTO disease_records (date, disease_name, cases_count, suspected_count, department)
                VALUES (?, ?, ?, ?, ?)
            """, (record_date, d_name, c_cnt, s_cnt, dept_name))

            disease_rows.append({
                "date": record_date,
                "disease_name": d_name,
                "cases_count": c_cnt,
                "suspected_count": s_cnt,
                "department": dept_name
            })

    # Save disease CSV as well
    pd.DataFrame(disease_rows).to_csv(DISEASE_CSV_PATH, index=False)

    # 6. Seed Inventory with Linked Disease Associations
    inventory_items = [
        ("Dengue NS1 Antigen Rapid Test Kits", "Diagnostic Kits", 24, 100, 25, "Tests", "Dengue"),
        ("Malaria Ag (P.f/P.v) Rapid Test Kits", "Diagnostic Kits", 115, 80, 16, "Tests", "Malaria"),
        ("Paracetamol 650mg Tablets", "Medication", 820, 1000, 280, "Strips", "Fever-related"),
        ("IV Normal Saline (0.9% 500ml)", "Fluids", 42, 150, 45, "Bottles", "Dengue"),
        ("Nitrile Examination Gloves", "Consumables", 480, 300, 85, "Boxes", None),
        ("N95 Particulate Respirator Masks", "PPE", 175, 200, 50, "Pieces", "Seasonal Influenza"),
        ("Artemether + Lumefantrine 80/480mg", "Medication", 130, 100, 22, "Packs", "Malaria"),
        ("Oral Rehydration Salts (ORS) Sachets", "Medication", 340, 200, 65, "Sachets", "Gastroenteritis"),
        ("Ceftriaxone 1g Injections", "Antibiotics", 85, 120, 28, "Vials", None),
        ("Blood Infusion Giving Sets", "Consumables", 55, 100, 32, "Sets", "Dengue")
    ]

    for item in inventory_items:
        cursor.execute("""
            INSERT INTO inventory (item_name, category, available_qty, min_stock, daily_usage, unit, associated_disease)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, item)

    # 7. Seed Initial Administrator Recommendations
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # A) Doctor workload rebalance: Dr. Rajesh Sharma -> Dr. Priya Nair
    rajesh_id = doctor_id_map["Dr. Rajesh Sharma"]
    priya_id = doctor_id_map["Dr. Priya Nair"]
    cursor.execute("""
        INSERT INTO recommendations (
            type, title, problem, supporting_data, predicted_impact, recommended_action,
            expected_benefit, priority, status, doctor_from_id, doctor_to_id, patient_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
    """, (
        "DOCTOR_REASSIGNMENT",
        "Workload Imbalance: General Medicine OPD",
        "Dr. Rajesh Sharma has 16 waiting patients while Dr. Priya Nair in the same department has only 3.",
        "Dr. Sharma queue: 16 patients (est. wait 135 mins). Dr. Nair queue: 3 patients (est. wait 24 mins).",
        "Severe bottleneck in Room 101, patient dissatisfaction and escalating delays.",
        "Reassign 6 eligible normal-priority patients from Dr. Rajesh Sharma to Dr. Priya Nair.",
        "Reduces Dr. Sharma's queue wait by ~55 mins with negligible load on Dr. Nair.",
        "HIGH",
        rajesh_id,
        priya_id,
        6,
        now_str
    ))

    # B) Bed Shortage Alert: Cardiology
    cursor.execute("""
        INSERT INTO recommendations (
            type, title, problem, supporting_data, predicted_impact, recommended_action,
            expected_benefit, priority, status, doctor_from_id, doctor_to_id, patient_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', NULL, NULL, 0, ?)
    """, (
        "BED_SHORTAGE",
        "Impending Bed Shortage: Cardiology Ward",
        "Cardiology ward has reached 92% occupancy (46 of 50 beds filled) with 8 expected admissions in next 3 hours.",
        "Current available beds: 4. Predicted admissions: 8. Expected discharges: 2.",
        "Capacity breach expected within 2.5 hours. Inability to admit acute cardiac patients.",
        "Expedite planned discharge evaluations and place 4 observation beds on standby in Step-down Unit.",
        "Prevents ward saturation and ensures 6 buffer beds for critical emergency cardiac admissions.",
        "CRITICAL",
        now_str
    ))

    # C) Inventory Stock Alert: Dengue Diagnostic Kits
    cursor.execute("""
        INSERT INTO recommendations (
            type, title, problem, supporting_data, predicted_impact, recommended_action,
            expected_benefit, priority, status, doctor_from_id, doctor_to_id, patient_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', NULL, NULL, 0, ?)
    """, (
        "INVENTORY_SHORTAGE",
        "Stock Depletion Risk: Dengue NS1 Antigen Kits",
        "Stock level at 24 kits against minimum safety threshold of 100 with daily consumption spiking to 25.",
        "Current stock: 24 tests. Spike in suspected Dengue cases (+42% over 7 days).",
        "Stock exhaustion predicted in under 24 hours.",
        "Approve emergency purchase order for 200 Dengue NS1 Antigen Kits and 150 IV Saline bottles.",
        "Maintains uninterrupted laboratory diagnostic screening during seasonal dengue surge.",
        "HIGH",
        now_str
    ))

    # D) Staff Redistribution: General Medicine
    cursor.execute("""
        INSERT INTO recommendations (
            type, title, problem, supporting_data, predicted_impact, recommended_action,
            expected_benefit, priority, status, doctor_from_id, doctor_to_id, patient_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', NULL, NULL, 0, ?)
    """, (
        "STAFF_REDISTRIBUTION",
        "Staff Surge Allocation: General Medicine OPD",
        "General Medicine has experienced sustained >140% OPD patient volume across consecutive 7 days.",
        "Daily OPD visits: ~95 patients vs designed capacity of 65. Average nurse-patient ratio strained.",
        "Prolonged patient wait times and staff burnout.",
        "Temporarily reassign 2 triage nurses from General Surgery OPD to General Medicine morning shift.",
        "Accelerates vital signs recording, cuts token intake bottleneck by 18 minutes.",
        "MEDIUM",
        now_str
    ))

    conn.commit()
    conn.close()
    print("[DB] Live operational database seeded successfully with realistic hospital records.")

if __name__ == "__main__":
    generate_training_dataset(1500)
    seed_database()
