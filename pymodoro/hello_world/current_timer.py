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
# from widgets.configuration import ConfigForm
# from widgets.countdown_timer import CountdownTimerComponent, CountdownTimerWidget
from pymodoro_state import StateStore
from text_to_image import Font, Face
from text_to_image.api import FONT_PATH
from rich.panel import Panel


class CurTimerApp(App):
    CSS_PATH = "../css/pymodoro.css"
    def compose(self) -> ComposeResult:
        yield CurTimerComponent()

class CurTimeWidget(Static):
    @property
    def _remaining_str(self) -> str:
        minutes, seconds = divmod(self.remaining, 60)
        hours, minutes = divmod(minutes, 60)
        hours_str = ""
        if hours:
            hours_str = f"{hours:02,.0f}:"

        return f"{hours_str}{minutes:02.0f}:{seconds:02.0f}"


    def compose(self) -> ComposeResult:
        yield self

    def _update(self):
        rem_str = self._remaining_str
        if rem_str == self.prev_remaining_str:
            return
        rich_str = self.font.to_rich(rem_str)
        self.update(rich_str)

    # ==========================================================================
    # event handlers
    # ==========================================================================
    def on_mount(self, event: events.Mount) -> None:
        self.remaining = 0.0
        self.font = Font(Face.menlo, 12)
        self._refresh_timer = self.set_interval(.25, self._update)
        self.prev_remaining_str = self._remaining_str


class CurTimerComponent(Static):
    """display of currently selected/running timer"""
    def on_mount(self, event: events.Mount) -> None:
        self.font = Font(Face.menlo, 12)
        p = Panel(self.font.to_rich('JEBTUSE'))
        self.update(p)
    

if __name__ == '__main__':
    from rich import print
    print(FONT_PATH)
    # print(font.to_rich('sntahoeu'))