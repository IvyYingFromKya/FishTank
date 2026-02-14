// scripts.js
document.addEventListener('DOMContentLoaded', () => {
  const readingsTableBody = document.querySelector('#readings-table tbody');
  if (readingsTableBody) {
    fetch('/sensors/latest')
      .then(res => res.json())
      .then(data => {
        readingsTableBody.innerHTML = '';
        data.forEach(r => {
          const row = `<tr>
            <td>${r.sensor_name}</td>
            <td>${r.temperature}°C</td>
            <td>${new Date(r.timestamp).toLocaleString()}</td>
          </tr>`;
          readingsTableBody.innerHTML += row;
        });
      })
      .catch(err => {
        readingsTableBody.innerHTML = `<tr><td colspan="3">Failed to load sensor data</td></tr>`;
        console.error(err);
      });
  }
});

document.addEventListener('DOMContentLoaded', () => {
  // Chart data sample (mocked for now)
  const mockSensorData = {
    temperature: [
      { name: "TempSensor1", data: [22, 23, 21, 20, 24, 25], color: "#3b82f6" },
      { name: "TempSensor2", data: [24, 22, 22, 23, 23, 24], color: "#f59e0b" },
    ],
    humidity: [
      { name: "HumSensor1", data: [60, 62, 61, 59, 58, 60], color: "#10b981" },
    ]
  };

  // Chart instance holders
  let charts = {};

async function createChart(tab, range = "24H") {
  const res = await fetch(`/api/sensor-data?type=${tab}&range=${range}`);
  const json = await res.json();

  const ctx = document.getElementById(`${tab}Chart`).getContext("2d");
  if (charts[tab]) charts[tab].destroy();

  charts[tab] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: json.labels,
      datasets: json.datasets
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'top' }
      },
      scales: {
        y: {
          beginAtZero: false
        }
      }
    }
  });
}
  // Load default tab
  createChart("temperature", mockSensorData.temperature);

  // Handle tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;

      // Switch active tab
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove("text-blue-600", "border-blue-600");
        b.classList.add("text-gray-500");
      });
      btn.classList.add("text-blue-600", "border-blue-600");
      btn.classList.remove("text-gray-500");

      // Switch tab content
      document.querySelectorAll('.tab-content').forEach(tc => tc.classList.add("hidden"));
      document.getElementById(`${tab}-tab`).classList.remove("hidden");

      // Load chart
      createChart(tab, mockSensorData[tab]);
    });
  });

  // Filter range switcher (not implemented — just highlight)
  let currentRange = "24H";

document.querySelectorAll('.range-filter').forEach(btn => {
  btn.addEventListener('click', () => {
    currentRange = btn.dataset.range;
    document.querySelectorAll('.range-filter').forEach(b => b.classList.remove("text-blue-600"));
    btn.classList.add("text-blue-600");

    const activeTab = document.querySelector('.tab-btn.text-blue-600').dataset.tab;
    createChart(activeTab, currentRange);
  });
});
