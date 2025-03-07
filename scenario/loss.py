import math
from copy import deepcopy
from enum import Enum, auto


class LossType(Enum):
    TIMEGAP = auto()
    DISTANCE = auto()


class Loss:
    time_gap: float
    distance: float
    mode: LossType

    def __init__(
        self,
        time_gap: float = math.inf,
        distance: float = math.inf,
        mode: LossType = LossType.DISTANCE,
    ):
        self.time_gap = time_gap
        self.distance = distance
        self.mode = mode

    @property
    def value(self) -> float:
        if self.mode is LossType.DISTANCE:
            return self.distance
        else:
            return self.time_gap

    def to_basic_data(self):
        return {
            "time_gap": self.time_gap,
            "distance": self.distance,
            "mode": "time_gap" if self.mode is LossType.TIMEGAP else "distance",
        }

    def __str__(self):
        return (
            "  loss: \n"
            + f"    time gap: {self.time_gap} \n"
            + f"    distance: {self.distance} \n"
        )


if __name__ == "__main__":
    a = Loss(1, 1)
    print(a.to_basic_data())
