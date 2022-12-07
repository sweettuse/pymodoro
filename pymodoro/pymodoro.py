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
from widgets.global_timer import GlobalTimerComponent, GlobalTimerWidget
from widgets.configuration import ConfigForm
from widgets.countdown_timer import CountdownTimerComponent, CountdownTimerWidget
from pymodoro_state import StateStore

from uuid import uuid4


HiddenBinding = partial(Binding, show=False)


class Pymodoro(App):
    """main pymodoro application"""
    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("j", "focus_next", "focus/move next", key_display="j/J"),
        Binding("k", "focus_prev", "focus/move prev", key_display="k/K"),
        Binding("e", "edit_time", "edit total time", key_display="e"),
        Binding("space", "start_or_stop", "start or stop", key_display="space"),
        HiddenBinding("d", "dump_state", "dump state"),
        HiddenBinding("J", "move_down", "move widget down"),
        HiddenBinding("K", "move_up", "move widget up"),
        HiddenBinding("escape", "focus_container", "focus outer container"),
    ]

    def compose(self) -> ComposeResult:
        self.has_active_timer = False
        if stored_timers := StateStore.load():
            timers = map(CountdownTimerComponent.from_state, stored_timers)
        else:
            timers = (
                CountdownTimerComponent(id=f"countdown_timer_container_{uuid4()}"),
                CountdownTimerComponent(id=f"countdown_timer_container_{uuid4()}"),
                CountdownTimerComponent(id=f"countdown_timer_container_{uuid4()}"),
                CountdownTimerComponent(id=f"countdown_timer_container_{uuid4()}"),
            )
        yield Header()
        yield GlobalTimerComponent()
        yield ConfigForm(classes="hidden")
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
        timers = [ctc.dump_state() for ctc in self.query(CountdownTimerComponent)]
        StateStore.dump(timers)
        print("============")

    def action_focus_next(self):
        """set focus to next timer"""
        self._focus_ctc(1)

    def action_focus_prev(self):
        """set focus to previous timer"""
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
            if self.has_active_timer:
                # can't have 2 timers running concurrently
                return
            button_id = "#start"
        ctc.query_one(button_id, Button).press()

    def action_quit(self):
        self.action_dump_state()
        self.exit()

    def action_move_down(self):
        """move timer down one"""
        self._move_timer(offset=1)

    def action_move_up(self):
        """move timer up one"""
        self._move_timer(offset=-1)

    # ==========================================================================
    # event handlers
    # ==========================================================================

    def on_time_input_new_total_seconds(self):
        """the total time for a pomodoro has been updated"""
        self._focus_ctc(0)

    async def on_countdown_timer_widget_started(
        self, event: CountdownTimerWidget.Started
    ):
        self.has_active_timer = True
        await self.query_one(GlobalTimerWidget).post_message(event)

    async def on_countdown_timer_widget_stopped(self, event):
        self.has_active_timer = False
        await self.query_one(GlobalTimerWidget).post_message(event)

    async def on_countdown_timer_widget_new_second(
        self, event: CountdownTimerWidget.NewSecond,
    ):
        await self.query_one(GlobalTimerWidget).post_message(event)
        
    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        await self.query_one(GlobalTimerWidget).post_message(event)
        self.bell()

    # ==========================================================================
    # helpers
    # ==========================================================================


    def _find_focused_or_focused_within(
        self,
    ) -> Optional[tuple[Optional[int], list[CountdownTimerComponent]]]:
        """find which CountdownTimerComponent has a widget with focus-within
        or itself has focus

        if exists, return its idx and a list of all CountdownTimerComponents
        else, return None
        """
        if not (ctcs := list(self.query(CountdownTimerComponent))):
            return

        for i, ctc in enumerate(ctcs):
            if ctc.has_focus or ctc.has_pseudo_class("focus-within"):
                break
        else:
            i = None

        return i, ctcs

    def _focus_ctc(self, offset: int) -> Optional[CountdownTimerComponent]:
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

        ctc = ctcs[idx]
        state = ctc.dump_state()
        new_ctc = CountdownTimerComponent.from_state(state)
        kw = {"before" if offset == -1 else "after": ctcs[new_idx]}
        ctc.remove()
        self.query_one("#timers").mount(new_ctc, **kw)
        new_ctc.focus()


if __name__ == "__main__":
    Pymodoro().run()
