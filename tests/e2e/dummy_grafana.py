"""
Dummy Grafana-like monitoring dashboard for end-to-end testing.

Serves a realistic monitoring dashboard with:
- Live CPU/Memory/Latency charts (auto-updating)
- Alert rules with configurable thresholds
- Alert history with triggered/resolved states
- Interactive controls (buttons, dropdowns, inputs)
- API endpoints for data and alert management

Run standalone:  python dummy_grafana.py
Used by:         test_e2e_grafana.py
"""

import math
import random
import time
from datetime import datetime, timezone
from threading import Thread

from flask import Flask, jsonify, request

app = Flask(__name__)

# ── Simulated metrics store ──────────────────────────────────────────
METRICS = {
	'cpu_usage': [],
	'memory_usage': [],
	'api_latency_ms': [],
	'error_rate': [],
	'requests_per_sec': [],
}

ALERTS = []
ALERT_RULES = [
	{'id': 1, 'name': 'High CPU', 'metric': 'cpu_usage', 'threshold': 85, 'severity': 'critical', 'enabled': True},
	{'id': 2, 'name': 'High Memory', 'metric': 'memory_usage', 'threshold': 90, 'severity': 'warning', 'enabled': True},
	{'id': 3, 'name': 'API Latency Spike', 'metric': 'api_latency_ms', 'threshold': 500, 'severity': 'critical', 'enabled': True},
	{'id': 4, 'name': 'Error Rate High', 'metric': 'error_rate', 'threshold': 5, 'severity': 'warning', 'enabled': True},
]

START_TIME = time.time()


def generate_metrics():
	"""Generate realistic metric data with occasional spikes."""
	t = time.time() - START_TIME
	ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

	# CPU: 30-70% baseline with occasional spikes to 90+
	cpu = 45 + 20 * math.sin(t / 30) + random.gauss(0, 5)
	if random.random() < 0.05:  # 5% chance of spike
		cpu = random.uniform(88, 98)
	cpu = max(0, min(100, cpu))

	# Memory: slowly climbing with sawtooth drops
	mem = 55 + 15 * math.sin(t / 120) + (t % 300) / 30 + random.gauss(0, 3)
	mem = max(0, min(100, mem))

	# API latency: 100-300ms with occasional spikes
	latency = 180 + 80 * math.sin(t / 20) + random.gauss(0, 30)
	if random.random() < 0.03:
		latency = random.uniform(500, 1200)
	latency = max(10, latency)

	# Error rate: 0-3% with occasional bursts
	err = 1.5 + math.sin(t / 45) + random.gauss(0, 0.5)
	if random.random() < 0.04:
		err = random.uniform(5, 12)
	err = max(0, err)

	# RPS: 200-800 with daily patterns
	rps = 450 + 200 * math.sin(t / 60) + random.gauss(0, 30)
	rps = max(50, rps)

	point = {
		'timestamp': ts,
		'cpu_usage': round(cpu, 1),
		'memory_usage': round(mem, 1),
		'api_latency_ms': round(latency, 1),
		'error_rate': round(err, 2),
		'requests_per_sec': round(rps, 0),
	}

	for key in METRICS:
		METRICS[key].append({'ts': ts, 'value': point[key]})
		if len(METRICS[key]) > 200:
			METRICS[key] = METRICS[key][-200:]

	# Check alert rules
	for rule in ALERT_RULES:
		if not rule['enabled']:
			continue
		val = point[rule['metric']]
		if val > rule['threshold']:
			alert = {
				'id': len(ALERTS) + 1,
				'rule_id': rule['id'],
				'rule_name': rule['name'],
				'metric': rule['metric'],
				'value': val,
				'threshold': rule['threshold'],
				'severity': rule['severity'],
				'status': 'firing',
				'triggered_at': ts,
				'resolved_at': None,
			}
			ALERTS.append(alert)

	return point


def background_generator():
	"""Generate metrics every 2 seconds in background."""
	while True:
		generate_metrics()
		time.sleep(2)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Grafana - Yeti Agent Monitoring</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
.topbar { background: #16213e; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #2a3a5e; }
.topbar h1 { font-size: 18px; color: #ff9800; }
.topbar .info { font-size: 12px; color: #888; }
.container { padding: 20px; }
.row { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.panel { background: #16213e; border: 1px solid #2a3a5e; border-radius: 8px; padding: 16px; flex: 1; min-width: 280px; }
.panel h3 { color: #4fc3f7; font-size: 14px; margin-bottom: 12px; border-bottom: 1px solid #2a3a5e; padding-bottom: 8px; }
.metric-value { font-size: 42px; font-weight: bold; text-align: center; padding: 20px 0; }
.metric-value.ok { color: #4caf50; }
.metric-value.warn { color: #ff9800; }
.metric-value.crit { color: #f44336; }
.metric-label { text-align: center; color: #888; font-size: 12px; }
canvas { width: 100% !important; height: 120px !important; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px; color: #4fc3f7; border-bottom: 1px solid #2a3a5e; }
td { padding: 8px; border-bottom: 1px solid #1a1a2e; }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
.badge.critical { background: #f44336; color: white; }
.badge.warning { background: #ff9800; color: black; }
.badge.firing { background: #f44336; color: white; }
.badge.resolved { background: #4caf50; color: white; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; margin: 4px; }
.btn-primary { background: #4fc3f7; color: #1a1a2e; }
.btn-danger { background: #f44336; color: white; }
.btn-success { background: #4caf50; color: white; }
.btn:hover { opacity: 0.85; }
select, input[type="number"] { background: #1a1a2e; color: #e0e0e0; border: 1px solid #2a3a5e; padding: 6px 10px; border-radius: 4px; }
.controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.alert-count { font-size: 16px; padding: 4px 12px; background: #f44336; color: white; border-radius: 12px; }
#status-bar { padding: 8px 24px; background: #0a0a1a; text-align: center; font-size: 12px; color: #666; }
.chart-container { position: relative; height: 140px; margin-top: 8px; }
.sparkline { display: flex; align-items: flex-end; gap: 1px; height: 100px; }
.sparkline .bar { flex: 1; background: #4fc3f7; min-width: 2px; border-radius: 1px 1px 0 0; transition: height 0.3s; }
.sparkline .bar.high { background: #f44336; }
.sparkline .bar.med { background: #ff9800; }
</style>
</head>
<body>

<div class="topbar">
    <h1>🏔️ Yeti Agent — Production Monitoring Dashboard</h1>
    <div class="info">
        <span id="clock"></span> |
        <span>Refresh: <select id="refresh-rate" onchange="updateRefreshRate()">
            <option value="2000">2s</option>
            <option value="5000" selected>5s</option>
            <option value="10000">10s</option>
            <option value="30000">30s</option>
        </select></span> |
        <span>Firing Alerts: <span class="alert-count" id="alert-count">0</span></span>
    </div>
</div>

<div class="container">
    <!-- Metric Gauges Row -->
    <div class="row">
        <div class="panel" id="panel-cpu">
            <h3>CPU Usage</h3>
            <div class="metric-value ok" id="cpu-val">--</div>
            <div class="metric-label">Threshold: 85%</div>
            <div class="sparkline" id="cpu-spark"></div>
        </div>
        <div class="panel" id="panel-mem">
            <h3>Memory Usage</h3>
            <div class="metric-value ok" id="mem-val">--</div>
            <div class="metric-label">Threshold: 90%</div>
            <div class="sparkline" id="mem-spark"></div>
        </div>
        <div class="panel" id="panel-latency">
            <h3>API Latency</h3>
            <div class="metric-value ok" id="lat-val">--</div>
            <div class="metric-label">Threshold: 500ms</div>
            <div class="sparkline" id="lat-spark"></div>
        </div>
        <div class="panel" id="panel-err">
            <h3>Error Rate</h3>
            <div class="metric-value ok" id="err-val">--</div>
            <div class="metric-label">Threshold: 5%</div>
            <div class="sparkline" id="err-spark"></div>
        </div>
        <div class="panel" id="panel-rps">
            <h3>Requests/sec</h3>
            <div class="metric-value ok" id="rps-val">--</div>
            <div class="metric-label">Current throughput</div>
            <div class="sparkline" id="rps-spark"></div>
        </div>
    </div>

    <!-- Alert Rules Row -->
    <div class="row">
        <div class="panel" style="flex: 2;">
            <h3>Alert Rules</h3>
            <table>
                <thead><tr><th>Rule</th><th>Metric</th><th>Threshold</th><th>Severity</th><th>Status</th><th>Action</th></tr></thead>
                <tbody id="rules-body"></tbody>
            </table>
        </div>
        <div class="panel" style="flex: 1;">
            <h3>Quick Actions</h3>
            <div style="padding: 12px;">
                <button class="btn btn-primary" id="btn-silence-all" onclick="silenceAll()">Silence All Alerts</button>
                <button class="btn btn-success" id="btn-acknowledge" onclick="acknowledgeAll()">Acknowledge All</button>
                <button class="btn btn-danger" id="btn-trigger-spike" onclick="triggerSpike()">Trigger CPU Spike</button>
                <br><br>
                <label>Custom Threshold:
                    <input type="number" id="custom-threshold" value="85" min="0" max="100" style="width: 70px;">
                    <button class="btn btn-primary" onclick="setThreshold()">Set CPU Threshold</button>
                </label>
            </div>
        </div>
    </div>

    <!-- Alert History Row -->
    <div class="row">
        <div class="panel" style="flex: 1;">
            <h3>Recent Alerts (Last 20)</h3>
            <table>
                <thead><tr><th>Time</th><th>Rule</th><th>Value</th><th>Severity</th><th>Status</th></tr></thead>
                <tbody id="alerts-body"></tbody>
            </table>
        </div>
    </div>
</div>

<div id="status-bar">Yeti Agent Monitoring Dashboard v1.0 | Data source: Local Simulator | Last updated: <span id="last-update">--</span></div>

<script>
let refreshInterval = 5000;
let timer;

function updateRefreshRate() {
    refreshInterval = parseInt(document.getElementById('refresh-rate').value);
    clearInterval(timer);
    timer = setInterval(fetchData, refreshInterval);
}

function colorClass(val, warn, crit) {
    if (val >= crit) return 'crit';
    if (val >= warn) return 'warn';
    return 'ok';
}

function renderSparkline(containerId, data, threshold) {
    const el = document.getElementById(containerId);
    const maxVal = Math.max(...data.map(d => d.value), threshold * 1.2);
    el.innerHTML = data.slice(-50).map(d => {
        const h = Math.max(2, (d.value / maxVal) * 100);
        const cls = d.value > threshold ? 'high' : (d.value > threshold * 0.8 ? 'med' : '');
        return '<div class="bar ' + cls + '" style="height:' + h + 'px" title="' + d.value + '"></div>';
    }).join('');
}

async function fetchData() {
    try {
        const [metricsRes, alertsRes, rulesRes] = await Promise.all([
            fetch('/api/metrics/latest'),
            fetch('/api/alerts?limit=20'),
            fetch('/api/rules')
        ]);
        const metrics = await metricsRes.json();
        const alerts = await alertsRes.json();
        const rules = await rulesRes.json();

        // Update gauge values
        const cpu = metrics.cpu_usage;
        document.getElementById('cpu-val').textContent = cpu.toFixed(1) + '%';
        document.getElementById('cpu-val').className = 'metric-value ' + colorClass(cpu, 70, 85);

        const mem = metrics.memory_usage;
        document.getElementById('mem-val').textContent = mem.toFixed(1) + '%';
        document.getElementById('mem-val').className = 'metric-value ' + colorClass(mem, 75, 90);

        const lat = metrics.api_latency_ms;
        document.getElementById('lat-val').textContent = lat.toFixed(0) + 'ms';
        document.getElementById('lat-val').className = 'metric-value ' + colorClass(lat, 300, 500);

        const err = metrics.error_rate;
        document.getElementById('err-val').textContent = err.toFixed(2) + '%';
        document.getElementById('err-val').className = 'metric-value ' + colorClass(err, 3, 5);

        const rps = metrics.requests_per_sec;
        document.getElementById('rps-val').textContent = rps.toFixed(0);
        document.getElementById('rps-val').className = 'metric-value ok';

        // Fetch sparkline data
        const histRes = await fetch('/api/metrics/history?points=50');
        const hist = await histRes.json();
        renderSparkline('cpu-spark', hist.cpu_usage, 85);
        renderSparkline('mem-spark', hist.memory_usage, 90);
        renderSparkline('lat-spark', hist.api_latency_ms, 500);
        renderSparkline('err-spark', hist.error_rate, 5);
        renderSparkline('rps-spark', hist.requests_per_sec, 9999);

        // Alert count
        const firingCount = alerts.filter(a => a.status === 'firing').length;
        document.getElementById('alert-count').textContent = firingCount;

        // Rules table
        document.getElementById('rules-body').innerHTML = rules.map(r =>
            '<tr><td>' + r.name + '</td><td>' + r.metric + '</td><td>' + r.threshold + '</td>' +
            '<td><span class="badge ' + r.severity + '">' + r.severity + '</span></td>' +
            '<td>' + (r.enabled ? '✅ Active' : '❌ Disabled') + '</td>' +
            '<td><button class="btn btn-primary" onclick="toggleRule(' + r.id + ')">' + (r.enabled ? 'Disable' : 'Enable') + '</button></td></tr>'
        ).join('');

        // Alerts table
        document.getElementById('alerts-body').innerHTML = alerts.slice(0, 20).map(a =>
            '<tr><td>' + a.triggered_at.split('T')[1].split('.')[0] + '</td>' +
            '<td>' + a.rule_name + '</td>' +
            '<td>' + a.value + '</td>' +
            '<td><span class="badge ' + a.severity + '">' + a.severity + '</span></td>' +
            '<td><span class="badge ' + a.status + '">' + a.status + '</span></td></tr>'
        ).join('');

        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        document.getElementById('clock').textContent = new Date().toLocaleString();
    } catch (e) {
        console.error('Fetch error:', e);
    }
}

async function toggleRule(id) { await fetch('/api/rules/' + id + '/toggle', {method: 'POST'}); fetchData(); }
async function silenceAll() { await fetch('/api/alerts/silence', {method: 'POST'}); fetchData(); }
async function acknowledgeAll() { await fetch('/api/alerts/acknowledge', {method: 'POST'}); fetchData(); }
async function triggerSpike() { await fetch('/api/simulate/spike', {method: 'POST'}); fetchData(); }
async function setThreshold() {
    const val = document.getElementById('custom-threshold').value;
    await fetch('/api/rules/1/threshold', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({threshold: parseInt(val)})});
    fetchData();
}

fetchData();
timer = setInterval(fetchData, refreshInterval);
</script>
</body>
</html>"""


@app.route('/')
def dashboard():
	return DASHBOARD_HTML


@app.route('/api/metrics/latest')
def metrics_latest():
	point = generate_metrics()
	return jsonify(point)


@app.route('/api/metrics/history')
def metrics_history():
	points = int(request.args.get('points', 50))
	result = {}
	for key, data in METRICS.items():
		result[key] = data[-points:]
	return jsonify(result)


@app.route('/api/alerts')
def get_alerts():
	limit = int(request.args.get('limit', 50))
	return jsonify(ALERTS[-limit:][::-1])


@app.route('/api/alerts/silence', methods=['POST'])
def silence_alerts():
	for a in ALERTS:
		if a['status'] == 'firing':
			a['status'] = 'silenced'
	return jsonify({'ok': True, 'message': 'All alerts silenced'})


@app.route('/api/alerts/acknowledge', methods=['POST'])
def acknowledge_alerts():
	for a in ALERTS:
		if a['status'] == 'firing':
			a['status'] = 'resolved'
			a['resolved_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
	return jsonify({'ok': True, 'message': 'All alerts acknowledged'})


@app.route('/api/rules')
def get_rules():
	return jsonify(ALERT_RULES)


@app.route('/api/rules/<int:rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
	for r in ALERT_RULES:
		if r['id'] == rule_id:
			r['enabled'] = not r['enabled']
			return jsonify(r)
	return jsonify({'error': 'not found'}), 404


@app.route('/api/rules/<int:rule_id>/threshold', methods=['POST'])
def set_threshold(rule_id):
	data = request.get_json()
	for r in ALERT_RULES:
		if r['id'] == rule_id:
			r['threshold'] = data['threshold']
			return jsonify(r)
	return jsonify({'error': 'not found'}), 404


@app.route('/api/simulate/spike', methods=['POST'])
def simulate_spike():
	"""Inject a CPU spike to trigger alerts."""
	ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
	spike_val = random.uniform(92, 99)
	METRICS['cpu_usage'].append({'ts': ts, 'value': round(spike_val, 1)})
	alert = {
		'id': len(ALERTS) + 1,
		'rule_id': 1,
		'rule_name': 'High CPU',
		'metric': 'cpu_usage',
		'value': round(spike_val, 1),
		'threshold': 85,
		'severity': 'critical',
		'status': 'firing',
		'triggered_at': ts,
		'resolved_at': None,
	}
	ALERTS.append(alert)
	return jsonify({'ok': True, 'spike_value': spike_val, 'alert': alert})


@app.route('/api/health')
def health():
	return jsonify({'status': 'healthy', 'uptime': round(time.time() - START_TIME, 1)})


def run_server(port=3000):
	# Start background metric generator
	t = Thread(target=background_generator, daemon=True)
	t.start()
	# Pre-generate some history
	for _ in range(30):
		generate_metrics()
	app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
	print('Starting Grafana-like monitoring dashboard on http://localhost:3000')
	run_server(3000)
