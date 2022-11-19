from contextlib import suppress
from datetime import datetime
from time import perf_counter
from textual.app import App, ComposeResult
from widgets.text_input_orig import TextInputOrig

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
    TextLog,
)


# from widgets.text_input import TextInput
# from widgets.timer import CountdownTimer, timer_container


# class TextLogApp(App):
#     """App to display key events."""

#     def on_mount(self) -> None:
#         self._count = 0
#         self._last_time = perf_counter()
#         self._timer = self.set_interval(1, self._mark)

#     def _mark(self) -> None:
#         if tl := self.query_one(TextLog):
#             msg = f"{perf_counter() - self._last_time:.2f} -> {self._count}"
#             tl.write(msg)
#         self._count = 0
#         self._last_time = perf_counter()

#     def compose(self) -> ComposeResult:
#         yield TextLog()

#     def on_key(self, event: events.Key) -> None:
#         self._count += 1
#         self.query_one(TextLog).write(event)


class InputTestApp(App):
    def compose(self) -> ComposeResult:
        yield Container(
            Input(),
            TextLog(),
        )

    def on_key(self, event: events.Key) -> None:
        self.query_one(TextLog).write(event)


if __name__ == "__main__":
    app = InputTestApp()
    app.run()
