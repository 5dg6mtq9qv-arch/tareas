const csrfToken = document.querySelector('.work-ticket input[name="csrfmiddlewaretoken"]')?.value
  || document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];

let activeDrag = null;
let savingMove = false;

function syncStatusSelectors() {
  document.querySelectorAll('.work-ticket').forEach(ticket => {
    const selector = ticket.querySelector('.work-status-form select');
    const actualColumn = ticket.closest('.work-drop-cell')?.dataset.column;
    if (selector && actualColumn) selector.value = actualColumn;
  });
}

syncStatusSelectors();
window.addEventListener('pageshow', syncStatusSelectors);

function targetAt(x, y) {
  if (!activeDrag) return null;
  const cell = document.elementFromPoint(x, y)?.closest('.work-drop-cell, .work-dock-target');
  return cell?.dataset.row === activeDrag.ticket.dataset.row ? cell : null;
}

function highlightTarget(target) {
  document.querySelectorAll('.work-drop-cell.is-target, .work-dock-target.is-target')
    .forEach(cell => cell.classList.remove('is-target'));
  target?.classList.add('is-target');
}

function startVisualDrag(event) {
  const {ticket} = activeDrag;
  const ghost = document.createElement('div');
  ghost.className = 'work-drag-ghost';
  ghost.textContent = ticket.querySelector('.work-ticket-name')?.textContent?.trim() || 'Tarea';
  document.body.appendChild(ghost);
  activeDrag.ghost = ghost;
  ticket.classList.add('is-dragging');
  document.body.classList.add('is-moving-ticket');

  const dock = document.createElement('div');
  dock.className = 'work-drag-dock';
  dock.setAttribute('aria-label', 'Soltar en un estado');
  document.querySelectorAll(`.work-drop-cell[data-row="${ticket.dataset.row}"]`).forEach(cell => {
    cell.classList.add('is-available');
    const destination = document.createElement('div');
    destination.className = 'work-dock-target';
    destination.dataset.column = cell.dataset.column;
    destination.dataset.row = cell.dataset.row;
    destination.textContent = cell.dataset.state;
    dock.appendChild(destination);
  });
  document.body.appendChild(dock);
  activeDrag.dock = dock;
  moveVisualDrag(event);
}

function moveVisualDrag(event) {
  if (!activeDrag?.ghost) return;
  activeDrag.ghost.style.left = `${event.clientX + 14}px`;
  activeDrag.ghost.style.top = `${event.clientY + 14}px`;
  highlightTarget(targetAt(event.clientX, event.clientY));
}

function endVisualDrag() {
  if (!activeDrag) return;
  activeDrag.ticket.classList.remove('is-dragging');
  activeDrag.ghost?.remove();
  activeDrag.dock?.remove();
  document.body.classList.remove('is-moving-ticket');
  document.querySelectorAll('.work-drop-cell.is-available, .work-drop-cell.is-target')
    .forEach(cell => cell.classList.remove('is-available', 'is-target'));
}

async function saveMove(ticket, columnId) {
  if (savingMove) return;
  savingMove = true;
  const url = ticket.dataset.kind === 'subtask'
    ? `/actividades/${ticket.dataset.id}/mover/`
    : `/tareas/${ticket.dataset.id}/mover/`;
  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'X-CSRFToken': csrfToken, 'Content-Type': 'application/json'},
      body: JSON.stringify({column_id: columnId})
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || 'No se pudo mover la tarea.');
    }
    window.location.reload();
  } catch (error) {
    savingMove = false;
    alert(error.message || 'No se pudo guardar el movimiento.');
  }
}

document.querySelectorAll('.work-ticket').forEach(ticket => {
  ticket.addEventListener('pointerdown', event => {
    if (savingMove || activeDrag || event.button !== 0 || event.target.closest('a, button, input, select, textarea')) return;
    activeDrag = {ticket, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY};
    ticket.setPointerCapture(event.pointerId);
  });

  ticket.addEventListener('pointermove', event => {
    if (!activeDrag || activeDrag.ticket !== ticket || activeDrag.pointerId !== event.pointerId) return;
    if (!activeDrag.ghost && Math.hypot(event.clientX - activeDrag.startX, event.clientY - activeDrag.startY) > 6) {
      startVisualDrag(event);
    }
    if (activeDrag.ghost) {
      event.preventDefault();
      moveVisualDrag(event);
    }
  });

  ticket.addEventListener('pointerup', event => {
    if (!activeDrag || activeDrag.ticket !== ticket || activeDrag.pointerId !== event.pointerId) return;
    const destination = activeDrag.ghost ? targetAt(event.clientX, event.clientY) : null;
    const oldColumn = ticket.closest('.work-drop-cell')?.dataset.column;
    endVisualDrag();
    activeDrag = null;
    if (destination && destination.dataset.column !== oldColumn) saveMove(ticket, destination.dataset.column);
  });

  ticket.addEventListener('pointercancel', () => {
    if (activeDrag?.ticket !== ticket) return;
    endVisualDrag();
    activeDrag = null;
  });
});
