from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


MAX_TITLE_LENGTH = 200


@dataclass
class Task:
    title: str
    priority: Priority
    done: bool = False

    def summarize(self) -> str:
        status = "done" if self.done else "pending"
        return f"[{status}] {self.title} ({self.priority.value})"
