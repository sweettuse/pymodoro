from __future__ import annotations

from time import monotonic
from contextlib import suppress
from textual.app import App, ComposeResult

from textual.containers import Container, Horizontal
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static


class CountdownTimer(Static):
    CSS_PATH = "css/timer.css"

    def on_mount(self):
        self._running = False
        self._elapsed = 0.0
        self._start = 0.0
        self.total_seconds = 25 * 60 - 55
        self._refresh_timer = self.set_interval(1 / 10, self._update, pause=True)
        self._update()

    def start(self):
        if self._running:
            return 

        self._running = True
        self._start = monotonic()
        self._refresh_timer.resume()

    def stop(self):
        if not self._running:
            return

        self._running = False
        self._elapsed += self._elapsed_since_start
        self._refresh_timer.pause()

    def _update(self):
        self.update(self)

    @property
    def total_elapsed(self):
        extra = self._elapsed_since_start if self._running else 0.0
        return self._elapsed + extra

    @property
    def _elapsed_since_start(self):
        return monotonic() - self._start

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_seconds - self.total_elapsed)

    def __rich_console__(self, *_):
        minutes, seconds = divmod(round(self.remaining), 60)
        yield f"{minutes:02d}:{seconds:02d}"


class TimerButton(Button):
    def __init__(self, label, fn, **button_args):
        super().__init__(label=label, **button_args)
        self.fn = fn

    def on_click(self):
        self.fn()


def timer_container() -> Container:
    ct = CountdownTimer()
    return Container(
        ct,
        Horizontal(
            TimerButton("start", ct.start, variant="success"),
            TimerButton("stop", ct.stop, variant="error"),
            classes="buttons",
        ),
        id="timer_containers",
    )


class TimerTest(App):
    CSS_PATH = "css/timer.css"

    def compose(self) -> ComposeResult:
        yield timer_container()
        yield timer_container()


if __name__ == "__main__":
    TimerTest().run()
