from todoapp.models import MAX_TITLE_LENGTH, Priority, Task


def create_task(title: str, priority: Priority = Priority.MEDIUM) -> Task:
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title exceeds {MAX_TITLE_LENGTH} characters")
    return Task(title=title, priority=priority)


def complete_task(task: Task) -> Task:
    return Task(title=task.title, priority=task.priority, done=True)


def summarize(task: Task) -> str:
    return task.summarize()
