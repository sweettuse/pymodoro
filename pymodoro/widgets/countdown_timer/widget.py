from __future__ import annotations
import asyncio

from time import monotonic, sleep
from contextlib import suppress
from typing import Any
from textual.app import App, ComposeResult

from textual.message import Message, MessageTarget
from textual.containers import Container, Horizontal
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static

from widgets.countdown_timer import CountdownTimer


class CountdownTimerWidget(Static, can_focus=True):
    """wrap a CountdownTimer in a widget"""

    CSS_PATH = "css/timer.css"

    class Started(Message):
        """indicate that widget has started"""

    class Stopped(Message):
        """indicate that widget has stopped or paused"""

        def __init__(self, sender: MessageTarget, remaining: float, elapsed: float):
            super().__init__(sender)
            self.remaining = remaining
            self.elapsed = elapsed

    class Completed(Message):
        """indicate that pomodoro has completed"""

    def __init__(self, countdown_timer: CountdownTimer, *, id=None):
        super().__init__(id=id)
        self.ct = countdown_timer

    async def on_mount(self):
        self._refresh_timer = self.set_interval(1 / 60, self._update, pause=True)
        await self._update()

    async def start(self):
        if not self.ct.start():
            return
        self._refresh_timer.resume()
        await self.emit(self.Started(self))

    async def stop(self):
        if not self.ct.is_active:
            return 0.0
        self._refresh_timer.pause()
        elapsed = self.ct.stop()
        await self._update()
        await self.emit(self.Stopped(self, self.ct.remaining, elapsed))

    async def reset(self):
        """reset time to original amount"""
        self.ct.reset()
        await self._update()

    async def _update(self):
        if self.ct.is_active and not self.ct.remaining:
            await self.stop()
            await self.emit(self.Completed(self))

        minutes, seconds = divmod(self.ct.remaining, 60)
        hours, minutes = divmod(minutes, 60)

        hours_str = ""
        if hours:
            hours_str = f"{hours:02,.0f}:"

        self.update(f"{hours_str}{minutes:02.0f}:{seconds:05.2f}")
