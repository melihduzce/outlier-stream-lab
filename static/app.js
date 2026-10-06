// app.js - AIOps Stream Lab Frontend Engine

let ws = null;
let chart = null;
const MAX_CHART_POINTS = 30;
let currentMode = "NORMAL";
let logEntriesCount = 0;

// Sayfa yüklendiğinde başlat
document.addEventListener("DOMContentLoaded", () => {
    initChart();
    connectWebSocket();
});

// Chart.js Zaman Serisi Grafiğini Başlat
function initChart() {
    const ctx = document.getElementById("metricsChart").getContext("2d");
    chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "CPU (%)",
                    borderColor: "#3B82F6",
                    backgroundColor: "rgba(59, 130, 246, 0.1)",
                    borderWidth: 2,
                    pointRadius: 1,
                    tension: 0.3,
                    fill: false,
                    data: []
                },
                {
                    label: "RAM (%)",
                    borderColor: "#F59E0B",
                    backgroundColor: "rgba(245, 158, 11, 0.1)",
                    borderWidth: 2,
                    pointRadius: 1,
                    tension: 0.3,
                    fill: false,
                    data: []
                },
                {
                    label: "GPU (%)",
                    borderColor: "#A855F7",
                    backgroundColor: "rgba(168, 85, 247, 0.1)",
                    borderWidth: 2,
                    pointRadius: 1,
                    tension: 0.3,
                    fill: false,
                    data: []
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    grid: { color: "rgba(31, 41, 55, 0.5)" },
                    ticks: { color: "#9CA3AF", font: { size: 10 } }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: "rgba(31, 41, 55, 0.5)" },
                    ticks: { color: "#9CA3AF", font: { size: 10 } }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// WebSocket Bağlantısı ve Canlı Akış Dinleme
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;
    
    const indicator = document.getElementById("ws-indicator");
    const wsText = document.getElementById("ws-text");

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        indicator.className = "h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse";
        wsText.textContent = "Canlı Yayın Aktif";
        wsText.className = "text-emerald-400 font-medium";
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleStreamData(data);
        } catch (err) {
            console.error("JSON parse hatası:", err);
        }
    };

    ws.onclose = () => {
        indicator.className = "h-2.5 w-2.5 rounded-full bg-rose-500";
        wsText.textContent = "Bağlantı Kesildi (Yeniden deneniyor)";
        wsText.className = "text-rose-400 font-medium";
        setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = (err) => {
        console.error("WebSocket Hatası:", err);
    };
}

// Gelen Telemetri ve Analiz Verisini Arayüze Dağıt
function handleStreamData(data) {
    const { telemetry, service_b, ml } = data;

    // 1. Servis A Metrik Kartları
    document.getElementById("metric-cpu").textContent = telemetry.cpu_usage;
    document.getElementById("bar-cpu").style.width = `${telemetry.cpu_usage}%`;

    document.getElementById("metric-ram").textContent = telemetry.ram_usage;
    document.getElementById("bar-ram").style.width = `${telemetry.ram_usage}%`;

    document.getElementById("metric-gpu").textContent = telemetry.gpu_usage;
    document.getElementById("bar-gpu").style.width = `${telemetry.gpu_usage}%`;

    document.getElementById("metric-temp").textContent = telemetry.temperature;
    document.getElementById("metric-tasks").textContent = telemetry.active_tasks;
    document.getElementById("bar-temp").style.width = `${Math.min(100, telemetry.temperature)}%`;

    // 2. Canlı Grafik Güncelleme (Sliding Window)
    updateChart(telemetry.timestamp, telemetry.cpu_usage, telemetry.ram_usage, telemetry.gpu_usage);

    // 3. ML Anomali Skoru ve Risk Göstergesi
    updateMlGauge(ml);

    // 4. Servis B Durum Paneli
    updateServiceB(service_b);

    // 5. Proaktif Tedbir Bildirim Kutusu
    updateAlertCard(ml.notification, telemetry.timestamp, ml.risk_score);

    // 6. Olay Günlüğüne Ekleme (Anomali veya kritik anlarda)
    if (ml.is_anomaly || service_b.status !== "HEALTHY") {
        addLogEntry(telemetry.timestamp, ml, service_b);
    }
}

// Zaman Serisi Grafiğini Güncelle
function updateChart(label, cpu, ram, gpu) {
    if (!chart) return;
    
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(cpu);
    chart.data.datasets[1].data.push(ram);
    chart.data.datasets[2].data.push(gpu);

    if (chart.data.labels.length > MAX_CHART_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
        chart.data.datasets[2].data.shift();
    }
    chart.update("none");
}

// ML Gösterge Güncelleme
function updateMlGauge(ml) {
    const riskElem = document.getElementById("risk-score");
    const riskBar = document.getElementById("risk-bar");
    const badge = document.getElementById("anomaly-badge");

    riskElem.textContent = ml.risk_score;
    riskBar.style.width = `${ml.risk_score}%`;

    document.getElementById("ml-raw-score").textContent = ml.raw_decision_score > 0 ? `+${ml.raw_decision_score}` : `${ml.raw_decision_score}`;
    document.getElementById("ml-primary-driver").textContent = ml.primary_driver;
    document.getElementById("ml-z-score").textContent = `${ml.primary_deviation_z > 0 ? '+' : ''}${ml.primary_deviation_z} σ`;

    if (ml.risk_score < 40) {
        riskElem.className = "text-5xl font-black text-emerald-400";
        riskBar.className = "h-2.5 rounded-full transition-all duration-300 bg-emerald-500";
        badge.className = "px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        badge.textContent = "STABİL";
    } else if (ml.risk_score < 65) {
        riskElem.className = "text-5xl font-black text-amber-400";
        riskBar.className = "h-2.5 rounded-full transition-all duration-300 bg-amber-500";
        badge.className = "px-2 py-0.5 rounded text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30";
        badge.textContent = "RİSKLİ";
    } else {
        riskElem.className = "text-5xl font-black text-rose-500 animate-pulse";
        riskBar.className = "h-2.5 rounded-full transition-all duration-300 bg-rose-500";
        badge.className = "px-2 py-0.5 rounded text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30";
        badge.textContent = "ANOMALİ!";
    }
}

// Servis B Bilgi Paneli Güncelleme
function updateServiceB(sb) {
    document.getElementById("srv-latency").textContent = sb.latency_ms;
    document.getElementById("srv-error-rate").textContent = sb.error_rate_pct;
    document.getElementById("srv-queue").textContent = sb.queue_depth;
    document.getElementById("srv-failed").textContent = sb.total_failed;

    const statusBadge = document.getElementById("service-b-status");
    statusBadge.textContent = sb.status;

    if (sb.status === "HEALTHY") {
        statusBadge.className = "px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    } else if (sb.status === "DEGRADED") {
        statusBadge.className = "px-2.5 py-1 rounded-md text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30";
    } else {
        statusBadge.className = "px-2.5 py-1 rounded-md text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse";
    }

    const issuesList = document.getElementById("srv-issues");
    issuesList.innerHTML = sb.issues.map(iss => `<li>${iss}</li>`).join("");
}

// Proaktif Tedbir Kartı Güncelleme
function updateAlertCard(notif, timestamp, riskScore) {
    const card = document.getElementById("alert-card");
    const badge = document.getElementById("alert-level-badge");
    const title = document.getElementById("alert-title");
    const message = document.getElementById("alert-message");
    const action = document.getElementById("alert-action");
    const icon = document.getElementById("alert-icon");
    const actionBox = document.getElementById("action-box");

    document.getElementById("alert-timestamp").textContent = `Son Güncelleme: ${timestamp}`;

    title.textContent = notif.title;
    message.textContent = notif.message;
    action.textContent = notif.action;
    badge.textContent = notif.badge;

    if (notif.level === "INFO") {
        card.classList.remove("glow-red", "glow-amber");
        badge.className = "px-2.5 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        icon.className = "p-2 rounded-xl bg-emerald-500/20 text-emerald-400";
        actionBox.className = "p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/20";
    } else if (notif.level === "WARNING") {
        card.classList.remove("glow-red");
        card.classList.add("glow-amber");
        badge.className = "px-2.5 py-1 rounded text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30";
        icon.className = "p-2 rounded-xl bg-amber-500/20 text-amber-400";
        actionBox.className = "p-4 rounded-xl bg-amber-950/30 border border-amber-500/30";
    } else { // CRITICAL
        card.classList.remove("glow-amber");
        card.classList.add("glow-red");
        badge.className = "px-2.5 py-1 rounded text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse";
        icon.className = "p-2 rounded-xl bg-rose-500/20 text-rose-400";
        actionBox.className = "p-4 rounded-xl bg-rose-950/40 border border-rose-500/40";
    }
}

// Canlı Olay Günlüğü Tablosuna Satır Ekle
function addLogEntry(time, ml, serviceB) {
    const tbody = document.getElementById("log-table-body");
    const tr = document.createElement("tr");
    tr.className = ml.notification.level === "CRITICAL" ? "bg-rose-950/20 hover:bg-rose-950/30" : "hover:bg-gray-800/40";

    const badgeColor = ml.notification.level === "CRITICAL" ? "text-rose-400" : (ml.notification.level === "WARNING" ? "text-amber-400" : "text-emerald-400");

    tr.innerHTML = `
        <td class="py-2 px-3 text-gray-400">${time}</td>
        <td class="py-2 px-3 font-bold ${badgeColor}">${ml.notification.badge}</td>
        <td class="py-2 px-3 font-semibold text-white">%${ml.risk_score}</td>
        <td class="py-2 px-3 text-indigo-400">${ml.primary_driver} (${ml.primary_deviation_z > 0 ? '+' : ''}${ml.primary_deviation_z}σ)</td>
        <td class="py-2 px-3 text-gray-300">${serviceB.latency_ms} ms</td>
        <td class="py-2 px-3 text-gray-300 font-sans truncate max-w-md">${ml.notification.action}</td>
    `;

    tbody.insertBefore(tr, tbody.firstChild);

    // Maksimum 15 satır tut
    logEntriesCount++;
    if (tbody.children.length > 15) {
        tbody.removeChild(tbody.lastChild);
    }
}

function clearLogs() {
    document.getElementById("log-table-body").innerHTML = "";
    logEntriesCount = 0;
}

// Simülasyon Modu Değiştirme (Anomali Enjeksiyonu)
async function setMode(mode) {
    try {
        const res = await fetch("/api/set-mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode })
        });
        const data = await res.json();
        if (data.success) {
            currentMode = mode;
            updateModeButtons(mode);
        }
    } catch (e) {
        console.error("Mod değiştirme hatası:", e);
    }
}

function updateModeButtons(mode) {
    const modes = ["NORMAL", "MEMORY_LEAK", "CPU_BURST", "GPU_RUNAWAY", "CRITICAL_CRASH"];
    modes.forEach(m => {
        const btn = document.getElementById(`btn-${m}`);
        if (btn) {
            if (m === mode) {
                btn.classList.add("active-mode");
                btn.classList.remove("bg-gray-800/50");
            } else {
                btn.classList.remove("active-mode");
                btn.classList.add("bg-gray-800/50");
            }
        }
    });

    const badge = document.getElementById("current-mode-badge");
    badge.textContent = mode;
    if (mode === "NORMAL") {
        badge.className = "px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    } else if (mode === "MEMORY_LEAK") {
        badge.className = "px-2.5 py-1 rounded-md text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30";
    } else {
        badge.className = "px-2.5 py-1 rounded-md text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30";
    }
}

// Modeli Yeniden Eğit Butonu
async function retrainModel() {
    try {
        const res = await fetch("/api/retrain", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            alert("Isolation Forest modeli yeni sentetik verilerle başarıyla eğitildi!");
        }
    } catch (e) {
        alert("Eğitim hatası: " + e.message);
    }
}
