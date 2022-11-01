from contextlib import suppress
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static

from widgets.text_input import TextInput
from widgets.timer import CountdownTimer, timer_container


class CountdownTimerWidget(Static, can_focus=True):
    def compose(self) -> ComposeResult:
        yield TextInput()
        yield Button('start', id='start', variant='success')
        yield CountdownTimer(60)
        yield Button('stop', id='stop', variant='error')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button_id = event.button.id
        ct = self.query_one(CountdownTimer)
        if button_id == "start":
            ct.start()
            self.add_class("started")
        elif button_id == "stop":
            ct.stop()
            self.remove_class("started")

class Pymodoro(App):
    CSS_PATH = "css/pymodoro.css"


    def compose(self) -> ComposeResult:
        yield Container(CountdownTimerWidget(), CountdownTimerWidget())

    


if __name__ == '__main__':
    Pymodoro().run()