from __future__ import annotations
from functools import cache, wraps
import os

from contextlib import suppress
from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Iterable, Literal, TYPE_CHECKING, TypeAlias

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


def _cache(fn):
    """cache StateStore based on `_updated`"""
    res = last_updated = None

    @wraps(fn)
    def wrapper(cls):
        nonlocal last_updated, res
        if last_updated == cls._updated:
            return res
        res = fn(cls)
        last_updated = cls._updated
        return res

    return wrapper


class StateStore:
    """store/read timer state to/from file.

    allows rehydrating of timers on startup
    """

    store = str(BASE_PATH / "state")
    # update when `dumped` to bust cache
    _updated: int = 0

    @classmethod
    @_cache
    def load(cls) -> list[CountdownTimerState] | None:
        with suppress(Exception):
            with open(cls.store, "r") as f:
                res = json.load(f)
            return [CountdownTimerState(**v) for v in res]

    @classmethod
    @_cache
    def load_current(cls) -> list[CountdownTimerState] | None:
        """load not deleted timers"""
        if not (states := cls.load()):
            return None
        return [cts for cts in states if cts.status != "deleted"]

    @classmethod
    @_cache
    def load_deleted(cls) -> list[CountdownTimerState] | None:
        """load deleted timers"""
        if not (states := cls.load()):
            return None
        return [cts for cts in states if cts.status == "deleted"]

    @classmethod
    def dump(cls, states: Iterable[CountdownTimerState]):
        cls._updated += 1
        dicts = [asdict(s) for s in states]
        with open(cls.store, "r") as f, open(cls.store + ".bak", "w") as out:
            out.write(f.read())
        with open(cls.store, "w") as f:
            json.dump(dicts, f, indent=2)


@dataclass
class CountdownTimerState:
    """class storing all data to rehydrate a CountdownTimerComponent"""

    id: str | None = ""
    status: Status = "in_progress"
    total_seconds_completed: float = 0.0
    num_pomodoros_completed: int = 0

    linear_state: dict | None = None
    description_state: dict | None = None
    countdown_timer_state: dict | None = None
    time_input_state: dict | None = None
    was_active: bool = False

    def calc_num_pomodoros(self, current_pomodoro_secs: float) -> int:
        """number of pomodoros that would've been completed based on the current length"""
        return int(self.total_seconds_completed / current_pomodoro_secs)

    @classmethod
    def from_countdown_timer_component(
        cls, ctc: CountdownTimerComponent
    ) -> CountdownTimerState:
        """convert a CountdownTimerComponent to its state"""
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

# if __name__ == '__main__':
#     states = [
#                  CountdownTimerState(
#                      id='countdown_timer_container_fa96715d-bb14-48b1-8b06-b48c13632982',
#                      status='in_progress',
#                      total_seconds_completed=5708.885919251887,
#                      num_pomodoros_completed=3,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc20',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 2400, 'total_elapsed': 430.8687494449259},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_23ff667c-cf39-46be-97c7-a9b4a5718e42',
#                      status='in_progress',
#                      total_seconds_completed=3.7281829079729505,
#                      num_pomodoros_completed=0,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'delete test',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={
#                          'initial_seconds': 1500,
#                          'total_elapsed': 3.7281829079729505
#                      },
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_ff78c432-e595-4bf5-b1fa-07fd0f8ef43b',
#                      status='in_progress',
#                      total_seconds_completed=39.84767976705916,
#                      num_pomodoros_completed=0,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'jeb',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 1500, 'total_elapsed': 39.84371856204234},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_0a833313-89a5-4fb6-ad6d-74611f0494e2',
#                      status='in_progress',
#                      total_seconds_completed=0.0,
#                      num_pomodoros_completed=0,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'tuse',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 1500, 'total_elapsed': 0.0},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_e3da11ef-4a01-4ff3-9080-403b9c3df8e1',
#                      status='in_progress',
#                      total_seconds_completed=6504.867730615981,
#                      num_pomodoros_completed=1,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc21',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 1200, 'total_elapsed': 1143.069422571978},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_53df532f-0abf-4f48-8b8a-de5b7081c4d4',
#                      status='in_progress',
#                      total_seconds_completed=4596.56786969502,
#                      num_pomodoros_completed=1,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc22',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={
#                          'initial_seconds': 2700,
#                          'total_elapsed': 1896.5666669450584
#                      },
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_d80e3d15-28ea-43f9-98b3-c409cfaf4f62',
#                      status='in_progress',
#                      total_seconds_completed=1500.0004960669903,
#                      num_pomodoros_completed=1,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc24',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={
#                          'initial_seconds': 1500,
#                          'total_elapsed': 1500.0004960669903
#                      },
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_f7c0ea4c-4dc5-48ac-838d-de27da6e1738',
#                      status='in_progress',
#                      total_seconds_completed=4842.719598564872,
#                      num_pomodoros_completed=2,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc18',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 300, 'total_elapsed': 300.0025539229973},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_90e6a916-0292-4266-a775-e2261a475d42',
#                      status='in_progress',
#                      total_seconds_completed=7136.079099636991,
#                      num_pomodoros_completed=2,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc15',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 4200, 'total_elapsed': 454.4788939190039},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
#                  CountdownTimerState(
#                      id='countdown_timer_container_7e739c66-1f6a-46fc-b57b-0e3018200fab',
#                      status='in_progress',
#                      total_seconds_completed=2552.6521332308766,
#                      num_pomodoros_completed=2,
#                      linear_state={
#                          'classes': [],
#                          'id': 'linear',
#                          'value': '',
#                          'placeholder': 'linear issue id',
#                          'password': False
#                      },
#                      description_state={
#                          'classes': [],
#                          'id': 'description',
#                          'value': 'aoc19',
#                          'placeholder': 'description',
#                          'password': False
#                      },
#                      countdown_timer_state={'initial_seconds': 2400, 'total_elapsed': 450.7160462278698},
#                      time_input_state={
#                          'classes': ['hidden'],
#                          'id': 'time_input',
#                          'value': '',
#                          'placeholder': '',
#                          'password': False
#                      },
#                      was_active=False
#                  ),
# 				 ]
#     StateStore.dump(states)
