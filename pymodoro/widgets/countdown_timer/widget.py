from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio

from time import monotonic, sleep
from contextlib import suppress
from typing import Any
import pendulum
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
from pymodoro_state import EventStore

from widgets.countdown_timer import CountdownTimer


class _CountdownTimerMessage(Message):
    def __init__(self, sender: MessageTarget) -> None:
        super().__init__(sender)
        self.at = pendulum.now()
        EventStore.register(self.event_data)

    @property
    def event_data(self) -> dict[str, str]:
        """as this should be stored in the EventStore"""
        return dict(
            component_id=self.component_id,
            name=self.name,
            at=str(self.at),
        )

    @property
    def component_id(self) -> str:
        from widgets.countdown_timer.container import CountdownTimerComponent

        component = next(
            a for a in self.sender.ancestors if isinstance(a, CountdownTimerComponent)
        )
        if component:
            return component.id
        return "unknown"


class CountdownTimerWidget(Static, can_focus=True):
    """wrap a CountdownTimer in a widget"""

    CSS_PATH = "css/timer.css"

    def __init__(self, countdown_timer: CountdownTimer, *, id=None):
        super().__init__(id=id)
        self.ct = countdown_timer

    # ==========================================================================
    # messages
    # ==========================================================================

    class Started(_CountdownTimerMessage):
        """indicate that widget has started"""

    class Stopped(_CountdownTimerMessage):
        """indicate that widget has stopped or paused"""

        def __init__(self, sender: MessageTarget, remaining: float, elapsed: float):
            self.remaining = remaining
            self.elapsed = elapsed
            super().__init__(sender)

        @property
        def event_data(self) -> dict[str, str]:
            """as this should be stored in the EventStore"""
            return super().event_data | dict(
                remaining=str(self.remaining),
                elapsed=str(self.elapsed),
            )

    class Completed(_CountdownTimerMessage):
        """indicate that pomodoro has completed"""

    # ==========================================================================
    # methods
    # ==========================================================================

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
