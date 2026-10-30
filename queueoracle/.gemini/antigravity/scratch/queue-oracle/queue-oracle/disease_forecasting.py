"""
QUEUE ORACLE - Disease Trend Analysis & Hospital Preparedness Forecasting Module
Provides aggregate epidemiological pattern analysis, tomorrow's demand forecasting
using Linear Regression and Moving Averages, and links disease surges to inventory preparedness.

NOTE: This is an aggregate hospital operational preparedness forecasting tool,
NOT an individual patient clinical diagnosis system.
All metrics distinguish medically verified cases from suspected/triaged cases.
"""

import datetime
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from database import get_db_connection

DISEASE_INVENTORY_MAP = {
    "Dengue": ["Dengue NS1 Antigen Rapid Test Kits", "IV Normal Saline (0.9% 500ml)", "Blood Infusion Giving Sets"],
    "Malaria": ["Malaria Ag (P.f/P.v) Rapid Test Kits", "Artemether + Lumefantrine 80/480mg"],
    "Seasonal Influenza": ["N95 Particulate Respirator Masks", "Paracetamol 650mg Tablets"],
    "Fever-related": ["Paracetamol 650mg Tablets", "IV Normal Saline (0.9% 500ml)"],
    "Gastroenteritis": ["Oral Rehydration Salts (ORS) Sachets", "IV Normal Saline (0.9% 500ml)"]
}

def analyze_disease_trends():
    """
    Analyzes historical and current disease aggregate cases across 30 days,
    computes 7-day moving averages, linear trends, and forecasts tomorrow's demand.
    """
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM disease_records ORDER BY date ASC", conn)
    conn.close()

    if df.empty:
        return {"diseases": [], "forecasts": [], "preparedness_alerts": []}

    unique_diseases = df["disease_name"].unique()
    disease_summaries = []
    preparedness_alerts = []

    for disease in unique_diseases:
        sub_df = df[df["disease_name"] == disease].copy()
        sub_df["date"] = pd.to_datetime(sub_df["date"])
        sub_df = sub_df.sort_values("date")

        total_records = len(sub_df)
        if total_records == 0:
            continue

        latest_record = sub_df.iloc[-1]
        today_cases = int(latest_record["cases_count"])
        today_suspected = int(latest_record["suspected_count"])
        dept = latest_record["department"]

        # 7-day stats
        last_7_days_df = sub_df.tail(7)
        sum_7d_cases = int(last_7_days_df["cases_count"].sum())
        sum_7d_suspected = int(last_7_days_df["suspected_count"].sum())
        avg_7d_cases = round(float(last_7_days_df["cases_count"].mean()), 1)

        # 30-day stats
        sum_30d_cases = int(sub_df["cases_count"].sum())
        avg_30d_cases = round(float(sub_df["cases_count"].mean()), 1)

        # Trend calculation: compare last 3 days avg vs previous 4 days
        if len(last_7_days_df) >= 7:
            recent_3d = last_7_days_df.iloc[-3:]["cases_count"].mean()
            prior_4d = last_7_days_df.iloc[:4]["cases_count"].mean()
            pct_change = round(((recent_3d - prior_4d) / max(1.0, prior_4d)) * 100, 1)
        else:
            pct_change = 0.0

        if pct_change >= 20.0:
            trend_direction = "SURGING"
            trend_badge = "CRITICAL"
        elif pct_change >= 8.0:
            trend_direction = "INCREASING"
            trend_badge = "WARNING"
        elif pct_change <= -8.0:
            trend_direction = "DECREASING"
            trend_badge = "NORMAL"
        else:
            trend_direction = "STABLE"
            trend_badge = "NORMAL"

        # Linear Regression & Moving Average Forecast for Tomorrow
        # Use last 14 days for linear projection
        sample_window = sub_df.tail(14)
        x_days = np.arange(len(sample_window)).reshape(-1, 1)
        y_cases = sample_window["cases_count"].values

        lr = LinearRegression()
        lr.fit(x_days, y_cases)
        next_day_x = np.array([[len(sample_window)]])
        lr_tomorrow = float(lr.predict(next_day_x)[0])

        # 3-day simple moving average
        ma_3d = float(sub_df.tail(3)["cases_count"].mean())
        # Blended forecast (60% Linear Regression trend + 40% 3-day Moving Average)
        blended_forecast = max(0, int(round(0.6 * lr_tomorrow + 0.4 * ma_3d)))
        forecast_suspected = int(round(blended_forecast * 1.5))

        # Check linked inventory status
        linked_supplies = DISEASE_INVENTORY_MAP.get(disease, [])
        inventory_warnings = check_inventory_for_disease(linked_supplies)

        summary_item = {
            "disease_name": disease,
            "department": dept,
            "today_verified": today_cases,
            "today_suspected": today_suspected,
            "past_7d_total": sum_7d_cases,
            "past_7d_avg": avg_7d_cases,
            "past_30d_total": sum_30d_cases,
            "past_30d_avg": avg_30d_cases,
            "trend_percentage": pct_change,
            "trend_direction": trend_direction,
            "trend_badge": trend_badge,
            "tomorrow_forecast_verified": blended_forecast,
            "tomorrow_forecast_suspected": forecast_suspected,
            "history_dates": sub_df.tail(14)["date"].dt.strftime("%b %d").tolist(),
            "history_cases": sub_df.tail(14)["cases_count"].tolist(),
            "history_suspected": sub_df.tail(14)["suspected_count"].tolist(),
            "linked_supplies": linked_supplies,
            "inventory_warnings": inventory_warnings
        }
        disease_summaries.append(summary_item)

        # Generate preparedness recommendations if increasing/surging
        if trend_direction in ["SURGING", "INCREASING"]:
            preparedness_alerts.append({
                "disease": disease,
                "badge": trend_badge,
                "headline": f"Surge Warning: {disease} cases rising ({pct_change:+0.1f}% recent spike).",
                "impact": f"Higher patient demand projected for {dept} tomorrow ({blended_forecast} verified, ~{forecast_suspected} suspected admissions/OPD consults).",
                "recommendations": [
                    f"Review inventory of {', '.join(linked_supplies)} immediately.",
                    f"Prepare observation beds in {dept} for potential hydration/monitoring admissions.",
                    f"Ensure triage nursing staff is briefed on {disease} symptom screening protocol.",
                    f"Check diagnostic laboratory throughput capacity for rapid test turnaround."
                ]
            })

    return {
        "diseases": disease_summaries,
        "preparedness_alerts": preparedness_alerts,
        "disclaimer": "AGGREGATE HOSPITAL PREPAREDNESS FORECASTING TOOL: Data represents aggregate surveillance counts and epidemiological trend projections. It is not an individual patient diagnostic system."
    }

def check_inventory_for_disease(supply_names):
    """Checks stock status of supplies linked to a disease surge."""
    if not supply_names:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in supply_names)
    cursor.execute(f"""
        SELECT item_name, available_qty, min_stock, daily_usage, unit
        FROM inventory
        WHERE item_name IN ({placeholders})
    """, supply_names)
    rows = cursor.fetchall()
    conn.close()

    warnings = []
    for r in rows:
        available = r["available_qty"]
        min_stock = r["min_stock"]
        daily = r["daily_usage"]
        days_left = round(available / max(1, daily), 1)

        if available < min_stock:
            risk = "CRITICAL" if days_left <= 1.5 else "WARNING"
            warnings.append({
                "item": r["item_name"],
                "available": available,
                "min_stock": min_stock,
                "daily_usage": daily,
                "unit": r["unit"],
                "days_cover": days_left,
                "risk": risk
            })
    return warnings
