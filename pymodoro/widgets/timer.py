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


class Period:
    """track an ongoing period of time and how much has elapsed"""

    def __init__(self):
        self._start = self._end = 0.0

    def start(self):
        self._start = self._end = monotonic()

    def stop(self):
        start = self._start
        self._start = self._end = 0.0
        return monotonic() - start

    @property
    def elapsed(self) -> float:
        """how many seconds have elapsed in this period"""
        if self._start:  # is it running?
            self._end = monotonic()
        return self._end - self._start


class CountdownTimer:
    """manage the logic of a countdown timer"""

    def __init__(self, initial_seconds=25 * 60):
        self.initial_seconds = initial_seconds
        self._active = False
        self._elapsed = 0.0
        self.period = Period()

    def start(self) -> bool:
        if self._active or not self.remaining:
            return False

        self._active = True
        self.period.start()
        return True

    def stop(self):
        if not self._active:
            return

        self._elapsed += self.period.stop()
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def remaining(self) -> float:
        """how many seconds remaining"""
        return max(0.0, self.initial_seconds - self.total_elapsed)

    @property
    def total_elapsed(self) -> float:
        """how much time has elapsed"""
        return self._elapsed + self.period.elapsed


class CountdownTimerWidget(Static, can_focus=True):
    """wrap a CountdownTimer in a widget"""

    CSS_PATH = "css/timer.css"

    class Stopped(Message):
        """indicate that app has stopped or paused"""

        def __init__(self, sender: MessageTarget, remaining: float):
            self.remaining = remaining
            super().__init__(sender)

    def __init__(self, countdown_timer: CountdownTimer, *, id=None):
        super().__init__(id=id)
        self.ct = countdown_timer

    async def on_mount(self):
        self._refresh_timer = self.set_interval(1 / 60, self._update, pause=True)
        await self._update()

    async def start(self):
        if not self.ct.start():
            return False
        self._refresh_timer.resume()
        return True

    async def stop(self):
        if not self.ct.is_active:
            return
        self._refresh_timer.pause()
        self.ct.stop()
        await self._update()
        await self.emit(self.Stopped(self, self.ct.remaining))

    async def _update(self):
        if self.ct.is_active and not self.ct.remaining:
            await self.stop()
        minutes, seconds = divmod(self.ct.remaining, 60)
        self.update(f"{minutes:02.0f}:{seconds:05.2f}")
