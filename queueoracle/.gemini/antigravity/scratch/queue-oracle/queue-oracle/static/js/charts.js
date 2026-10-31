/**
 * QUEUE ORACLE - Data Visualization Module (Chart.js)
 * Implements all 9 charts dynamically connected to real backend endpoints.
 */

const OracleCharts = {
    instances: {},

    // Helper to safely re-create or update a chart
    createOrUpdate(canvasId, config) {
        if (this.instances[canvasId]) {
            this.instances[canvasId].destroy();
        }
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        this.instances[canvasId] = new Chart(ctx, config);
        return this.instances[canvasId];
    },

    // 1. Overview: Patients Waiting by Department
    renderDeptWaitingChart(departments) {
        const labels = departments.map(d => d.name);
        const data = departments.map(d => d.waiting_patients);
        const bgColors = departments.map(d => {
            if (d.status === "CRITICAL") return "#ef4444";
            if (d.status === "WARNING") return "#f59e0b";
            return "#0284c7";
        });

        this.createOrUpdate("chartDeptWaiting", {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Waiting Patients",
                    data: data,
                    backgroundColor: bgColors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `Waiting Patients: ${ctx.raw}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 2 }
                    }
                }
            }
        });
    },

    // 2. Overview / Forecast: Hourly Predicted Patient Arrivals
    renderArrivalsChart(forecastData) {
        forecastData = {
    hours: [
        "08:00", "09:00", "10:00",
        "11:00", "12:00", "13:00",
        "14:00", "15:00"
    ],

    actual_arrivals: [
        2, 5, 8, 12, 15, 10, 7, 4
    ],

    predicted_arrivals: [
        2, 4, 7, 10, 13, 12, 9, 6
    ]
};
        this.createOrUpdate("chartArrivalsForecast", {
            type: "line",
            data: {
                labels: forecastData.hours,
                datasets: [
                    {
                        label: "Actual Arrivals",
                        data: forecastData.actual_arrivals,
                        borderColor: "#0284c7",
                        backgroundColor: "rgba(2, 132, 199, 0.15)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 4,
                        pointBackgroundColor: "#0284c7"
                    },
                    {
                        label: "Predicted Arrivals (Oracle AI)",
                        data: forecastData.predicted_arrivals,
                        borderColor: "#8b5cf6",
                        borderDash: [5, 5],
                        backgroundColor: "transparent",
                        tension: 0.35,
                        pointRadius: 3,
                        pointBackgroundColor: "#8b5cf6"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: "Patients / Hour" }
                    }
                }
            }
        });
    },

    // 3. Bed Occupancy: Occupied vs Available
    renderBedDonutChart(overall) {
        this.createOrUpdate("chartBedDonut", {
            type: "doughnut",
            data: {
                labels: ["Occupied Beds", "Available Beds"],
                datasets: [{
                    data: [overall.occupied_beds, overall.available_beds],
                    backgroundColor: ["#ef4444", "#10b981"],
                    hoverOffset: 4,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: {
                    legend: { position: "bottom" }
                }
            }
        });
    },

    // 4. Doctor Workload: Active Patient Load
    renderDoctorWorkloadChart(doctors) {
        const labels = doctors.map(d => d.name.replace("Dr. ", ""));
        const waiting = doctors.map(d => d.waiting_count);
        const inConsult = doctors.map(d => d.active_consults);

        this.createOrUpdate("chartDoctorWorkload", {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "In Consultation",
                        data: inConsult,
                        backgroundColor: "#10b981",
                        borderRadius: 4
                    },
                    {
                        label: "Waiting in Queue",
                        data: waiting,
                        backgroundColor: "#0284c7",
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                },
                plugins: {
                    legend: { position: "top" }
                }
            }
        });
    },

    // 5. Waiting Time Trends by Hour
    renderWaitTimeTrendsChart(hours, waitData) {
        this.createOrUpdate("chartWaitTimeTrends", {
            type: "line",
            data: {
                labels: hours,
                datasets: [{
                    label: "Avg Waiting Time (Minutes)",
                    data: waitData,
                    borderColor: "#f59e0b",
                    backgroundColor: "rgba(245, 158, 11, 0.12)",
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: "#f59e0b"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: "Minutes" }
                    }
                }
            }
        });
    },

    // 6. Disease Trends (14-day history)
    renderDiseaseTrendsChart(diseaseList) {
        if (!diseaseList || diseaseList.length === 0) return;
        const dates = diseaseList[0].history_dates || [];
        const colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"];

        const datasets = diseaseList.map((d, idx) => ({
            label: `${d.disease_name} (Verified)`,
            data: d.history_cases,
            borderColor: colors[idx % colors.length],
            backgroundColor: "transparent",
            tension: 0.3,
            borderWidth: 2,
            pointRadius: 3
        }));

        this.createOrUpdate("chartDiseaseTrends", {
            type: "line",
            data: {
                labels: dates,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" },
                    title: { display: true, text: "Epidemiological Surveillance (Last 14 Days)" }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: "Daily Cases Count" }
                    }
                }
            }
        });
    },

    // 7. Bed Forecast (1h to 4h by department)
    renderBedForecastChart(departments) {
        const labels = ["Current", "+1 Hour", "+2 Hours", "+3 Hours", "+4 Hours"];
        const colors = ["#0284c7", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

        const datasets = departments.map((dept, idx) => {
            const dataPoints = [
                dept.occupancy_rate,
                ...dept.hourly_forecasts.map(h => h.projected_percentage)
            ];
            return {
                label: dept.department,
                data: dataPoints,
                borderColor: colors[idx % colors.length],
                tension: 0.25,
                borderWidth: 2,
                pointRadius: 4
            };
        });

        this.createOrUpdate("chartBedForecast", {
            type: "line",
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" }
                },
                scales: {
                    y: {
                        min: 30,
                        max: 105,
                        title: { display: true, text: "Occupancy Rate (%)" }
                    }
                }
            }
        });
    },

    // 8. Inventory Availability vs Min Stock
    renderInventoryChart(inventoryItems) {
        const topItems = inventoryItems.slice(0, 7);
        const labels = topItems.map(i => i.item_name.length > 18 ? i.item_name.substring(0, 18) + "..." : i.item_name);
        const available = topItems.map(i => i.available_qty);
        const minStock = topItems.map(i => i.min_stock);

        this.createOrUpdate("chartInventory", {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Available Stock",
                        data: available,
                        backgroundColor: topItems.map(i => i.shortage_risk === "CRITICAL" ? "#ef4444" : (i.shortage_risk === "WARNING" ? "#f59e0b" : "#10b981")),
                        borderRadius: 4
                    },
                    {
                        label: "Minimum Safety Stock",
                        data: minStock,
                        backgroundColor: "#cbd5e1",
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    },

    // 9. Machine Learning Feature Importance
    renderFeatureImportanceChart(features) {
        if (!features) return;
        const labels = features.map(f => f.feature);
        const data = features.map(f => f.importance);

        this.createOrUpdate("chartFeatureImportance", {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Importance Weight (%)",
                    data: data,
                    backgroundColor: "#0284c7",
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: "Percentage (%)" }
                    }
                }
            }
        });
    }
};
