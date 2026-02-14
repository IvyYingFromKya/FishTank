// File: static/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
  const ctx = document.getElementById('temperatureChart').getContext('2d');
  let currentRange = '24H';

  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Temperature',
        data: [],
        backgroundColor: 'rgba(59,130,246,0.1)',
        borderColor: 'rgba(59,130,246,1)',
        borderWidth: 2,
        pointRadius: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'time',
          time: { unit: 'hour', tooltipFormat: 'MMM dd, HH:mm' },
          title: { display: true, text: 'Time' }
        },
        y: {
          title: { display: true, text: 'Value' }
        }
      }
    }
  });

  async function fetchData(range) {
    const res = await fetch(`/api/sensor-data?range=${range}`);
    const data = await res.json();

    const labels = data.map(d => new Date(d.timestamp));
    const values = data.map(d => d.value);

    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update();
  }

  document.querySelectorAll('.range-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      currentRange = btn.getAttribute('data-range');
      fetchData(currentRange);
    });
  });

  fetchData(currentRange);
});
