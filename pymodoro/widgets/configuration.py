from __future__ import annotations

from functools import partial

from typing import Any, Optional
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.message import Message, MessageTarget
from textual.widgets import Button, Header, Footer, Static, TextLog, Input
from textual.containers import Horizontal
from textual.binding import Binding
from widgets.text_input import TextInput
from pymodoro_state import StateStore


class LabelInput:
    def __init__(self, label: str, *, password: bool = False):
        self.label = label
        self.password = password

    def __iter__(self) -> ComposeResult:
        yield Static(self.label, classes="label")
        yield TextInput(placeholder=self.label, password=self.password)


class ConfigFields(Static):
    def compose(self) -> ComposeResult:
        yield from LabelInput("linear team name")
        for a in "abcdefgh":
            yield from LabelInput(a)


class ConfigTitle(Static):
    pass


class ConfigForm(Static):
    def compose(self) -> ComposeResult:
        yield ConfigTitle('configuration')
        yield ConfigFields()


