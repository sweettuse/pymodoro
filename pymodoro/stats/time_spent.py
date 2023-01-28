from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from operator import attrgetter, itemgetter
from time import monotonic

from pymodoro.pymodoro_state import EventStore, StateStore
import pandas as pd
from rich import print


def _group_by_comp_id(events: list[dict]) -> dict[str, list[str]]:
    by_comp_id = defaultdict(list)
    for e in events:
        by_comp_id[e["component_id"]].append(e)
    return dict(by_comp_id.items())


def _augment_with_state(events: list[dict]) -> list[dict]:
    state = StateStore.load()
    return state


def calc_time_spent():
    events = EventStore.load()
    by_comp_id = _group_by_comp_id(events)
    return by_comp_id


def _floor_hour(dt: datetime) -> datetime:
    return dt.replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def get_elapsed_events() -> list[dict]:
    events = EventStore.load_cached()
    event_types = {"stopped", "manually_accounted_time"}
    return sorted(
        (e.copy() for e in events if e.get("name") in event_types), key=itemgetter("at")
    )


def _explore_missing():
    events = EventStore.load_cached()
    comp_id = "countdown_timer_container_1d221fc7-d747-4022-b23f-0e6c654424a5"
    comp_id = "countdown_timer_container_87c2f2dc-de53-482c-9224-914d9552d597"
    return sorted(
        (e.copy() for e in events if e["component_id"] == comp_id), key=itemgetter("at")
    )


def as_df():
    start = monotonic()
    events = EventStore.load()
    print({e.get("name") for e in events})
    event_types = {"stopped", "manually_accounted_time"}
    events = [e for e in events if e.get("name") in event_types]
    print(events[0])
    import pendulum

    return
    # event_types = {'manually_accounted_time'}
    df = pd.DataFrame(events)
    end1 = monotonic()
    print(df)
    print(end1 - start)
    print(monotonic() - end1)


def main():
    events = _explore_missing()
    print(events)
    print(sum(e.get("elapsed", 0.0) for e in events))

    return
    comp_id = "countdown_timer_container_1d221fc7-d747-4022-b23f-0e6c654424a5"
    events = get_elapsed_events()
    print([e for e in events if e["component_id"] == comp_id])
    return
    return as_df()
    events = EventStore.load()

    for e in events[:30]:
        print(e)
    grouped = _group_by_comp_id(events)
    total = {
        k: sum(float(d.get("elapsed", 0.0)) for d in group)
        for k, group in grouped.items()
    }
    print(total)
    states = StateStore.load()
    state_total = {s.id: s.total_seconds_completed for s in states}
    for k in total.keys() & state_total:
        print(k, total[k] - state_total[k])


if __name__ == "__main__":
    main()
