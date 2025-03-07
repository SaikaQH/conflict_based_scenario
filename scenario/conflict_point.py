from .loss import Loss


class Conflict_Point:
    loss: Loss

    def __init__(self, ego_pass_tick=-1, obj_pass_tick=-1, loss: Loss = Loss()):
        self.ego_pass_tick = ego_pass_tick
        self.obj_pass_tick = obj_pass_tick
        self.loss = loss

    def to_basic_data(self):
        return {
            "ego_pass_tick": self.ego_pass_tick,
            "obj_pass_tick": self.obj_pass_tick,
            "loss": self.loss.to_basic_data(),
        }

    def __str__(self):
        return (
            f"     ego_pass_tick: {self.ego_pass_tick} \n"
            + f"     obj_pass_tick: {self.obj_pass_tick} \n"
            + "     loss: \n"
            + f"        time gap: {self.loss.time_gap:>.4f} \n"
            + f"        distance: {self.loss.distance:>.4f} \n"
        )


if __name__ == "__main__":
    loss = Loss(1, 1)
    cp = Conflict_Point(1, 1, loss)
    print(cp.to_basic_data())
