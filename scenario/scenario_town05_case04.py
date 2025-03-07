import carla
from pathlib import Path
import random

from scenario import Scenario
from .seed import Seed
from .utils import kmh_2_ms


class Scenario_case04(Scenario):
    def __init__(self, host, port, world_map, output_root_dir: Path):
        Scenario.__init__(self, host, port, world_map, output_root_dir)

    def set_npc_car(self, position=None, velocity=None):
        self.npc_vehicle_bp = self.world.get_blueprint_library().find("vehicle.audi.tt")
        self.npc_vehicle_bp.set_attribute("color", "240,240,240")
        # Town05
        npc_init_point = 277  # <-- spawn point #277: (x: -51.091713, y: -21.431129)
        self.npc_init_transform = carla.Transform(
            location=self.spawn_points[npc_init_point].location,
            rotation=self.spawn_points[npc_init_point].rotation,
        )
        self.npc_init_transform.location.y -= 7.7  # distance to walker path: 18
        self.npc_lane_change_direction = 1

        if position is None:
            self.p_npc = random.randint(0, 10)
        elif isinstance(position, (int, float)):
            self.p_npc = position
        self.npc_init_transform.location.y += self.p_npc
        # self.npc_init_transform.location.z = 1
        self.npc = self.world.spawn_actor(self.npc_vehicle_bp, self.npc_init_transform)  # type: ignore

        if velocity is None:
            self.v_npc = random.randint(0, 80)
        elif isinstance(velocity, (int, float)):
            self.v_npc = velocity
        self.npc_init_velocity = carla.Vector3D(
            kmh_2_ms(self.v_npc),
            0,
            0,
        )
        self.npc.enable_constant_velocity(self.npc_init_velocity)

        self.traffic_manager.random_left_lanechange_percentage(self.npc, 0)
        self.traffic_manager.update_vehicle_lights(self.npc, True)
        self.traffic_manager.random_right_lanechange_percentage(self.npc, 0)
        self.traffic_manager.ignore_lights_percentage(self.npc, 100)
        self.traffic_manager.ignore_signs_percentage(self.npc, 100)

    def set_npc_car_route(self):
        self.npc_route = [self.spawn_points[i].location for i in [204, 243]]
        self.traffic_manager.set_path(self.npc, self.npc_route)  # type: ignore


_HOST = "localhost"
_PORT = 2000
_WORLD_MAP = "Town05"
_OUTPUT_ROOT_DIR = Path("./result")

_TOTAL_ROUND = 10000

if __name__ == "__main__":
    scene = Scenario_case04(_HOST, _PORT, _WORLD_MAP, _OUTPUT_ROOT_DIR)
    scene.draw_spawn_points()
    p = carla.Location(scene.spawn_points[277].location)
    print(p)
    p.y += 10.3
    scene.world.debug.draw_point(p, color=carla.Color(0, 0, 255), life_time=0)

    seed = Seed(0, 0, 0, 0, 0)
    # seed.round_result = scene.run(seed=seed)
    # print(seed.round_result)
    scene.run(seed)

    print()
    print()
