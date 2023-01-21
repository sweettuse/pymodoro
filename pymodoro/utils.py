from __future__ import annotations
from collections import deque
from functools import partial, wraps
from time import monotonic
from typing import Callable


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
    fn: Callable = None, *, num_repeat: int = 2, window_ms: int | float = 250
):
    """decorator to enable exec'ing actions after a
    repeated number of calls in a certain amount of time
    """
    if not fn:
        return partial(fn, num_repeat=num_repeat, window_ms=window_ms)

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
        print("call_times", call_times)
        if (call_times[-1] - call_times[0]) > window_secs:
            return
        _reset()
        return fn(*a, **kw)

    return wrapper
