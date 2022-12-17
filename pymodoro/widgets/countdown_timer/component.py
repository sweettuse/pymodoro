from __future__ import annotations

import asyncio
from enum import Enum
from functools import partial

from typing import Any, Optional
from uuid import uuid4
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
from utils import format_time
from pymodoro_state import CountdownTimerState, StateStore
from widgets.text_input import LinearInput, TextInput, TimeInput

from widgets.countdown_timer import CountdownTimer, CountdownTimerWidget


class TotalTimeSpent(Static):
    spent_in_current_period = reactive(0.0)
    prev_spent = var(0.0)

    def watch_spent_in_current_period(self, new_amount):
        rem = int(new_amount + self.prev_spent)
        text = Align(format_time(rem) , "center", vertical="middle")
        res = Panel(text, title="spent")
        self.update(res)


class TimeGroup(Vertical):
    ...


class Caret(Static):
    active = reactive(False)
    val = var(" ")

    def watch_active(self, active):
        self.val = "> " if active else "  "
        self.update(Align(self.val, "center", vertical="middle"))


class CountdownTimerComponent(Static, can_focus=True):
    @classmethod
    def from_state(cls, state: CountdownTimerState) -> CountdownTimerComponent:
        res = cls(id=state.id)
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
        return self.has_class("active")

    @property
    def focused_or_within(self) -> bool:
        return self.has_focus or self.has_pseudo_class("focus-within")

    @property
    def _can_start_or_stop(self) -> bool:
        return not self.app.has_active_timer or self.is_active

    def compose(self) -> ComposeResult:
        if not (state := getattr(self, "state", None)):
            state = CountdownTimerState.new_default()

        self.state = state

        tts = TotalTimeSpent(id="total")
        tts.prev_spent = self.state.total_seconds_completed
        yield Horizontal(
            # Caret(id='caret'),
            LinearInput.from_state(state.linear_state),
            TextInput.from_state(state.description_state),
            Button("start", id="start", variant="success"),
            Button("stop", id="stop", variant="error", classes="hidden"),
            TimeGroup(
                CountdownTimerWidget(
                    CountdownTimer.from_state(state.countdown_timer_state)
                ),
                TimeInput.from_state(state.time_input_state),
                tts,
            ),
            Button("reset", id="reset", variant="default"),
        )

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

    async def stop(self):
        await self.query_one(CountdownTimerWidget).stop()

    async def on_linear_input_new_title(self, event: LinearInput.NewTitle):
        """we received a new title from linear, so update the description with it"""
        desc = self.query_one("#description", TextInput)
        desc.value = event.title

    async def on_countdown_timer_widget_started(
        self, event: CountdownTimerWidget.Started
    ):
        self._set_active(active=True)

    async def on_countdown_timer_widget_stopped(
        self, event: CountdownTimerWidget.Stopped
    ):
        self.log(f"{event.sender} timer stopped")
        self.state.total_seconds_completed += event.elapsed
        tts = self.query_one(TotalTimeSpent)
        tts.prev_spent += event.elapsed
        tts.spent_in_current_period = 0
        self._set_active(active=False)

    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        self.log(f"{event.sender} timer completed")
        self.state.num_pomodoros_completed += 1
        self._set_active(active=False)

    async def on_countdown_timer_widget_new_second(
        self,
        event: CountdownTimerWidget.NewSecond,
    ):
        self.query_one(TotalTimeSpent).spent_in_current_period = event.elapsed

    async def on_time_input_new_total_seconds(self, msg: TimeInput.NewTotalSeconds):
        ctw = self.query_one(CountdownTimerWidget)
        ctw.ct.initial_seconds = msg.total_seconds
        await ctw.reset()
        self.exit_edit_time()

    def on_click(self):
        self.focus()

    # ==========================================================================
    # helpers
    # ==========================================================================
    def dump_state(self) -> CountdownTimerState:
        self.state = CountdownTimerState.from_countdown_timer_container(self)
        return self.state

    def enter_edit_time(self):
        ti = self._set_edit_time_classes(editing=True)
        ti.focus()

    def exit_edit_time(self):
        ti = self._set_edit_time_classes(editing=False)
        ti.value = ""

    def _set_edit_time_classes(self, *, editing: bool) -> TimeInput:
        self.query_one(CountdownTimerWidget).set_class(editing, "hidden")
        self.query_one(TotalTimeSpent).set_class(editing, "hidden")
        (ti := self.query_one(TimeInput)).set_class(not editing, "hidden")
        return ti

    def _set_active(self, *, active: bool) -> None:
        self.query_one("#start").set_class(active, "hidden")
        self.query_one("#reset").set_class(active, "hidden")
        self.query_one("#stop").set_class(not active, "hidden")
        self.set_class(active, "active")
