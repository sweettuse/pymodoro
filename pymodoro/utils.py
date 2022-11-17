from abc import ABC, abstractmethod
from typing import Any


class classproperty:
    def __init__(self, f):
        self.f = f

    def __get__(self, _, cls):
        return self.f(cls)


class StateManagement:
    @classproperty
    @abstractmethod
    def state_attrs(cls) -> tuple[str, ...]:
        raise NotImplemented

    def dump_state(self) -> dict[str, Any]:
        return dict(cls=type(self)) | {a: getattr(self, a) for a in self.state_attrs}

    def set_state(self, state_dict: dict[str, Any]) -> None:
        for a, v in state_dict.items():
            if a == "cls":
                continue
            setattr(self, a, v)
