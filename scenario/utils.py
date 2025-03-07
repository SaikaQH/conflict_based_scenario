from typing import Optional

import carla
import math

from .conflict_point import Conflict_Point
from .loss import Loss


def kmh_2_ms(velocity) -> float:
    return velocity * 1000 / 3600


def distance(p1: carla.Location, p2: carla.Location):
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)


def calculate_time_distance(p1, p2) -> Loss:
    return Loss(
        time_gap=abs(p1[0] - p2[0]),
        distance=math.sqrt(
            (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2 + (p1[3] - p2[3]) ** 2
        ),
    )


def get_conflict_point(ego_traj, obj_traj) -> Optional[Conflict_Point]:
    cross_point: Optional[Conflict_Point] = None
    delta_end_distance = 0.003
    epsilon_distance = 1
    for i in range(len(ego_traj)):
        for j in range(len(obj_traj)):
            try:
                temp_loss: Loss = calculate_time_distance(ego_traj[i], obj_traj[j])
            except Exception as err:
                print(
                    '[debug] type(i):{};value:{}'.format(type(i),i)
                )
                print(
                    '[debug] type(j):{};value:{}'.format(type(j),j)
                )
                temp_loss = Loss()
                raise err
            if temp_loss.distance > epsilon_distance:
                continue
            if cross_point is None:
                cross_point = Conflict_Point(
                    ego_pass_tick=i, obj_pass_tick=j, loss=temp_loss
                )
            elif (
                temp_loss.time_gap < cross_point.loss.time_gap
                and cross_point.loss.distance > delta_end_distance
            ):
                cross_point = Conflict_Point(
                    ego_pass_tick=i, obj_pass_tick=j, loss=temp_loss
                )
    return cross_point

def calculate_min_distance(ego_traj, obj_traj):
    timestamp = -1
    min_distance = math.inf
    for i in range(min(len(ego_traj), len(obj_traj))):
        temp_loss: Loss = calculate_time_distance(ego_traj[i], obj_traj[i])
        temp_distance = temp_loss.distance
        if temp_distance < min_distance:
            min_distance = temp_distance
            timestamp = i
    return (timestamp, min_distance)
    # return {"timestamp": timestamp, "min_distance": min_distance}


if __name__ == "__main__":
    cp = Conflict_Point()
    print(cp)
