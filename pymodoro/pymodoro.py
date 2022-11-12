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
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.containers import Horizontal
from textual.binding import Binding
from pymodoro.widgets.text_input import TextInput

from widgets.timer import CountdownTimer, CountdownTimerWidget
from uuid import uuid4

id_gen = count()


class CountdownTimerContainer(Static, can_focus=True):
    def compose(self) -> ComposeResult:
        yield Horizontal(
            TextInput(id="linear", placeholder="linear issue id"),
            TextInput(id="description", placeholder="description"),
            Button("start", id="start", variant="success"),
            CountdownTimerWidget(CountdownTimer(10)),
            Button("stop", id="stop", variant="error"),
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        ct = self.query_one(CountdownTimerWidget)
        if button_id == "start":
            if await ct.start():
                self.add_class("active")
        elif button_id == "stop":
            await ct.stop()

    async def on_countdown_timer_widget_stopped(
        self, event: CountdownTimerWidget.Stopped
    ):
        self.remove_class("active")

    def on_key(self, event: events.Key):
        if event.key == "escape":
            print("ESCAPE BITCHES")
            self.parent.focus()

    def action_dump_state(self):
        # TODO: implement
        self.log("dump state currently does nothing")
        for ctw in self.query(CountdownTimerWidget):
            self.log("================================")
            self.log("================================")
            self.log(ctw.id)
            self.log("================================")
            self.log("================================")
        # self.log("================================")
        # self.log("================================")
        # self.log("================================")
        # self.log("================================")
        # # states = [ti.dump_state() for ti in self.query(TextInput)]
        # # states.append(self.query_one(CountdownTimerWidget).dump_state())
        # # self.log(states)
        # self.log("================================")
        # self.log("================================")
        # self.log("================================")
        # self.log("================================")


class Pymodoro(App):
    CSS_PATH = "css/pymodoro.css"

    BINDINGS = [
        Binding("d", "dump_state", "dump state"),
        Binding("j", "move_next", "move to next pomodoro"),
        Binding("k", "move_prev", "move to next pomodoro"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            CountdownTimerContainer(id=f"countdown_timer_container_{next(id_gen)}"),
            id="timers",
        )

    def action_dump_state(self):
        print("============")
        print(list(self.query("#timers")))
        for ctc in self.query(CountdownTimerContainer):
            print(ctc)
        print("============")

    def _find_focused_within(
        self,
    ) -> Optional[tuple[int, list[CountdownTimerContainer]]]:
        """find which CountdownTimerContainer has a widget with focus-within

        if exists, return its idx and a list of all CountdownTimerContainers
        else, return None
        """
        if not (ctcs := list(self.query(CountdownTimerContainer))):
            return

        for i, ctc in enumerate(ctcs):
            if ctc.has_pseudo_class("focus-within"):
                break
        else:
            # start at the first one if none found
            i = 0

        return i, ctcs

    def _focus_ctc(self, offset: int) -> None:
        """set focus to ctc by offset"""
        if not (focused := self._find_focused_within()):
            return
        idx, ctcs = focused
        ctc = ctcs[(idx + offset) % len(ctcs)]
        ctc.focus()

    def action_move_next(self):
        # self.screen.focus_next()
        self._focus_ctc(1)

    def action_move_prev(self):
        # self.screen.focus_next()
        self._focus_ctc(-1)


if __name__ == "__main__":
    Pymodoro().run()
