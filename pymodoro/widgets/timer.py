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

from threading import RLock

from pymodoro.utils import StateManagement, classproperty


class CountdownTimer(Static, can_focus=True):
    CSS_PATH = "css/timer.css"

    # @classproperty
    # def state_attrs(cls):
    #     return 'initial_seconds', '_active', '_elapsed', '_mark_time'

    def __init__(self, initial_seconds=25 * 60, *, id=None):
        super().__init__(id=id)
        self.initial_seconds = initial_seconds
        self._active = False
        self._elapsed = 0.0
        self._mark_time = 0.0

    def on_mount(self):
        self._refresh_timer = self.set_interval(1 / 60, self._update, pause=True)
        self._update()

    def start(self):
        if self._active:
            return

        self._active = True
        self._mark_time = monotonic()
        self._refresh_timer.resume()

    def stop(self):
        if not self._active:
            return

        self._refresh_timer.pause()
        self._active = False
        self._elapsed += self._since_last_mark
        self._update()

    def _update(self):
        self.update(self)

    @property
    def remaining(self) -> float:
        return max(0.0, self.initial_seconds - self.total_elapsed)

    @property
    def total_elapsed(self):
        current = self._since_last_mark if self._active else 0.0
        return self._elapsed + current

    @property
    def _since_last_mark(self):
        return monotonic() - self._mark_time

    def __rich_console__(self, *_):
        self.log(f"{self._active}, {self.total_elapsed=}")
        minutes, seconds = divmod(self.remaining, 60)
        yield f"{minutes:02.0f}:{seconds:05.2f}"
