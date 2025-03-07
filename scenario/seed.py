from dataclasses import dataclass, field
import math
from typing import Literal, Optional

from .loss import Loss
from .conflict_point import Conflict_Point

ResultType = Literal["Error", "arrive", "collision, hit NPC", "timeout"]


@dataclass
class Round_Result:
    result: ResultType = "Error"
    loss: Loss = field(default=Loss())
    min_distance: tuple[int, float] = (-1, math.inf)
    action_seq: list[tuple[int, str, int]] = field(default_factory=list)  # type: ignore
    conflict_point: Optional[Conflict_Point] = None

    # def __init__(
    #     self,
    #     result: ResultType = "Error",
    #     loss: Loss = Loss(),
    #     action_seq: Optional[list[tuple[int, str, int]]] = None,
    #     conflict_point: Optional[Conflict_Point] = None,
    # ):
    #     self.result = result
    #     self.loss = loss
    #     self.action_seq = action_seq
    #     self.conflict_point = conflict_point

    def sort(self):
        self.action_seq.sort(key=lambda x: x[0])

    def to_basic_data(self):
        return {
            "result": self.result,
            "loss": self.loss.to_basic_data(),
            "min_distance": self.min_distance,
            "action_seq": self.action_seq,
            "conflict_point": self.conflict_point.to_basic_data()
            if self.conflict_point is not None
            else None,
        }

    def __str__(self):
        round_result_str = ""
        action_seq_str = ""
        for action in self.action_seq:
            action_seq_str += (
                f"     tick: {action[0]}, action: {action[1]}, duration: {action[2]} \n"
            )
        conflict_point_str = ""
        if self.conflict_point is not None:
            conflict_point_str += self.conflict_point.__str__()
        round_result_str += (
            f"\n   result: -- < {self.result} > -- \n"
            + f"   loss: {self.loss.value:>.4f} \n"
            + f"   min_distance: {self.min_distance[0]}, {self.min_distance[1]:>.4f} \n"
            + "   action seq: \n"
            + action_seq_str
            + "   conflict point: \n"
            + conflict_point_str
        )
        return round_result_str


class Seed:
    round_num: int
    p_ego: Optional[float]
    p_npc: Optional[float]
    v_npc: Optional[float]
    action_capability: int
    action_chain: list[tuple[int, str]]
    round_result: Optional[Round_Result]
    last_loss: tuple[int, float]

    def __init__(
        self,
        round_num: int = 0,
        p_ego: Optional[float] = None,
        p_npc: Optional[float] = None,
        v_npc: Optional[float] = None,
        action_capability: int = 0,
        action_chain: list[tuple[int, str]] = list(),
        round_result: Optional[Round_Result] = None,
        last_loss: tuple[int, float] = (-1, math.inf)
    ):
        self.round_num = round_num
        self.p_ego = p_ego  # 0~10
        self.p_npc = p_npc  # 0~10
        self.v_npc = v_npc  # 0~60
        self.action_capability = action_capability
        self.action_chain = [x for x in action_chain]
        self.round_result = round_result
        self.last_loss = last_loss

    def sort(self):
        self.action_chain.sort(key=lambda x: x[0])
        if self.round_result is not None:
            self.round_result.sort()

    def update(self):
        print(" ---- update seed ----")
        if self.round_result is None:
            print(" -- < no result seq > ")
            return False
        else:
            for action_result in self.round_result.action_seq:
                # print(action_result)
                new_action = (action_result[0], action_result[1])
                if new_action in self.action_chain:
                    print(f"   <{new_action}> already recorded")
                else:
                    print(f"   <{new_action}> updated")
                    self.action_chain.append(new_action)
            self.sort()
            self.clean_result()

    def update_and_gen_seed(self, round_num):
        new_seed = Seed(
            round_num=round_num,
            p_ego=self.p_ego,
            p_npc=self.p_npc,
            v_npc=self.v_npc,
            action_capability=self.action_capability + 1,
            action_chain=[],
        )
        assert self.round_result is not None
        for action_result in self.round_result.action_seq:
            if (action_result[0], action_result[1]) not in new_seed.action_chain:
                new_seed.action_chain.append((action_result[0], action_result[1]))
        # new_seed.round_result = self.round_result
        new_seed.sort()
        return new_seed

    def clean_result(self):
        self.round_result = None

    def to_basic_data(self):
        return {
            "round_num": self.round_num,
            "p_ego": self.p_ego,
            "p_npc": self.p_npc,
            "v_npc": self.v_npc,
            "action_cap": self.action_capability,
            "action_chain": self.action_chain,
            "round_result": self.round_result.to_basic_data()
            if self.round_result is not None
            else None,
        }
    
    def recover_from_basic_data(self):
        ...

    def __str__(self):
        action_chain_str = ""
        for action in self.action_chain:
            action_chain_str += f"     tick: {action[0]}, action: {action[1]} \n"

        round_result_str = ""
        if self.round_result is not None:
            round_result_str += self.round_result.__str__()

        return (
            f" ------------ Round {self.round_num:>4d} ------------ \n"
            + f"   p_ego: {self.p_ego} \n"
            + f"   p_npc: {self.p_npc} \n"
            + f"   v_npc: {self.v_npc} \n"
            + f"   action_cap: {self.action_capability} \n"
            + f"   action_chain: {len(self.action_chain)} \n"
            + action_chain_str
            + round_result_str
            + " ------------------------------------"
        )


if __name__ == "__main__":
    seed = Seed(0, 0, 0, 20, 2, [(200, "acc"), (250, "dec")])
    print(seed.to_basic_data())
    # result = Round_Result(action_seq=[(1, "aaa", 20)])
    # print(result.to_basic_data())
    # result = Round_Result()
    # print(result)
