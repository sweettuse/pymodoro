from __future__ import annotations
from abc import ABC, abstractmethod

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
from widgets.countdown_timer.time_spent import TimeSpentContainer
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
                TimeSpentContainer.create(state.id),
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
        # self.query_one(TimeSpentContainer).spent_in_current_period = 0.0
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

        search_str = search_str.casefold()
        return (
            search_str in self.query_one("#linear", TextInput).value.casefold()
            or search_str in self.query_one("#description", TextInput).value.casefold()
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
