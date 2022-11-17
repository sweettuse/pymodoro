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

from pymodoro.utils import StateManagement, classproperty


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


class CountdownTimer(StateManagement):
    """manage the logic of a countdown timer"""

    def __init__(self, initial_seconds=25 * 60.0):
        self.initial_seconds = initial_seconds
        self._active = False
        self._elapsed = 0.0
        self.period = Period()

    @classproperty
    def state_attrs(cls) -> tuple[str, ...]:
        return "initial_seconds", "total_elapsed"

    @classmethod
    def from_state(cls, state_dict: dict[str, Any]):
        res = cls()
        res.set_state(state_dict)
        return res

    def start(self) -> bool:
        if self._active or not self.remaining:
            return False

        self._active = True
        self.period.start()
        return True

    def stop(self):
        """return time elapsed in period"""
        if not self._active:
            return 0.0

        period_elapsed = self.period.stop()
        self._elapsed += period_elapsed
        self._active = False
        return period_elapsed

    def reset(self):
        self._elapsed = 0.0
        return self.period.stop()

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

    @total_elapsed.setter
    def total_elapsed(self, v):
        self._elapsed = v


class CountdownTimerWidget(Static, can_focus=True):
    """wrap a CountdownTimer in a widget"""

    CSS_PATH = "css/timer.css"

    class Stopped(Message):
        """indicate that app has stopped or paused"""

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
            return False
        self._refresh_timer.resume()
        return True

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
