/**
 * QUEUE ORACLE - Interactive Simulation Engine (Section 13)
 * Provides comprehensive hackathon simulation controls that modify underlying
 * SQLite data and trigger dynamic real-time recalculations across all modules.
 */

function loadSimulationControls() {
    // Populate doctors in simulation selector
    fetch("/api/doctors")
        .then(res => res.json())
        .then(doctors => {
            const docSelect = document.getElementById("simSelectDoctor");
            if (docSelect) {
                docSelect.innerHTML = doctors.map(d => `
                    <option value="${d.id}">${d.name} (${d.department}) - Room ${d.room_no}</option>
                `).join("");
            }
        });
}

// 1. Simulate Burst Patient Arrival
async function simBurstArrival(count, priority = "Normal") {
    const dept = document.getElementById("simSelectDept")?.value || "General Medicine";
    const docId = document.getElementById("simSelectDoctor")?.value;

    try {
        const res = await fetch("/api/simulation/burst-patients", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ count, department: dept, priority, doctor_id: docId })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: Burst of +${count} ${priority} patients added! Queues recalculated.`, "success");
            loadOverview();
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 2. Simulate Consultation Delay
async function simDoctorDelay(delayMinutes) {
    const docId = document.getElementById("simSelectDoctor")?.value;
    if (!docId) {
        showToast("Please select a target doctor first.", "warning");
        return;
    }

    try {
        // Find active patient in consultation or first waiting for this doctor
        const patRes = await fetch(`/api/patients?doctor_id=${docId}`);
        const patients = await patRes.json();
        const targetPat = patients.find(p => p.status === "IN_CONSULTATION") || patients[0];

        if (!targetPat) {
            showToast("No active patients found for selected doctor to delay.", "warning");
            return;
        }

        const res = await fetch(`/api/patients/${targetPat.id}/delay`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ delay_minutes: delayMinutes })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: Injected +${delayMinutes}m delay on ${targetPat.name}'s consultation! All subsequent patient wait times shifted forward.`, "warning");
            loadOverview();
            loadQueue();
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 3. Simulate Complete Current Consultation
async function simCompleteCurrentConsultation() {
    const docId = document.getElementById("simSelectDoctor")?.value;
    try {
        const patRes = await fetch(`/api/patients?doctor_id=${docId}`);
        const patients = await patRes.json();
        const inConsult = patients.find(p => p.status === "IN_CONSULTATION");

        if (!inConsult) {
            showToast("No patient currently in consultation for selected doctor.", "info");
            return;
        }

        const res = await fetch(`/api/patients/${inConsult.id}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "COMPLETED", actual_duration: inConsult.estimated_duration })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: Consultation completed for Token #${inConsult.opd_token}! Remaining queue times updated.`, "success");
            loadOverview();
            loadQueue();
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 4. Simulate Doctor Availability Toggle (Goes on Break / Emergency)
async function simToggleDoctorAvail() {
    const docId = document.getElementById("simSelectDoctor")?.value;
    if (!docId) return;

    try {
        const res = await fetch(`/api/doctors/${docId}/availability`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: ${data.message} Queue recalculation triggered!`, "warning");
            loadOverview();
            loadDoctors();
            loadQueue();
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 5. Simulate Hospital Bed Admission Surge
async function simBedAdmission() {
    const dept = document.getElementById("simSelectBedDept")?.value || "Cardiology";
    try {
        const res = await fetch("/api/beds/simulate-admit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ department: dept })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: ${data.message} Bed occupancy increased!`, "warning");
            loadOverview();
            loadBeds();
        } else {
            showToast(data.message, "danger");
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 6. Simulate Hospital Bed Discharge
async function simBedDischarge() {
    const dept = document.getElementById("simSelectBedDept")?.value || "Cardiology";
    try {
        const res = await fetch("/api/beds/simulate-discharge", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ department: dept })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: ${data.message} Available beds increased!`, "success");
            loadOverview();
            loadBeds();
        } else {
            showToast(data.message, "danger");
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 7. Simulate Disease Outbreak Surge (Dengue / Malaria)
async function simDiseaseOutbreak(disease, count) {
    try {
        const res = await fetch("/api/disease-trends/simulate-surge", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ disease: disease, additional_cases: count })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: ${data.message} Recalculated epidemiological forecasts & inventory warnings!`, "danger");
            loadOverview();
            loadDiseaseTrends();
            loadInventory();
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 8. Simulate Inventory Depletion (Force Stockout)
async function simDepleteInventory(itemId, qty) {
    try {
        const res = await fetch(`/api/inventory/${itemId}/adjust`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ available_qty: qty })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Simulation: Injected inventory depletion to ${qty} units. Shortage alert active!`, "danger");
            loadOverview();
            loadInventory();
        }
    } catch (err) {
        showToast("Simulation error: " + err, "danger");
    }
}

// 9. Reset Entire Simulation to Clean Seed
async function resetSimulationBaseline() {
    if (!confirm("Are you sure you want to reset hospital operational data back to the clean demonstration baseline?")) {
        return;
    }

    try {
        const res = await fetch("/api/simulation/reset", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            showToast("Simulation reset: Database reseeded and models re-synced!", "success");
            loadOverview();
            loadPatients();
            loadQueue();
            loadDoctors();
            loadBeds();
            loadDiseaseTrends();
            loadInventory();
            loadRecommendations();
        }
    } catch (err) {
        showToast("Error resetting simulation: " + err, "danger");
    }
}
