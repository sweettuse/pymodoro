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
from rich.align import Align
from rich.panel import Panel
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static
from utils import format_time
from pymodoro_state import EventStore

from widgets.countdown_timer import CountdownTimer


class _CountdownTimerMessage(Message):
    """base class to log all changes to the EventStore"""

    def __init__(self, sender: MessageTarget) -> None:
        super().__init__(sender)
        self.at = pendulum.now()
        EventStore.register(self.event_data)

    @property
    def event_data(self) -> dict[str, Any]:
        """as this should be stored in the EventStore"""
        return dict(
            component_id=self.component_id,
            name=self.name,
            at=str(self.at),
        )

    @property
    def name(self):
        """lowercase class name"""
        return type(self).__name__.lower()

    @property
    def component_id(self) -> str:
        """get the related ctc's id"""
        from widgets.countdown_timer.component import CountdownTimerComponent

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

        def __init__(self, sender: MessageTarget, remaining: float) -> None:
            super().__init__(sender)
            self.remaining = remaining

    class Stopped(_CountdownTimerMessage):
        """indicate that widget has stopped or paused"""

        def __init__(
            self,
            sender: MessageTarget,
            remaining: float,
            elapsed: float,
            total_elapsed: float,
        ):
            self.remaining = remaining
            self.elapsed = elapsed
            self.total_elapsed = total_elapsed
            super().__init__(sender)

        @property
        def event_data(self) -> dict[str, Any]:
            """as this should be stored in the EventStore"""
            return super().event_data | dict(
                remaining=round(self.remaining, 3),
                elapsed=round(self.elapsed, 3),
            )

    class Completed(_CountdownTimerMessage):
        """indicate that pomodoro has completed"""

    class NewSecond(Message):
        """emit the current amount remaining/elapsed"""

        def __init__(
            self, sender: MessageTarget, remaining: float, elapsed: float
        ) -> None:
            super().__init__(sender)
            self.remaining = remaining
            self.elapsed = elapsed

    # ==========================================================================
    # methods
    # ==========================================================================

    async def on_mount(self):
        self._refresh_timer = self.set_interval(1 / 60, self._update, pause=True)
        self._refresh_global = self.set_interval(
            1 / 5, self._update_global_timer, pause=True
        )
        await self._update()

    def _pause_or_resume_timers(self, pause: bool):
        """if pause, pause timers. else resume"""
        method = "pause" if pause else "resume"
        for fn in self._refresh_global, self._refresh_timer:
            getattr(fn, method)()

    async def start(self):
        """start a pomodoro"""
        remaining = self.ct.remaining
        self._completion_sent = False
        if not self.ct.start():
            return
        self._pause_or_resume_timers(pause=False)
        await self.emit(self.Started(self, remaining))

    async def stop(self):
        """stop a pomodoro"""
        if not self.ct.is_active:
            return 0.0
        self._pause_or_resume_timers(pause=True)
        elapsed = self.ct.stop()
        await self._update()

        remaining = self.ct.remaining
        await self.emit(self.Stopped(self, remaining, elapsed, self.ct.total_elapsed))
        if not remaining:
            await self.emit(self.Completed(self))

    async def reset(self):
        """reset time to original amount"""
        self.ct.reset()
        await self._update()

    async def _update(self):
        """update display
        
        if complete, stop recurring function calls
        """
        if self.ct.is_active and not self.ct.remaining:
            await self.stop()

        text = Align(format_time(self.ct.remaining), "center", vertical="middle")
        res = Panel(text, title="remaining")
        self.update(res)

    async def _update_global_timer(self):
        """let the global timer know how much is remaining"""
        await self.emit(self.NewSecond(self, self.ct.remaining, self.ct.period.elapsed))
