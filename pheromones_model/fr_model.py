import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from channels import ChannelEnvironment

#phi_step = np.pi / CHANNEL_HL  # 26 body length opposite side - figS3A
# 1 step 0.5 s, 1 BL

FLY_EATING_TIME = 10

# run lengths distributions parameters
RL_mean = 4.125
RL_std = 2.625
dRL_mean = 0.03125
dRL_std = 1.875


class MyFlyFR:
    def __init__(self, myenv: ChannelEnvironment = None):
        self.eating_time = FLY_EATING_TIME
        if myenv is None:
            self.environment = ChannelEnvironment()
        else:
            self.environment = myenv
        self.t = 0
        self.phi_step = np.pi / self.environment.channel_hl  # 1 body length step in radians depending on channel length
        # mind
        self.state = 'walking'  # or eating
        self.mode = 'GS'  # or LS
        self.direction = 1  # or -1
        self.last_state = None
        self.integrator_x = 0
        self.integrator_y = 0

        self.current_run = 0  # distance integrator

        # env
        self.coord_x = 0
        self.coord_y = 0
        self.coord_phi = - 8 * self.phi_step

        # log to save history, for plotting
        self.t_log = [0]
        self.phi_log = [self.coord_phi]
        self.eat_log=[False]
        self.direction_log=[self.direction]

    def log(self, eating=False):
        self.t_log.append(self.t)
        self.phi_log.append(self.coord_phi)
        self.eat_log.append(eating)
        self.direction_log.append(self.direction)

    def make_step(self, direction):
        self.t += 1
        d_angle = self.phi_step * direction
        self.coord_phi += d_angle
        self.coord_x = np.cos(self.coord_phi)
        self.coord_y = np.sin(self.coord_phi)
        dx = np.cos(d_angle)
        dy = np.sin(d_angle)
        self.integrator_x += dx
        self.integrator_y += dy
        self.current_run += np.sqrt(dx ** 2 + dy ** 2)

        self.log()

        # index of food the fly is on at the moment, None if not on an active food
        am_on_food = self.environment.update(self.coord_phi, self.t)
        if am_on_food is not None:
            self.on_food(am_on_food)

    def plot_angle_history(self, ax=None):
        if ax is None:
            ax = plt.gca()
        ax.plot(self.t_log, self.phi_log, '.-')

    def plot_trajectory(self, ax=None):
        if ax is None:
            ax = plt.gca()

        angles = np.array(self.phi_log)
        xx = np.cos(angles)
        yy = np.sin(angles)
        ax.plot(xx, yy)
        ax.axis('equal')

    def on_food(self, food_index):
        # print(self.t, " - fly on food!")
        self.mode = 'LS'  # enter the local search mode

        # remember the eating state
        self.last_state = 'eating'

        # disable food source for refractory period
        self.environment.disable_food(food_index, refractory=True)

        # stay on food location for a while
        self.eat()

        self.zero_integrator()
        self.choose_run_length()

    def eat(self):
        # do nothing for self.eating time (only update the environment based on current time)
        for t in range(self.eating_time):
            self.t += 1
            # update log at every step
            self.log(eating=True)
            # update environment
            # print('fly eating', self.t)
            self.environment.update(self.coord_phi, self.t)

    def choose_run_length(self):
        # if just was on food
        if self.last_state == 'eating':
            self.run_length = np.random.normal(RL_mean, RL_std) + self.current_run
        elif self.last_state == 'reversal':
            self.run_length = np.abs(self.current_run + np.random.normal(dRL_mean, dRL_std))
        print(f"Prev: {self.last_state}, current run: {self.current_run}, RL:{self.run_length}")

    def zero_integrator(self):
        self.integrator_x = 0
        self.integrator_y = 0
        self.current_run = 0

    def start_walking(self, Tlim=500):
        while self.mode == "GS":
            self.make_step(self.direction)
        if self.mode == 'LS':
            while self.t < Tlim:
                # print(f"{self.t} | run: {self.current_run}")
                self.make_step(self.direction)
                if self.current_run >= self.run_length:
                    self.reversal()

    def reversal(self):
        self.direction *= -1
        self.choose_run_length()
        self.zero_integrator()
        self.last_state = 'reversal'

    def get_df(self):
        df = pd.DataFrame(dict(t=self.t_log, angle=self.phi_log,
                                 eating=self.eat_log, direction=self.direction_log))
        run_num = df.direction.diff().abs()/2
        df["run_num"] = run_num.cumsum()
        df.loc[0, "run_num"] = 0
        df.run_num = df.run_num - df[df.eating].iloc[-1].run_num - 1
        return df


def plot_story(fly_df, food_log, ax_fly=None, ax_food=None):
    if ax_fly is None:
        f, ax_fly = plt.subplots()
    if ax_food is None:
        ax_food = ax_fly

    ax_fly.plot(fly_df.t, fly_df.angle, '.-')
    ax_fly.plot(fly_df[fly_df.eating].t, fly_df[fly_df.eating].angle, '.', color='red')
    if "smelling" in fly_df.columns:
        ax_fly.plot(fly_df[fly_df.smelling].t, fly_df[fly_df.smelling].angle, '.', color='cyan')

    t = np.array(food_log["t"])
    for foodid in food_log.keys():
        if foodid != "t":
            curfood = np.array(food_log[foodid])
            ax_food.plot(t, curfood + foodid, label=str(foodid))
    ax_food.legend()
    # foodid = 0
    # ax_food.plot(food_log["t"], food_log[foodid])


if __name__ == '__main__':
    dfs = []
    n_simulations = 300
    for i in range(n_simulations):
        channel = ChannelEnvironment(enable_food_time=5, disable_food_time=300 * 2)
        fly = MyFlyFR(channel)
        fly.start_walking(Tlim=600*2)
        # fly.plot_angle_history()
        # plt.plot(fly.environment.food_log["t"], fly.environment.food_log[0])
        # plt.show()
        flydf = fly.get_df()
        flydf["flyid"] = i
        dfs.append(flydf)

    df = pd.concat(dfs, ignore_index=True)
    print(df.shape)
    df.to_csv("fr_simulations.csv", index=False)
