from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import shelve
from typing import Any, Optional, TYPE_CHECKING
from pymodoro.utils import classproperty


if TYPE_CHECKING:
    from .pymodoro import CountdownTimerContainer


class StateManagement:
    @classproperty
    @abstractmethod
    def state_attrs(cls) -> tuple[str, ...]:
        raise NotImplemented

    def dump_state(self) -> dict[str, Any]:
        return dict(cls=type(self)) | {a: getattr(self, a) for a in self.state_attrs}

    def set_state(self, state_dict: dict[str, Any]) -> None:
        for a, v in state_dict.items():
            if a == "cls":
                continue
            setattr(self, a, v)


class StateStore:
    store = Path("~/.pymodoro").expanduser()

    @classmethod
    def load(cls):
        with shelve.open(str(cls.store)) as s:
            return s.get("timers")

    @classmethod
    def dump(cls, timers):
        with shelve.open(str(cls.store)) as s:
            s["timers"] = timers


@dataclass
class CountdownTimerState:
    id: Optional[str] = ""
    total_seconds_completed: float = 0.0
    num_pomodoros_completed: int = 0

    linear_state: Optional[dict] = None
    description_state: Optional[dict] = None
    countdown_timer_state: Optional[dict] = None
    time_input_state: Optional[dict] = None

    def calc_num_pomodoros(self, current_pomodoro_secs: float) -> int:
        return int(self.total_seconds_completed / current_pomodoro_secs)

    @classmethod
    def from_countdown_timer_container(
        cls, ctc: CountdownTimerContainer
    ) -> CountdownTimerState:
        from pymodoro.widgets.text_input import TextInput
        from pymodoro.widgets.countdown_timer import CountdownTimerWidget

        return cls(
            ctc.id,
            ctc.state.total_seconds_completed,
            ctc.state.num_pomodoros_completed,
            linear_state=ctc.query_one("#linear", TextInput).dump_state(),
            description_state=ctc.query_one("#description", TextInput).dump_state(),
            countdown_timer_state=ctc.query_one(CountdownTimerWidget).ct.dump_state(),
            time_input_state=ctc.query_one("#time_input", TextInput).dump_state(),
        )
