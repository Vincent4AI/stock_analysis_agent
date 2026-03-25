"""核心数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class TaskStep:
    content: str
    agent: str
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""


@dataclass
class TaskPlan:
    query: str
    steps: list[TaskStep] = field(default_factory=list)
    current_step: int = 0

    @property
    def is_finished(self) -> bool:
        return self.current_step >= len(self.steps) or any(
            s.status == TaskStatus.FAILED for s in self.steps
        )

    def current(self) -> TaskStep:
        return self.steps[self.current_step]

    def advance(self, result: str):
        self.steps[self.current_step].status = TaskStatus.SUCCESS
        self.steps[self.current_step].result = result
        self.current_step += 1
