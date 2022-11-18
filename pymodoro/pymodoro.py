from __future__ import annotations
import asyncio
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
from pymodoro.pymodoro_state import CountdownTimerState, StateStore
from pymodoro.widgets.text_input import LinearInput, TextInput, TimeInput

from widgets.countdown_timer import CountdownTimer, CountdownTimerWidget
from uuid import uuid4


class CountdownTimerContainer(Static, can_focus=True):
    @classmethod
    def from_state(cls, state: CountdownTimerState) -> CountdownTimerContainer:
        res = cls(id=state.id)
        res.state = state
        return res

    def compose(self) -> ComposeResult:
        if state := getattr(self, "state", None):
            yield from self.compose_from_state(state)
            return

        self.state = CountdownTimerState(self.id)
        yield Horizontal(
            TextInput(id="linear", placeholder="linear issue id"),
            TextInput(id="description", placeholder="description"),
            Button("start", id="start", variant="success"),
            Button("stop", id="stop", variant="error", classes="hidden"),
            CountdownTimerWidget(CountdownTimer(10)),
            TimeInput(id="time_input", classes="hidden"),
            Button("reset", id="reset", variant="default"),
        )

    def compose_from_state(self, state: CountdownTimerState):
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
        ctw = self.query_one(CountdownTimerWidget)
        if button_id == "start":
            await ctw.start()
        elif button_id == "stop":
            await ctw.stop()
        elif button_id == "reset":
            await ctw.reset()

    async def on_linear_input_new_title(self, event: LinearInput.NewTitle):
        desc = self.query_one("#description", TextInput)
        desc.value = event.title

    async def action_quit(self):
        ctw = self.query_one(CountdownTimerWidget)
        await ctw.stop()

    def _enter_active(self):
        self.query_one("#start").add_class("hidden")
        self.query_one("#reset").add_class("hidden")
        self.query_one("#stop").remove_class("hidden")
        self.add_class("active")

    def _exit_active(self):
        self.query_one("#start").remove_class("hidden")
        self.query_one("#reset").remove_class("hidden")
        self.query_one("#stop").add_class("hidden")
        self.remove_class("active")

    async def on_countdown_timer_widget_stopped(
        self, event: CountdownTimerWidget.Stopped
    ):
        self.log(f"{event.sender} timer stopped")
        self.state.total_seconds_completed += event.elapsed
        self._exit_active()

    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        self.log(f"{event.sender} timer completed")
        self.state.num_pomodoros_completed += 1
        self._exit_active()

    async def on_countdown_timer_widget_started(
        self, event: CountdownTimerWidget.Started
    ):
        self._enter_active()

    def dump_state(self):
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

    async def on_time_input_new_total_seconds(self, msg: TimeInput.NewTotalSeconds):
        ctw = self.query_one(CountdownTimerWidget)
        ctw.ct.initial_seconds = msg.total_seconds
        await ctw._update()
        self.exit_edit_time()


HiddenBinding = partial(Binding, show=False)


class Pymodoro(App):
    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("j", "move_next", "focus/move next", key_display="j/J"),
        Binding("k", "move_prev", "focus/move prev", key_display="k/K"),
        Binding("e", "edit_time", "edit total time", key_display="e"),
        Binding("space", "start_or_stop", "start or stop", key_display="space"),
        HiddenBinding("d", "dump_state", "dump state"),
        HiddenBinding("J", "move_down", "move widget down", key_display="J"),
        HiddenBinding("K", "move_up", "move widget up", key_display="K"),
        HiddenBinding("escape", "focus_container", "focus outer container"),
    ]

    def compose(self) -> ComposeResult:
        if stored_timers := StateStore.load():
            timers = map(CountdownTimerContainer.from_state, stored_timers)
        else:
            timers = (
                CountdownTimerContainer(id=f"countdown_timer_container_{uuid4()}"),
                CountdownTimerContainer(id=f"countdown_timer_container_{uuid4()}"),
                CountdownTimerContainer(id=f"countdown_timer_container_{uuid4()}"),
                CountdownTimerContainer(id=f"countdown_timer_container_{uuid4()}"),
            )
        yield Container(*timers, id="timers")
        yield Footer()

    # ==========================================================================
    # actions
    # ==========================================================================
    def action_dump_state(self):
        print("============")
        timers = self.query_one("#timers")
        for c in timers.children:
            print(c)

        # print(list(self.query("#timers")))
        timers = [ctc.dump_state() for ctc in self.query(CountdownTimerContainer)]
        StateStore.dump(timers)
        print("============")

    def action_move_next(self):
        self._focus_ctc(1)

    def action_move_prev(self):
        self._focus_ctc(-1)

    def action_focus_container(self):
        if ctc := self._focus_ctc(0):
            ctc.exit_edit_time()

    def action_edit_time(self):
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        ctc = ctcs[idx or 0]
        ctc.enter_edit_time()

    def action_start_or_stop(self):
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        ctc = ctcs[idx or 0]
        if ctc.has_class("active"):
            button_id = "#stop"
        else:
            if self.has_class("timer_active"):
                # can't start 2 timers simultaneously
                return
            button_id = "#start"
        ctc.query_one(button_id, Button).press()

    def action_quit(self):
        self.action_dump_state()
        self.exit()

    def action_move_down(self):
        self._move_timer(offset=1)

    def action_move_up(self):
        self._move_timer(offset=-1)

    # ==========================================================================
    # events
    # ==========================================================================

    def on_time_input_new_total_seconds(self):
        self._focus_ctc(0)

    async def on_countdown_timer_widget_started(self):
        self.add_class("timer_active")

    async def on_countdown_timer_widget_stopped(self):
        self.remove_class("timer_active")

    # ==========================================================================
    # helpers
    # ==========================================================================

    def _find_focused_or_focused_within(
        self,
    ) -> Optional[tuple[Optional[int], list[CountdownTimerContainer]]]:
        """find which CountdownTimerContainer has a widget with focus-within
        or itself has focus

        if exists, return its idx and a list of all CountdownTimerContainers
        else, return None
        """
        if not (ctcs := list(self.query(CountdownTimerContainer))):
            return

        for i, ctc in enumerate(ctcs):
            if ctc.has_focus or ctc.has_pseudo_class("focus-within"):
                break
        else:
            i = None

        return i, ctcs

    def _focus_ctc(self, offset: int) -> Optional[CountdownTimerContainer]:
        """set focus to ctc by offset from current focus"""
        if not (focused := self._find_focused_or_focused_within()):
            return
        idx, ctcs = focused

        if idx is None:
            # no focus, so focus on first one
            ctcs[0].focus()
            return

        ctc = ctcs[(idx + offset) % len(ctcs)]
        ctc.focus()
        return ctc

    def _move_timer(self, offset: int):
        """move timer container up or down in the list"""
        if offset not in {1, -1}:
            return

        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        if idx is None:
            return

        new_idx = idx + offset
        if not (0 <= new_idx <= len(ctcs) - 1):
            return

        timers = self.query_one("#timers")
        ctc = ctcs[idx]
        state = ctc.dump_state()
        kw = {"before" if offset == -1 else "after": ctcs[new_idx]}
        new_ctc = CountdownTimerContainer.from_state(state)
        ctc.remove()
        timers.mount(new_ctc, **kw)
        new_ctc.focus()


if __name__ == "__main__":
    Pymodoro().run()
