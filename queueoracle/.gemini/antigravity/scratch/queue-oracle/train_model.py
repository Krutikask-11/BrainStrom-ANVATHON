"""
QUEUE ORACLE - Machine Learning Training & Evaluation Module
Trains Random Forest Regression and Linear Regression models on synthetic
hospital OPD historical data to predict patient waiting times.

Evaluates performance using MAE, RMSE, and R-squared.
Saves models and metrics for transparent evaluation.
"""

import os
import json
import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

from data_generator import CSV_PATH, generate_training_dataset

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

RF_MODEL_PATH = os.path.join(MODELS_DIR, "wait_time_rf.joblib")
LINEAR_MODEL_PATH = os.path.join(MODELS_DIR, "wait_time_linear.joblib")
METRICS_PATH = os.path.join(MODELS_DIR, "model_metrics.json")

FEATURE_COLUMNS = [
    "patients_ahead",
    "doctor_workload",
    "avg_consult_duration",
    "priority_code",
    "dept_code",
    "doctor_available",
    "arrival_hour",
    "emergency_interruptions"
]

FEATURE_DESCRIPTIONS = {
    "patients_ahead": "Number of active patients queued ahead of this token",
    "doctor_workload": "Total active backlog for the assigned doctor",
    "avg_consult_duration": "Doctor's average consultation duration (minutes)",
    "priority_code": "Triage Priority (0 = Normal, 1 = Medium, 2 = Emergency)",
    "dept_code": "Hospital Department index (0 to 5)",
    "doctor_available": "Doctor status (1 = Active, 0 = In Emergency / On Break)",
    "arrival_hour": "OPD registration hour (8 to 20)",
    "emergency_interruptions": "Simulated emergency cases interrupting routine queue"
}

def train_and_evaluate():
    """Trains Random Forest & Linear Regression, evaluates metrics, and saves artifacts."""
    if not os.path.exists(CSV_PATH):
        print("[ML] Training CSV not found. Generating new dataset...")
        df = generate_training_dataset(1500)
    else:
        df = pd.read_csv(CSV_PATH)

    print(f"[ML] Loaded training dataset with {len(df)} patient records.")

    X = df[FEATURE_COLUMNS]
    y = df["actual_wait_time"]

    # 80/20 Train-Test split with fixed seed for honest evaluation
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    # 1. Train Random Forest Regressor
    rf = RandomForestRegressor(
        n_estimators=120,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)

    # Calculate actual RF metrics
    rf_mae = float(mean_absolute_error(y_test, rf_preds))
    rf_rmse = float(np.sqrt(mean_squared_error(y_test, rf_preds)))
    rf_r2 = float(r2_score(y_test, rf_preds))

    # 2. Train Linear Regression as Baseline
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    lr_preds = lr.predict(X_test)

    # Calculate actual Linear Regression metrics
    lr_mae = float(mean_absolute_error(y_test, lr_preds))
    lr_rmse = float(np.sqrt(mean_squared_error(y_test, lr_preds)))
    lr_r2 = float(r2_score(y_test, lr_preds))

    # 3. Extract Feature Importances from Random Forest
    importances = rf.feature_importances_
    feature_importance_list = []
    for col, imp in zip(FEATURE_COLUMNS, importances):
        feature_importance_list.append({
            "feature": col,
            "importance": round(float(imp) * 100, 2),
            "description": FEATURE_DESCRIPTIONS.get(col, "")
        })

    # Sort descending by importance
    feature_importance_list.sort(key=lambda x: x["importance"], reverse=True)

    # 4. Save trained models using joblib
    joblib.dump(rf, RF_MODEL_PATH)
    joblib.dump(lr, LINEAR_MODEL_PATH)
    print(f"[ML] Random Forest model saved to: {RF_MODEL_PATH}")
    print(f"[ML] Linear Regression model saved to: {LINEAR_MODEL_PATH}")

    # 5. Save metrics to JSON for frontend presentation
    metrics_data = {
        "trained_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "features": FEATURE_COLUMNS,
        "rf_metrics": {
            "model_name": "Random Forest Regressor (Tuned)",
            "mae": round(rf_mae, 2),
            "rmse": round(rf_rmse, 2),
            "r2": round(rf_r2, 4),
            "r2_percentage": round(rf_r2 * 100, 2)
        },
        "linear_metrics": {
            "model_name": "Multiple Linear Regression (Baseline)",
            "mae": round(lr_mae, 2),
            "rmse": round(lr_rmse, 2),
            "r2": round(lr_r2, 4),
            "r2_percentage": round(lr_r2 * 100, 2)
        },
        "feature_importance": feature_importance_list,
        "explanation": {
            "summary": "Random Forest captures non-linear relationships such as triage priority queue jumping, doctor overload compounding, and emergency interruptions far better than linear regression.",
            "mae_meaning": f"On average, the Random Forest prediction is within ±{round(rf_mae, 1)} minutes of actual waiting time.",
            "r2_meaning": f"The Random Forest model explains approximately {round(rf_r2 * 100, 1)}% of the total variance in patient waiting times."
        }
    }

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_data, f, indent=4)

    print(f"[ML] Metrics successfully saved to: {METRICS_PATH}")
    print(f"     Random Forest -> MAE: {rf_mae:.2f} mins | RMSE: {rf_rmse:.2f} mins | R²: {rf_r2:.4f}")
    print(f"     Linear Reg    -> MAE: {lr_mae:.2f} mins | RMSE: {lr_rmse:.2f} mins | R²: {lr_r2:.4f}")
    return metrics_data

if __name__ == "__main__":
    train_and_evaluate()
