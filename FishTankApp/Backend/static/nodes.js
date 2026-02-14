// frontend/static/nodes.js
document.addEventListener('DOMContentLoaded', () => {
  const nodeForm = document.getElementById('node-form');
  const nodesList = document.getElementById('nodes-list');

  const loadNodes = async () => {
    const res = await fetch('/nodes/');
    const nodes = await res.json();
    nodesList.innerHTML = '';
    nodes.forEach(n => {
      nodesList.innerHTML += `<tr>
        <td>${n.node_id}</td>
        <td>${n.ip_address}</td>
        <td>${n.location}</td>
        <td>${n.status}</td>
        <td><button onclick="deleteNode('${n.node_id}')">Delete</button></td>
      </tr>`;
    });
  };

  window.deleteNode = async (id) => {
    await fetch(`/nodes/${id}`, { method: 'DELETE' });
    loadNodes();
  };

  nodeForm.addEventListener('submit', async e => {
    e.preventDefault();
    const formData = new FormData(nodeForm);
    const data = Object.fromEntries(formData.entries());
    await fetch('/nodes/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    nodeForm.reset();
    loadNodes();
  });

  loadNodes();
});
