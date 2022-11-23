from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Literal, Optional, TYPE_CHECKING, TypeAlias


if TYPE_CHECKING:
    from widgets.countdown_timer import CountdownTimerContainer


class StateStore:
    store = str(Path("~/.pymodoro").expanduser())

    @classmethod
    def load(cls) -> Optional[list[CountdownTimerState]]:
        with suppress(Exception):
            with open(cls.store, "r") as f:
                res = json.load(f)
            return [CountdownTimerState(**v) for v in res]

    @classmethod
    def dump(cls, states: list[CountdownTimerState]):
        dicts = [asdict(s) for s in states]
        with open(cls.store, "w") as f:
            json.dump(dicts, f, indent=2)


Stage: TypeAlias = Literal["todo", "in_progress", "done", "canceled"]


@dataclass
class CountdownTimerState:
    id: Optional[str] = ""
    stage: Stage = "in_progress"
    total_seconds_completed: float = 0.0
    num_pomodoros_completed: int = 0

    linear_state: Optional[dict] = None
    description_state: Optional[dict] = None
    countdown_timer_state: Optional[dict] = None
    time_input_state: Optional[dict] = None

    def calc_num_pomodoros(self, current_pomodoro_secs: float) -> int:
        """number of pomodoros that would've been completed based on the current length"""
        return int(self.total_seconds_completed / current_pomodoro_secs)

    @classmethod
    def from_countdown_timer_container(
        cls, ctc: CountdownTimerContainer
    ) -> CountdownTimerState:
        from widgets.text_input import TextInput
        from widgets.countdown_timer import CountdownTimerWidget

        return cls(
            ctc.id,
            ctc.state.stage,
            ctc.state.total_seconds_completed,
            ctc.state.num_pomodoros_completed,
            linear_state=ctc.query_one("#linear", TextInput).dump_state(),
            description_state=ctc.query_one("#description", TextInput).dump_state(),
            countdown_timer_state=ctc.query_one(CountdownTimerWidget).ct.dump_state(),
            time_input_state=ctc.query_one("#time_input", TextInput).dump_state(),
        )
