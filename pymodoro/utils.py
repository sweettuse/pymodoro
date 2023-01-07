from __future__ import annotations


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
