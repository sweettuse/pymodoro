from __future__ import annotations

import asyncio
from collections import deque
from enum import Enum
from functools import partial
from itertools import takewhile

from typing import Any, Optional, Type
from uuid import uuid4
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
from utils import classproperty
from stats.time_spent import get_elapsed_events
from utils import format_time
from pymodoro_state import CountdownTimerState, StateStore, EventStore
from widgets.text_input import (
    LinearInput,
    TextInput,
    TimeInput,
    DescriptionInput,
    TimeInputBase,
    ManualTimeAccounting,
)

from widgets.countdown_timer import CountdownTimer, CountdownTimerWidget


class TimeSpent(Static):
    prev_spent = reactive(0.0)
    spent_in_current_period = reactive(0.0)

    def _update(self, spent_in_current_period: float):
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


class TimeSpentWeek(TimeSpent):
    def __init__(self, component_id: str):
        super().__init__(id="time_spent_week")
        self.component_id = component_id
        self.events = self._init_events(component_id)
        self.prev_spent = 0.0
        self._update_prev_spent(force=True)
        EventStore.subscribe(self.on_new_event)

    @classproperty
    def start_dt(cls):
        return pendulum.now().subtract(weeks=1)

    @classmethod
    def _init_events(cls, component_id: str):
        events = get_elapsed_events()
        return deque(e for e in events if e["component_id"] == component_id)

    def on_new_event(self, d: dict):
        if not self._is_event_relevant(d):
            return
        self.events.append(d)
        self._update_prev_spent(force=True)

    def _is_event_relevant(self, d: dict):
        return d.get("component_id") == self.component_id and d["name"] in {
            "stopped",
            "manually_accounted_time",
        }

    def _update(self, spent_in_current_period: float):
        self._update_prev_spent()
        self.app._debug(f"huh: {spent_in_current_period}, {self.prev_spent}")
        t = format_time(int(spent_in_current_period + self.prev_spent))
        text = Align(t, "center", vertical="middle")
        res = Panel(text, title="spent(w)")
        self.update(res)

    def _update_prev_spent(self, *, force=False):
        if not self.events:
            return

        old_found = 0
        min_time = self.start_dt
        for e in self.events:
            if e["at"] > min_time:
                break
            old_found += 1

        if not (old_found or force):
            return

        for _ in range(old_found):
            self.events.popleft()

        self.prev_spent = sum(e["elapsed"] for e in self.events)


class TimeSpentContainer(Static):
    spent_in_current_period = reactive(0.0)
    current_time_spent_ptr: TimeSpent = reactive(None)
    time_spents: list[TimeSpent] = var(list)
    component_id: str = var("")

    def compose(self) -> ComposeResult:
        return iter(self.time_spents)

    @classmethod
    def create(cls, component_id: str, prev_spent: float) -> TimeSpentContainer:
        res = cls()
        res.component_id = component_id

        res.time_spents = [
            TotalTimeSpent(prev_spent),
            TimeSpentWeek(component_id),
        ]
        res.current_time_spent_ptr = res.time_spents[0]
        return res

    def watch_current_time_spent_ptr(self, time_spent: Type[TimeSpent]):
        """only display the `current_time_spent_ptr`; hide all others"""
        self.app._debug(f"ptr: {time_spent}")
        for ts in self.time_spents:
            ts.set_class(ts is not time_spent, "hidden")

    def watch_spent_in_current_period(self, elapsed: float):
        for ts in self.time_spents:
            ts.spent_in_current_period = elapsed

    def on_click(self):
        """switch to next time spent type"""
        idx = self.time_spents.index(self.current_time_spent_ptr)
        next_idx = (idx + 1) % len(self.time_spents)
        self.app._debug(f"click: {idx}, {next_idx}")
        self.current_time_spent_ptr = self.time_spents[next_idx]


class TimeGroup(Vertical):
    ...


class Caret(Static):
    active = reactive(False)
    val = var(" ")

    def watch_active(self, active):
        self.val = "> " if active else "  "
        self.update(Align(self.val, "center", vertical="middle"))


class CountdownTimerComponent(Static, can_focus=True, can_focus_children=True):
    """wrap all the widgets that represent a "timer"

    things like the linear issue, description, remaining, spent, etc
    """

    @classmethod
    def from_state(cls, state: CountdownTimerState) -> CountdownTimerComponent:
        res = cls(id=state.id)
        state.status = "in_progress"
        res.state = state
        return res

    @classmethod
    def new_id(cls) -> str:
        return f"countdown_timer_container_{uuid4()}"

    @classmethod
    def create(cls) -> CountdownTimerComponent:
        return cls.from_state(CountdownTimerState.new_default())

    @property
    def is_active(self) -> bool:
        """is this timer currently running"""
        return self.has_class("active")

    @property
    def focused_or_within(self) -> bool:
        """whether this component or one if its children has focus"""
        return self.has_focus or self.has_pseudo_class("focus-within")

    @property
    def _can_start_or_stop(self) -> bool:
        return not self.app.has_active_timer or self.is_active

    def compose(self) -> ComposeResult:
        if not (state := getattr(self, "state", None)):
            state = CountdownTimerState.new_default()

        self.state = state
        time_spent_container = TimeSpentContainer.create(
            state.id, self.state.total_seconds_completed
        )

        yield Horizontal(
            # Caret(id='caret'),
            LinearInput.from_state(state.linear_state),
            DescriptionInput.from_state(state.description_state),
            Button("start", id="start", variant="success"),
            Button("stop", id="stop", variant="error", classes="hidden"),
            TimeGroup(
                CountdownTimerWidget(
                    CountdownTimer.from_state(state.countdown_timer_state)
                ),
                TimeInput.from_state(state.time_input_state),
                ManualTimeAccounting.from_state(state.manual_accounting_state),
                time_spent_container,
            ),
            Button("reset", id="reset", variant="default"),
        )

    async def start(self):
        """start child widget"""
        await self.query_one(CountdownTimerWidget).start()

    async def stop(self):
        """stop child widget"""
        if self.is_active:
            await self.query_one(CountdownTimerWidget).stop()

    async def reset(self):
        await self.query_one(CountdownTimerWidget).reset()

    # ==========================================================================
    # actions
    # ==========================================================================
    async def action_quit(self):
        ctw = self.query_one(CountdownTimerWidget)
        await ctw.stop()

    # ==========================================================================
    # event handlers
    # ==========================================================================
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        self.focus()

        # if app has active timer and this one isn't it
        if not self._can_start_or_stop and button_id in {"start", "stop"}:
            return

        ctw = self.query_one(CountdownTimerWidget)
        if button_id == "start":
            await ctw.start()
        elif button_id == "stop":
            await ctw.stop()
        elif button_id == "reset":
            await ctw.reset()

    async def on_linear_input_new_title(self, event: LinearInput.NewTitle):
        """we received a new title from linear, so update the description with it"""
        desc = self.query_one("#description", TextInput)
        desc.value = event.title

    async def on_countdown_timer_widget_started(
        self, event: CountdownTimerWidget.Started
    ):
        """when the child widget is started, set this as active"""
        self._set_active(active=True)

    async def on_countdown_timer_widget_stopped(
        self, event: CountdownTimerWidget.Stopped
    ):
        """deactivate timer and relevant time spent fields"""
        self.log(f"{event.sender} timer stopped")
        self.state.total_seconds_completed += event.elapsed
        tts = self.query_one(TotalTimeSpent)
        tts.prev_spent += event.elapsed

        self.query_one(TimeSpentContainer).spent_in_current_period = 0.0
        self._set_active(active=False)

    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        """deactivate timer on completion"""
        self.log(f"{event.sender} timer completed")
        self.state.num_pomodoros_completed += 1
        self._set_active(active=False)

    async def on_countdown_timer_widget_new_second(
        self,
        event: CountdownTimerWidget.NewSecond,
    ):
        """update total time spent with how long this current timer has been active"""
        self.query_one(TimeSpentContainer).spent_in_current_period = event.elapsed

    async def on_time_input_new_total_seconds(self, msg: TimeInput.NewTotalSeconds):
        """handle when amount remaining is changed"""
        await self.stop()
        ctw = self.query_one(CountdownTimerWidget)
        ctw.ct.initial_seconds = msg.total_seconds
        await ctw.reset()
        self.exit_edit_time()

    async def on_manual_time_accounting_accounted_time(
        self,
        event: ManualTimeAccounting.AccountedTime,
    ):
        self.query_one(TotalTimeSpent).prev_spent += event.elapsed
        self.state.total_seconds_completed += event.elapsed
        self.exit_manually_accounting_for_time()
        self.focus()

    def on_click(self):
        self.focus()

    # ==========================================================================
    # helpers
    # ==========================================================================
    def dump_state(self) -> CountdownTimerState:
        self.state = CountdownTimerState.from_countdown_timer_component(self)
        return self.state

    def enter_edit_time(self):
        """called to allow changing of remaining time"""
        ti = self._set_edit_time_classes(editing=True, time_class=TimeInput)
        ti.focus()

    def exit_edit_time(self):
        """called when done editing remaining time"""
        ti = self._set_edit_time_classes(editing=False, time_class=TimeInput)
        ti.value = ""

    def enter_manually_accounting_for_time(self):
        """called to allow entering manually accounted time"""
        ti = self._set_edit_time_classes(editing=True, time_class=ManualTimeAccounting)
        ti.focus()

    def exit_manually_accounting_for_time(self):
        """called when done manually accounting for time"""
        ti = self._set_edit_time_classes(editing=False, time_class=ManualTimeAccounting)
        ti.value = ""

    def matches_search(self, search_str: str) -> bool:
        """whether this component matches the search str"""
        if not search_str:
            return True

        return (
            search_str in self.query_one("#linear", TextInput).value
            or search_str in self.query_one("#description", TextInput).value
        )

    def _set_edit_time_classes(
        self, *, editing: bool, time_class: Type[TimeInputBase]
    ) -> TimeInputBase:
        """hide/show relevant widgets when editing remaining time or manually accounting for time spent"""
        self.query_one(CountdownTimerWidget).set_class(editing, "hidden")
        self.query_one(TimeSpentContainer).set_class(editing, "hidden")
        (ti := self.query_one(time_class)).set_class(not editing, "hidden")
        return ti

    def _set_active(self, *, active: bool) -> None:
        """show/hide relevant buttons depending on whether this timer is running"""
        self.query_one("#start").set_class(active, "hidden")
        self.query_one("#reset").set_class(active, "hidden")
        self.query_one("#stop").set_class(not active, "hidden")
        self.set_class(active, "active")
