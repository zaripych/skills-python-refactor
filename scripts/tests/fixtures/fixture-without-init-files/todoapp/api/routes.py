from todoapp.models import Task
from todoapp.services.tasks.crud import create_task
from todoapp.services.tasks.validation import validate_task


def handle_create(title: str) -> Task:
    task = create_task(title)
    validate_task(task)
    return task
