from pathlib import Path
import random
import yaml

from scenario import Scenario
from scenario import Scenario_case00 as case00
from scenario import Scenario_case04 as case04
from scenario import Scenario_case06 as case06
from scenario.conflict_point import Conflict_Point
from scenario.loss import Loss
from scenario.seed import Seed, Round_Result

_P_EGO_RANGE = (0, 10)
_P_NPC_RANGE = (0, 10)
_V_NPC_RANGE = (0, 60)

_D_P_EGO = 1
_D_P_NPC = 1
_D_V_NPC = 4

_LR = 0.2


def gen_seed_list() -> list[Seed]:
    print("generate initial seed ... ", end="", flush=True)
    seed_list: list[Seed] = []
    p_ego_list = [
        x / 10
        for x in range(
            int((_P_EGO_RANGE[0] + _D_P_EGO) * 10 / 2),
            int(_P_EGO_RANGE[1] * 10),
            _D_P_EGO * 10,
        )
    ]
    p_npc_list = [
        x / 10
        for x in range(
            int((_P_NPC_RANGE[0] + _D_P_NPC) * 10 / 2),
            int(_P_NPC_RANGE[1] * 10),
            _D_P_NPC * 10,
        )
    ]
    v_npc_list = [
        x / 10
        for x in range(
            int((_V_NPC_RANGE[0] + _D_V_NPC) * 10 / 2),
            int(_V_NPC_RANGE[1] * 10),
            _D_V_NPC * 10,
        )
    ]
    for p_ego in p_ego_list:
        for p_npc in p_npc_list:
            for v_npc in v_npc_list:
                seed_list.append(
                    Seed(
                        round_num=-1,
                        p_ego=p_ego,
                        p_npc=p_npc,
                        v_npc=v_npc,
                        action_capability=0,
                        action_chain=[],
                    )
                )
    # for v_npc in v_npc_list:
    #     seed_list.append(
    #         Seed(
    #             round_num=len(seed_list),
    #             p_ego=0,
    #             p_npc=0,
    #             v_npc=v_npc,
    #             action_capability=0,
    #             action_chain=[],
    #         )
    #     )
    print("Done")
    return seed_list


def update_range(new_range, old_range):
    l = new_range[0] if new_range[0] > old_range[0] else old_range[0]
    r = new_range[1] if new_range[1] < old_range[1] else old_range[1]
    return (l, r)


def gen_new_seed(seed: Seed, round_no) -> Seed:
    p_ego = seed.p_ego
    p_npc = seed.p_npc
    v_npc = seed.v_npc
    assert p_ego is not None
    assert p_npc is not None
    assert v_npc is not None
    p_ego_range = (p_ego - _D_P_EGO / 2, p_ego + _D_P_EGO / 2)
    p_npc_range = (p_npc - _D_P_NPC / 2, p_npc + _D_P_NPC / 2)
    v_npc_range = (v_npc - _D_V_NPC / 2, v_npc + _D_V_NPC / 2)

    new_p_ego_range = update_range(
        (p_ego - _D_P_EGO * _LR * 0.5, p_ego + _D_P_EGO * _LR * 0.5), p_ego_range
    )
    new_p_ego = random.uniform(new_p_ego_range[0], new_p_ego_range[1])

    new_p_npc_range = update_range(
        (p_npc - _D_P_NPC * _LR * 0.5, p_npc + _D_P_NPC * _LR * 0.5), p_npc_range
    )
    new_p_npc = random.uniform(new_p_npc_range[0], new_p_npc_range[1])

    new_v_npc_range = update_range(
        (v_npc - _D_V_NPC * _LR * 0.5, v_npc + _D_V_NPC * _LR * 0.5), v_npc_range
    )
    new_v_npc = random.uniform(new_v_npc_range[0], new_v_npc_range[1])

    new_seed: Seed = Seed(
        round_num=round_no,
        p_ego=new_p_ego,
        p_npc=new_p_npc,
        v_npc=new_v_npc,
        action_capability=seed.action_capability + 1,
        action_chain=seed.action_chain,
    )

    return new_seed


def fuzzing(seed):
    global round_cnt
    global collision_seed_list
    global other_seed_list

    last_seed = seed
    fuzzing_round = 0
    while fuzzing_round < _SEED_FUZZING_MAX_ITER:
        new_seed: Seed = gen_new_seed(last_seed, round_cnt)
        round_cnt += 1
        fuzzing_round += 1

        assert last_seed.round_result is not None
        if last_seed.round_result.conflict_point is not None:
            conflict_point: Conflict_Point = last_seed.round_result.conflict_point
            # if new_seed.action_capability <= len(new_seed.action_chain):
            #     pass
            if conflict_point.ego_pass_tick < conflict_point.obj_pass_tick:
                new_seed.action_chain.append(
                    (
                        int(random.randint(0, conflict_point.ego_pass_tick) / 10) * 10,
                        "acc",
                    )
                )
            else:
                new_seed.action_chain.append(
                    (
                        int(random.randint(0, conflict_point.obj_pass_tick) / 10) * 10,
                        "dec",
                    )
                )

        new_seed.round_result = scene.run(new_seed)
        if new_seed.round_result.result == "collision, hit NPC":
            print(f"Found collision, round: {round_cnt}")
            collision_seed_list.append(new_seed)
            return "collision"

        other_seed_list.append(new_seed)
        if new_seed.round_result.loss.value < last_seed.round_result.loss.value:
            last_seed = new_seed

        if round_cnt >= _TOTAL_ROUND:
            return "not found collision, max round"

    return "not found collision, max fuzzing"


def record_seed(init_seed_list: list[Seed]):
    collision_record = {}
    for seed in collision_seed_list:
        collision_record[f"{seed.round_num}"] = {
            "p_ego": seed.p_ego,
            "p_npc": seed.p_npc,
            "v_npc": seed.v_npc,
            "action_chain": seed.action_chain,
            "result": seed.round_result,
        }
    with open(_META_RESULT_DIR / "collision_seed.yml", "w") as f:
        yaml.dump(collision_record, f)
        f.close()

    other_record = {}
    for seed in other_seed_list:
        other_record[f"{seed.round_num}"] = {
            "p_ego": seed.p_ego,
            "p_npc": seed.p_npc,
            "v_npc": seed.v_npc,
            "action_chain": seed.action_chain,
            "result": seed.round_result,
        }
    with open(_META_RESULT_DIR / "other_seed.yml", "w") as f:
        yaml.dump(other_record, f)
        f.close()

    init_record = {}
    for seed in init_seed_list:
        init_record[f"{seed.round_num}"] = {
            "p_ego": seed.p_ego,
            "p_npc": seed.p_npc,
            "v_npc": seed.v_npc,
            "action_chain": seed.action_chain,
            "result": seed.round_result,
        }
    with open(_META_RESULT_DIR / "init_seed.yml", "w") as f:
        yaml.dump(init_record, f)
        f.close()


def record_init_seed(init_seed_list: list[Seed]):
    init_record = {}
    seed_order_record = []
    for seed in init_seed_list:
        init_record[f"{seed.round_num}"] = seed.to_basic_data()
        seed_order_record.append(seed.round_num)
    with open(_META_RESULT_DIR / "init_seed_result.yml", "w") as f:
        yaml.dump(init_record, f)
        f.close()
    with open(_META_RESULT_DIR / "init_seed_order.yml", "w") as f:
        yaml.dump(seed_order_record, f)
        f.close()


def recover_init_seed() -> list[Seed]:
    with open(_META_RESULT_DIR / "init_seed_order.yml", "r") as f:
        seed_order_record = yaml.load(f, yaml.FullLoader)
        f.close()
    with open(_META_RESULT_DIR / "init_seed_result.yml", "r") as f:
        seed_list = yaml.load(f, yaml.FullLoader)
        f.close()
    init_seed_list: list[Seed] = []

    print("recovering ... ", end='', flush=True)
    for seed_name in seed_list:
        seed = seed_list[seed_name]
        if seed["round_result"] is not None:
            if seed["round_result"]["conflict_point"] is not None:
                cp = Conflict_Point(
                    ego_pass_tick=seed["round_result"]["conflict_point"][
                        "ego_pass_tick"
                    ],
                    obj_pass_tick=seed["round_result"]["conflict_point"][
                        "obj_pass_tick"
                    ],
                    loss=Loss(
                        time_gap=seed["round_result"]["conflict_point"]["loss"]["time_gap"],
                        distance=seed["round_result"]["conflict_point"]["loss"]["distance"],
                    ),
                )
            else:
                cp = None
            round_result = Round_Result(
                result=seed["round_result"]["result"],
                loss=Loss(
                    time_gap=seed["round_result"]["loss"]["time_gap"],
                    distance=seed["round_result"]["loss"]["distance"],
                ),
                action_seq=seed["round_result"]["action_seq"],
                conflict_point=cp,
            )
        else:
            round_result = None
        init_seed_list.append(
            Seed(
                round_num=seed["round_num"],
                p_ego=seed["p_ego"],
                p_npc=seed["p_npc"],
                v_npc=seed["v_npc"],
                action_capability=seed["action_cap"],
                action_chain=seed["action_chain"],
                round_result=round_result,
            )
        )
    print("Done")

    return init_seed_list


def record_state(round_cnt, seed_no):
    state = {"current_round": round_cnt, "current_seed": seed_no}
    with open(_META_RESULT_DIR / "current_state.yml", "w") as f:
        yaml.dump(state, f)
        f.close()


def restore_state():
    with open(_META_RESULT_DIR / "current_state.yml", "r") as f:
        state = yaml.load(f, yaml.FullLoader)
        f.close()
    return state["current_round"], state["current_seed"]


scenario_type = "town05_case06"
_HOST = "localhost"
_PORT = 2000
_WORLD_MAP = "Town05"
_META_RESULT_DIR = Path(f"./result_{scenario_type}/loss_time_gap_with_guiding")
_OUTPUT_ROOT_DIR = _META_RESULT_DIR / "result"

_TOTAL_ROUND = 10000
_SEED_FUZZING_MAX_ITER = 50

round_cnt = 0
collision_seed_list: list[Seed] = []
other_seed_list: list[Seed] = []

if __name__ == "__main__":
    scene: Scenario
    if scenario_type == "town05_case04":
        scene = case04(_HOST, _PORT, _WORLD_MAP, _OUTPUT_ROOT_DIR)
    elif scenario_type == "town05_case06":
        scene = case06(_HOST, _PORT, _WORLD_MAP, _OUTPUT_ROOT_DIR)
    elif scenario_type == "town05_case00":
        scene = case00(_HOST, _PORT, _WORLD_MAP, _OUTPUT_ROOT_DIR)

    if not (_META_RESULT_DIR / "init_seed_result.yml").exists():
        seed_list = gen_seed_list()
        runned_seed_list: list[Seed] = []
        # seed_list = [Seed(0, 0, 4, 2)]
        for seed in seed_list:
            seed.round_num = round_cnt
            round_cnt += 1
            seed.round_result = scene.run(seed=seed)
            if seed.round_result.result == "collision, hit NPC":
                collision_seed_list.append(seed)
            else:
                runned_seed_list.append(seed)

        runned_seed_list.sort(key=lambda x: x.round_result.loss.value)  # type: ignore
        record_init_seed(runned_seed_list)
    else:
        runned_seed_list = recover_init_seed()

    if (_META_RESULT_DIR / "current_state.yml").exists():
        round_cnt, current_seed_no = restore_state()
    else:
        round_cnt = len(runned_seed_list)
        current_seed_no = 0

    for i in range(len(runned_seed_list)):
        if i < current_seed_no:
            continue

        seed = runned_seed_list[i]
        record_state(round_cnt, i)
        fuzzing_result = fuzzing(seed)
        print(fuzzing_result)
        print(f"Collision seed: {len(collision_seed_list)}")
        print(f"Other seed: {len(other_seed_list)}")

        if round_cnt > _TOTAL_ROUND:
            break

    record_seed(runned_seed_list)
