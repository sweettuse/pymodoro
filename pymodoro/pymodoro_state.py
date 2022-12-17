from __future__ import annotations
import os

from contextlib import suppress
from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Literal, Optional, TYPE_CHECKING, TypeAlias

import pendulum


if TYPE_CHECKING:
    from widgets.countdown_timer import CountdownTimerComponent

BASE_PATH = Path("~/.pymodoro").expanduser()
with suppress(FileExistsError):
    os.mkdir(str(BASE_PATH))


class EventStore:
    """store relevant events out to file"""

    store = str(BASE_PATH / "events")
    in_mem_events = []

    @classmethod
    def register(cls, d: dict):
        """log event dict to events file"""
        d["at"] = d.get("at", pendulum.now())
        cls.in_mem_events.append(d)
        msg = json.dumps(d)
        with open(cls.store, "a") as f:
            f.write(msg + "\n")

    @classmethod
    def load(cls):
        with open(cls.store) as f:
            return [cls._parse(l.strip()) for l in f]

    @classmethod
    def _parse(cls, s: str) -> dict:
        res = json.loads(s)
        res["at"] = pendulum.parse(res["at"])  # type: ignore  # pylance so dumb - thinks `parse` is not exported but it is :(
        return res


Status: TypeAlias = Literal["todo", "in_progress", "completed", "deleted"]


class StateStore:
    """store/read timer state to/from file.

    allows rehydrating of timers on startup
    """

    store = str(BASE_PATH / "state")

    @classmethod
    def load(cls) -> Optional[list[CountdownTimerState]]:
        with suppress(Exception):
            with open(cls.store, "r") as f:
                res = json.load(f)
            return [CountdownTimerState(**v) for v in res]

    @classmethod
    def load_current(cls) -> Optional[list[CountdownTimerState]]:
        """load not deleted timers"""
        if not (states := cls.load()):
            return None
        return [cts for cts in states if cts.status != "deleted"]

    @classmethod
    def dump(cls, states: list[CountdownTimerState]):
        dicts = [asdict(s) for s in states]
        with open(cls.store, "w") as f:
            json.dump(dicts, f, indent=2)


@dataclass
class CountdownTimerState:
    """class storing all data to rehydrate a CountdownTimerComponent"""

    id: Optional[str] = ""
    status: Status = "in_progress"
    total_seconds_completed: float = 0.0
    num_pomodoros_completed: int = 0

    linear_state: Optional[dict] = None
    description_state: Optional[dict] = None
    countdown_timer_state: Optional[dict] = None
    time_input_state: Optional[dict] = None
    was_active: bool = False

    def calc_num_pomodoros(self, current_pomodoro_secs: float) -> int:
        """number of pomodoros that would've been completed based on the current length"""
        return int(self.total_seconds_completed / current_pomodoro_secs)

    @classmethod
    def from_countdown_timer_component(
        cls, ctc: CountdownTimerComponent
    ) -> CountdownTimerState:
        from widgets.text_input import TextInput
        from widgets.countdown_timer import CountdownTimerWidget

        return cls(
            ctc.id,
            ctc.state.status,
            ctc.state.total_seconds_completed,
            ctc.state.num_pomodoros_completed,
            linear_state=ctc.query_one("#linear", TextInput).dump_state(),
            description_state=ctc.query_one("#description", TextInput).dump_state(),
            countdown_timer_state=ctc.query_one(CountdownTimerWidget).ct.dump_state(),
            time_input_state=ctc.query_one("#time_input", TextInput).dump_state(),
            was_active=ctc.is_active,
        )

    @classmethod
    def new_default(cls) -> CountdownTimerState:
        """create new default state with id added"""
        from widgets.countdown_timer import CountdownTimerComponent

        return cls(
            **(dict(id=CountdownTimerComponent.new_id()) | json.loads(default_config))
        )


default_config = """
  {
    "status": "in_progress",     
    "total_seconds_completed": 0.0,
    "num_pomodoros_completed": 0,
    "linear_state": {   
      "classes": [],   
      "id": "linear",                  
      "value": "",     
      "placeholder": "linear issue id",
      "password": false                                                    
    },                      
    "description_state": {         
      "classes": [],             
      "id": "description",         
      "value": "",     
      "placeholder": "description",
      "password": false       
    },                                 
    "countdown_timer_state": {         
      "initial_seconds": 1500,
      "total_elapsed": 0.0
    },              
    "time_input_state": { 
      "classes": [
        "hidden"                   
      ],               
      "id": "time_input",
      "value": "",            
      "placeholder": "",      
      "password": false   
    } 
  }
"""
