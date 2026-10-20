const csrftoken = document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];
let dragged = null;

document.querySelectorAll('.board-item[draggable="true"]').forEach(item => {
  item.addEventListener('dragstart', event => {
    dragged = item;
    item.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
  });
  item.addEventListener('dragend', () => {
    item.classList.remove('dragging');
    dragged = null;
    document.querySelectorAll('.drop-cell').forEach(cell => cell.classList.remove('drop-target'));
  });
});

document.querySelectorAll('.drop-cell').forEach(cell => {
  cell.addEventListener('dragover', event => {
    if (!dragged || cell.dataset.row !== dragged.dataset.row) return;
    event.preventDefault();
    cell.classList.add('drop-target');
  });
  cell.addEventListener('dragleave', () => cell.classList.remove('drop-target'));
  cell.addEventListener('drop', async event => {
    event.preventDefault();
    cell.classList.remove('drop-target');
    if (!dragged || cell.dataset.row !== dragged.dataset.row) return;
    const kind = dragged.dataset.kind;
    const url = kind === 'subtask'
      ? `/actividades/${dragged.dataset.id}/mover/`
      : `/tareas/${dragged.dataset.id}/mover/`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'X-CSRFToken': csrftoken, 'Content-Type': 'application/json'},
        body: JSON.stringify({column_id: cell.dataset.column})
      });
      if (!response.ok) {
        const result = await response.json();
        alert(result.error || 'No se pudo mover.');
      }
    } catch {
      alert('No se pudo guardar el movimiento.');
    }
    window.location.reload();
  });
});
