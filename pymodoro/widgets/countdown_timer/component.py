from __future__ import annotations

import asyncio
from enum import Enum
from functools import partial

from typing import Any, Optional
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.message import Message, MessageTarget
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.containers import Horizontal
from textual.binding import Binding
from pymodoro_state import CountdownTimerState, StateStore
from widgets.text_input import LinearInput, TextInput, TimeInput

from widgets.countdown_timer import CountdownTimer, CountdownTimerWidget


class CountdownTimerComponent(Static, can_focus=True):
    @classmethod
    def from_state(cls, state: CountdownTimerState) -> CountdownTimerComponent:
        res = cls(id=state.id)
        res.state = state
        return res

    @property
    def is_active(self) -> bool:
        return self.has_class("active")

    @property
    def _can_start_or_stop(self) -> bool:
        return not self.app.has_active_timer or self.is_active

    def compose(self) -> ComposeResult:
        if state := getattr(self, "state", None):
            yield from self._compose_from_state(state)
        else:
            yield from self._compose_new()

    def _compose_new(self):
        self.state = CountdownTimerState(self.id)
        yield Horizontal(
            LinearInput(id="linear", placeholder="linear issue id"),
            TextInput(id="description", placeholder="description"),
            Button("start", id="start", variant="success"),
            Button("stop", id="stop", variant="error", classes="hidden"),
            CountdownTimerWidget(CountdownTimer(25 * 60)),
            TimeInput(id="time_input", classes="hidden"),
            Button("reset", id="reset", variant="default"),
        )

    def _compose_from_state(self, state: CountdownTimerState):
        yield Horizontal(
            LinearInput.from_state(state.linear_state),
            TextInput.from_state(state.description_state),
            Button("start", id="start", variant="success"),
            Button("stop", id="stop", variant="error", classes="hidden"),
            CountdownTimerWidget(
                CountdownTimer.from_state(state.countdown_timer_state)
            ),
            TimeInput.from_state(state.time_input_state),
            Button("reset", id="reset", variant="default"),
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        # if app has active timer and this one isn't it
        self.focus()
        if not self._can_start_or_stop and button_id in {"start", "stop"}:
            return

        ctw = self.query_one(CountdownTimerWidget)
        if button_id == "start":
            await ctw.start()
        elif button_id == "stop":
            await ctw.stop()
        elif button_id == "reset":
            await ctw.reset()

    # ==========================================================================
    # actions
    # ==========================================================================
    async def action_quit(self):
        ctw = self.query_one(CountdownTimerWidget)
        await ctw.stop()

    # ==========================================================================
    # event handlers
    # ==========================================================================
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
        self._set_active(active=False)

    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        self.log(f"{event.sender} timer completed")
        self.state.num_pomodoros_completed += 1
        self._set_active(active=False)

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
        self.query_one(CountdownTimerWidget).add_class("hidden")
        (ti := self.query_one(TimeInput)).remove_class("hidden")
        ti.focus()

    def exit_edit_time(self):
        self.query_one(CountdownTimerWidget).remove_class("hidden")
        (ti := self.query_one(TimeInput)).add_class("hidden")
        ti.value = ""

    def _set_active(self, *, active: bool):
        self.query_one("#start").set_class(active, "hidden")
        self.query_one("#reset").set_class(active, "hidden")
        self.query_one("#stop").set_class(not active, "hidden")
        self.set_class(active, "active")
