from __future__ import annotations

import asyncio
from datetime import datetime
from functools import cache, partial
from itertools import chain
from operator import attrgetter

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
from textual._node_list import DuplicateIds
from widgets.text_input import LinearInput, TextInput, DescriptionInput
from sound import play_sound
from widgets.global_timer import (
    GlobalTimerComponent,
    GlobalTimerWidget,
    DebugLog,
    SearchBox,
)
from widgets.configuration import ConfigForm
from widgets.countdown_timer import CountdownTimerComponent, CountdownTimerWidget
from pymodoro_state import StateStore, CountdownTimerState


HiddenBinding = partial(Binding, show=False)


class Pymodoro(App):
    """main pymodoro application"""

    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("j", "focus_next_timer", "focus/move prev/next", key_display="j/J/k/K"),
        Binding("e", "edit_time", "edit remaining", key_display="e"),
        Binding("space", "start_or_stop", "start or stop", key_display="space"),
        Binding("A", "add_new_timer", "add timer", key_display="A"),
        Binding("D", "delete_selected_timer", "del timer", key_display="D"),
        Binding("U", "undo_delete_timer", "undo del", key_display="U"),
        Binding("/", "focus_search", "search", key_display="/"),
        Binding("r", "reset", "reset", key_display="r"),
        HiddenBinding("d", "dump_state", "dump state"),
        HiddenBinding("k", "focus_prev_timer", "focus/move prev"),
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

    @property
    @cache
    def _prev_deleted_timers(self):
        """get timers that were previously deleted"""
        return StateStore.load_deleted()

    # ==========================================================================
    # actions
    # ==========================================================================
    def action_dump_state(self):
        """dump state out to state store"""
        active_states = [ctc.dump_state() for ctc in self.query(CountdownTimerComponent)]
        # add active_states twice, first to ensure proper ordering, second to ensure proper data
        states = [
            active_states,
            StateStore.load_deleted() or [],
            self._deleted,
            active_states,
        ]
        by_id = {state.id: state for state in chain.from_iterable(states)}
        StateStore.dump(by_id.values())

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
        """focus the current container"""
        if ctc := self._focus_ctc(0):
            ctc.exit_edit_time()

    def action_edit_time(self):
        """change to edit remaining time"""
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        ctc = ctcs[idx or 0]
        ctc.enter_edit_time()

    async def action_start_or_stop(self):
        """start or stop a timer"""
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        ctc = ctcs[idx or 0]
        if ctc.is_active:
            fn_name = "stop"
        else:
            if self.has_active_timer:
                # can't have 2 timers running concurrently
                return
            fn_name = "start"
        await getattr(ctc, fn_name)()

    async def action_quit(self):
        """called by framework"""
        for ctc in self.query(CountdownTimerComponent).filter(".active"):
            await ctc.stop()
        self.action_dump_state()
        self.exit()

    async def action_add_new_timer(self):
        """add a new timer below the current focused one"""
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

    def action_focus_search(self):
        """set focus to search box and clear the current value"""
        sb = self.query_one(SearchBox)
        sb.value = ""
        sb.focus()

    def action_delete_selected_timer(self):
        """rm the currently focused timer if there is one"""
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

    async def action_reset(self):
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        ctc = ctcs[idx or 0]
        await ctc.stop()
        await ctc.reset()

    # ==========================================================================
    # event handlers
    # ==========================================================================

    def on_time_input_new_total_seconds(self):
        """the total time for a pomodoro has been updated"""
        self._focus_ctc(0)

    async def on_countdown_timer_widget_started(self, event: CountdownTimerWidget.Started):
        """start the global timer"""
        self.has_active_timer = True
        self._debug(event)
        await self._update_global_timer(event)

    async def on_countdown_timer_widget_stopped(self, event):
        """stop the global timer"""
        self.has_active_timer = False
        self._debug(event)
        await self._update_global_timer(event)

    async def on_countdown_timer_widget_new_second(
        self,
        event: CountdownTimerWidget.NewSecond,
    ):
        """tick the global timer"""
        await self._update_global_timer(event)

    async def on_countdown_timer_widget_completed(self, event: CountdownTimerWidget.Completed):
        """let the global timer know the timer has completed and play a sound"""
        self._debug(event)
        await self._update_global_timer(event)
        play_sound.play()

    async def on_search_box_search(self, event: SearchBox.Search):
        """filter results whenever the value of the search box changes"""
        self._debug(event.search_str)
        await self._filter_based_on_search(event.search_str)

    async def on_text_input_value_after_blur(self, event: TextInput.ValueAfterBlur):
        """check to see if description or linear issue matches a previously deleted
        countdown timer component.

        if it does, replace this one with the previously deleted one
        """
        self._debug(f"blur: {event.value}")
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        if idx is None:
            return

        if not (state := (await self._find_matching_timer(event))):
            return

        state.status = "in_progress"
        orig_ctc = CountdownTimerComponent.from_state(state)

        cur_ctc: CountdownTimerComponent = ctcs[idx]
        await cur_ctc.stop()
        try:
            await self._add_timer(orig_ctc, before=cur_ctc)
        except DuplicateIds:
            return

        cur_ctc.remove()
        orig_ctc.focus()

    # ==========================================================================
    # helpers
    # ==========================================================================

    async def _update_global_timer(self, event):
        """forward message on to global timer"""
        event.stop()
        await self.query_one(GlobalTimerWidget).post_message(event)

    def _find_focused_or_focused_within(
        self,
    ) -> Optional[tuple[Optional[int], list[CountdownTimerComponent]]]:
        """find which CountdownTimerComponent has a widget with focus-within
        or itself has focus

        if exists, return its idx and a list of all CountdownTimerComponents
        else, return None
        """
        if not (ctcs := list(self.query(CountdownTimerComponent).exclude(".hidden"))):
            return None

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
        await ctc.stop()
        new_ctc = CountdownTimerComponent.from_state(state)
        kw = {"before" if offset == -1 else "after": ctcs[new_idx]}
        self._currently_moving = True
        ctc.remove()
        await self._add_timer(new_ctc, **kw)

    async def _add_timer(self, timer: CountdownTimerComponent, **kw):
        """add a timer to existing timers"""
        await self.query_one("#timers").mount(timer, **kw)
        timer.focus()
        timer.scroll_visible()
        self.call_after_refresh(lambda: setattr(self, "_currently_moving", False))
        return timer

    def _debug(self, msg: Any):
        """log to the DebugLog object

        needs to be enabled in `pymodoro.css` - comment out `display: none`
        """
        now = datetime.now().replace(microsecond=0).time()
        self.query_one(DebugLog).write(f"{now} - {msg}")

    async def _filter_based_on_search(self, search_str: str):
        """hide classes that don't match the filter"""
        for ctc in self.query(CountdownTimerComponent):
            ctc.set_class(not ctc.matches_search(search_str), "hidden")

    async def _find_matching_timer(
        self, event: TextInput.ValueAfterBlur
    ) -> Optional[CountdownTimerState]:
        """find a matching timer based on the value in the recently blurred field

        return its state if found
        otherwise, return None
        """
        if not event.value:
            return None

        event_value_lower = event.value.lower()
        event_ctc = event.ctc

        def _match(value) -> bool:
            """whether value case insensitive equals the new event.value"""
            if not value:
                return False
            return value.lower() == event_value_lower

        async def _find_matching() -> Optional[CountdownTimerState]:
            if isinstance(event.sender, LinearInput):
                getter = attrgetter("linear_state")
            elif isinstance(event.sender, DescriptionInput):
                getter = attrgetter("description_state")
            else:
                return None

            # check current timers
            for ctc in self.query(CountdownTimerComponent):
                if ctc is not event_ctc and _match(getter(ctc.state)["value"]):
                    await ctc.stop()
                    state = ctc.dump_state()
                    await ctc.remove()
                    return state

            # check in-memory deleted states
            for i, state in enumerate(self._deleted):
                if _match(getter(state)["value"]):
                    self._deleted.pop(i)
                    return state

            # check persisted states
            for state in self._prev_deleted_timers or []:
                if _match(getter(state)["value"]):
                    return state

        if not (state := (await _find_matching())):
            return None

        if state.id in (ctc.id for ctc in self.query(CountdownTimerComponent)):
            return None

        return state


if __name__ == "__main__":
    Pymodoro().run()
