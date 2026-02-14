// frontend/static/config.js
document.addEventListener('DOMContentLoaded', () => {
  const configForm = document.getElementById('config-form');
  const configList = document.getElementById('config-list');

  const loadConfigs = async () => {
    const res = await fetch('/config/');
    const configs = await res.json();
    configList.innerHTML = '';
    configs.forEach(c => {
      configList.innerHTML += `<tr>
        <td>${c.key}</td>
        <td>${c.value}</td>
        <td><button onclick="deleteConfig('${c.key}')">Delete</button></td>
      </tr>`;
    });
  };

  window.deleteConfig = async (key) => {
    await fetch(`/config/${key}`, { method: 'DELETE' });
    loadConfigs();
  };

  configForm.addEventListener('submit', async e => {
    e.preventDefault();
    const formData = new FormData(configForm);
    const data = Object.fromEntries(formData.entries());
    await fetch('/config/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    configForm.reset();
    loadConfigs();
  });

  loadConfigs();
});
