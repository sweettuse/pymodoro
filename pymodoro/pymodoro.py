from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial

from typing import Any, Optional
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive, var
from textual.message import Message, MessageTarget
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.containers import Horizontal
from textual.binding import Binding
from pymodoro.widgets.global_timer import DebugLog
from sound import play_sound
from widgets.global_timer import GlobalTimerComponent, GlobalTimerWidget
from widgets.configuration import ConfigForm
from widgets.countdown_timer import CountdownTimerComponent, CountdownTimerWidget
from pymodoro_state import StateStore, CountdownTimerState


HiddenBinding = partial(Binding, show=False)


class Pymodoro(App):
    """main pymodoro application"""

    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("j", "focus_next_timer", "focus/move next", key_display="j/J"),
        Binding("k", "focus_prev_timer", "focus/move prev", key_display="k/K"),
        Binding("e", "edit_time", "edit total time", key_display="e"),
        Binding("space", "start_or_stop", "start or stop", key_display="space"),
        Binding("A", "add_new_timer", "add timer", key_display="A"),
        Binding("D", "delete_selected_timer", "del timer", key_display="D"),
        Binding("U", "undo_delete_timer", "undo del", key_display="U"),
        HiddenBinding("d", "dump_state", "dump state"),
        HiddenBinding("J", "move_down", "move widget down"),
        HiddenBinding("K", "move_up", "move widget up"),
        HiddenBinding("escape", "focus_container", "focus outer container"),
    ]

    _currently_moving = var(False)

    def _create_new_timer(self) -> CountdownTimerComponent:
        return CountdownTimerComponent.create()

    def compose(self) -> ComposeResult:
        self.has_active_timer = False
        self._deleted = []

        if states := StateStore.load_current():
            timers = map(CountdownTimerComponent.from_state, states)
        else:
            timers = (self._create_new_timer() for _ in range(4))

        yield GlobalTimerComponent()
        yield ConfigForm(classes="hidden")
        yield Container(*timers, id="timers")
        yield Footer()

    # ==========================================================================
    # actions
    # ==========================================================================
    def action_dump_state(self):
        timers = [ctc.dump_state() for ctc in self.query(CountdownTimerComponent)]
        timers.extend(self._deleted)
        StateStore.dump(timers)

    def action_focus_next_timer(self):
        """set focus to next timer"""
        self._focus_ctc(1)

    def action_focus_prev_timer(self):
        """set focus to previous timer"""
        self._focus_ctc(-1)

    async def action_move_down(self):
        """move timer down one"""
        await self._move_timer(offset=1)

    async def action_move_up(self):
        """move timer up one"""
        await self._move_timer(offset=-1)

    def action_focus_container(self):
        """on hitting escape, focus the current container"""
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
        if ctc.is_active:
            button_id = "#stop"
        else:
            if self.has_active_timer:
                # can't have 2 timers running concurrently
                return
            button_id = "#start"
        ctc.query_one(button_id, Button).press()

    async def action_quit(self):
        """called by framework"""
        for ctc in self.query(CountdownTimerComponent).filter(".active"):
            await ctc.stop()
        self.action_dump_state()
        self.exit()

    async def action_add_new_timer(self):
        kw = {}
        if focused := self._find_focused_or_focused_within():
            idx, ctcs = focused
            if idx is not None:
                kw = dict(after=ctcs[idx])
        await self._add_timer(self._create_new_timer(), **kw)

    async def action_undo_delete_timer(self):
        if not self._deleted:
            return

        state = self._deleted.pop()
        await self._add_timer(CountdownTimerComponent.from_state(state))

    def action_delete_selected_timer(self):
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        if idx is None:
            return

        ctc = ctcs[idx]

        num_ctcs = len(ctcs)
        if num_ctcs == 1:
            to_focus = None
        elif idx == num_ctcs - 1:
            to_focus = ctcs[idx - 1]
        else:
            to_focus = ctcs[idx + 1]

        state = ctc.dump_state()
        state.status = "deleted"
        self._deleted.append(state)
        ctc.remove()
        if to_focus:
            to_focus.focus()

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
        self._debug(event)
        await self._update_global_timer(event)

    async def on_countdown_timer_widget_stopped(self, event):
        self.has_active_timer = False
        self._debug(event)
        await self._update_global_timer(event)

    async def on_countdown_timer_widget_new_second(
        self,
        event: CountdownTimerWidget.NewSecond,
    ):
        await self._update_global_timer(event)

    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        self._debug(event)
        await self._update_global_timer(event)
        play_sound.play()

    async def _update_global_timer(self, event):
        """forward message on to global timer"""
        event.stop()
        await self.query_one(GlobalTimerWidget).post_message(event)

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
            if ctc.focused_or_within:
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

        new_idx = min(len(ctcs) - 1, max(0, (idx + offset)))
        ctc = ctcs[new_idx]
        ctc.focus()
        return ctc

    async def _move_timer(self, offset: int):
        """move timer container up or down in the list"""
        if self._currently_moving:
            return

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
        if ctc.is_active:
            ctc.query_one("#stop", Button).press()
        new_ctc = CountdownTimerComponent.from_state(state)
        kw = {"before" if offset == -1 else "after": ctcs[new_idx]}
        self._currently_moving = True
        ctc.remove()
        await self._add_timer(new_ctc, **kw)

    async def _add_timer(self, timer: CountdownTimerComponent, **kw):
        await self.query_one("#timers").mount(timer, **kw)
        timer.focus()
        timer.scroll_visible()
        self.call_after_refresh(lambda: setattr(self, "_currently_moving", False))
        return timer

    def _debug(self, msg: Any):
        now = datetime.now().replace(microsecond=0)
        self.query_one(DebugLog).write(f"{now} - {msg}")


if __name__ == "__main__":
    Pymodoro().run()
