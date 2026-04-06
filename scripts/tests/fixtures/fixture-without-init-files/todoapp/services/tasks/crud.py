from todoapp.models import Task


def create_task(title: str) -> Task:
    return Task(title=title, done=False)
