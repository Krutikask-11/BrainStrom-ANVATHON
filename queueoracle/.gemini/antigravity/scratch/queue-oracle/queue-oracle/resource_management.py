"""
QUEUE ORACLE - Resource Management Module
Manages and forecasts:
1. Department-wise Bed Occupancy (Current + 1h, 2h, 3h, 4h predictive horizon)
2. Inventory & Medical Supplies Preparedness with Stockout Risk Assessment
3. Department-wise Staffing Requirement Analytics
"""

import math
from database import get_db_connection

def get_bed_occupancy_analysis():
    """
    Computes department-wise bed occupancy metrics and forecasts next 1, 2, 3, 4 hour occupancy.
    Admissions are modeled based on OPD queue conversion rate (~8-15% of active OPD patients)
    and emergency intake.
    Discharges are modeled from beds with expected_discharge_hours <= forecast window.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get departments
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()

    bed_data = []
    overall_total = 0
    overall_occupied = 0

    for dept in departments:
        dept_name = dept["name"]
        total_beds = dept["total_beds"]
        occupied_beds = dept["occupied_beds"]
        available_beds = max(0, total_beds - occupied_beds)
        occupancy_rate = round((occupied_beds / max(1, total_beds)) * 100, 1)

        overall_total += total_beds
        overall_occupied += occupied_beds

        # Count active OPD patients waiting/called in this department
        cursor.execute("""
            SELECT COUNT(*) AS opd_count FROM patients
            WHERE department = ? AND status IN ('WAITING', 'CALLED', 'IN_CONSULTATION')
        """, (dept_name,))
        opd_active = cursor.fetchone()["opd_count"]

        # Admission conversion rate: Emergency ~40%, Cardiology ~25%, Gen Med ~15%, Others ~10%
        conv_rates = {
            "Emergency": 0.35,
            "Cardiology": 0.25,
            "General Medicine": 0.15,
            "General Surgery": 0.12,
            "Pediatrics": 0.10,
            "Orthopedics": 0.08
        }
        conv_rate = conv_rates.get(dept_name, 0.12)

        # Baseline expected hourly admission and discharge rates
        hourly_admissions_expected = max(0.5, round((opd_active * conv_rate) / 3.0, 1))

        # Discharges from bed schedule
        cursor.execute("""
            SELECT COUNT(*) as near_discharges FROM beds
            WHERE department = ? AND status = 'OCCUPIED' AND expected_discharge_hours <= 4.0
        """, (dept_name,))
        discharges_in_4h = cursor.fetchone()["near_discharges"]
        hourly_discharges_expected = max(0.3, round(discharges_in_4h / 4.0, 1))

        # Hourly forecasts for 1h, 2h, 3h, 4h
        hourly_forecasts = []
        curr_occ = occupied_beds
        shortage_detected = False
        shortage_hour = None

        for h in range(1, 5):
            predicted_adm = int(round(hourly_admissions_expected * h))
            predicted_dis = int(round(hourly_discharges_expected * h))
            forecast_occ = max(0, min(total_beds + 5, curr_occ + predicted_adm - predicted_dis))
            forecast_pct = round((forecast_occ / max(1, total_beds)) * 100, 1)

            if forecast_occ >= total_beds and not shortage_detected:
                shortage_detected = True
                shortage_hour = h

            hourly_forecasts.append({
                "hour": h,
                "projected_occupied": forecast_occ,
                "projected_available": max(0, total_beds - forecast_occ),
                "projected_percentage": forecast_pct,
                "projected_admissions": predicted_adm,
                "projected_discharges": predicted_dis,
                "status": "CRITICAL" if forecast_pct >= 90.0 else ("WARNING" if forecast_pct >= 75.0 else "NORMAL")
            })

        # Determine overall department alert level
        if occupancy_rate >= 90.0 or shortage_detected:
            dept_status = "CRITICAL"
            badge_color = "danger"
            action_suggestion = f"Bed saturation critical! Expedite planned discharges in {dept_name} and prepare overflow transition beds."
        elif occupancy_rate >= 75.0:
            dept_status = "WARNING"
            badge_color = "warning"
            action_suggestion = f"Moderate bed pressure. Review pending discharge candidate charts for {dept_name}."
        else:
            dept_status = "NORMAL"
            badge_color = "success"
            action_suggestion = f"Bed capacity comfortable. {available_beds} beds readily open."

        bed_data.append({
            "department": dept_name,
            "code": dept["code"],
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds,
            "occupancy_rate": occupancy_rate,
            "status": dept_status,
            "badge_color": badge_color,
            "active_opd_load": opd_active,
            "shortage_risk": shortage_detected,
            "shortage_hour": shortage_hour,
            "action_suggestion": action_suggestion,
            "hourly_forecasts": hourly_forecasts
        })

    conn.close()

    overall_available = max(0, overall_total - overall_occupied)
    overall_occupancy_rate = round((overall_occupied / max(1, overall_total)) * 100, 1)

    return {
        "overall": {
            "total_beds": overall_total,
            "occupied_beds": overall_occupied,
            "available_beds": overall_available,
            "occupancy_rate": overall_occupancy_rate,
            "status": "CRITICAL" if overall_occupancy_rate >= 90 else ("WARNING" if overall_occupancy_rate >= 75 else "NORMAL")
        },
        "departments": bed_data
    }

def get_inventory_status():
    """
    Analyzes hospital supplies, medications, and diagnostic kits.
    Computes days until stockout and recommends replenishment quantities.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory ORDER BY (available_qty * 1.0 / min_stock) ASC")
    items = cursor.fetchall()
    conn.close()

    inventory_list = []
    critical_count = 0
    warning_count = 0

    for item in items:
        avail = item["available_qty"]
        min_stk = item["min_stock"]
        daily = max(1, item["daily_usage"])
        days_cover = round(avail / daily, 1)

        # Calculate shortage risk
        if avail <= min_stk * 0.4 or days_cover <= 1.5:
            risk = "CRITICAL"
            badge = "danger"
            critical_count += 1
            # Recommend bringing stock back up to min_stock + 3 days buffer
            replenish_qty = (min_stk * 2) - avail
        elif avail <= min_stk or days_cover <= 3.5:
            risk = "WARNING"
            badge = "warning"
            warning_count += 1
            replenish_qty = (min_stk * 2) - avail
        else:
            risk = "NORMAL"
            badge = "success"
            replenish_qty = 0

        inventory_list.append({
            "id": item["id"],
            "item_name": item["item_name"],
            "category": item["category"],
            "available_qty": avail,
            "min_stock": min_stk,
            "daily_usage": daily,
            "unit": item["unit"],
            "days_cover": days_cover,
            "associated_disease": item["associated_disease"],
            "shortage_risk": risk,
            "badge": badge,
            "recommended_replenish": max(0, replenish_qty)
        })

    return {
        "items": inventory_list,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "total_items": len(inventory_list)
    }

def get_staffing_requirements():
    """
    Analyzes department-wise patient demand and doctor loads to identify
    repeatedly strained departments and formulate staffing recommendations.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()

    staffing_analysis = []

    for dept in departments:
        dept_name = dept["name"]
        base_staff = dept["base_staff"]

        # Count active doctors and active patients
        cursor.execute("""
            SELECT COUNT(*) as doc_count FROM doctors
            WHERE department = ? AND is_available = 1
        """, (dept_name,))
        active_docs = max(1, cursor.fetchone()["doc_count"])

        cursor.execute("""
            SELECT COUNT(*) as patient_count FROM patients
            WHERE department = ? AND status IN ('WAITING', 'CALLED', 'IN_CONSULTATION')
        """, (dept_name,))
        patient_count = cursor.fetchone()["patient_count"]

        patient_to_doctor_ratio = round(patient_count / active_docs, 1)

        # Benchmark: Normal ratio is 4-7 patients per doctor
        if patient_to_doctor_ratio >= 10.0:
            status = "CRITICAL"
            badge = "danger"
            recommendation = f"Immediate surge support required. Allocate 2 additional nurses and 1 on-call physician to {dept_name}."
            additional_staff_needed = 3
        elif patient_to_doctor_ratio >= 7.0:
            status = "WARNING"
            badge = "warning"
            recommendation = f"Moderate staff strain. Plan staggered break schedules and alert relief doctors for {dept_name}."
            additional_staff_needed = 1
        else:
            status = "NORMAL"
            badge = "success"
            recommendation = f"Staffing level currently optimal for current patient arrival rate."
            additional_staff_needed = 0

        staffing_analysis.append({
            "department": dept_name,
            "base_staff": base_staff,
            "active_doctors": active_docs,
            "active_patients": patient_count,
            "patient_to_doctor_ratio": patient_to_doctor_ratio,
            "status": status,
            "badge": badge,
            "additional_staff_needed": additional_staff_needed,
            "recommendation": recommendation
        })

    conn.close()
    return staffing_analysis
