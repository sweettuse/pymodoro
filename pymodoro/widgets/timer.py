from __future__ import annotations
import asyncio

from time import monotonic, sleep
from contextlib import suppress
from typing import Any
from textual.app import App, ComposeResult

from textual.containers import Container, Horizontal
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static


class Period:
    def __init__(self):
        self._start = self._end = 0.0

    def start(self):
        self._start = self._end = monotonic()

    def stop(self):
        start = self._start
        self._start = self._end = 0.0
        return monotonic() - start

    @property
    def elapsed(self):
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

    def start(self):
        if self._active:
            return

        self._active = True
        self.period.start()

    def stop(self):
        if not self._active:
            return

        self._elapsed += self.period.stop()
        self._active = False

    @property
    def active(self):
        return self._active

    @property
    def remaining(self) -> float:
        return max(0.0, self.initial_seconds - self.total_elapsed)

    @property
    def total_elapsed(self):
        return self._elapsed + self.period.elapsed


class CountdownTimerWidget(Static, can_focus=True):
    """wrap a CountdownTimer in a widget"""

    CSS_PATH = "css/timer.css"

    def __init__(self, *, countdown_timer: CountdownTimer, id=None):
        super().__init__(id=id)
        self.ct = countdown_timer

    def on_mount(self):
        self._refresh_timer = self.set_interval(1 / 60, self._update, pause=True)
        self._update()

    def start(self):
        self.ct.start()
        self._refresh_timer.resume()

    def stop(self):
        self._refresh_timer.pause()
        self.ct.stop()
        self._update()

    def _update(self):
        if self.ct.active and not self.ct.remaining:
            self.stop()
        self.update(self)

    def __rich_console__(self, *_):
        minutes, seconds = divmod(self.ct.remaining, 60)
        yield f"{minutes:02.0f}:{seconds:05.2f}"
