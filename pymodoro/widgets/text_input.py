from contextlib import suppress
from textual.app import App, ComposeResult

from textual.containers import Container
from textual import events
from textual.scroll_view import ScrollView
from rich.color import Color
from rich.style import Style
from rich.segment import Segment
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static


class TextInput(Static, can_focus=True):
    # CSS_PATH = "css/text_input.css"

    text = reactive("")
    _cursor = reactive(0)

    def __init__(self, max_width=None):
        pass

    def on_mount(self) -> None:
        self.expand = True

    @property
    def cursor(self) -> int:
        return self._cursor

    @cursor.setter
    def cursor(self, value):
        self._cursor = max(min(len(self.text), value), 0)

    @property
    def _split(self) -> tuple[str, str, str]:
        return tuple(self.text[s] for s in self._slices)

    @property
    def _slices(self) -> tuple[slice, slice, slice]:
        return (
            slice(self.cursor),
            slice(self.cursor, self.cursor + 1),
            slice(self.cursor + 1, None),
        )

    @staticmethod
    def _supported_ascii(event: events.Key) -> bool:
        with suppress(Exception):
            o = ord(event.char)
            return 32 <= o < 127 or o in {10, 13}

        return False

    def on_key(self, event: events.Key) -> None:
        self.log(f"EVENT: {event}")
        self._debug(f"BEFORE:")
        if event.key == "delete":
            if self.text:
                before, _, after = self._split
                self.text = before + after

        elif event.key == "backspace":
            if self.text:
                before, cursor, after = self._split
                self.text = before[:-1] + cursor + after
                self.cursor -= 1

        elif self._supported_ascii(event):
            char = event.char
            if event.key == "enter":
                char = "\n"
            before, cursor, after = self._split
            self.text = before + char + cursor + after
            self.cursor += 1

        elif event.key in {"left", "right"}:
            offset = 1 if event.key == "right" else -1
            self.cursor += offset
            self._update()

        self._debug("AFTER:")

    def _debug(self, addl=""):
        self.log(
            f"DEBUG: {addl}",
            dict(
                split=self._split,
                cursor=self.cursor,
            ),
        )

    def __rich_console__(self, *_):
        s = Style(bgcolor=Color.parse("grey37"), blink2=True)
        before, cursor, after = self._split

        if before:
            yield Segment(before)

        yield Segment(cursor or " ", s if self.has_focus else None)

        if after:
            yield Segment(after)

    def _update(self) -> None:
        self.renderable = self

    def watch_text(self, text: str) -> None:
        self._update()


class TextInputApp(App):
    CSS_PATH = "css/text_input.css"

    def on_mount(self):
        self.screen.styles.border = "heavy", "white"

    def compose(self) -> ComposeResult:
        yield Container(
            TextInput(),
            TextInput(),
            TextInput(),
            TextInput(),
            id="text_input_app",
        )


if __name__ == "__main__":
    app = TextInputApp()
    app.run()
