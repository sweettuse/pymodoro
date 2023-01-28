from __future__ import annotations
from abc import ABC, abstractmethod

from collections import deque
from itertools import chain, takewhile

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


class TimeSpentWindowed(TimeSpent):
    """base class for looking at time spent over different windows

    just implement `window_start` and `panel_title` and you're good to go
    """

    def __init__(self, component_id: str):
        super().__init__(id=self.window_id)
        self.component_id = component_id
        self.events = self._init_events()
        self._prune(update_prev_spent=False)
        self.prev_spent = sum(float(e["elapsed"]) for e in self.events)
        self._prune_regularly = self.set_interval(60, self._prune)
        EventStore.subscribe(self.on_new_event)

    @classproperty
    def window_start(cls) -> pendulum.DateTime:
        """what datetime is the earliest event this window should consider.

        can/should be dynamic"""
        raise NotImplementedError

    @classproperty
    def panel_title(cls) -> str:
        """how should this be displayed in the UI"""
        raise NotImplementedError

    @classproperty
    def window_id(cls) -> str:
        return cls.__name__

    def _init_events(self):
        events = chain(
            EventStore.load_cached(),
            EventStore.in_mem_events,
        )
        return deque(filter(self._is_event_relevant, events))

    def on_new_event(self, d: dict):
        if not self._is_event_relevant(d):
            return

        self.events.append(d)
        self.prev_spent += float(d["elapsed"])
        self.spent_in_current_period = 0.0

    def _is_event_relevant(self, d: dict):
        return (
            d["component_id"] == self.component_id
            and d["name"] in {"stopped", "manually_accounted_time"}
            and d["at"] >= self.window_start
        )  # fmt: skip

    def _update(self, spent_in_current_period: float):
        """update the display"""
        self._prune()
        t = format_time(int(spent_in_current_period + self.prev_spent))
        text = Align(t, "center", vertical="middle")
        res = Panel(text, title=self.panel_title)
        self.update(res)

    def _prune(self, *, update_prev_spent=True):
        """remove old events and update prev_spent if necessary"""
        min_time = self.window_start
        to_prune = list(takewhile(lambda e: e["at"] <= min_time, self.events))
        to_rm = sum(float(e["elapsed"]) for e in to_prune) or 0.0

        for _ in range(len(to_prune)):
            self.events.popleft()

        if to_rm and update_prev_spent:
            self.prev_spent -= to_rm


class TimeSpentTotal(TimeSpentWindowed):
    """how much time spent overall

    could/should ultimately replace the current `TotalTimeSpent` object
    """

    @classproperty
    def window_start(cls):
        return pendulum.now().min

    @classproperty
    def panel_title(cls):
        return "spent"


class TimeSpentWeek(TimeSpentWindowed):
    """how much time spent over last week"""

    @classproperty
    def window_start(cls):
        return pendulum.now().subtract(weeks=1)

    @classproperty
    def panel_title(cls):
        return "spent(w)"


class TimeSpentWorkWeek(TimeSpentWindowed):
    """how much time spent over last week"""

    @classproperty
    def window_start(cls):
        return pendulum.now().start_of("week")

    @classproperty
    def panel_title(cls):
        return "spent(ww)"


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
    def create(cls, component_id: str) -> TimeSpentContainer:
        """register `TimeSpent` objects here"""
        res = cls()
        res.component_id = component_id

        for ts in (
            TimeSpentTotal(component_id),
            TimeSpentWeek(component_id),
            TimeSpentWorkWeek(component_id),
            TimeSpentDay(component_id),
        ):
            res._add_time_spent(ts)

        res.time_spent_to_next_map = res._init_time_spent_to_next_map(res.time_spents)
        res.set_time_spent(res.app.current_time_window_id)
        return res

    def _add_time_spent(self, ts: TimeSpent):
        self.time_spents[ts.id] = ts

    @staticmethod
    def _init_time_spent_to_next_map(keys):
        d = deque(keys)
        d.rotate(-1)
        return dict(zip(keys, d))

    def set_time_spent(self, window_id: str):
        self.current_time_spent_ptr = self.time_spents[window_id]

    def watch_current_time_spent_ptr(self, time_spent: Type[TimeSpent]):
        """only display the `current_time_spent_ptr`; hide all others"""
        for ts in self.time_spents.values():
            ts.set_class(ts is not time_spent, "hidden")

    def watch_spent_in_current_period(self, elapsed: float):
        for ts in self.time_spents.values():
            ts.spent_in_current_period = elapsed

    def on_click(self):
        """switch to next time spent instance"""
        self.app.current_time_window_id = self.time_spent_to_next_map[
            self.current_time_spent_ptr.id
        ]
