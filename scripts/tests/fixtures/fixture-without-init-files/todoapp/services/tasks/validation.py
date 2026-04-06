from todoapp.models import Task


def validate_task(task: Task) -> bool:
    return bool(task.title)
