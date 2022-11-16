from dataclasses import dataclass
from itertools import count
import pickle
import shelve
from contextlib import suppress
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
from pymodoro.widgets.text_input import TextInput

from widgets.timer import CountdownTimer, CountdownTimerWidget
from uuid import uuid4

id_gen = count()


class TimeInput(TextInput):
    """enter new time for countdown timer"""
    class NewTotalSeconds(Message):
        def __init__(self, sender: MessageTarget, new_total_seconds: float):
            super().__init__(sender)
            self.total_seconds = new_total_seconds

    async def action_submit(self):
        if new_seconds := self._to_seconds():
            await self.emit(self.NewTotalSeconds(self, new_seconds))

    def _to_seconds(self) -> Optional[float]:
        if self.value.endswith('m'):
            return 60 * int(self.value[:-1])

        fields = self.value.split(":")
        if len(fields) > 3:
            return None

        m = 1
        res = 0.0
        with suppress(Exception):
            for f in reversed(fields):
                res += m * float(f)
                m *= 60
            return res

@dataclass
class CountdownTimerState:
    id: Optional[str] = ''
    total_seconds_completed: float = 0.0
    num_pomodoros_completed: int = 0


    def calc_num_pomodoros(self, current_pomodoro_secs: float):
        return self.total_seconds_completed // current_pomodoro_secs

class CountdownTimerContainer(Static, can_focus=True):
    def compose(self) -> ComposeResult:
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

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        ctw = self.query_one(CountdownTimerWidget)
        if button_id == "start":
            if await ctw.start():
                self._enter_active()
        elif button_id == "stop":
            await ctw.stop()
            self._exit_active()
        elif button_id == "reset":
            await ctw.reset()

    def _enter_active(self):
        self.query_one("#start").add_class('hidden')
        self.query_one("#reset").add_class('hidden')
        self.query_one("#stop").remove_class('hidden')
        self.add_class('active')

    def _exit_active(self):
        self.query_one("#start").remove_class('hidden')
        self.query_one("#reset").remove_class('hidden')
        self.query_one("#stop").add_class('hidden')
        self.remove_class('active')


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


    def dump_state(self):
        ctw = self.query_one(CountdownTimerWidget)
        print("____________________")
        print(ctw)
        print(self.state)
        print("--------------------")

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


class Pymodoro(App):
    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("d", "dump_state", "dump state", show=False),
        Binding("escape", "focus_container", "focus outer container", show=False),
        Binding("j", "move_next", "move next", key_display="j"),
        Binding("k", "move_prev", "move prev", key_display="k"),
        Binding("e", "edit_time", "edit total time", key_display="e"),
        # Binding("J", "move_down", "move widget down", key_display="J"),
        Binding("space", "start_or_stop", "start or stop", key_display="space"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            id="timers",
        )
        yield Footer()

    def action_dump_state(self):
        print("============")
        timers = self.query_one('#timers')
        for c in timers.children:
            print(c)

        # print(list(self.query("#timers")))
        for ctc in self.query(CountdownTimerContainer):
            ctc.dump_state()
        print("============")

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
        """set focus to ctc by offset"""
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

    def action_move_next(self):
        self._focus_ctc(1)

    def action_move_prev(self):
        self._focus_ctc(-1)

    def action_focus_container(self):
        if ctc := self._focus_ctc(0):
            ctc.exit_edit_time()

    def on_time_input_new_total_seconds(self, _):
        self._focus_ctc(0)

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
        button_id = '#stop' if ctc.has_class('active') else '#start'
        ctc.query_one(button_id).press()
        
    # def action_move_down(self):
    #     if not (focused := self._find_focused_or_focused_within()):
    #         return
    #     idx, ctcs = focused
    #     idx = idx or 0
    #     if idx >= len(ctcs) - 1:
    #         return
            
    #     timers = self.query_one('#timers')
    #     _n = timers.children._nodes
    #     _n[idx], _n[idx + 1] = _n[idx + 1], _n[idx]


if __name__ == "__main__":
    Pymodoro().run()
