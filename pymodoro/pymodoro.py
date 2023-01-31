from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from functools import cache, partial
from itertools import chain
from operator import attrgetter

from typing import Any, Literal
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
from textual.css.query import DOMQuery
from textual._node_list import DuplicateIds
from utils import exec_on_repeat
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
from widgets.countdown_timer.time_spent import TimeSpentContainer, TimeSpentTotal
from pymodoro_state import StateStore, CountdownTimerState


HiddenBinding = partial(Binding, show=False)


class Pymodoro(App):
    """main pymodoro application"""

    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("j", "focus_next_timer", "focus/move prev/next", key_display="j/J/k/K"),
        HiddenBinding("k", "focus_prev_timer", "focus/move prev"),
        HiddenBinding("J", "move_down", "move widget down"),
        HiddenBinding("K", "move_up", "move widget up"),
        Binding("e", "edit_time", "edit remaining", key_display="e"),
        Binding("space", "start_or_stop", "start or stop", key_display="space"),
        Binding("o", "add_new_timer_after", "new timer", key_display="o/O"),
        HiddenBinding("O", "add_new_timer_before", "new timer"),
        Binding("d", "delete_selected_timer_dd", "del timer", key_display="dd"),
        Binding("U", "undo_delete_timer", "undo del", key_display="U"),
        Binding("/", "focus_search", "search", key_display="/"),
        Binding("r", "reset", "reset", key_display="r"),
        HiddenBinding("escape", "focus_container", "focus outer container"),
        HiddenBinding("g", "focus_top_ctc", "focus top timer"),
        HiddenBinding("G", "focus_bottom_ctc", "focus bottom"),
        HiddenBinding("p", "add_deleted_after", "add recently deleted timer after"),
        HiddenBinding("P", "add_deleted_before", "add recently deleted timer before"),
        Binding("m", "add_manually_accounted_time", "add time", key_display="m"),
    ]

    # global id of the type of time window we should display for spent time
    current_time_window_id: str = reactive(TimeSpentTotal.window_id)

    def _create_new_timer(self) -> CountdownTimerComponent:
        return CountdownTimerComponent.create()

    def compose(self) -> ComposeResult:
        self.has_active_timer = False
        self._deleted = []
        self._last_deleted = None

        if states := StateStore.load_current():
            timers = map(CountdownTimerComponent.from_state, states)
        else:
            timers = (self._create_new_timer() for _ in range(4))

        yield GlobalTimerComponent()
        yield ConfigForm(classes="hidden")
        yield Container(*timers, id="timers")
        yield Footer()
        self.call_after_refresh(
            setattr, self, "current_time_window_id", TimeSpentTotal.window_id
        )

    @property
    @cache
    def _prev_deleted_timers(self):
        """get timers that were previously deleted"""
        return StateStore.load_deleted()

    @property
    def _ctc_query(self) -> DOMQuery[CountdownTimerComponent]:
        return self.query(CountdownTimerComponent)

    @property
    def _visible_ctc_query(self) -> DOMQuery[CountdownTimerComponent]:
        return self._ctc_query.exclude(".hidden")

    @property
    def _focused_ctc(self) -> CountdownTimerComponent | None:
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        if idx is not None:
            return ctcs[idx]

    def watch_current_time_window_id(self, window_id):
        """change displayed time based on `window_id`"""
        self._debug(f"{window_id=}")
        if not window_id:
            return

        for tsc in self.query(TimeSpentContainer):
            tsc.set_displayed_time(window_id)

    # ==========================================================================
    # actions
    # ==========================================================================

    def action_dump_state(self):
        """dump state out to state store"""
        active_states = [
            ctc.dump_state() for ctc in self.query(CountdownTimerComponent)
        ]
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
            ctc.exit_manually_accounting_for_time()

    def action_edit_time(self):
        """change to edit remaining time"""
        if not (ctc := self._focused_ctc):
            return

        ctc.enter_edit_time()

    def action_add_manually_accounted_time(self):
        if not (ctc := self._focused_ctc):
            return

        ctc.enter_manually_accounting_for_time()

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
        for ctc in self._ctc_query.filter(".active"):
            await ctc.stop()

        # wait for stop message to propagate
        for _ in range(100):
            await asyncio.sleep(0.01)
            if not self._ctc_query.filter(".active"):
                break

        self.action_dump_state()
        self.exit()

    async def action_add_new_timer_before(self):
        """add a new timer before the current focused one"""
        await self._action_add_new_timer("before")

    async def action_add_new_timer_after(self):
        """add a new timer after the current focused one"""
        await self._action_add_new_timer("after")

    async def _action_add_new_timer(
        self,
        before_or_after: Literal["before", "after"],
        timer: CountdownTimerComponent | None = None,
    ):
        kw = {}
        if _focused_ctc := self._focused_ctc:
            kw = {before_or_after: _focused_ctc}
        timer = timer or self._create_new_timer()
        await self._add_timer(timer, **kw)

    async def action_undo_delete_timer(self):
        """resurrect in-memory 'deleted' timer"""
        if not self._deleted:
            return

        state = self._deleted.pop()

        kw = {}
        if _focused_ctc := self._focused_ctc:
            kw = dict(before=_focused_ctc)
        await self._add_timer(CountdownTimerComponent.from_state(state), **kw)

    def action_focus_search(self):
        """set focus to search box and clear the current value"""
        sb = self.query_one(SearchBox)
        sb.value = ""
        sb.focus()

    async def action_delete_selected_timer(self):
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

        await ctc.stop()
        state = ctc.dump_state()
        state.status = "deleted"
        self._deleted.append(state)
        self._last_deleted = state
        ctc.remove()
        if to_focus:
            to_focus.focus()

    action_delete_selected_timer_dd = exec_on_repeat(action_delete_selected_timer)

    async def action_reset(self):
        """reset time on focused timer"""
        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        ctc = ctcs[idx or 0]
        await ctc.stop()
        await ctc.reset()

    @exec_on_repeat
    def action_focus_top_ctc(self):
        self._focus_ctc_by_idx(0)

    def action_focus_bottom_ctc(self):
        self._focus_ctc_by_idx(-1)

    def _focus_ctc_by_idx(self, index: int):
        if not (ctcs := list(self._visible_ctc_query)):
            return

        ctcs[index].focus()

    async def action_add_deleted_after(self):
        await self._action_add_deleted_timer("after")

    async def action_add_deleted_before(self):
        await self._action_add_deleted_timer("before")

    async def _action_add_deleted_timer(
        self, before_or_after: Literal["before", "after"]
    ):
        if not self._last_deleted:
            return

        ld = self._last_deleted
        self._last_deleted = None
        await self._action_add_new_timer(
            before_or_after, CountdownTimerComponent.from_state(ld)
        )

    # ==========================================================================
    # event handlers
    # ==========================================================================

    def on_time_input_new_total_seconds(self):
        """the total time for a pomodoro has been updated"""
        self._focus_ctc(0)

    async def on_countdown_timer_widget_started(
        self, event: CountdownTimerWidget.Started
    ):
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
        self.query_one(GlobalTimerComponent).query_one(TimeSpentContainer).spent_in_current_period = event.elapsed

    async def on_countdown_timer_widget_completed(
        self, event: CountdownTimerWidget.Completed
    ):
        """let the global timer know the timer has completed and play a sound"""
        self._debug(event)
        await self._update_global_timer(event)
        play_sound.play()

    async def on_search_box_search(self, event: SearchBox.Search):
        """filter results whenever the value of the search box changes"""
        self._debug(event.search_str)
        await self._filter_based_on_search(event.search_str)

    async def on_text_input_value_after_blur(self, event: TextInput.ValueAfterBlur):
        """check to see if description or linear issue matches either an existing
        or previously deleted countdown timer component.

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
    ) -> None | tuple[int | None, list[CountdownTimerComponent]]:
        """find which CountdownTimerComponent has a widget with focus-within
        or itself has focus

        if exists, return its idx and a list of all CountdownTimerComponents
        else, return None
        """
        if not (ctcs := list(self._visible_ctc_query)):
            return None

        for i, ctc in enumerate(ctcs):
            if ctc.focused_or_within:
                break
        else:
            i = None

        return i, ctcs

    def _focus_ctc(self, offset: int) -> None | CountdownTimerComponent:
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
        if offset not in {1, -1}:
            return

        if not (focused := self._find_focused_or_focused_within()):
            return

        idx, ctcs = focused
        if idx is None:
            return

        new_idx = idx + offset
        if not (0 <= new_idx < len(ctcs)):
            return

        kw = {"before" if offset == -1 else "after": ctcs[new_idx]}
        ctc = ctcs[idx]
        self.query_one("#timers").move_child(ctc, **kw)
        self.call_after_refresh(ctc.scroll_visible)

    async def _add_timer(self, timer: CountdownTimerComponent, **kw):
        """add a timer to existing timers"""
        await self.query_one("#timers").mount(timer, **kw)
        timer.focus()
        timer.scroll_visible()
        return timer

    def _debug(self, msg: Any):
        """log to the DebugLog object

        needs to be enabled in `pymodoro.css` - comment out `display: none`
        """
        now = datetime.now().replace(microsecond=0).time()
        with suppress(Exception):
            self.query_one(DebugLog).write(f"{now} - {msg}")

    async def _filter_based_on_search(self, search_str: str):
        """hide classes that don't match the filter"""
        for ctc in self.query(CountdownTimerComponent):
            ctc.set_class(not ctc.matches_search(search_str), "hidden")

    async def _find_matching_timer(
        self, event: TextInput.ValueAfterBlur
    ) -> None | CountdownTimerState:
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

        async def _find_matching() -> None | CountdownTimerState:
            if isinstance(event.sender, LinearInput):
                getter = attrgetter("linear_state")
            elif isinstance(event.sender, DescriptionInput):
                getter = attrgetter("description_state")
            else:
                return

            # check current timers
            for ctc in self.query(CountdownTimerComponent):
                if ctc is event_ctc:
                    continue
                if _match(getter(ctc.state)["value"]):
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
