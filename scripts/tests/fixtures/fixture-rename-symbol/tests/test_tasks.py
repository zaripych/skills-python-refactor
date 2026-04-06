from todoapp.models import Priority, Task
from todoapp.services.tasks import complete_task, create_task, summarize


def test_create_task():
    task = create_task("Buy milk", Priority.LOW)
    assert task == Task(title="Buy milk", priority=Priority.LOW)


def test_complete_task():
    task = create_task("Buy milk")
    done = complete_task(task)
    assert done.done is True


def test_summarize():
    task = create_task("Buy milk", Priority.HIGH)
    assert summarize(task) == "[pending] Buy milk (high)"
