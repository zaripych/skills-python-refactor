from dataclasses import dataclass


@dataclass
class Task:
    title: str
    done: bool


@dataclass
class Priority:
    level: int
    label: str
