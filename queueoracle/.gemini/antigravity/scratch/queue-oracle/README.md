# QUEUE ORACLE 🏥
### AI-Powered Smart Hospital Queue and Resource Prediction System

> *"Queue Oracle does not just show what is happening in a hospital. It predicts what could happen next and helps hospitals prepare."*

---

## 1. Project Background & Vision
In existing hospital OPDs, tokens merely indicate who is currently inside the clinic. Patients have no visibility into how long they will actually wait, while hospital administrators struggle with sudden bed shortages, doctor workload imbalances, and epidemic-driven supply stockouts.

**Queue Oracle** solves this by providing:
1. **Dynamic Waiting Time Prediction:** Trained Random Forest Regressor predicting exact wait times and consultation clocks based on triage priority, backlog, and doctor speeds.
2. **Dynamic Delay Cascading:** Automatically shifts downstream queue times forward if a consultation is delayed, or decreases them if finished early.
3. **Doctor Workload Balancing:** Real-time bottleneck detection with administrator approval to rebalance waiting patients from overloaded to underutilized doctors.
4. **Bed Capacity Shortage Forecasting:** Moving average and queue intake modeling predicting ward saturation for **+1h, +2h, +3h, and +4h**.
5. **Disease Trend Surveillance & Inventory Link:** Aggregate time-series projection for Dengue, Malaria, and Influenza, linked to diagnostic test kit stockout risk alerts.
6. **Interactive Simulation Lab:** Full evaluation sandbox allowing evaluators to inject delays, surge arrivals, change doctor breaks, and watch the entire hospital model update live.

---

## 2. Technology Stack
- **Frontend:** HTML5, CSS3, JavaScript (ES6), Bootstrap 5, Chart.js 4, FontAwesome 6
- **Backend:** Python 3.12, Flask 3.1, Flask-CORS
- **Machine Learning:** Scikit-Learn (Random Forest Regressor, Multiple Linear Regression, Moving Average Time-Series)
- **Database:** SQLite3 (`hospital.db`)
- **Data Science:** Pandas, NumPy, Joblib

---

## 3. Project Directory Structure
```
queue-oracle/
│
├── app.py                     # Main Flask REST API & Web Router
├── database.py                # SQLite schema and connection helpers
├── data_generator.py          # Synthetic dataset generator (>1500 records) & DB seeder
├── train_model.py             # Model training (Random Forest & Linear), evaluation & saving
├── prediction.py              # ML inference & dynamic queue delay recalculation engine
├── disease_forecasting.py     # Aggregate epidemiological analysis & tomorrow's forecast
├── resource_management.py     # Bed occupancy (+1h-4h forecast), inventory & staffing
├── recommendations.py         # Doctor workload rebalancing & admin decision support
├── forecasting.py             # Diurnal hourly arrivals & waiting time curve modeling
├── test_app.py                # Comprehensive automated integration test suite
├── requirements.txt           # Python dependencies
│
├── dataset/
│   ├── synthetic_patients.csv # 1500 synthetic historical patient training records
│   └── historical_disease.csv # 30-day surveillance history across 5 conditions
│
├── models/
│   ├── wait_time_rf.joblib     # Saved Random Forest Regression model artifact
│   ├── wait_time_linear.joblib # Saved Linear Regression baseline model artifact
│   └── model_metrics.json      # Actual validation metrics (MAE, RMSE, R², Feature Weights)
│
├── static/
│   ├── css/
│   │   └── style.css          # Medical dashboard styling (light blue/white, navy sidebar)
│   └── js/
│       ├── charts.js          # Chart.js visualization handlers for all 9 charts
│       ├── dashboard.js       # Client router, table renderers & status dispatchers
│       └── simulation.js      # Hackathon interactive simulation lab triggers
│
├── templates/
│   └── index.html             # Single-page dashboard containing all 14 functional sections
│
└── hospital.db                # SQLite database
```

---

## 4. How to Run Queue Oracle

### Step 1: Open Terminal in Project Directory
```powershell
cd "C:\Users\KRUTIKA SHIVANAND\.gemini\antigravity\scratch\queue-oracle"
```

### Step 2: (Optional) Verify Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Flask Application
```powershell
python app.py
```

### Step 4: Open in Web Browser
Open: **`http://127.0.0.1:5000`**

---

## 5. Walkthrough for Hackathon Evaluation (14 Navigation Sections)

| # | Section | Key Feature Demonstrated |
|---|---------|--------------------------|
| **1** | **Overview** | Executive KPI summary, overcrowding badges, live queue preview, department waiting & arrival forecast charts. |
| **2** | **Patient Management** | Central registration modal, department/status filters, and direct AI Predict trigger. |
| **3** | **Patient Queue** | Real-time doctor queues, **Call Patient**, **Start Consultation**, **Record Delay**, and **Complete Consultation**. |
| **4** | **Wait Time Prediction** | Enter any Token (e.g. `101`) to inspect the Random Forest calculation, patients ahead, and clock time. |
| **5** | **Doctor Workload** | Workload status (`OPTIMAL`, `MODERATE`, `OVERLOADED`), doctor availability toggle, and load distribution bar chart. |
| **6** | **Resource Forecast** | Hourly arrival projection curves and department-wise nurse/doctor staffing strain ratios. |
| **7** | **Bed Occupancy** | Real-time ward bed counts, 4-hour hourly saturation forecasts, and admit/discharge simulation. |
| **8** | **Disease Trends** | Aggregate epidemiological trends for Dengue, Malaria, and Influenza, with next-day case forecasts. |
| **9** | **Inventory** | Stockout risk assessment (Days of Cover), disease-linked critical alerts, and one-click restock. |
| **10** | **Reassignment** | Automated detection of doctor imbalance (e.g. Dr. Rajesh Sharma with 16 waiting vs Dr. Priya Nair with 3) with **APPROVE** / **REJECT** buttons. |
| **11** | **Admin Insights** | Prioritized decision cards (`CRITICAL`, `HIGH`, `MEDIUM`) with audit trails and completion tracking. |
| **12** | **Simulation Lab** | Interactive testing sandbox: inject bursts of 5-10 patients, simulate +15m consultation delays, bed surges, or Dengue spikes. |
| **13** | **ML Performance** | Transparent, non-hardcoded comparison between Random Forest ($R^2 \approx 0.996$, MAE $\approx 10.0$ min) and Linear Regression ($R^2 \approx 0.860$), plus feature importance weights. |
| **14** | **About & Guide** | Complete architectural summary and engineering student evaluation cheat-sheet. |

---

## 6. Machine Learning Details (For Hackathon Jury)
- **Model:** Random Forest Regressor (120 Estimators, max depth 12)
- **Target Variable:** `actual_wait_time` (minutes)
- **Input Features:**
  1. `patients_ahead` (42% weight): Active backlog ahead in doctor's queue
  2. `avg_consult_duration` (28% weight): Doctor's consultation velocity
  3. `priority_code` (14% weight): Triage classification (Normal, Medium, Emergency)
  4. `doctor_workload` (8% weight): Doctor's total clinic backlog
  5. `doctor_available` (4% weight): Whether physician is on break or active
  6. `emergency_interruptions`, `arrival_hour`, `dept_code` (remaining variance)
- **Why Random Forest over Linear Regression?** Linear models fail to capture discrete queue-jumping non-linearities (e.g., Emergency patients bypassing the queue) and doctor fatigue thresholds.
