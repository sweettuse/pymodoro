from __future__ import annotations
from abc import abstractmethod
from collections import deque
from functools import partial, wraps
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable
import pendulum

from textual.message import Message, MessageTarget

from pymodoro_state import EventStore

if TYPE_CHECKING:
    from widgets.countdown_timer.component import CountdownTimerComponent


class EventMessage(Message):
    """base class to log all changes to the EventStore

    ⚠️ note: must override `event_data` and fill in with what data you
    want your event to persist.

    ⚠️ note: because we register on event creation, must call
        `super().__init__(sender)`
    last from subclasses

    see `ManualTimeAccounting.AccountedTime` for an example of both of these
    """

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

        try:
            return self.ctc.id
        except Exception:
            return "unknown"

    @property
    def ctc(self) -> CountdownTimerComponent:
        """find the ctc related to this event"""
        from widgets.countdown_timer.component import CountdownTimerComponent

        return next(
            a for a in self.sender.ancestors if isinstance(a, CountdownTimerComponent)
        )


def format_time(num_secs: int | float) -> str:
    """format time based on type to str"""
    if isinstance(num_secs, int):
        seconds_fmt = "02d"
        decimal_padding = "   "
    else:
        seconds_fmt = "05.2f"
        decimal_padding = ""

    minutes, seconds = divmod(num_secs, 60)
    minutes = int(minutes)
    hours, minutes = divmod(minutes, 60)
    hours_str = f"{hours:3d}:" if hours else "    "

    minutes_fmt = "02d" if hours else "2d"

    return (
        f"{hours_str}{minutes:{minutes_fmt}}:{seconds:{seconds_fmt}}{decimal_padding}"
    )


def exec_on_repeat(
    fn: Callable | None = None, /, *, num_repeat: int = 2, window_ms: int | float = 250
):
    """decorator to enable exec'ing actions after a
    repeated number of calls in a certain amount of time

    e.g. if the wrapped function is called two times within 250 ms, it will execute.
    example:
        it enables typing `dd` to delete a timer
        works with and around the binding machinery of textual to enable repeated
        keystrokes to cause an action
    """
    if not fn:
        return partial(exec_on_repeat, num_repeat=num_repeat, window_ms=window_ms)

    assert num_repeat > 0
    assert window_ms > 0
    window_secs = window_ms / 1000

    call_times: deque[float]
    _deque_init_vals = [float("-inf")] * num_repeat

    def _reset():
        nonlocal call_times
        call_times = deque(_deque_init_vals, maxlen=num_repeat)

    _reset()

    @wraps(fn)
    def wrapper(*a, **kw):
        call_times.append(monotonic())
        if (call_times[-1] - call_times[0]) > window_secs:
            return

        _reset()
        return fn(*a, **kw)

    return wrapper
