from __future__ import annotations

import asyncio
from functools import partial

from typing import Any, Optional
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.console import RenderableType
from rich.style import Style
from rich.panel import Panel
from rich.align import Align
from rich.segment import Segment
from textual.reactive import reactive, var, Reactive
from textual.timer import Timer
from textual.message import Message, MessageTarget
from textual.widgets import Button, Header, Footer, Static, TextLog, Input, Placeholder
from textual.containers import Horizontal
from textual.binding import Binding
from widgets.countdown_timer.time_spent import TimeSpentContainer
from widgets.text_input_orig import TextInputOrig
from utils import format_time
from widgets.countdown_timer.widget import CountdownTimerWidget

# from widgets.configuration import ConfigForm
# from widgets.countdown_timer import CountdownTimerComponent, CountdownTimerWidget
from pymodoro_state import StateStore
from text_to_image import Font, Face
from text_to_image.api import FONT_PATH


class Spacer(Static):
    ...


INACTIVE_COLOR_STR = "grey37"
ACTIVE_COLOR_STR = "yellow"
COMPLETED_COLOR_STR = "light_cyan3"


class GlobalTimerWidget(Static):
    """display of currently selected/running timer"""

    color_str = reactive(INACTIVE_COLOR_STR)
    remaining = reactive(0.0)
    last_seen = reactive(-1)
    color_str_override = reactive("")

    font = var(Font(Face.menlo, 14))
    cur_timer: Optional[Timer] = var(None)

    @property
    def _remaining_str(self) -> str:
        return format_time(int(self.remaining)).strip()

    @property
    def color(self):
        return Color.parse(self.color_str_override or self.color_str)

    def watch_remaining(self, remaining):
        if int(self.remaining) == self.last_seen:
            return

        self._update()

    def watch_color_str(self, color_str):
        self._update()

    def watch_color_str_override(self, color_str):
        self._update()

    def _update(self):
        self.last_seen = int(self.remaining)
        rich_str = self.font.to_rich(self._remaining_str, color=self.color)
        self.update(rich_str)
    
    def on_click(self):
        self.app.focus_scroll_active()

    # ==========================================================================
    # event handlers
    # ==========================================================================

    def on_countdown_timer_widget_started(
        self,
        event: CountdownTimerWidget.Started,
    ):
        event.stop()
        self.color_str = ACTIVE_COLOR_STR
        self.remaining = event.remaining
        self._clear_color_override()

    def on_countdown_timer_widget_new_second(
        self,
        event: CountdownTimerWidget.NewSecond,
    ):
        event.stop()
        self.remaining = event.remaining

    def on_countdown_timer_widget_stopped(
        self,
        event: CountdownTimerWidget.Stopped,
    ):
        event.stop()
        self.color_str = INACTIVE_COLOR_STR
        self.remaining = event.remaining

    def on_countdown_timer_widget_completed(
        self,
        event: CountdownTimerWidget.Completed,
    ):
        event.stop()
        self._override_color_temporarily(COMPLETED_COLOR_STR)

    def _override_color_temporarily(self, color_str, num_secs=6):
        """temporarily change the color of the global timer"""
        self.color_str_override = color_str
        self.cur_timer = self.set_timer(num_secs, self._clear_color_override)

    def _clear_color_override(self):
        """clear the overridden color"""
        self.color_str_override = ""
        if not self.cur_timer:
            return

        self.cur_timer.stop_no_wait()
        self.cur_timer = None


class DebugLog(TextLog):
    """text log to which you can log useful debug info"""


DL = DebugLog(classes="debug")


class SearchBox(Input):
    """search/filter timers here"""

    class Search(Message):
        def __init__(self, sender: MessageTarget, search_str: str) -> None:
            super().__init__(sender)
            self.search_str = search_str

    async def watch_value(self, value):
        await self.emit(self.Search(self, value))


class SearchAndTimeSpent(Static):
    def compose(self) -> ComposeResult:
        yield TimeSpentContainer.create("")
        yield SearchBox(placeholder="search")


class GlobalTimerComponent(Static):
    """top component"""

    def compose(self) -> ComposeResult:
        yield GlobalTimerWidget()
        yield DL
        yield SearchAndTimeSpent()


class GlobalTimerApp(App):
    """for debugging purposes"""

    CSS_PATH = "../css/pymodoro.css"

    def compose(self) -> ComposeResult:
        yield GlobalTimerComponent()
