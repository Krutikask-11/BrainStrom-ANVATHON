/**
 * QUEUE ORACLE - Dashboard Logic & API Integration
 * Manages all 14 navigation sections, live updates, and interactive workflows.
 */

// Global State
const OracleState = {
    currentSection: "overview",
    overviewData: null,
    doctors: [],
    patients: [],
    beds: null,
    diseaseData: null,
    inventoryData: null,
    recommendations: [],
    autoRefreshInterval: null
};

// UI Notification Toast
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `oracle-toast ${type}`;
    let icon = "fa-info-circle text-primary";
    if (type === "success") icon = "fa-check-circle text-success";
    if (type === "danger") icon = "fa-exclamation-triangle text-danger";
    if (type === "warning") icon = "fa-exclamation-circle text-warning";

    toast.innerHTML = `
        <i class="fas ${icon} fa-lg"></i>
        <div class="flex-grow-1">${message}</div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Navigation Handler
function navigateTo(sectionId) {
    OracleState.currentSection = sectionId;

    // Update sidebar active class
    document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => {
        if (link.dataset.section === sectionId) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });

    // Update visible section
    document.querySelectorAll(".dashboard-section").forEach(sec => {
        if (sec.id === `section-${sectionId}`) {
            sec.classList.add("active");
        } else {
            sec.classList.remove("active");
        }
    });

    // Load data specific to this section
    switch (sectionId) {
        case "overview":
            loadOverview();
            break;
        case "patients":
            loadPatients();
            break;
        case "queue":
            loadQueue();
            break;
        case "prediction":
            // Ready for lookup
            break;
        case "doctors":
            loadDoctors();
            break;
        case "forecast":
            loadResourceForecast();
            break;
        case "beds":
            loadBeds();
            break;
        case "disease":
            loadDiseaseTrends();
            break;
        case "inventory":
            loadInventory();
            break;
        case "recommendations":
            loadRecommendations();
            break;
        case "insights":
            loadInsights();
            break;
        case "simulation":
            loadSimulationControls();
            break;
        case "ml-performance":
            loadMLPerformance();
            break;
        case "about":
            // Static guide
            break;
    }
}

// Clock updates
function updateClock() {
    const el = document.getElementById("live-clock");
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
}

// ---------------------------------------------------------------------
// 1. OVERVIEW MODULE
// ---------------------------------------------------------------------
async function loadOverview() {
    try {
        const res = await fetch("/api/overview");
        const data = await res.json();
        OracleState.overviewData = data;

        // KPI Counts
        document.getElementById("kpiTotalPatients").textContent = data.total_registered;
        document.getElementById("kpiWaitingPatients").textContent = data.waiting_patients;
        document.getElementById("kpiInConsultation").textContent = data.in_consultation;
        document.getElementById("kpiAvgWaitTime").textContent = `${data.avg_predicted_wait_time}m`;
        document.getElementById("kpiDoctorsRatio").textContent = `${data.available_doctors} / ${data.available_doctors + data.busy_doctors}`;
        document.getElementById("kpiBedOccupancy").textContent = `${data.overall_occupancy_rate}%`;

        // Overcrowding alerts
        const alertBox = document.getElementById("overviewAlertsBanner");
        if (alertBox) {
            let alertHtml = "";
            if (data.overcrowded_departments.length > 0) {
                alertHtml += `<div class="alert alert-warning py-2 mb-2 d-flex align-items-center gap-2">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span><strong>High OPD Traffic:</strong> ${data.overcrowded_departments.join(", ")} experiencing bottleneck patient volume.</span>
                </div>`;
            }
            if (data.predicted_shortages.length > 0) {
                alertHtml += `<div class="alert alert-danger py-2 mb-2 d-flex align-items-center gap-2">
                    <i class="fas fa-biohazard"></i>
                    <span><strong>Resource Alerts:</strong> ${data.predicted_shortages.join(" | ")}</span>
                </div>`;
            }
            alertBox.innerHTML = alertHtml;
        }

        // Render Overview Department Waiting Chart
        OracleCharts.renderDeptWaitingChart(data.departments);

        // Fetch hourly arrivals forecast for chart
        const fRes = await fetch("/api/forecast/arrivals");
        const forecastData = await fRes.json();
        OracleCharts.renderArrivalsChart(forecastData);

        // Populate recent queue table
        const tbody = document.getElementById("tableRecentQueue");
        if (tbody) {
            tbody.innerHTML = data.recent_queue.map(p => `
                <tr>
                    <td><span class="token-badge">#${p.opd_token}</span></td>
                    <td><strong>${p.name}</strong><br><small class="text-muted">${p.patient_id}</small></td>
                    <td>${p.department}</td>
                    <td>${p.doctor_name} <br><small class="text-muted">Rm ${p.room_no}</small></td>
                    <td><span class="priority-pill priority-${p.priority.toLowerCase()}">${p.priority}</span></td>
                    <td><strong>${p.predicted_wait_time} min</strong></td>
                    <td><span class="badge bg-light text-dark border">${p.expected_consultation_time}</span></td>
                    <td><span class="badge-status badge-${p.status === 'IN_CONSULTATION' ? 'success' : (p.status === 'CALLED' ? 'warning' : 'info')}">${p.status}</span></td>
                </tr>
            `).join("");
        }

        // Populate department summary cards
        const deptCardsContainer = document.getElementById("overviewDeptCards");
        if (deptCardsContainer) {
            deptCardsContainer.innerHTML = data.departments.map(d => `
                <div class="col-md-4 col-sm-6 mb-3">
                    <div class="p-3 border rounded bg-white shadow-sm h-100">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0 fw-bold">${d.name}</h6>
                            <span class="badge-status badge-${d.status}">${d.status}</span>
                        </div>
                        <div class="d-flex justify-content-between small text-muted mb-1">
                            <span>Waiting Patients:</span>
                            <strong class="text-dark">${d.waiting_patients}</strong>
                        </div>
                        <div class="d-flex justify-content-between small text-muted mb-1">
                            <span>Bed Occupancy:</span>
                            <strong class="text-dark">${d.occupied_beds}/${d.total_beds} (${d.occupancy_rate}%)</strong>
                        </div>
                        <div class="progress" style="height: 6px;">
                            <div class="progress-bar ${d.occupancy_rate >= 90 ? 'bg-danger' : (d.occupancy_rate >= 75 ? 'bg-warning' : 'bg-primary')}" style="width: ${d.occupancy_rate}%;"></div>
                        </div>
                    </div>
                </div>
            `).join("");
        }

    } catch (err) {
        console.error("Error loading overview:", err);
    }
}

// ---------------------------------------------------------------------
// 2. PATIENT MANAGEMENT MODULE
// ---------------------------------------------------------------------
async function loadPatients() {
    try {
        const dept = document.getElementById("filterPatientDept")?.value || "";
        const status = document.getElementById("filterPatientStatus")?.value || "";

        let url = "/api/patients?";
        if (dept) url += `department=${encodeURIComponent(dept)}&`;
        if (status) url += `status=${encodeURIComponent(status)}&`;

        const res = await fetch(url);
        const patients = await res.json();
        OracleState.patients = patients;

        const tbody = document.getElementById("tablePatientsList");
        if (tbody) {
            tbody.innerHTML = patients.map(p => `
                <tr>
                    <td><span class="token-badge">#${p.opd_token}</span></td>
                    <td><strong>${p.name}</strong><br><small class="text-muted">${p.patient_id}</small></td>
                    <td>${p.department}</td>
                    <td>${p.doctor_name}</td>
                    <td>${p.arrival_time}</td>
                    <td><span class="priority-pill priority-${p.priority.toLowerCase()}">${p.priority}</span></td>
                    <td><strong>${p.predicted_wait_time}m</strong></td>
                    <td><span class="badge bg-light text-dark border">${p.expected_consultation_time}</span></td>
                    <td><span class="badge-status badge-${p.status === 'IN_CONSULTATION' ? 'success' : (p.status === 'CALLED' ? 'warning' : 'info')}">${p.status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary py-0" onclick="lookupToken(${p.opd_token})">
                            <i class="fas fa-brain"></i> AI Predict
                        </button>
                    </td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading patients:", err);
    }
}

async function handleRegisterPatient(e) {
    e.preventDefault();
    const name = document.getElementById("regPatientName").value;
    const department = document.getElementById("regPatientDept").value;
    const priority = document.getElementById("regPatientPriority").value;
    const disease_tag = document.getElementById("regPatientDisease").value;

    try {
        const res = await fetch("/api/patients", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, department, priority, disease_tag })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Patient #${data.patient.opd_token} (${data.patient.name}) registered! Predicted wait: ${data.patient.predicted_wait_time}m`, "success");
            // Reset modal & form
            document.getElementById("formRegisterPatient").reset();
            const modalEl = document.getElementById("modalRegisterPatient");
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();

            loadPatients();
            loadOverview();
        }
    } catch (err) {
        showToast("Error registering patient: " + err, "danger");
    }
}

// ---------------------------------------------------------------------
// 3. PATIENT QUEUE & STATUS TRACKING (Section 5 & 6)
// ---------------------------------------------------------------------
async function loadQueue() {
    try {
        const docRes = await fetch("/api/doctors");
        const doctors = await docRes.json();

        const patRes = await fetch("/api/patients");
        const patients = await patRes.json();

        const container = document.getElementById("doctorQueuesContainer");
        if (!container) return;

        let html = "";
        doctors.forEach(doc => {
            const docPatients = patients.filter(p => p.assigned_doctor_id === doc.id && p.status !== "COMPLETED");
            const inConsult = docPatients.find(p => p.status === "IN_CONSULTATION");
            const waitingPatients = docPatients.filter(p => p.status !== "IN_CONSULTATION");

            html += `
                <div class="card-widget mb-4">
                    <div class="widget-header">
                        <div>
                            <h5 class="widget-title mb-0">
                                <i class="fas fa-user-md"></i> ${doc.name}
                                <span class="badge-status badge-${doc.workload_badge} ms-2">${doc.workload_status}</span>
                                ${!doc.is_available ? '<span class="badge bg-secondary ms-1">ON BREAK</span>' : ''}
                            </h5>
                            <small class="text-muted">${doc.department} | ${doc.specialization} | Room ${doc.room_no} | Avg Consult: ${doc.avg_consult_time} mins</small>
                        </div>
                       <div class="d-flex align-items-center gap-2">
    <span class="badge bg-primary fs-6">${docPatients.length} Active in Queue</span>
</div>
                    </div>

                    <!-- Currently In Consultation Banner -->
                    <div class="p-3 mb-3 rounded" style="background-color: #f0fdf4; border: 1px solid #bbf7d0;">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <span class="badge bg-success mb-1">IN CONSULTATION NOW</span>
                                ${inConsult ? `
                                    <h6 class="mb-0 fw-bold">Token #${inConsult.opd_token} - ${inConsult.name} (${inConsult.patient_id})</h6>
                                    <small class="text-muted">Arrival: ${inConsult.arrival_time} | Priority: ${inConsult.priority} | Est. Duration: ${inConsult.estimated_duration}m</small>
                                ` : `
                                    <p class="mb-0 text-muted fst-italic">No patient currently in consultation room.</p>
                                `}
                            </div>
                            ${inConsult ? `
                                <div class="btn-group">
                                    <button class="btn btn-sm btn-outline-warning" onclick="promptDelay(${inConsult.id}, '${inConsult.name}')">
                                        <i class="fas fa-clock"></i> Record Delay
                                    </button>
                                    <button class="btn btn-sm btn-success" onclick="updateStatus(${inConsult.id}, 'COMPLETED')">
                                        <i class="fas fa-check-double"></i> Complete Consultation
                                    </button>
                                </div>
                            ` : ''}
                        </div>
                    </div>

                    <!-- Waiting Queue Table -->
                    <h6>Waiting & Called Queue (${waitingPatients.length} Patients)</h6>
                    <div class="table-responsive">
                        <table class="table-custom">
                            <thead>
                                <tr>
                                    <th>Pos</th>
                                    <th>Token</th>
                                    <th>Patient</th>
                                    <th>Priority</th>
                                    <th>Arrival</th>
                                    <th>Pred. Wait</th>
                                    <th>Expected Time</th>
                                    <th>Status</th>
                                    <th>Queue Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${waitingPatients.length === 0 ? `
                                    <tr><td colspan="9" class="text-center text-muted py-3">Queue is currently clear for this doctor.</td></tr>
                                ` : waitingPatients.map((p, idx) => `
                                    <tr class="${p.priority === 'Emergency' ? 'table-danger' : ''}">
                                        <td><strong>#${idx + 1}</strong></td>
                                        <td><span class="token-badge">#${p.opd_token}</span></td>
                                        <td><strong>${p.name}</strong></td>
                                        <td><span class="priority-pill priority-${p.priority.toLowerCase()}">${p.priority}</span></td>
                                        <td>${p.arrival_time}</td>
                                        <td><strong class="text-primary">${p.predicted_wait_time} min</strong></td>
                                        <td><span class="badge bg-light text-dark border">${p.expected_consultation_time}</span></td>
                                        <td><span class="badge-status badge-${p.status === 'CALLED' ? 'warning' : 'info'}">${p.status}</span></td>
                                        <td>
                                            <div class="btn-group btn-group-sm">
                                                ${p.status === 'WAITING' ? `
                                                    <button class="btn btn-warning py-0" onclick="updateStatus(${p.id}, 'CALLED')">
                                                        <i class="fas fa-bell"></i> Call Patient
                                                    </button>
                                                ` : `
                                                    <button class="btn btn-primary py-0" onclick="updateStatus(${p.id}, 'IN_CONSULTATION')">
                                                        <i class="fas fa-play"></i> Start Consultation
                                                    </button>
                                                `}
                                                <button class="btn btn-outline-danger py-0" onclick="changePriorityModal(${p.id}, '${p.priority}')" title="Change Priority">
                                                    <i class="fas fa-sort-amount-up"></i>
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    } catch (err) {
        console.error("Error loading queue:", err);
    }
}

// Status update dispatcher
async function updateStatus(patientId, status, actualDuration = null) {
    try {
        const body = { status };
        if (actualDuration !== null) body.actual_duration = actualDuration;

        const res = await fetch(`/api/patients/${patientId}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Patient status updated: ${status}. Waiting times dynamically recalculated!`, "success");
            loadQueue();
            loadOverview();
        }
    } catch (err) {
        showToast("Error updating status: " + err, "danger");
    }
}

// Prompt consultation delay
function promptDelay(patientId, patientName) {
    const minsStr = prompt(`Simulate Consultation Delay for ${patientName}:\nEnter additional consultation delay in minutes (e.g. 15 or 25):`, "15");
    if (minsStr && !isNaN(minsStr)) {
        const mins = parseInt(minsStr);
        applyDelay(patientId, mins);
    }
}

async function applyDelay(patientId, delayMins) {
    try {
        const res = await fetch(`/api/patients/${patientId}/delay`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ delay_minutes: delayMins })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Consultation delayed by +${delayMins} mins! Recalculated all subsequent patient waiting times.`, "warning");
            loadQueue();
            loadOverview();
        }
    } catch (err) {
        showToast("Error applying delay: " + err, "danger");
    }
}

async function toggleDoctorAvail(doctorId) {
    try {
        const res = await fetch(`/api/doctors/${doctorId}/availability`, {
            method: "POST"
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, "info");
            loadQueue();
            loadDoctors();
            loadOverview();
        }
    } catch (err) {
        showToast("Error changing doctor status: " + err, "danger");
    }
}

function changePriorityModal(patientId, currentPriority) {
    const newPri = prompt(`Change Priority (Current: ${currentPriority}):\nType: Normal, Medium, or Emergency`, currentPriority === "Normal" ? "Emergency" : "Normal");
    if (newPri && ["Normal", "Medium", "Emergency"].includes(newPri)) {
        fetch(`/api/patients/${patientId}/priority`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ priority: newPri })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                showToast(`Priority updated to ${newPri}! Queue re-sorted.`, "success");
                loadQueue();
                loadPatients();
            }
        });
    }
}

// ---------------------------------------------------------------------
// 4. WAITING TIME PREDICTION LOOKUP (Section 4)
// ---------------------------------------------------------------------
async function lookupToken(token) {
    if (!token) {
        token = document.getElementById("inputLookupToken").value.trim();
    }
    if (!token) {
        showToast("Please enter a valid OPD Token Number or Patient ID.", "warning");
        return;
    }

    try {
        const res = await fetch(`/api/patients/${encodeURIComponent(token)}`);
        const data = await res.json();
        const displayCard = document.getElementById("predictionResultCard");

        if (!data.success) {
            displayCard.innerHTML = `<div class="alert alert-danger mb-0">${data.message}</div>`;
            return;
        }

        const p = data.patient;
        navigateTo("prediction");
        document.getElementById("inputLookupToken").value = p.opd_token;

        displayCard.innerHTML = `
            <div class="card-widget border-primary" style="background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%);">
                <div class="d-flex justify-content-between align-items-center mb-3 pb-2 border-bottom">
                    <div>
                        <span class="token-badge fs-5">OPD Token: #${p.opd_token}</span>
                        <h4 class="mt-2 mb-0 fw-bold text-navy">${p.name}</h4>
                        <small class="text-muted">${p.patient_id} | ${p.department} Department</small>
                    </div>
                    <div class="text-end">
                        <span class="priority-pill priority-${p.priority.toLowerCase()} fs-6">${p.priority} Priority</span>
                        <div class="mt-2"><span class="badge-status badge-${p.status === 'IN_CONSULTATION' ? 'success' : (p.status === 'CALLED' ? 'warning' : 'info')}">${p.status}</span></div>
                    </div>
                </div>

                <div class="row g-3 my-2">
                    <div class="col-md-3 col-6">
                        <div class="p-3 bg-white rounded border">
                            <small class="text-muted d-block text-uppercase">Assigned Doctor</small>
                            <strong class="fs-6 text-dark">${p.assigned_doctor}</strong>
                            <div class="small text-muted">Room ${p.room_no} (${p.doctor_available ? '<span class="text-success">Available</span>' : '<span class="text-warning">On Break</span>'})</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-6">
                        <div class="p-3 bg-white rounded border">
                            <small class="text-muted d-block text-uppercase">Patients Ahead</small>
                            <strong class="fs-3 text-primary">${p.patients_ahead}</strong>
                            <div class="small text-muted">Waiting ahead in queue</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-6">
                        <div class="p-3 bg-white rounded border">
                            <small class="text-muted d-block text-uppercase">Predicted Waiting Time</small>
                            <strong class="fs-3 text-danger">${p.predicted_wait_time} mins</strong>
                            <div class="small text-muted">Model: Random Forest Regressor</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-6">
                        <div class="p-3 bg-white rounded border">
                            <small class="text-muted d-block text-uppercase">Expected Consultation</small>
                            <strong class="fs-3 text-success">${p.expected_consultation}</strong>
                            <div class="small text-muted">Arrival: ${p.arrival_time}</div>
                        </div>
                    </div>
                </div>

                <div class="p-3 bg-white rounded border mt-3">
                    <h6 class="fw-bold mb-2 text-navy"><i class="fas fa-microchip text-primary"></i> AI Explainability & Model Input Factors</h6>
                    <div class="row small text-muted">
                        <div class="col-md-4">
                            • Triage Priority: <strong>${p.priority}</strong> (Priority Code applied)<br>
                            • Average Doctor Consult Speed: <strong>${p.estimated_duration} mins</strong><br>
                            • Doctor State: <strong>${p.doctor_available ? 'Active in Clinic' : 'Delayed / Interrupted'}</strong>
                        </div>
                        <div class="col-md-4">
                            • Active Consultation Delays: <strong>+${p.delay_minutes} mins recorded</strong><br>
                            • Queue Order: Calculated via Emergency-first prioritization<br>
                            • Clinical Tag: <strong>${p.disease_tag}</strong>
                        </div>
                        <div class="col-md-4">
                            • Dynamic Recalculation: <strong>Active</strong><br>
                            • Model Inference Confidence: <strong>High (R² 0.996)</strong><br>
                            • Next scheduled recalculation on status change.
                        </div>
                    </div>
                </div>
            </div>
        `;

    } catch (err) {
        showToast("Error querying patient: " + err, "danger");
    }
}

// ---------------------------------------------------------------------
// 5. DOCTOR WORKLOAD & REASSIGNMENT RECOMMENDATIONS (Section 8)
// ---------------------------------------------------------------------
async function loadDoctors() {
    try {
        const res = await fetch("/api/doctors");
        const doctors = await res.json();
        OracleState.doctors = doctors;

        OracleCharts.renderDoctorWorkloadChart(doctors);

        const tbody = document.getElementById("tableDoctorsWorkload");
        if (tbody) {
            tbody.innerHTML = doctors.map(d => `
                <tr>
                    <td><strong>${d.name}</strong></td>
                    <td>${d.department}</td>
                    <td>${d.specialization}</td>
                    <td>Rm ${d.room_no}</td>
                    <td>
                        <span class="badge ${d.is_available ? 'bg-success' : 'bg-secondary'}">
                            ${d.is_available ? 'Available' : 'On Break'}
                        </span>
                    </td>
                    <td><strong class="text-primary fs-6">${d.waiting_count}</strong></td>
                    <td><span class="badge bg-light text-dark border">${d.active_consults} active</span></td>
                    <td>${d.avg_consult_time} mins</td>
                    <td><strong class="text-danger">${d.avg_wait_time}m</strong></td>
                    <td><span class="badge-status badge-${d.workload_badge}">${d.workload_status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-secondary py-0" onclick="toggleDoctorAvail(${d.id})">
                            <i class="fas fa-toggle-on"></i> Toggle
                        </button>
                    </td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading doctors:", err);
    }
}

async function loadRecommendations() {
    try {
        const res = await fetch("/api/recommendations");
        const recs = await res.json();
        OracleState.recommendations = recs;

        const container = document.getElementById("recommendationsListContainer");
        if (!container) return;

        const docRecs = recs.filter(r => r.type === "DOCTOR_REASSIGNMENT");

        if (docRecs.length === 0) {
            container.innerHTML = `
                <div class="card-widget text-center py-5">
                    <i class="fas fa-check-circle text-success fa-3x mb-3"></i>
                    <h5 class="fw-bold">Doctor Workload is Well Balanced</h5>
                    <p class="text-muted mb-0">No severe queue imbalances currently detected across departments.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = docRecs.map(r => `
            <div class="card-widget border-${r.priority === 'CRITICAL' ? 'danger' : 'warning'} mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom">
                    <div>
                        <span class="badge-status badge-${r.priority === 'CRITICAL' ? 'critical' : 'warning'} me-2">${r.priority} PRIORITY</span>
                        <h5 class="d-inline fw-bold text-navy">${r.title}</h5>
                    </div>
                    <span class="badge ${r.status === 'APPROVED' ? 'bg-success' : (r.status === 'REJECTED' ? 'bg-danger' : 'bg-warning')} fs-6">${r.status}</span>
                </div>

                <div class="row my-3">
                    <div class="col-md-6">
                        <div class="p-3 bg-light rounded mb-2">
                            <strong class="text-danger"><i class="fas fa-exclamation-triangle"></i> Identified Problem:</strong>
                            <p class="mb-0 mt-1 small">${r.problem}</p>
                        </div>
                        <div class="p-3 bg-light rounded">
                            <strong class="text-dark"><i class="fas fa-database"></i> Supporting Data:</strong>
                            <p class="mb-0 mt-1 small text-muted">${r.supporting_data}</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="p-3 bg-light rounded mb-2">
                            <strong class="text-primary"><i class="fas fa-arrow-circle-right"></i> Recommended Action:</strong>
                            <p class="mb-0 mt-1 small">${r.recommended_action}</p>
                        </div>
                        <div class="p-3 bg-light rounded">
                            <strong class="text-success"><i class="fas fa-chart-line"></i> Expected Benefit:</strong>
                            <p class="mb-0 mt-1 small text-muted">${r.expected_benefit}</p>
                        </div>
                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center pt-2 border-top">
                    <small class="text-muted"><i class="fas fa-clock"></i> Generated: ${r.created_at}</small>
                    <div>
                        ${r.status === 'PENDING' ? `
                            <button class="btn btn-oracle btn-oracle-success me-2" onclick="approveRec(${r.id})">
                                <i class="fas fa-check"></i> APPROVE REASSIGNMENT
                            </button>
                            <button class="btn btn-oracle btn-oracle-danger" onclick="rejectRec(${r.id})">
                                <i class="fas fa-times"></i> REJECT REASSIGNMENT
                            </button>
                        ` : `
                            <span class="text-muted small"><i class="fas fa-lock"></i> Decision executed (${r.status})</span>
                        `}
                    </div>
                </div>
            </div>
        `).join("");

    } catch (err) {
        console.error("Error loading recommendations:", err);
    }
}

async function approveRec(recId) {
    try {
        const res = await fetch(`/api/recommendations/${recId}/approve`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, "success");
            loadRecommendations();
            loadOverview();
            loadDoctors();
            loadQueue();
        } else {
            showToast(data.message, "warning");
        }
    } catch (err) {
        showToast("Error approving recommendation: " + err, "danger");
    }
}

async function rejectRec(recId) {
    try {
        const res = await fetch(`/api/recommendations/${recId}/reject`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, "info");
            loadRecommendations();
        }
    } catch (err) {
        showToast("Error rejecting recommendation: " + err, "danger");
    }
}

// ---------------------------------------------------------------------
// 6. BED OCCUPANCY MODULE (Section 9)
// ---------------------------------------------------------------------
async function loadBeds() {
    try {
        const res = await fetch("/api/beds");
        const bedData = await res.json();
        OracleState.beds = bedData;

        // KPI
        document.getElementById("bedKpiTotal").textContent = bedData.overall.total_beds;
        document.getElementById("bedKpiOccupied").textContent = bedData.overall.occupied_beds;
        document.getElementById("bedKpiAvailable").textContent = bedData.overall.available_beds;
        document.getElementById("bedKpiRate").textContent = `${bedData.overall.occupancy_rate}%`;

        // Render Donut & Forecast Charts
        OracleCharts.renderBedDonutChart(bedData.overall);
        OracleCharts.renderBedForecastChart(bedData.departments);

        // Bed occupancy table
        const tbody = document.getElementById("tableBedOccupancy");
        if (tbody) {
            tbody.innerHTML = bedData.departments.map(d => `
                <tr>
                    <td><strong>${d.department}</strong></td>
                    <td>${d.total_beds}</td>
                    <td>${d.occupied_beds}</td>
                    <td><strong class="text-success">${d.available_beds}</strong></td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <span>${d.occupancy_rate}%</span>
                            <div class="progress flex-grow-1" style="height: 6px;">
                                <div class="progress-bar ${d.occupancy_rate >= 90 ? 'bg-danger' : (d.occupancy_rate >= 75 ? 'bg-warning' : 'bg-primary')}" style="width: ${d.occupancy_rate}%;"></div>
                            </div>
                        </div>
                    </td>
                    <td>${d.hourly_forecasts[0].projected_percentage}%</td>
                    <td>${d.hourly_forecasts[1].projected_percentage}%</td>
                    <td>${d.hourly_forecasts[2].projected_percentage}%</td>
                    <td><strong class="${d.hourly_forecasts[3].projected_percentage >= 90 ? 'text-danger' : 'text-dark'}">${d.hourly_forecasts[3].projected_percentage}%</strong></td>
                    <td><span class="badge-status badge-${d.status}">${d.status}</span></td>
                    <td>
                        <small class="text-muted">${d.action_suggestion}</small>
                    </td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading beds:", err);
    }
}

// ---------------------------------------------------------------------
// 7. DISEASE TRENDS & PREPAREDNESS (Section 7 & 10)
// ---------------------------------------------------------------------
async function loadDiseaseTrends() {
    try {
        const res = await fetch("/api/disease-trends");
        const data = await res.json();
        OracleState.diseaseData = data;

        // Render 14-day history chart
        OracleCharts.renderDiseaseTrendsChart(data.diseases);

        // Render Preparedness Alerts Banner
        const alertBox = document.getElementById("diseasePreparednessAlerts");
        if (alertBox) {
            if (data.preparedness_alerts.length === 0) {
                alertBox.innerHTML = `<div class="alert alert-success py-2 mb-3">All disease surveillance trends are currently within seasonal baseline parameters.</div>`;
            } else {
                alertBox.innerHTML = data.preparedness_alerts.map(a => `
                    <div class="card-widget border-${a.badge === 'CRITICAL' ? 'danger' : 'warning'} mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="fw-bold mb-0 text-${a.badge === 'CRITICAL' ? 'danger' : 'warning'}">
                                <i class="fas fa-virus"></i> ${a.headline}
                            </h6>
                            <span class="badge-status badge-${a.badge}">${a.badge} SURGE</span>
                        </div>
                        <p class="small text-muted mb-2">${a.impact}</p>
                        <h6 class="small fw-bold text-navy mb-1">Operational Preparedness Recommendations:</h6>
                        <ul class="small mb-0 ps-3 text-muted">
                            ${a.recommendations.map(r => `<li>${r}</li>`).join("")}
                        </ul>
                    </div>
                `).join("");
            }
        }

        // Disease Table
        const tbody = document.getElementById("tableDiseaseTrends");
        if (tbody) {
            tbody.innerHTML = data.diseases.map(d => `
                <tr>
                    <td><strong>${d.disease_name}</strong></td>
                    <td>${d.department}</td>
                    <td><strong class="text-primary">${d.today_verified}</strong> <small class="text-muted">(${d.today_suspected} susp)</small></td>
                    <td>${d.past_7d_total} <small class="text-muted">(avg ${d.past_7d_avg}/d)</small></td>
                    <td>${d.past_30d_total}</td>
                    <td><strong class="${d.trend_percentage > 0 ? 'text-danger' : 'text-success'}">${d.trend_percentage > 0 ? '+' : ''}${d.trend_percentage}%</strong></td>
                    <td><span class="badge-status badge-${d.trend_badge}">${d.trend_direction}</span></td>
                    <td><strong class="text-dark">${d.tomorrow_forecast_verified}</strong> <small class="text-muted">(~${d.tomorrow_forecast_suspected} susp)</small></td>
                    <td>
                        ${d.inventory_warnings.length > 0 ? `
                            <span class="badge bg-danger">Shortage Risk (${d.inventory_warnings.length} items)</span>
                        ` : `
                            <span class="badge bg-success">Supplies Normal</span>
                        `}
                    </td>
                </tr>
            `).join("");
        }

    } catch (err) {
        console.error("Error loading disease trends:", err);
    }
}

// ---------------------------------------------------------------------
// 8. INVENTORY MODULE (Section 10)
// ---------------------------------------------------------------------
async function loadInventory() {
    try {
        const res = await fetch("/api/inventory");
        const inv = await res.json();
        OracleState.inventoryData = inv;

        OracleCharts.renderInventoryChart(inv.items);

        const tbody = document.getElementById("tableInventory");
        if (tbody) {
            tbody.innerHTML = inv.items.map(item => `
                <tr>
                    <td><strong>${item.item_name}</strong></td>
                    <td>${item.category}</td>
                    <td><strong class="${item.shortage_risk === 'CRITICAL' ? 'text-danger' : (item.shortage_risk === 'WARNING' ? 'text-warning' : 'text-success')}">${item.available_qty} ${item.unit}</strong></td>
                    <td>${item.min_stock} ${item.unit}</td>
                    <td>${item.daily_usage} / day</td>
                    <td>${item.days_cover} days</td>
                    <td>${item.associated_disease ? `<span class="badge bg-light text-dark border">${item.associated_disease}</span>` : '<span class="text-muted">-</span>'}</td>
                    <td><span class="badge-status badge-${item.badge}">${item.shortage_risk}</span></td>
                    <td><strong>${item.recommended_replenish} ${item.unit}</strong></td>
                    <td>
                        <button class="btn btn-sm btn-outline-success py-0" onclick="restockItem(${item.id})">
                            <i class="fas fa-plus-circle"></i> Restock
                        </button>
                    </td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading inventory:", err);
    }
}

async function restockItem(itemId) {
    const qtyStr = prompt("Enter replenishment quantity to add to stock:", "100");
    if (qtyStr && !isNaN(qtyStr)) {
        const qty = parseInt(qtyStr);
        try {
            const res = await fetch(`/api/inventory/${itemId}/restock`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ quantity: qty })
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message, "success");
                loadInventory();
                loadOverview();
            }
        } catch (err) {
            showToast("Error restocking item: " + err, "danger");
        }
    }
}

// ---------------------------------------------------------------------
// 9. RESOURCE FORECAST & STAFFING (Section 11)
// ---------------------------------------------------------------------
async function loadResourceForecast() {
    try {
        const arrRes = await fetch("/api/forecast/arrivals");
        const forecastData = await arrRes.json();

        OracleCharts.renderArrivalsChart(forecastData);
        OracleCharts.renderWaitTimeTrendsChart(forecastData.hours, forecastData.wait_time_trend);

        // Staffing table
        const stRes = await fetch("/api/staffing");
        const staffData = await stRes.json();

        const tbody = document.getElementById("tableStaffingForecast");
        if (tbody) {
            tbody.innerHTML = staffData.map(s => `
                <tr>
                    <td><strong>${s.department}</strong></td>
                    <td>${s.base_staff} Staff</td>
                    <td>${s.active_doctors}</td>
                    <td><strong>${s.active_patients}</strong></td>
                    <td>${s.patient_to_doctor_ratio} : 1</td>
                    <td><span class="badge-status badge-${s.badge}">${s.status}</span></td>
                    <td><strong>+${s.additional_staff_needed}</strong></td>
                    <td><small class="text-muted">${s.recommendation}</small></td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading resource forecast:", err);
    }
}

// ---------------------------------------------------------------------
// 10. ADMINISTRATOR INSIGHTS (Section 12)
// ---------------------------------------------------------------------
async function loadInsights() {
    try {
        const res = await fetch("/api/recommendations");
        const recs = await res.json();

        const container = document.getElementById("insightsListContainer");
        if (!container) return;

        container.innerHTML = recs.map(r => `
            <div class="card-widget border-${r.priority === 'CRITICAL' ? 'danger' : (r.priority === 'HIGH' ? 'warning' : 'primary')} mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom">
                    <div>
                        <span class="badge-status badge-${r.priority === 'CRITICAL' ? 'critical' : (r.priority === 'HIGH' ? 'warning' : 'info')} me-2">${r.priority}</span>
                        <span class="badge bg-light text-dark border me-2">${r.type}</span>
                        <h5 class="d-inline fw-bold text-navy">${r.title}</h5>
                    </div>
                    <span class="badge ${r.status === 'APPROVED' ? 'bg-success' : (r.status === 'REJECTED' ? 'bg-danger' : 'bg-warning')} fs-6">${r.status}</span>
                </div>

                <div class="row g-3 my-2">
                    <div class="col-md-6">
                        <div class="p-2 bg-light rounded mb-2">
                            <strong class="text-danger small d-block">Problem Identified:</strong>
                            <span class="small">${r.problem}</span>
                        </div>
                        <div class="p-2 bg-light rounded">
                            <strong class="text-dark small d-block">Supporting Clinical / Operational Data:</strong>
                            <span class="small text-muted">${r.supporting_data}</span>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="p-2 bg-light rounded mb-2">
                            <strong class="text-primary small d-block">Recommended Action:</strong>
                            <span class="small">${r.recommended_action}</span>
                        </div>
                        <div class="p-2 bg-light rounded">
                            <strong class="text-success small d-block">Predicted Operational Benefit:</strong>
                            <span class="small text-muted">${r.expected_benefit}</span>
                        </div>
                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center pt-2 border-top">
                    <small class="text-muted"><i class="fas fa-clock"></i> Generated: ${r.created_at}</small>
                    <div class="btn-group btn-group-sm">
                        ${r.status === 'PENDING' ? `
                            <button class="btn btn-success" onclick="approveRec(${r.id})"><i class="fas fa-check"></i> Approve</button>
                            <button class="btn btn-danger" onclick="rejectRec(${r.id})"><i class="fas fa-times"></i> Reject</button>
                        ` : (r.status === 'APPROVED' ? `
                            <button class="btn btn-outline-secondary" onclick="completeRec(${r.id})"><i class="fas fa-check-double"></i> Mark Completed</button>
                        ` : `
                            <span class="text-muted small">Status: ${r.status}</span>
                        `)}
                    </div>
                </div>
            </div>
        `).join("");

    } catch (err) {
        console.error("Error loading insights:", err);
    }
}

async function completeRec(recId) {
    try {
        const res = await fetch(`/api/recommendations/${recId}/complete`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, "success");
            loadInsights();
        }
    } catch (err) {
        showToast("Error updating recommendation: " + err, "danger");
    }
}

// ---------------------------------------------------------------------
// 11. MACHINE LEARNING MODEL PERFORMANCE (Section 16)
// ---------------------------------------------------------------------
async function loadMLPerformance() {
    try {
        const res = await fetch("/api/model-performance");
        const data = await res.json();

        // RF Metrics
        document.getElementById("rfMae").textContent = `${data.rf_metrics.mae} mins`;
        document.getElementById("rfRmse").textContent = `${data.rf_metrics.rmse} mins`;
        document.getElementById("rfR2").textContent = `${data.rf_metrics.r2} (${data.rf_metrics.r2_percentage}%)`;

        // Linear Metrics
        document.getElementById("linearMae").textContent = `${data.linear_metrics.mae} mins`;
        document.getElementById("linearRmse").textContent = `${data.linear_metrics.rmse} mins`;
        document.getElementById("linearR2").textContent = `${data.linear_metrics.r2} (${data.linear_metrics.r2_percentage}%)`;

        // Explanations
        document.getElementById("mlTrainedAt").textContent = data.trained_at;
        document.getElementById("mlDatasetSamples").textContent = `${data.dataset_samples} records (${data.train_samples} train / ${data.test_samples} test)`;
        document.getElementById("mlExplanation").textContent = data.explanation.summary;
        document.getElementById("mlMaeMeaning").textContent = data.explanation.mae_meaning;
        document.getElementById("mlR2Meaning").textContent = data.explanation.r2_meaning;

        // Render feature importance chart
        OracleCharts.renderFeatureImportanceChart(data.feature_importance);

        // Feature table
        const tbody = document.getElementById("tableFeatureImportance");
        if (tbody) {
            tbody.innerHTML = data.feature_importance.map(f => `
                <tr>
                    <td><code>${f.feature}</code></td>
                    <td><strong>${f.importance}%</strong></td>
                    <td>${f.description}</td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading ML performance:", err);
    }
}

// ---------------------------------------------------------------------
// 12. INITIALIZATION ON DOM READY
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    // Clock
    updateClock();
    setInterval(updateClock, 1000);

    // Sidebar navigation click listeners
    document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            navigateTo(link.dataset.section);
        });
    });

    // Patient filter listeners
    document.getElementById("filterPatientDept")?.addEventListener("change", loadPatients);
    document.getElementById("filterPatientStatus")?.addEventListener("change", loadPatients);
    document.getElementById("formRegisterPatient")?.addEventListener("submit", handleRegisterPatient);

    // Initial Overview load
    loadOverview();
});
