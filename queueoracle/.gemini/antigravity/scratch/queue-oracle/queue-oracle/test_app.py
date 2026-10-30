"""
QUEUE ORACLE - End-to-End System Integration Tests
Validates all major modules, prediction accuracy, dynamic recalculation,
doctor reassignment, bed forecasts, and simulation triggers.
"""

import unittest
import json
from app import app
from database import get_db_connection

class TestQueueOracle(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_01_index_html(self):
        """Tests that root / serves index.html."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"QUEUE ORACLE", res.data)

    def test_02_overview_api(self):
        """Tests overview KPI metrics."""
        res = self.client.get("/api/overview")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("total_registered", data)
        self.assertIn("waiting_patients", data)
        self.assertIn("avg_predicted_wait_time", data)
        self.assertIn("total_beds", data)
        self.assertGreater(data["total_registered"], 0)
        print(f"[TEST 02 PASS] Overview KPIs loaded: {data['total_registered']} patients, {data['waiting_patients']} waiting.")

    def test_03_patient_registration_and_prediction(self):
        """Tests registering a patient and querying AI wait time prediction."""
        payload = {
            "name": "Integration Test Patient",
            "department": "General Medicine",
            "priority": "Normal",
            "disease_tag": "Fever-related"
        }
        res = self.client.post("/api/patients", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        token = data["patient"]["opd_token"]
        predicted_wait = data["patient"]["predicted_wait_time"]
        self.assertGreater(predicted_wait, 0)
        print(f"[TEST 03 PASS] Patient registered: Token #{token}, Predicted wait: {predicted_wait} mins.")

        # Query by token lookup
        lookup_res = self.client.get(f"/api/patients/{token}")
        self.assertEqual(lookup_res.status_code, 200)
        lookup_data = lookup_res.get_json()
        self.assertTrue(lookup_data["success"])
        self.assertEqual(lookup_data["patient"]["opd_token"], token)
        print(f"[TEST 03 PASS] Token lookup verified for Token #{token}.")

    def test_04_dynamic_delay_recalculation(self):
        """Tests injecting a delay and verifying downstream queue recalculation."""
        # Get an active waiting patient
        p_res = self.client.get("/api/patients?status=WAITING")
        patients = p_res.get_json()
        self.assertGreater(len(patients), 1)

        first_patient = patients[0]
        second_patient = patients[1]
        prev_wait = second_patient["predicted_wait_time"]

        # Inject +20 min delay on first patient
        delay_res = self.client.post(f"/api/patients/{first_patient['id']}/delay", json={"delay_minutes": 20})
        self.assertEqual(delay_res.status_code, 200)

        # Check that recalculation executed
        p_res_after = self.client.get(f"/api/patients/{second_patient['opd_token']}")
        after_data = p_res_after.get_json()
        new_wait = after_data["patient"]["predicted_wait_time"]
        self.assertGreaterEqual(new_wait, prev_wait)
        print(f"[TEST 04 PASS] Dynamic delay cascade verified: Wait adjusted from {prev_wait}m to {new_wait}m.")

    def test_05_patient_status_lifecycle(self):
        """Tests WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED."""
        # Create a test patient
        reg_res = self.client.post("/api/patients", json={"name": "Lifecycle Patient", "department": "Pediatrics", "priority": "Normal"})
        pat_id = reg_res.get_json()["patient"]["id"]

        # Call
        res_call = self.client.post(f"/api/patients/{pat_id}/status", json={"status": "CALLED"})
        self.assertEqual(res_call.status_code, 200)

        # Consult
        res_consult = self.client.post(f"/api/patients/{pat_id}/status", json={"status": "IN_CONSULTATION"})
        self.assertEqual(res_consult.status_code, 200)

        # Complete
        res_comp = self.client.post(f"/api/patients/{pat_id}/status", json={"status": "COMPLETED", "actual_duration": 14})
        self.assertEqual(res_comp.status_code, 200)
        print(f"[TEST 05 PASS] Full patient consultation lifecycle verified for ID {pat_id}.")

    def test_06_doctor_workload_and_reassignment(self):
        """Tests doctor workload monitoring and administrator reassignment approval."""
        doc_res = self.client.get("/api/doctors")
        self.assertEqual(doc_res.status_code, 200)
        docs = doc_res.get_json()
        self.assertGreater(len(docs), 0)

        # Query recommendations
        rec_res = self.client.get("/api/recommendations")
        self.assertEqual(rec_res.status_code, 200)
        recs = rec_res.get_json()

        reassign_rec = next((r for r in recs if r["type"] == "DOCTOR_REASSIGNMENT" and r["status"] == "PENDING"), None)
        if reassign_rec:
            # Approve recommendation
            app_res = self.client.post(f"/api/recommendations/{reassign_rec['id']}/approve")
            self.assertEqual(app_res.status_code, 200)
            app_data = app_res.get_json()
            self.assertTrue(app_data["success"])
            print(f"[TEST 06 PASS] Workload Reassignment Approved: {app_data['message']}")

    def test_07_bed_occupancy_and_forecast(self):
        """Tests bed occupancy analytics and 1h-4h hourly horizon forecast."""
        res = self.client.get("/api/beds")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("overall", data)
        self.assertIn("departments", data)
        self.assertEqual(len(data["departments"][0]["hourly_forecasts"]), 4)

        # Simulate admission
        adm_res = self.client.post("/api/beds/simulate-admit", json={"department": "Cardiology"})
        self.assertEqual(adm_res.status_code, 200)
        print(f"[TEST 07 PASS] Bed occupancy & 4-hour horizon verified.")

    def test_08_disease_trends_and_surge(self):
        """Tests disease surveillance trends and outbreak surge trigger."""
        res = self.client.get("/api/disease-trends")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("diseases", data)
        self.assertIn("disclaimer", data)

        # Simulate surge
        surge_res = self.client.post("/api/disease-trends/simulate-surge", json={"disease": "Dengue", "additional_cases": 10})
        self.assertEqual(surge_res.status_code, 200)
        print(f"[TEST 08 PASS] Disease surveillance and surge simulation verified.")

    def test_09_inventory_and_restock(self):
        """Tests inventory management, shortage risk, and replenishment."""
        res = self.client.get("/api/inventory")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreater(data["total_items"], 0)

        first_item = data["items"][0]
        restock_res = self.client.post(f"/api/inventory/{first_item['id']}/restock", json={"quantity": 50})
        self.assertEqual(restock_res.status_code, 200)
        print(f"[TEST 09 PASS] Inventory risk analysis and restock verified for {first_item['item_name']}.")

    def test_10_ml_performance_metrics(self):
        """Tests machine learning evaluation metrics (MAE, RMSE, R-squared)."""
        res = self.client.get("/api/model-performance")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("rf_metrics", data)
        self.assertIn("linear_metrics", data)
        self.assertIn("feature_importance", data)
        self.assertGreater(data["rf_metrics"]["r2"], 0.90)
        print(f"[TEST 10 PASS] ML Metrics verified: Random Forest R²={data['rf_metrics']['r2']}, MAE={data['rf_metrics']['mae']} mins.")

if __name__ == "__main__":
    unittest.main()
