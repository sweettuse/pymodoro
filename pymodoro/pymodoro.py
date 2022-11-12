import pickle
import shelve
from contextlib import suppress
from typing import Any
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


class CountdownTimerContainer(Static, can_focus=True):
    BINDINGS = [
        Binding("d", "dump_state", "dump state"),
    ]

    def compose(self) -> ComposeResult:
        yield Horizontal(
            TextInput(id="linear", placeholder="linear issue id..."),
            TextInput(id="description", placeholder="description"),
            Button("start", id="start", variant="success"),
            CountdownTimerWidget(countdown_timer=CountdownTimer(60)),
            Button("stop", id="stop", variant="error"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button_id = event.button.id
        ct = self.query_one(CountdownTimerWidget)
        if button_id == "start":
            ct.start()
            self.add_class("started")
        elif button_id == "stop":
            self.remove_class("started")
            ct.stop()

    def action_dump_state(self) -> dict[str, Any]:
        self.log("dump state currently does nothing")
        pass
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

    def compose(self) -> ComposeResult:
        yield Container(
            CountdownTimerContainer(),
            CountdownTimerContainer(),
            id="timers",
        )


if __name__ == "__main__":
    Pymodoro().run()
