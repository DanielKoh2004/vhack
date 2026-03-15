// ── Config ──
const API_URL = 'http://localhost:8000/api/v1';
let isRunning = true;
let stats = { total: 0, approve: 0, flag: 0, block: 0, latency_sum: 0 };
let hourRisks = new Array(24).fill(null).map(() => []);
let txnCounter = 10000;

// ── Charts ──
const decisionChart = new Chart(document.getElementById('decisionChart'), {
    type: 'doughnut',
    data: {
        labels: ['Approved', 'Flagged', 'Blocked'],
        datasets: [{
            data: [0, 0, 0],
            backgroundColor: ['rgba(16,185,129,0.8)', 'rgba(245,158,11,0.8)', 'rgba(239,68,68,0.8)'],
            borderColor: '#111827', borderWidth: 2
        }]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#64748b', font: { family: 'Outfit', size: 11 }, padding: 12 } } },
        cutout: '72%'
    }
});

const hourChart = new Chart(document.getElementById('hourChart'), {
    type: 'bar',
    data: {
        labels: Array.from({length: 24}, (_, i) => `${i}h`),
        datasets: [{
            label: 'Avg Risk',
            data: new Array(24).fill(0),
            backgroundColor: new Array(24).fill('rgba(99,102,241,0.4)'),
            borderRadius: 3, barThickness: 6
        }]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
            x: { grid: { display: false }, ticks: { color: '#475569', font: { size: 9 } } },
            y: { display: false, min: 0, max: 1 }
        },
        plugins: { legend: { display: false } }
    }
});

// ── KPIs ──
function updateKPIs() {
    document.getElementById('kpi-total').textContent = stats.total.toLocaleString();
    document.getElementById('kpi-approved').textContent = stats.approve.toLocaleString();
    document.getElementById('kpi-flagged').textContent = stats.flag.toLocaleString();
    document.getElementById('kpi-blocked').textContent = stats.block.toLocaleString();
    if (stats.total > 0) document.getElementById('kpi-latency').textContent = (stats.latency_sum / stats.total).toFixed(1);

    decisionChart.data.datasets[0].data = [stats.approve, stats.flag, stats.block];
    decisionChart.update('none');
}

// ── Hour heatmap ──
function updateHourChart(hour, score) {
    hourRisks[hour].push(score);
    if (hourRisks[hour].length > 20) hourRisks[hour].shift(); // rolling window of 20

    const avgScores = hourRisks.map(arr => arr.length ? arr.reduce((a,b) => a+b, 0) / arr.length : 0);
    hourChart.data.datasets[0].data = avgScores;

    // Color by risk
    hourChart.data.datasets[0].backgroundColor = avgScores.map(s =>
        s > 0.5 ? 'rgba(239,68,68,0.6)' : s > 0.2 ? 'rgba(245,158,11,0.5)' : 'rgba(16,185,129,0.4)'
    );
    hourChart.update('none');
}

// ── Gauge ──
function updateGauge(score, decision) {
    const fill = document.getElementById('gauge-fill');
    const scoreText = document.getElementById('gauge-score');
    const decText = document.getElementById('gauge-decision');

    const offset = 157 - (score * 157);
    fill.style.strokeDashoffset = offset;
    scoreText.textContent = score.toFixed(3);
    decText.textContent = decision;

    const c = decision === 'APPROVE' ? '#10b981' : decision === 'FLAG' ? '#f59e0b' : '#ef4444';
    scoreText.setAttribute('fill', c);
}

// ── Layer Bars ──
function updateLayerBars(layers) {
    ['lgb', 'pyod', 'beh'].forEach(key => {
        const mapped = key === 'lgb' ? 'lightgbm' : key === 'pyod' ? 'isolation_forest' : 'behavioral';
        const val = layers[mapped];
        document.getElementById(`bar-${key}`).style.width = `${val * 100}%`;
        document.getElementById(`val-${key}`).textContent = val.toFixed(2);
    });
}

// ── Select Row ──
function selectRow(tr, data) {
    document.querySelectorAll('.transaction-table tr').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');

    document.getElementById('detail-empty').classList.add('hidden');
    document.getElementById('detail-content').classList.remove('hidden');

    updateGauge(data.risk_score, data.decision);
    updateLayerBars(data.layer_scores);

    const list = document.getElementById('detail-reasons');
    list.innerHTML = '';
    (data.reasons || ['Normal behavior pattern']).forEach(r => {
        const li = document.createElement('li');
        li.textContent = r;
        list.appendChild(li);
    });
}

// ── Alerts ──
function addAlert(data, txn) {
    const scroll = document.getElementById('alerts-scroll');
    const chip = document.createElement('div');
    chip.className = 'alert-chip';
    chip.textContent = `${data.transaction_id} | $${txn.amount.toFixed(0)} | Score: ${data.risk_score.toFixed(2)} | ${data.decision}`;
    scroll.insertBefore(chip, scroll.firstChild);
    if (scroll.children.length > 12) scroll.removeChild(scroll.lastChild);
}

// ── Transaction Generator ──
function generateTxn() {
    txnCounter++;
    const fraud = Math.random() < 0.06;
    const txn = {
        transaction_id: `TXN_${txnCounter}`,
        name_sender: `C${Math.floor(Math.random() * 90000) + 10000}`,
        name_recipient: Math.random() > 0.8 ? `M${Math.floor(Math.random() * 9000) + 1000}` : `C${Math.floor(Math.random() * 90000) + 10000}`,
        transfer_type: Math.random() > 0.5 ? "CASH_OUT" : "TRANSFER",
        amount: fraud ? +(Math.random() * 5000 + 800).toFixed(2) : +(Math.random() * 200 + 10).toFixed(2),
        avg_transaction_amount_30d: fraud ? 50.0 : +(Math.random() * 150 + 20).toFixed(2),
        transaction_hour: fraud ? Math.floor(Math.random() * 5) : Math.floor(Math.random() * 14) + 8,
        is_weekend: Math.random() > 0.7 ? 1 : 0,
        is_new_device: fraud ? 1 : (Math.random() > 0.9 ? 1 : 0),
        failed_login_attempts: fraud ? Math.floor(Math.random() * 4) + 1 : 0,
        is_proxy_ip: fraud ? 1 : 0,
        ip_risk_score: fraud ? +(Math.random() * 0.5 + 0.5).toFixed(2) : +(Math.random() * 0.1).toFixed(2),
        sender_account_fully_drained: fraud ? 1 : 0,
        account_age_days: fraud ? Math.floor(Math.random() * 30) + 1 : Math.floor(Math.random() * 1000) + 100,
        tx_count_24h: fraud ? Math.floor(Math.random() * 12) + 5 : Math.floor(Math.random() * 3) + 1,
        country_mismatch: fraud ? (Math.random() > 0.4 ? 1 : 0) : 0,
        is_new_recipient: fraud ? 1 : (Math.random() > 0.7 ? 1 : 0),
        established_user_new_recipient: fraud ? 0 : 1
    };
    txn.amount_vs_avg_ratio = +(txn.amount / Math.max(txn.avg_transaction_amount_30d, 1)).toFixed(2);
    return txn;
}

// ── Process ──
async function processTxn() {
    if (!isRunning) return;
    const txn = generateTxn();

    try {
        const res = await fetch(`${API_URL}/score-transaction`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(txn) });
        if (!res.ok) return;
        const data = await res.json();

        stats.total++;
        stats[data.decision.toLowerCase()]++;
        stats.latency_sum += data.latency_ms;
        updateKPIs();
        updateHourChart(txn.transaction_hour, data.risk_score);

        // Add alert for flagged/blocked
        if (data.decision !== 'APPROVE') addAlert(data, txn);

        const tbody = document.getElementById('transaction-feed');
        const tr = document.createElement('tr');
        tr.className = 'flash-in';
        const bc = data.decision.toLowerCase();
        const barColor = bc === 'approve' ? 'var(--success)' : bc === 'flag' ? 'var(--warning)' : 'var(--danger)';

        tr.innerHTML = `
            <td>${new Date().toLocaleTimeString()}</td>
            <td>${data.transaction_id}</td>
            <td style="font-family:Outfit;font-size:12px">${txn.name_sender} → ${txn.name_recipient}</td>
            <td>$${txn.amount.toFixed(2)}</td>
            <td><div class="risk-bar"><span>${data.risk_score.toFixed(3)}</span><div class="risk-bar-track"><div class="risk-bar-fill" style="width:${data.risk_score*100}%;background:${barColor}"></div></div></div></td>
            <td><span class="badge ${bc}">${data.decision}</span></td>
            <td style="text-align:right"><button class="btn-primary" style="padding:2px 8px;font-size:11px">Inspect</button></td>
        `;

        tr.addEventListener('click', () => selectRow(tr, data));
        tbody.insertBefore(tr, tbody.firstChild);
        if (tbody.children.length > 60) tbody.removeChild(tbody.lastChild);

    } catch (e) {
        console.error('API unreachable:', e.message);
    }
}

// ── Controls ──
document.getElementById('toggle-sim').addEventListener('click', e => {
    isRunning = !isRunning;
    e.target.textContent = isRunning ? '⏸ Pause' : '▶ Resume';
    e.target.style.background = isRunning ? '' : 'var(--border)';
});

setInterval(processTxn, 1200);

// ══════ PAGE SWITCHING ══════
document.querySelectorAll('[data-page]').forEach(link => {
    link.addEventListener('click', e => {
        e.preventDefault();
        const pageId = link.dataset.page;

        // Update nav
        document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
        link.parentElement.classList.add('active');

        // Show target page, hide others
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(`page-${pageId}`).classList.add('active');
    });
});

// ══════ INVESTIGATION FORM ══════
document.getElementById('inv-submit').addEventListener('click', async () => {
    const amt = parseFloat(document.getElementById('inv-amount').value) || 100;
    const avg = parseFloat(document.getElementById('inv-avg').value) || 50;
    const txn = {
        transaction_id: `INV_${Date.now()}`,
        name_sender: "C_INVESTIGATOR",
        name_recipient: "C_TARGET",
        transfer_type: document.getElementById('inv-type').value,
        amount: amt,
        avg_transaction_amount_30d: avg,
        amount_vs_avg_ratio: +(amt / Math.max(avg, 1)).toFixed(2),
        transaction_hour: parseInt(document.getElementById('inv-hour').value) || 12,
        is_weekend: parseInt(document.getElementById('inv-weekend').value),
        is_new_device: parseInt(document.getElementById('inv-device').value),
        failed_login_attempts: parseInt(document.getElementById('inv-logins').value) || 0,
        is_proxy_ip: parseInt(document.getElementById('inv-proxy').value),
        ip_risk_score: parseFloat(document.getElementById('inv-ip').value) || 0,
        sender_account_fully_drained: parseInt(document.getElementById('inv-drained').value),
        account_age_days: parseInt(document.getElementById('inv-age').value) || 100,
        tx_count_24h: parseInt(document.getElementById('inv-txcount').value) || 1,
        country_mismatch: parseInt(document.getElementById('inv-country').value),
        is_new_recipient: parseInt(document.getElementById('inv-newrecip').value),
        established_user_new_recipient: 0
    };

    const resultDiv = document.getElementById('inv-result');
    resultDiv.innerHTML = '<div class="empty-state">⏳ Scoring...</div>';

    try {
        const res = await fetch(`${API_URL}/score-transaction`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(txn) });
        const d = await res.json();
        const color = d.decision === 'APPROVE' ? '#10b981' : d.decision === 'FLAG' ? '#f59e0b' : '#ef4444';

        resultDiv.innerHTML = `
            <div class="inv-result-data">
                <div class="inv-score-large" style="color:${color}">${d.risk_score.toFixed(4)}</div>
                <div class="inv-decision-large" style="color:${color}">${d.decision}</div>
                <div class="inv-layers">
                    <div class="layer-bar-row"><span class="layer-label">LightGBM</span><div class="bar-track"><div class="bar-fill lgb" style="width:${d.layer_scores.lightgbm*100}%"></div></div><span class="bar-val">${d.layer_scores.lightgbm.toFixed(2)}</span></div>
                    <div class="layer-bar-row"><span class="layer-label">IsoForest</span><div class="bar-track"><div class="bar-fill pyod" style="width:${d.layer_scores.isolation_forest*100}%"></div></div><span class="bar-val">${d.layer_scores.isolation_forest.toFixed(2)}</span></div>
                    <div class="layer-bar-row"><span class="layer-label">Behavioral</span><div class="bar-track"><div class="bar-fill beh" style="width:${d.layer_scores.behavioral*100}%"></div></div><span class="bar-val">${d.layer_scores.behavioral.toFixed(2)}</span></div>
                </div>
                <h4 class="section-title" style="margin-top:8px">Risk Drivers</h4>
                <ul class="reason-list">${d.reasons.map(r => `<li>${r}</li>`).join('')}</ul>
                <div class="privacy-note">🔒 PII hashed · Latency: ${d.latency_ms.toFixed(1)}ms</div>
            </div>
        `;

        // Log entry
        const bc = d.decision.toLowerCase();
        const logBody = document.getElementById('inv-log');
        const tr = document.createElement('tr');
        tr.className = 'flash-in';
        tr.innerHTML = `<td>${new Date().toLocaleTimeString()}</td><td>$${amt.toFixed(2)}</td><td>${d.risk_score.toFixed(3)}</td><td><span class="badge ${bc}">${d.decision}</span></td><td style="font-family:Outfit;font-size:12px">${d.reasons[0] || '-'}</td>`;
        logBody.insertBefore(tr, logBody.firstChild);
    } catch (e) {
        resultDiv.innerHTML = `<div class="empty-state" style="color:#f87171">❌ API unreachable: ${e.message}</div>`;
    }
});
