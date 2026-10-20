from collections import defaultdict


def task_progress(task, columns, subtasks=None):
    """Porcentaje de avance por estado, promediado entre subtareas."""
    if not columns:
        return 0
    steps = max(len(columns) - 1, 1)
    positions = {column.pk: index for index, column in enumerate(columns)}

    def state_progress(column_id, completed):
        if completed:
            return 100
        return round(100 * positions.get(column_id, 0) / steps)

    if subtasks is None:
        subtasks = list(task.activities.all())
    if subtasks:
        return round(
            sum(state_progress(subtask.column_id, subtask.completed) for subtask in subtasks)
            / len(subtasks)
        )
    return state_progress(task.column_id, bool(task.completed_at))


def progress_by_board(tasks, columns_by_board):
    grouped = defaultdict(list)
    for task in tasks:
        columns = columns_by_board.get(task.board_id, [])
        progress = task_progress(task, columns)
        task.progress_percent = progress
        grouped[task.board_id].append(progress)
    return {
        board_id: round(sum(values) / len(values))
        for board_id, values in grouped.items()
    }
