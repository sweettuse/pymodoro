from __future__ import annotations
from contextlib import suppress

from typing import Any, Optional
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.message import Message, MessageTarget
from textual import events
from rich.console import RenderableType
from rich.text import Text, Span
from rich.style import Style
from linear.api import IssueQuery


class TextInput(Input):
    """text input with some state management help"""

    state_attrs: tuple[str, ...] = "id", "value", "placeholder", "password"

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


class LinearInput(TextInput):
    url_format = "https://linear.app/tuse/issue/{}"

    class NewTitle(Message):
        def __init__(self, sender: MessageTarget, title: str):
            super().__init__(sender)
            self.title = title

    async def on_key(self, event: events.Key):
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


class TimeInput(TextInput):
    """enter new time for countdown timer"""

    class NewTotalSeconds(Message):
        def __init__(self, sender: MessageTarget, new_total_seconds: float):
            super().__init__(sender)
            self.total_seconds = new_total_seconds

    async def action_submit(self):
        if new_seconds := self._to_seconds():
            await self.emit(self.NewTotalSeconds(self, new_seconds))

    def _to_seconds(self) -> Optional[float]:
        with suppress(Exception):
            if self.value.endswith("s"):
                return int(self.value[:-1])
            if self.value.endswith("s"):
                return 60 * int(self.value[:-1])

            fields = self.value.split(":")
            if len(fields) > 3:
                return None

            if len(fields) == 1:
                return 60 * int(fields[0])

            m = 1
            res = 0.0
            for f in reversed(fields):
                res += m * float(f)
                m *= 60
            return res
