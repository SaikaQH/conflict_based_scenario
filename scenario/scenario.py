from typing import Optional

import carla
import os
from pathlib import Path
import random
import yaml

from .conflict_point import Conflict_Point
from .loss import Loss, LossType
from .seed import Seed, Round_Result
from .utils import kmh_2_ms, distance, get_conflict_point, calculate_min_distance


class Scenario:
    client: carla.Client
    world: carla.World
    traffic_manager: carla.TrafficManager
    spawn_points: list[carla.Transform]

    scenario_center: carla.Vector3D  # carla.Location

    ego: carla.Vehicle
    npc: carla.Vehicle
    # collision_detector: carla.Sensor.Other.Collision

    start_timestamp: Optional[carla.Timestamp]
    result: Round_Result
    tick_cnt: int

    def __init__(self, host, port, world_map, output_root_dir: Path):
        self.client = carla.Client(host, port)
        self.client.load_world(world_map)
        self.world = self.client.get_world()
        self.output_root_dir: Path = output_root_dir

        self.traffic_manager = self.client.get_trafficmanager()
        self.traffic_manager.set_synchronous_mode(True)

        self.set_default_weather()

        self.spawn_points = self.world.get_map().get_spawn_points()
        # self.draw_spawn_points()

        # Town05
        self.scenario_center = carla.Vector3D(self.spawn_points[204].location)
        self.scenario_center.x += 1.5
        self.scenario_center.y -= 12.4
        # ---- scenario center: (x: -49.102310, y: 0.867327)
        self.set_spectator()
        self.waypoints = self.get_waypoints_in_spectator()
        # for location in self.spawn_points:
        #     spectator_location = location.location
        #     self.set_spectator(spectator_location)
        #     time.sleep(3)

        self.result = Round_Result()

    def set_default_weather(self):
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.01  # type: ignore
        self.world.apply_settings(settings)

    def draw_spawn_points(self):
        self.world.debug.draw_point(
            self.scenario_center,  # type: ignore
            color=carla.Color(0, 0, 255),
            life_time=0,
        )
        for i, spawn_point in enumerate(self.spawn_points):
            self.world.debug.draw_point(spawn_point.location, life_time=0)
            self.world.debug.draw_string(spawn_point.location, str(i), life_time=10000)

    def draw_waypoints(self):
        for wp in self.waypoints:
            sp = carla.Location(wp.transform.location)
            sp.z = 1
            tp = carla.Location(sp + wp.transform.get_forward_vector())  # type: ignore
            tp.z = 1
            self.world.debug.draw_point(sp, color=carla.Color(0, 255, 0), life_time=0)
            self.world.debug.draw_arrow(
                sp, tp, color=carla.Color(0, 255, 0), life_time=0
            )

    def get_waypoints_in_spectator(self, range=30):
        waypoints: list[carla.WayPoint] = list()
        for waypoint in self.world.get_map().generate_waypoints(2):
            if distance(waypoint.transform.location, self.scenario_center) <= range:  # type: ignore
                waypoints.append(waypoint)
        return waypoints

    def set_spectator(self, location: Optional[carla.Location] = None):
        if location is None:
            spectator_location = carla.Location(self.scenario_center)  # type: ignore
        else:
            spectator_location = location
        camera_height = 50
        camera_angle = 270
        spectator_location.z = camera_height
        spectator_transform = carla.Transform(
            spectator_location,
            carla.Rotation(pitch=camera_angle),  # type: ignore
        )
        self.world.get_spectator().set_transform(spectator_transform)

    def set_collision_detector(self):
        collision_detector_bp = self.world.get_blueprint_library().find(
            "sensor.other.collision"
        )
        self.collision_detector = self.world.spawn_actor(
            collision_detector_bp, carla.Transform(), attach_to=self.ego
        )
        self.collision = None

        def detect_collision(event):
            if self.collision is None:
                self.collision = event
                self.npc.enable_constant_velocity(carla.Vector3D(0, 0, 0))
                print(self.collision)

        self.collision_detector.listen(lambda event: detect_collision(event))  # type: ignore

    def init_scenario(self, p_ego=None, p_npc=None, v_npc=None):
        self.set_ego_car(position=p_ego)
        self.set_npc_car(position=p_npc, velocity=v_npc)
        self.set_ego_car_route()
        self.set_npc_car_route()
        self.set_collision_detector()

        self.ego_traj = []
        self.npc_traj = []
        self.start_timestamp = None
        self.result = Round_Result()
        self.tick_cnt = 0
        self.init_snapshot_info_log()

    def set_ego_car(self, position=None):
        self.ego_vehicle_bp = self.world.get_blueprint_library().find("vehicle.audi.a2")
        self.ego_vehicle_bp.set_attribute("role_name", "autoware_v1")
        self.ego_vehicle_bp.set_attribute("color", "255,0,0")
        # print(self.ego_vehicle_bp.get_attribute('color').recommended_values)
        # Town05
        ego_init_point = 65  # <-- spawn point #65: (x: -82.602486, y: 2.750381)
        self.ego_init_transform = carla.Transform(
            location=self.spawn_points[ego_init_point].location,
            rotation=self.spawn_points[ego_init_point].rotation,
        )

        if position is None:
            self.p_ego = random.randint(0, 10)
        elif isinstance(position, (int, float)):
            self.p_ego = position
        self.ego_init_transform.location.x += self.p_ego
        # self.ego_init_transform.location.z = 1
        self.ego = self.world.spawn_actor(self.ego_vehicle_bp, self.ego_init_transform)  # type: ignore

        self.traffic_manager.random_left_lanechange_percentage(self.ego, 0)
        self.traffic_manager.update_vehicle_lights(self.ego, True)
        self.traffic_manager.random_right_lanechange_percentage(self.ego, 0)
        self.traffic_manager.ignore_lights_percentage(self.ego, 100)
        self.traffic_manager.ignore_signs_percentage(self.ego, 100)

    def set_npc_car(self, position=None, velocity=None):
        self.npc_vehicle_bp = self.world.get_blueprint_library().find("vehicle.audi.tt")
        self.npc_vehicle_bp.set_attribute("color", "240,240,240")
        # Town05
        npc_init_point = 22  # <-- spawn point #22: (x: -19.079281, y: -0.880121),  distance to walker pass: 18
        self.npc_init_transform = carla.Transform(
            location=self.spawn_points[npc_init_point].location,
            rotation=self.spawn_points[npc_init_point].rotation,
        )
        self.npc_lane_change_direction = 1

        if position is None:
            self.p_npc = random.randint(0, 10)
        elif isinstance(position, (int, float)):
            self.p_npc = position
        self.npc_init_transform.location.x -= self.p_npc
        # self.npc_init_transform.location.z = 1
        self.npc = self.world.spawn_actor(self.npc_vehicle_bp, self.npc_init_transform)  # type: ignore

        if velocity is None:
            self.v_npc = random.randint(0, 80)
        elif isinstance(velocity, (int, float)):
            self.v_npc = velocity
        self.npc_init_velocity = carla.Vector3D(
            abs(kmh_2_ms(self.v_npc) * self.npc_init_transform.get_forward_vector())  # type: ignore
        )
        self.npc.enable_constant_velocity(self.npc_init_velocity)

        self.traffic_manager.random_left_lanechange_percentage(self.npc, 0)
        self.traffic_manager.update_vehicle_lights(self.npc, True)
        self.traffic_manager.random_right_lanechange_percentage(self.npc, 0)
        self.traffic_manager.ignore_lights_percentage(self.npc, 100)
        self.traffic_manager.ignore_signs_percentage(self.npc, 100)

    def set_ego_car_route(self):
        self.ego_route = [self.spawn_points[i].location for i in [205, 240, 124]]
        self.traffic_manager.set_path(self.ego, self.ego_route)  # type: ignore

    def set_npc_car_route(self):
        self.npc_route = [self.spawn_points[i].location for i in [202, 64]]
        self.traffic_manager.set_path(self.npc, self.npc_route)  # type: ignore

    def stop_npc_car(self):
        self.npc.enable_constant_velocity(carla.Vector3D(0, 0, 0))

    def record_seed_info(self):
        env_info = {
            "p_ego": self.seed.p_ego,
            "p_npc": self.seed.p_npc,
            "v_npc": self.seed.v_npc,
            "result": self.result.result,
            "loss": self.result.loss.value,
            "action_seq": self.result.action_seq,
        }
        output_dir = self.output_root_dir / f"round_{self.seed.round_num:>04d}"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(output_dir / "env_info.yml", "w") as f:
            yaml.dump(env_info, f)
            f.close()

    def init_snapshot_info_log(self):
        output_dir = os.path.join(
            self.output_root_dir, f"round_{self.seed.round_num:>04d}"
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.snapshot_file = open(os.path.join(output_dir, "snapshot_record.csv"), "w")
        self.snapshot_file.writelines(
            "frame, time, tick_num, "
            + "ego_x, ego_y, ego_z, "
            + "npc_x, npc_y, npc_z, "
            + "ego_v_x, ego_v_y, "
            + "ego_a_x, ego_a_y, "
            + "ego_throttle, ego_brake, ego_steer, ego_gear, "
            + "npc_v_x, npc_v_y, "
            + "npc_a_x, npc_a_y, "
            + "npc_throttle, npc_brake, npc_steer, npc_gear \n"
        )

    def record_snapshot_info(self, snapshot: carla.WorldSnapshot):
        timestamp = snapshot.timestamp
        ego_current_location = self.ego.get_transform().location
        npc_current_location = self.npc.get_transform().location
        ego_current_velocity = self.ego.get_velocity()
        ego_current_accelerate = self.ego.get_acceleration()
        ego_current_control: carla.VehicleControl = self.ego.get_control()
        npc_current_velocity = self.npc.get_velocity()
        npc_current_accelerate = self.npc.get_acceleration()
        npc_current_control: carla.VehicleControl = self.npc.get_control()

        snapshot_record = (
            f"{timestamp.frame - self.start_timestamp.frame}, {timestamp.elapsed_seconds - self.start_timestamp.elapsed_seconds}, {self.tick_cnt}, "  # type: ignore
            + f"{ego_current_location.x}, {ego_current_location.y}, {ego_current_location.z}, "
            + f"{npc_current_location.x}, {npc_current_location.y}, {npc_current_location.z}, "
            + f"{ego_current_velocity.x}, {ego_current_velocity.y}, "
            + f"{ego_current_accelerate.x}, {ego_current_accelerate.y}, "
            + f"{ego_current_control.throttle}, {ego_current_control.brake}, {ego_current_control.steer}, {ego_current_control.gear}, "
            + f"{npc_current_velocity.x}, {npc_current_velocity.y}, "
            + f"{npc_current_accelerate.x}, {npc_current_accelerate.y}, "
            + f"{npc_current_control.throttle}, {npc_current_control.brake}, {npc_current_control.steer}, {npc_current_control.gear} \n"
        )
        self.snapshot_file.writelines(snapshot_record)

    def record_tick(self):
        snapshot = self.world.get_snapshot()
        timestamp = snapshot.timestamp
        if self.start_timestamp is None:
            self.start_timestamp = timestamp

        ego_current_location = self.ego.get_transform().location
        npc_current_location = self.npc.get_transform().location
        self.ego_traj.append(
            (
                timestamp.elapsed_seconds - self.start_timestamp.elapsed_seconds,
                ego_current_location.x,
                ego_current_location.y,
                ego_current_location.z,
            )
        )
        self.npc_traj.append(
            (
                timestamp.elapsed_seconds - self.start_timestamp.elapsed_seconds,
                npc_current_location.x,
                npc_current_location.y,
                npc_current_location.z,
            )
        )

        self.record_snapshot_info(snapshot)

    def finish_state_judge(self):
        _END_POINT_SCOPE = 5
        _MAX_RUNTIME = 30

        snapshot = self.world.get_snapshot()
        ego_current_location = self.ego.get_transform().location
        if self.collision is not None:
            self.result.result = "collision, hit NPC"
            print(
                f"\n-- Collision, hit NPC, frame={self.collision.frame - self.start_timestamp.frame}, time={self.collision.timestamp - self.start_timestamp.elapsed_seconds}"  # type: ignore
            )
            return True
        if distance(ego_current_location, self.ego_route[-1]) <= _END_POINT_SCOPE:
            self.result.result = "arrive"
            print("\n-- arrive --")
            return True
        if (
            snapshot.timestamp.elapsed_seconds - self.start_timestamp.elapsed_seconds  # type: ignore
            >= _MAX_RUNTIME
        ):
            self.result.result = "timeout"
            print("\n-- time out --")
            return True
        return False

    def calculate_loss(self):
        if self.collision is not None:
            self.result.loss = Loss(0, 0)
            print(f"loss: {self.result.loss.value:>.4f}")
        else:
            conflict_point: Optional[Conflict_Point] = get_conflict_point(
                self.ego_traj, self.npc_traj
            )
            self.result.min_distance = calculate_min_distance(
                self.ego_traj, self.npc_traj
            )
            if conflict_point is None:
                print("No conflict")
            else:
                self.result.loss = conflict_point.loss
                self.result.conflict_point = conflict_point
                print(f"loss: {self.result.loss.value:>.4f}")

    def check_action_chain(self) -> Optional[tuple[int, str, int]]:
        for tick, action in self.seed.action_chain:
            if tick == self.tick_cnt:
                if action == "none":
                    print(f"< none action >, tick: {self.tick_cnt}")
                elif action == "acc":
                    print(
                        f"< action: accelerate >, tick: {self.tick_cnt} ~ ",
                        end="",
                        flush=True,
                    )
                    self.action_accelerate()
                    print(self.tick_cnt)
                elif action == "dec":
                    print(
                        f"< action: decelerate >, tick: {self.tick_cnt} ~ ",
                        end="",
                        flush=True,
                    )
                    self.action_decelerate()
                    print(self.tick_cnt)
                elif action == "lane":
                    if self.npc_lane_change_direction:
                        lane_change_direction = "right"
                    else:
                        lane_change_direction = "left"
                    print(
                        f"< action: lane change >, direction: {lane_change_direction}"
                    )
                    self.action_lane_change()
                elif action == "stop":
                    print(
                        f"< action: stop >, tick: {self.tick_cnt} ~ ",
                        end="",
                        flush=True,
                    )
                    self.action_stop()
                    print(self.tick_cnt)
                action_duration = self.tick_cnt - tick
                return (tick, action, action_duration)
        return None

    def random_run_action(self):
        action = random.choice(self._ACTION_OPTIONS)
        # action = self._ACTION_OPTIONS[0]
        tick = self.tick_cnt
        if action == "none":
            print(f"< none action >, tick: {self.tick_cnt}")
        elif action == "acc":
            print(
                f"-- New action, < action: accelerate >, tick: {self.tick_cnt} ~ ",
                end="",
                flush=True,
            )
            self.action_accelerate()
            print(self.tick_cnt)
        elif action == "dec":
            print(
                f"-- New action, < action: decelerate >, tick: {self.tick_cnt} ~ ",
                end="",
                flush=True,
            )
            self.action_decelerate()
            print(self.tick_cnt)
        elif action == "lane":
            if self.npc_lane_change_direction:
                lane_change_direction = "right"
            else:
                lane_change_direction = "left"
            print(
                f"-- New action, < action: lane change >, direction: {lane_change_direction}"
            )
            self.action_lane_change()
        elif action == "stop":
            print(
                f"-- New action, < action: stop >, tick: {self.tick_cnt} ~ ",
                end="",
                flush=True,
            )
            self.action_stop()
            print(self.tick_cnt)
        action_duration = self.tick_cnt - tick
        return (tick, action, action_duration)

    def world_tick(self):
        self.world.tick()
        self.record_tick()
        self.tick_cnt += 1

    def run(
        self,
        seed: Seed = Seed(),
        action_check_interval=20,
        action_odds=0.3,
    ):
        self.seed = seed
        print(self.seed)
        self.init_scenario(
            p_ego=self.seed.p_ego, p_npc=self.seed.p_npc, v_npc=self.seed.v_npc
        )

        self.world.tick()
        self.start_round()

        _ACTION_CHECK_INTERVAL = action_check_interval
        _ACTION_ODDS = action_odds
        _flag_action = False

        round_action_chain = [x for x in self.seed.action_chain]

        while True:
            self.world_tick()

            if self.finish_state_judge():
                break

            action_info = self.check_action_chain()
            if action_info is not None:
                self.result.action_seq.append(action_info)
                continue

            if (
                len(round_action_chain) < self.seed.action_capability
                and self.tick_cnt % _ACTION_CHECK_INTERVAL == 0
            ):
                if random.choices([True, False], [_ACTION_ODDS, 1 - _ACTION_ODDS])[0]:
                    action_result = self.random_run_action()
                    self.result.action_seq.append(action_result)
                    round_action_chain.append((action_result[0], action_result[1]))
                    # _flag_action = True
                    continue

        self.calculate_loss()

        print(self.result)

        self.end_round()
        return self.result

    def start_round(self):
        self.ego.set_autopilot(True)  # <-- ego's ADS
        self.npc.disable_constant_velocity()
        self.npc.set_autopilot(True)  # <-- npc's ADS

    def end_round(self):
        self.record_seed_info()

        self.ego.destroy()
        self.npc.destroy()
        self.collision_detector.destroy()
        self.snapshot_file.close()

        # self.seed.round_result = {'result': self.result, 'loss': self.loss, 'action_seq': self.action_seq}

    # _ACTION_OPTIONS = ['none', 'acc', 'dec', 'lane', 'stop']
    _ACTION_OPTIONS = ["none", "acc", "dec", "lane"]

    def action_lane_change(self):
        self.traffic_manager.force_lane_change(self.npc, self.npc_lane_change_direction)  # type: ignore
        self.npc_lane_change_direction = (self.npc_lane_change_direction + 1) % 2

    def action_accelerate(self, throttle=1, duration=10):
        self.npc.set_autopilot(False)
        npc_control = carla.VehicleControl(throttle=throttle)
        self.npc.apply_control(npc_control)
        for i in range(duration):
            self.world_tick()
        self.npc.set_autopilot(True)
        return duration

    def action_decelerate(self, brake=1, duration=10):
        self.npc.set_autopilot(False)
        npc_control = carla.VehicleControl(brake=brake)
        self.npc.apply_control(npc_control)
        for i in range(duration):
            self.world_tick()
        self.npc.set_autopilot(True)
        return duration

    def action_stop(self, duration=5):  # <-- have bug
        self.npc.set_autopilot(False)
        npc_control = carla.VehicleControl(brake=1)
        self.npc.apply_control(npc_control)
        while self.npc.get_velocity().length() > 0:
            self.world_tick()
        for i in range(duration):
            self.world_tick()
        self.npc.set_autopilot(True)

    def run_test(self):
        flag_start = False
        count = 0
        ego_init_point = 65  # <-- spawn point #65: (x: -82.602486, y: 2.750381)
        self.ego_init_transform = carla.Transform(
            location=self.spawn_points[ego_init_point].location,
            rotation=self.spawn_points[ego_init_point].rotation,
        )
        print(self.ego_init_transform)
        while True:
            self.world.tick()

            # if not flag_start:
            #     flag_start = True
            #     # self.start_round()

            # count += 1
            # if count == 20:
            #     self.action_stop()

            # for sp in self.spawn_points:
            #     self.world.tick()
            #     self.set_spectator(sp.location)
            #     time.sleep(3)
