from __future__ import annotations

from typing import Any, Optional
from textual.widgets import Button, Header, Footer, Static, TextLog, Input

from pymodoro.utils import StateManagement, classproperty


class TextInput(Input, StateManagement):
    @classproperty
    def state_attrs(cls):
        return "id", "value"
