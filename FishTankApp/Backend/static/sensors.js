// frontend/static/sensors.js
document.addEventListener('DOMContentLoaded', () => {
  const sensorForm = document.getElementById('sensor-form');
  const sensorsList = document.getElementById('sensors-list');

  const loadSensors = async () => {
    const res = await fetch('/sensors/');
    const sensors = await res.json();
    sensorsList.innerHTML = '';
    sensors.forEach(s => {
      sensorsList.innerHTML += `<tr>
        <td>${s.sensor_id}</td>
        <td>${s.node_id}</td>
        <td>${s.name}</td>
        <td>${s.status}</td>
        <td><button onclick="deleteSensor('${s.sensor_id}')">Delete</button></td>
      </tr>`;
    });
  };

  window.deleteSensor = async (id) => {
    await fetch(`/sensors/${id}`, { method: 'DELETE' });
    loadSensors();
  };

  sensorForm.addEventListener('submit', async e => {
    e.preventDefault();
    const formData = new FormData(sensorForm);
    const data = Object.fromEntries(formData.entries());
    await fetch('/sensors/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    sensorForm.reset();
    loadSensors();
  });

  loadSensors();
});
