import copy
import mujoco
import mujoco.viewer
import numpy as np
from Bezier import get_my_Bezier_point,pos_2_angle
import math
import random
import torch
import matplotlib.pyplot as plt

delta_St = np.array([0, 1, 1, 0])
dt = 0.02

para = [[[-0.00, -0.045], [0.03, 0.01]], [[-0.00, -0.045], [0.03, 0.005]], [[0.00, -0.05], [0.03, 0.01]],[[0.00, -0.05], [0.03, 0.005]]]
max_dis=0.03

class Env(object):
    def __init__(self, modelPath, max_steps=5000, view=False, rand=False):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(modelPath)  # 加载模型
        self.data = mujoco.MjData(self.model)
        self.render = view
        if self.render:
            self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
        else:
            self.viewer = None

        self.legPosName = [
            # shoulder对应front left/right leg(fl/fr)，hip对应rear left/right leg(rl/rr)；router为上方关节、foot为下方关节
            ["router_shoulder_fl", "foot_s_fl"],
            ["router_shoulder_fr", "foot_s_fr"],
            ["router_hip_rl", "foot_s_rl"],
            ["router_hip_rr", "foot_s_rr"]]
        self.fixPoint = "body_ss"  # "neck_ss"
        self.index = {"m1_fl": 0, "m2_fl": 1, "m1_fr": 2, "m2_fr": 3, "m1_rl": 4, "m2_rl": 5, "m1_rr": 6, "m2_rr": 7,
                      "m1_tail": 8,
                      "neck": 9, "head": 10, "spine": 11, "fl_t1": 12, "fr_t1": 13, "rl_t1": 14, "rr_t1": 15,
                      "com_pos": 16, "com_quat": 19, "com_vel": 23, "imu_acc": 26, "imu_gyro": 29}  # 设置传感器的序号

        self.movePath = [[], [], []]
        self.control_point_list = []
        self.pos = []
        self.linvel = []
        self.angvel = []
        self.acc = []

        self.last_pos = [0, 0, 0]
        self.last_action = 0
        self.max_steps = max_steps
        self.steps = 0
        self.ctrldata = np.array([])
        self.t=0
        self.old_ctrl=0
        self.n=0
        self.rand=rand
        self.initializing()

    def initializing(self):
        for i in range(50):
            self.data.ctrl = [0.0, 1.5, 0.0, 1.5, 0.0, -1.2, 0.0, -1.2, 0, 0, 0, 0]
            mujoco.mj_step(self.model, self.data)
            if self.render:
                self.viewer.sync()
        if self.rand:
            self.random_env()
        self.old_ctrl=0
        self.t=0
        self.steps = 0
        self.ctrldata = np.array([])
        state, pos, vel,acc = self.get_sensors()
        self.last_pos = copy.deepcopy(pos)
        self.last_action = 0
        self.n=0

        self.movePath = [[], [], []]
        self.control_point_list = []
        self.pos = []
        self.linvel = []
        self.angvel = []
        self.acc = []

        state = np.concatenate([[-1]*12, state, self.t + delta_St, [0]])

        return state


    def runStep(self, ctrlData):
        # ------------------------------------------ #
        # ID 0, 1 left-fore leg and coil
        # ID 2, 3 right-fore leg and coil
        # ID 4, 5 left-hide leg and coil
        # ID 6, 7 right-hide leg and coil
        # Note: For leg, it has [-1: front; 1: back]
        # Note: For fore coil, it has [-1: leg up; 1: leg down]
        # Note: For hide coil, it has [-1: leg down; 1: leg up]
        # ------------------------------------------ #
        # ID 08 is neck		(Horizontal)
        # ID 09 is head		(vertical)
        # ID 10 is spine	(Horizontal)  [-1: right, 1: left]
        # Note: range is [-1, 1]
        # ------------------------------------------ #

        ctrlData*=max_dis
        ctrlData[0]=ctrlData[0]-max_dis
        ctrlData[1]=(ctrlData[1]-max_dis)*1.4
        ctrlData[2]=(ctrlData[2]-max_dis)*1.5
        ctrlData[3]*=0.5
        ctrlData[4]=(ctrlData[4]+max_dis)*1.5
        ctrlData[5]=(ctrlData[5]+max_dis)*1.4
        ctrlData[6]=ctrlData[6]+max_dis
        ctrlData[7]=(ctrlData[7]+max_dis)*0.3
        ctrlData[8]=(ctrlData[8]+max_dis)*0.3
        ctrlData[9]=(ctrlData[9]+max_dis)*0.4
        ctrlData[10]=ctrlData[10]+max_dis
        ctrlData[11]=(ctrlData[11]-max_dis)*0.2

        self.old_ctrl=copy.deepcopy(ctrlData)
        old=np.array(self.data.ctrl[:8])

        for i in range(4):
            x, y, control_points = get_my_Bezier_point(ctrlData, self.t + delta_St[i])
            if i < 2:
                leg = "f"
            else:
                leg = "h"

            dx = para[i][0][0]
            dy = para[i][0][1]

            X = x + dx
            Y = y + dy

            self.data.ctrl[i * 2:(i + 1) * 2] = pos_2_angle(X, Y, leg)
        self.data.ctrl[8:]=0

        now=np.array(self.data.ctrl[:8])
        dif=np.mean(np.abs(now-old))

        mujoco.mj_step(self.model, self.data)
        self.steps+=1
        if self.render:
            self.viewer.sync()

        tData = self.data.site(self.fixPoint).xpos

        state,pos,linvel,acc = self.get_sensors()

        for i in range(3):
            self.movePath[i].append(tData[i])
        self.control_point_list.append(control_points)
        self.pos.append(pos)
        self.linvel.append(linvel)
        self.angvel.append(state[-7:-4])
        self.acc.append(acc)

        c_F=np.sum(state[:4])
        if c_F ==0:
            self.n+=1
        else:
            self.n=0

        if abs(linvel[1])<0.35:
            reward = -linvel[1] * 4
        else:
            reward = - 0.1

        self.t = (self.t + dt) % 2
        state = np.concatenate([ctrlData, state, self.t + delta_St, [reward]])

        done=False
        if self.steps >= self.max_steps:
            done = True


        self.last_pos=copy.deepcopy(pos)
        return state, reward, done, pos

    def get_sensors(self):  # 得到观测值与质心位置坐标
        sensors = self.data.sensordata
        pos = sensors[self.index["com_pos"]:self.index["com_pos"] + 3].copy()  # 位置
        acc = sensors[self.index["imu_acc"]:self.index["imu_acc"] + 3].copy()  # 加速度
        angvel = sensors[self.index["imu_gyro"]:self.index["imu_gyro"] + 3].copy()  # 角速度
        framequat = sensors[self.index["com_quat"]:self.index["com_quat"] + 4].copy() # 四元数（代替Pitch Angle（俯仰角）和Body Roll（滚转角））
        linvel = sensors[self.index["com_vel"]:self.index["com_vel"] + 3].copy()  # 线速度
        c_F = sensors[self.index["fl_t1"]:self.index["fl_t1"] + 4].copy()  # 腿部压力传感器
        state = np.concatenate([c_F, linvel, angvel, framequat])
        return state,pos,linvel,acc

    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        return self.initializing()

    def random_env(self):
        for i in range(1, 451):
            self.model.geom("box{}".format(i)).size[-1] = random.random() * 0.01

    def drawPath(self):
        ax = plt.axes(projection='3d')
        ax.plot3D(self.movePath[0], self.movePath[1], self.movePath[2])
        ax.set_xlabel('X', fontsize=16)
        ax.set_ylabel('Y', fontsize=16)
        ax.set_zlabel('Z', fontsize=16)
        plt.show()

    def write_log(self):  # 记录传感器数据
        def compute_L2(arr,digit=4):
            sum = 0
            for i in range(len(arr)):
                sum += arr[i] ** 2
                arr[i] = round(arr[i], digit)
            sum = round(math.sqrt(sum), digit)
            return sum


        f1 = open("position.txt", mode='w')
        f2 = open("linear velocity.txt", mode='w')
        f3 = open("angular velocity.txt", mode='w')
        f4 = open("acceleration.txt", mode='w')
        f5 = open("control point.txt",mode='w')
        for i in range(len(self.pos)):
            pos_scalar = compute_L2(self.pos[i])
            linvel_scalar = compute_L2(self.linvel[i])
            angvel_scalar = compute_L2(self.angvel[i])
            acc_scalar = compute_L2(self.acc[i])
            f1.writelines(str(self.pos[i]) + ":  " + str(pos_scalar) + "\n")
            f2.writelines(str(self.linvel[i]) + ":  " + str(linvel_scalar) + "\n")
            f3.writelines(str(self.angvel[i]) + ":  " + str(angvel_scalar) + "\n")
            f4.writelines(str(self.acc[i]) + ":  " + str(acc_scalar) + "\n")
            f5.writelines(str(self.control_point_list[i]) + "\n")
        f1.close()
        f2.close()
        f3.close()
        f4.close()
        f5.close()


def generate_boxes(x_min=-0.5, x_max=0.5, y_min=-3.5, y_max=1, size=0.05):
    with open("box.txt", 'w') as file:
        x = x_min
        counter = 1
        while x_max - x > 1e-6:
            y = y_min
            while y_max - y > 1e-6:
                file.write(
                    '<geom name="box{}" type="box" size="{:.3} {:.3} {:.3}" pos="{:.3} {:.3} 0" rgba="0.5 0.5 0.5 1"/> \n'.format(
                        counter, size, size, size, x, y))
                y += size * 2
                counter += 1
            x += size * 2

def quat2rm(q):
    r=np.zeros([3,3])
    r[0,0]=q[0]**2+q[1]**2-q[2]**2-q[3]**2
    r[0,1]=2*(q[1]*q[2]-q[0]*q[3])
    r[0,2]=2*(q[1]*q[3]+q[0]*q[2])
    r[1,0]=2*(q[1]*q[2]+q[0]*q[3])
    r[1,1]=q[0]**2-q[1]**2+q[2]**2-q[3]**2
    r[1,2]=2*(q[2]*q[3]-q[0]*q[1])
    r[2,0]=2*(q[1]*q[3]-q[0]*q[2])
    r[2,1]=2*(q[2]*q[3]+q[0]*q[1])
    r[2,2]=q[0]**2-q[1]**2-q[2]**2+q[3]**2
    return r

if __name__ == '__main__':
    generate_boxes()