from __future__ import annotations
from contextlib import suppress

from typing import TYPE_CHECKING, Any, Optional
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.message import Message, MessageTarget
from textual.reactive import reactive, var
from textual import events
from rich.console import RenderableType
from rich.text import Text, Span
from rich.style import Style
from linear.api import IssueQuery
from utils import EventMessage

if TYPE_CHECKING:
    from widgets.countdown_timer.component import CountdownTimerComponent


class TextInput(Input):
    """text input with some state management functionality"""

    state_attrs: tuple[str, ...] = "id", "value", "placeholder", "password"
    dirty = var(False)

    def dump_state(self) -> dict:
        return dict(classes=list(self.classes)) | {
            k: getattr(self, k) for k in self.state_attrs
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]):
        classes = state.pop("classes")
        kw = {k: state.get(k) for k in cls.state_attrs}
        res = cls(**kw)
        res.add_class(*classes)
        return res

    class ValueAfterBlur(Message):
        def __init__(self, sender: TextInput, value: str):
            super().__init__(sender)
            self.value = value

        @property
        def ctc(self) -> CountdownTimerComponent:
            """find the ctc related to this event"""
            from widgets.countdown_timer.component import CountdownTimerComponent

            return next(
                a
                for a in self.sender.ancestors
                if isinstance(a, CountdownTimerComponent)
            )

    async def on_blur(self, _):
        if self.dirty:
            await self.emit(self.ValueAfterBlur(self, self.value))
            self.dirty = False

    def watch_value(self, _):
        self.dirty = True


class DescriptionInput(TextInput):
    """class for the description input box"""


class LinearInput(TextInput):
    """get description from linear and update description in CTC.

    link to the url of the issue in linear
    """

    url_format = "https://linear.app/tuse/issue/{}"

    class NewTitle(Message):
        def __init__(self, sender: MessageTarget, title: str):
            super().__init__(sender)
            self.title = title

    async def on_key(self, event: events.Key):
        """get the issue and emit event if it has a matching title in linear"""
        if event.key != "enter":
            return

        if not self.value:
            title = ""
        else:
            title = IssueQuery(self.value).get()

        if title is not None:
            await self.emit(self.NewTitle(self, title))

    @property
    def _value(self):
        """add link to linear"""
        if not self.value:
            return super()._value

        link = Style(link=self.url_format.format(self.value.upper()))
        span = Span(0, len(self.value), link)
        return Text(self.value, spans=[span])


class TimeInputBase(TextInput):
    """enter new remaining time for countdown timer"""

    def _to_seconds(self) -> float | None:
        """convert value to seconds

        by default, interpret value as minutes.
        if suffixed with `s`, interpret as seconds
        can also parse something like:
            "[hours:][minutes:]seconds"
        """
        with suppress(Exception):
            if not self.value:
                return None

            if self.value.endswith("s"):
                return int(self.value[:-1])
            if self.value.endswith("m"):
                return 60 * int(self.value[:-1])

            fields = self.value.split(":")
            if len(fields) > 3:
                return None

            if len(fields) == 1:
                return 60 * float(fields[0])

            m = 1
            if fields[0].startswith("-"):
                m = -1
                fields[0] = fields[0][1:]
            res = 0.0
            for f in reversed(fields):
                res += m * float(f)
                m *= 60
            return res


class TimeInput(TimeInputBase):
    """class to change remaining time"""

    class NewTotalSeconds(Message):
        """emit when the total remaining time has changed"""

        def __init__(self, sender: MessageTarget, new_total_seconds: float):
            super().__init__(sender)
            self.total_seconds = new_total_seconds

    async def action_submit(self):
        if new_seconds := self._to_seconds():
            await self.emit(self.NewTotalSeconds(self, new_seconds))

    def _to_seconds(self) -> float | None:
        if not (res := super()._to_seconds()):
            return res
        return max(0.0, res)


class ManualTimeAccounting(TimeInputBase):
    """class to manually account for time that you might have missed"""

    class AccountedTime(EventMessage):
        def __init__(self, sender: MessageTarget, elapsed_secs: float):
            self.elapsed = elapsed_secs
            super().__init__(sender)

        @property
        def name(self) -> str:
            return "manually_accounted_time"

        @property
        def event_data(self) -> dict[str, Any]:
            return super().event_data | dict(elapsed=round(self.elapsed, 3))

    async def action_submit(self):
        if elapsed := self._to_seconds():
            await self.emit(self.AccountedTime(self, elapsed))
