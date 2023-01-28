from __future__ import annotations
from abc import ABC, abstractmethod

from collections import deque

from typing import Any, Optional, Type
import pendulum
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.align import Align
from rich.panel import Panel
from rich.segment import Segment
from textual.reactive import reactive, var
from textual.message import Message, MessageTarget
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from utils import classproperty, format_time
from pymodoro_state import CountdownTimerState, StateStore, EventStore


class TimeSpent(Static):
    prev_spent = reactive(0.0)
    spent_in_current_period = reactive(0.0)

    def _update(self, spent_in_current_period: float):
        """update the displayed value"""
        raise NotImplementedError

    def watch_spent_in_current_period(self, val):
        self._update(val)

    def watch_prev_spent(self, _):
        self._update(self.spent_in_current_period)


class TotalTimeSpent(TimeSpent):
    def __init__(self, prev_spent):
        super().__init__(id="total")
        self.prev_spent = prev_spent

    def _update(self, spent_in_current_period: float):
        rem = int(spent_in_current_period + self.prev_spent)
        text = Align(format_time(rem), "center", vertical="middle")
        res = Panel(text, title="spent")
        self.update(res)


class TimeSpentWindowed(TimeSpent):
    """base class for looking at time spent over different windows

    just implement `window_start` and `panel_title` and you're good to go
    """

    def __init__(self, component_id: str):
        super().__init__(id=type(self).__name__)
        self.component_id = component_id
        self.events = self._init_events(component_id)
        self.prev_spent = 0.0
        self._update_prev_spent(force=True)
        EventStore.subscribe(self.on_new_event)

    @classproperty
    def window_start(cls) -> pendulum.DateTime:
        raise NotImplementedError

    @classproperty
    def panel_title(cls) -> str:
        raise NotImplementedError

    @classmethod
    def _init_events(cls, component_id: str):
        events = EventStore.get_elapsed_events()
        return deque(e for e in events if e["component_id"] == component_id)

    def on_new_event(self, d: dict):
        if not self._is_event_relevant(d):
            return
        self.events.append(d)
        self._update_prev_spent(force=True)

    def _is_event_relevant(self, d: dict):
        return (
            d.get("component_id") == self.component_id
            and d["name"] in { "stopped", "manually_accounted_time"}
            and d["at"] >= self.window_start
        )  # fmt: skip

    def _update(self, spent_in_current_period: float):
        """update the display"""
        self._update_prev_spent()
        t = format_time(int(spent_in_current_period + self.prev_spent))
        text = Align(t, "center", vertical="middle")
        res = Panel(text, title=self.panel_title)
        self.update(res)

    def _update_prev_spent(self, *, force=False):
        """sum up how much time has elapsed in events that have occured between
        `window_start` and now

        update `prev_spent` with that value
        """
        if not self.events:
            return

        old_found = 0
        min_time = self.window_start
        for e in self.events:
            if e["at"] > min_time:
                break
            old_found += 1

        if not (old_found or force):
            return

        for _ in range(old_found):
            self.events.popleft()

        self.prev_spent = sum(float(e["elapsed"]) for e in self.events)


class TimeSpentTotal(TimeSpentWindowed):
    """how much time spent overall

    could/should ultimately replace the current `TotalTimeSpent` object
    """

    @classproperty
    def window_start(cls):
        return pendulum.now().min

    @classproperty
    def panel_title(cls):
        return "spent(tot)"


class TimeSpentWeek(TimeSpentWindowed):
    """how much time spent over last week"""

    @classproperty
    def window_start(cls):
        return pendulum.now().subtract(weeks=1)

    @classproperty
    def panel_title(cls):
        return "spent(w)"


class TimeSpentDay(TimeSpentWindowed):
    """how much time spent today"""

    @classproperty
    def window_start(cls):
        return pendulum.today()

    @classproperty
    def panel_title(cls):
        return "spent(d)"


class TimeSpentContainer(Static):
    """container wrapping all the time spent objects"""

    spent_in_current_period = reactive(0.0)
    current_time_spent_ptr: TimeSpent = reactive(None)
    time_spents: dict[str, TimeSpent] = var(dict)
    component_id: str = var("")
    time_spent_to_next_map: dict[str, str] = var(dict)

    def compose(self) -> ComposeResult:
        return iter(self.time_spents.values())

    @classmethod
    def create(cls, component_id: str, prev_spent: float) -> TimeSpentContainer:
        """register `TimeSpent` objects here"""
        res = cls()
        res.component_id = component_id

        for ts in (
            TotalTimeSpent(prev_spent),
            TimeSpentTotal(component_id),
            TimeSpentWeek(component_id),
            TimeSpentDay(component_id),
        ):
            res._add_time_spent(ts)

        res.current_time_spent_ptr = next(iter(res.time_spents.values()))
        res.time_spent_to_next_map = res._init_time_spent_to_next_map(res.time_spents)
        return res

    def _add_time_spent(self, ts: TimeSpent):
        self.time_spents[ts.id] = ts

    @staticmethod
    def _init_time_spent_to_next_map(keys):
        d = deque(keys)
        d.rotate(-1)
        return dict(zip(keys, d))

    def watch_current_time_spent_ptr(self, time_spent: Type[TimeSpent]):
        """only display the `current_time_spent_ptr`; hide all others"""
        for ts in self.time_spents.values():
            ts.set_class(ts is not time_spent, "hidden")

    def watch_spent_in_current_period(self, elapsed: float):
        for ts in self.time_spents.values():
            ts.spent_in_current_period = elapsed

    def on_click(self):
        """switch to next time spent instance"""
        next_id = self.time_spent_to_next_map[self.current_time_spent_ptr.id]
        for tsc in self.app.query(TimeSpentContainer):
            tsc._select_next_time_spent(next_id)

    def _select_next_time_spent(self, id):
        self.current_time_spent_ptr = self.time_spents[id]
