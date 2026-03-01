// File: static/dashboard.js

// Expected backend endpoints (absolute paths):
//   GET /api/dashboard/summary  -> {
//     total_nodes, active_nodes, total_sensors, active_sensors,
//     total_alerts, critical_alerts, data_points_today
//   }
//   GET /api/dashboard/chart?type=temperature|humidity&range=24H|7D|1M
//     -> { labels: [iso_ts,...], values: [number,...] }
//   GET /api/dashboard/latest -> [
//     { sensor_id, name, node_name, value, timestamp, status_code }, ...
//   ]

document.addEventListener('DOMContentLoaded', () => {
  // ---------- helpers ----------
  const $ = (sel) => document.querySelector(sel);
  const $all = (sel) => document.querySelectorAll(sel);
  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val ?? '0';
  };
  const fetchJSON = async (url) => {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' }});
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  };
  const formatTs = (ts) => {
    try { return new Date(ts).toLocaleString(); } catch { return ts; }
  };

  // ---------- cards ----------
  async function loadSummary() {
    try {
      const s = await fetchJSON('/api/dashboard/summary');
      setText('total-nodes', s.total_nodes);
      setText('active-nodes', s.active_nodes);
      setText('total-sensors', s.total_sensors);
      setText('active-sensors', s.active_sensors);
      setText('total-alerts', s.total_alerts);
      setText('critical-alerts', s.critical_alerts);
      setText('data-points-today', s.data_points_today);
    } catch (e) {
      // Soft-fail: keep UI usable even if summary fails
      console.error('Summary load failed:', e);
    }
  }

  // ---------- charts ----------
  let currentRange = 'ALL';
  let currentTab = 'temperature'; // 'temperature' | 'humidity'

  // Create charts
  const tempCtx = document.getElementById('temperatureChart')?.getContext('2d');
  const humCtx  = document.getElementById('humidityChart')?.getContext('2d');

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: {
        type: 'time',
        time: { tooltipFormat: 'MMM dd, HH:mm' },
        title: { display: true, text: 'Time' }
      },
      y: {
        title: { display: true, text: 'Value' },
        ticks: { beginAtZero: false }
      }
    },
    plugins: {
      legend: { display: true }
    }
  };

  const temperatureChart = tempCtx ? new Chart(tempCtx, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Temperature', data: [], borderWidth: 2, pointRadius: 0 }] },
    options: baseOptions
  }) : null;

  const humidityChart = humCtx ? new Chart(humCtx, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Humidity', data: [], borderWidth: 2, pointRadius: 0 }] },
    options: baseOptions
  }) : null;

  const palette = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#f59e0b', '#0ea5e9', '#84cc16', '#f97316'];

  async function loadChart(type, range) {
    try {
      const { datasets = [] } = await fetchJSON(`/api/dashboard/chart?type=${encodeURIComponent(type)}&range=${encodeURIComponent(range)}`);

      const chartDatasets = datasets.map((s, i) => ({
        label: s.label || `Sensor ${s.sensor_id ?? i + 1}`,
        data: (s.data || []).map(p => ({ x: new Date(p.x), y: p.y })),
        borderColor: palette[i % palette.length],
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2
      }));

      if (type === 'temperature' && temperatureChart) {
        temperatureChart.data.datasets = chartDatasets;
        temperatureChart.update();
      }
      if (type === 'humidity' && humidityChart) {
        humidityChart.data.datasets = chartDatasets;
        humidityChart.update();
      }
    } catch (e) {
      console.error(`${type} chart load failed:`, e);
    }
  }

  // Tab controls
  $all('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab'); // temperature | humidity
      if (!tab || tab === currentTab) return;

      currentTab = tab;

      // Visual tab state
      $all('.tab-btn').forEach(b => {
        b.classList.remove('text-blue-600', 'border-blue-600');
        b.classList.add('text-gray-500');
      });
      btn.classList.remove('text-gray-500');
      btn.classList.add('text-blue-600', 'border-b-2', 'border-blue-600');

      // Show/hide panels
      document.getElementById('temperature-tab')?.classList.toggle('hidden', tab !== 'temperature');
      document.getElementById('humidity-tab')?.classList.toggle('hidden', tab !== 'humidity');

      // Load the selected chart if needed
      loadChart(currentTab, currentRange);
    });
  });

  // Range controls
  $all('.range-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      const range = btn.getAttribute('data-range'); // ALL | 24H | 7D | 1M
      if (!range) return;
      currentRange = range;

      // Visual state
      $all('.range-filter').forEach(b => b.classList.remove('text-blue-600'));
      btn.classList.add('text-blue-600');

      // Reload current tab’s chart
      loadChart(currentTab, currentRange);
    });
  });

  // ---------- latest readings table ----------
  async function loadLatestReadings() {
    try {
      const rows = await fetchJSON('/api/dashboard/latest');
      const tbody = document.getElementById('sensor-table-body');
      if (!tbody) return;

      tbody.innerHTML = '';
      (rows || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="px-6 py-3 text-sm text-gray-900">${r.sensor_id ?? ''}</td>
          <td class="px-6 py-3 text-sm text-gray-900">${r.name ?? ''}</td>
          <td class="px-6 py-3 text-sm text-gray-900">${r.node_name ?? ''}</td>
          <td class="px-6 py-3 text-sm text-gray-900">${r.value ?? ''}</td>
          <td class="px-6 py-3 text-sm text-gray-500">${formatTs(r.timestamp ?? '')}</td>
          <td class="px-6 py-3 text-sm">
            <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium
              ${r.status_code === 'Active' ? 'bg-green-100 text-green-800'
                : r.status_code === 'Inactive' ? 'bg-yellow-100 text-yellow-800'
                : r.status_code === 'Faulty' ? 'bg-red-100 text-red-800'
                : 'bg-gray-100 text-gray-800'}">
              <i class="fas fa-circle mr-1 text-xs"></i> ${r.status_code ?? '—'}
            </span>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error('Latest readings load failed:', e);
    }
  }

  // ---------- initial load ----------
  loadSummary();
  loadChart('temperature', currentRange);
  loadChart('humidity', currentRange); // pre-load so switching tabs is instant
  loadLatestReadings();

  // ---------- optional auto-refresh ----------
  // Refresh summary & latest table every 60s; charts refresh when range/tab changes
  setInterval(() => {
    loadSummary();
    loadLatestReadings();
  }, 60_000);
});
