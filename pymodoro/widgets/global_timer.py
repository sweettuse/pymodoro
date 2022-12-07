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
from widgets.countdown_timer.widget import CountdownTimerWidget

# from widgets.configuration import ConfigForm
# from widgets.countdown_timer import CountdownTimerComponent, CountdownTimerWidget
from pymodoro_state import StateStore
from text_to_image import Font, Face
from text_to_image.api import FONT_PATH
from rich.panel import Panel


class Spacer(Static):
    ...


class GlobalTimerApp(App):
    CSS_PATH = "../css/pymodoro.css"

    def compose(self) -> ComposeResult:
        yield GlobalTimerComponent()


inactive_color_str = 'grey37'
active_color_str = 'yellow'

class GlobalTimerWidget(Static):
    color_str = reactive(inactive_color_str)
    remaining = reactive(0.0)
    last_seen = reactive(-1)
    face = Face.menlo

    @property
    def _remaining_str(self) -> str:
        # cheat a bit to render at same time as individual timer
        rem = int(self.remaining)
        minutes, seconds = divmod(rem, 60)
        hours, minutes = divmod(minutes, 60)
        hours_str = ""
        if hours:
            hours_str = f"{hours:02,d}:"

        return f"{hours_str}{minutes:02d}:{seconds:02d}"
    
    @property
    def color(self):
        return Color.parse(self.color_str)

    def watch_remaining(self, remaining):
        rem = int(remaining)
        if rem == self.last_seen:
            return
        self.last_seen = rem
        rich_str = self.font.to_rich(self._remaining_str, color=self.color)
        self.update(rich_str)

    def watch_color_str(self, color_str):
        self.remaining = self.remaining

    # ==========================================================================
    # event handlers
    # ==========================================================================
    def on_mount(self, event: events.Mount) -> None:
        self.font = Font(self.face, 12)
        self.remaining = 0

    def on_countdown_timer_widget_started(
        self,
        event: CountdownTimerWidget.Started,
    ):
        self.color_str = active_color_str
        self.remaining = event.remaining
        event.stop()

    def on_countdown_timer_widget_new_second(
        self,
        event: CountdownTimerWidget.NewSecond,
    ):
        self.remaining = event.remaining
        event.stop()

    def on_countdown_timer_widget_stopped(
        self,
        event: CountdownTimerWidget.Stopped,
    ):
        self.color_str = inactive_color_str
        self.remaining = event.remaining
        event.stop()


class GlobalTimerComponent(Static):
    """display of currently selected/running timer"""

    def compose(self) -> ComposeResult:
        yield Spacer()
        yield GlobalTimerWidget(expand=True)
        yield Spacer()


if __name__ == "__main__":
    from rich import print

    print(FONT_PATH)
    # print(font.to_rich('sntahoeu'))
