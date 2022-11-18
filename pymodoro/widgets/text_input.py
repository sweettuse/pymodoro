from __future__ import annotations
from contextlib import suppress

from typing import Any, Optional
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.message import Message, MessageTarget
from textual import events
from pymodoro.linear.api import IssueQuery

from pymodoro.utils import classproperty
from pymodoro.pymodoro_state import StateManagement


class TextInput(Input, StateManagement):
    """text input with some state management help"""

    @classproperty
    def state_attrs(cls):
        return "id", "value", "placeholder", "classes"

    @classmethod
    def from_state(cls, state: dict[str, Any]):
        kw = {k: state[k] for k in set(cls.state_attrs) - {"classes"}}
        res = cls(**kw)
        res.add_class(*state["classes"])
        return res


class LinearInput(TextInput):
    class NewTitle(Message):
        def __init__(self, sender: MessageTarget, title: str):
            super().__init__(sender)
            self.title = title

    async def on_key(self, event: events.Key):

        if event.key != "enter":
            return

        title = None
        if not self.value:
            title = ""
        else:
            title = IssueQuery(self.value).get()

        if title is not None:
            await self.emit(self.NewTitle(self, title))


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
        if self.value.endswith("m"):
            return 60 * int(self.value[:-1])

        fields = self.value.split(":")
        if len(fields) > 3:
            return None

        m = 1
        res = 0.0
        with suppress(Exception):
            for f in reversed(fields):
                res += m * float(f)
                m *= 60
            return res
