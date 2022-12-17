from __future__ import annotations
from collections import defaultdict

from pymodoro.pymodoro_state import EventStore, StateStore
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


def main():
    events = EventStore.load()
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
