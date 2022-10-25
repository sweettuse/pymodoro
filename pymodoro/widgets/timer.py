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
        self.start()

    def start(self):
        if not self._running:
            self._running = True
            self._refresh_timer.resume()
            self._start = monotonic()

    def stop(self):
        if self._running:
            self._running = False
            self._elapsed = self.total_elapsed
            self._refresh_timer.pause()

    def _update(self):
        minutes, seconds = divmod(round(self.remaining), 60)
        self.update(f"{minutes:02d}:{seconds:02d}")

    @property
    def total_elapsed(self):
        return self._elapsed + (monotonic() - self._start)

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_seconds - self.total_elapsed)


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
