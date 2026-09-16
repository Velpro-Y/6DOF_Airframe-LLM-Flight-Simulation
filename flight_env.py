"""
=========================================================
Flight Environment

负责：

1. reset()
2. step()
3. get_state()

=========================================================
"""

import os
import logging

from config import *
from matlab_engine import get_engine

import csv


logger = logging.getLogger(__name__)


class FlightEnv:

    def __init__(self):

        self.eng = get_engine()

        self.model = MODEL_NAME
        self.state_file = str(STATE_FILE)
        self.time = 0
        self.current_altitude = DEFAULT_STATE["AltitudeMSL"]
        self.last_altitude = DEFAULT_STATE["AltitudeMSL"]
        self.target_altitude = DEFAULT_STATE["AltitudeMSL"]  # 复飞爬升的目标高度
        # 是否已经发生左发失效
        self.left_engine_fail = False
        self.engine_out_time = 0.0
        self._reset_single_engine_stabilizer()
        self.log_file = LOG_FILE


        # 创建目录
        # STATE_DIR.mkdir(exist_ok=True)
        LOG_DIR.mkdir(exist_ok=True)

    # =====================================================
    # Reset
    # =====================================================

    def reset(self):

        logger.info("Reset Flight Environment")

        self.time = 0
        self.last_altitude = DEFAULT_STATE["AltitudeMSL"]
        self.current_altitude = DEFAULT_STATE["AltitudeMSL"]
        self.left_engine_fail = False
        self.engine_out_time = 0.0
        self._reset_single_engine_stabilizer()

        # 初始化/清空历史日志并写入表头
        with open(self.log_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time", "altitude", "airspeed", "vertical_speed", "roll",
                "pitch", "roll_rate", "pitch_rate", "yaw_rate", "event",
                "aileron", "elevator", "rudder", "throttle_left",
                "throttle_right"
            ])

        logger.info(f"Current Working Directory: {os.getcwd()}")
        logger.info(f"State File: {self.state_file}")
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

        # 清除上一轮 Simulink 状态
        self.eng.eval("""
                clear xFinal simIn simOut;
                """, nargout=0)

        logger.info("Environment Ready")

        initial_state = self.get_state()

        return {
            "done": False,
            "event": "RESET",
            "instruction": "Aircraft initialized successfully. Begin steady descent to 91.4 m (300 ft).",
            "state": initial_state
        }
    # =====================================================
    # Step
    # =====================================================

    def step(self, action: dict):

        logger.info(f"Receive Action : {action}")

        event = "NORMAL"
        instruction = "Maintain stable descent."

        # -------------------------
        #  控制限幅与左发强制切断
        # -------------------------
        aileron = max(ACTION_LIMIT["aileron"][0], min(ACTION_LIMIT["aileron"][1], action["aileron"]))
        elevator = max(ACTION_LIMIT["elevator"][0], min(ACTION_LIMIT["elevator"][1], action["elevator"]))
        rudder = max(ACTION_LIMIT["rudder"][0], min(ACTION_LIMIT["rudder"][1], action["rudder"]))

        # 如果左发失效，强制覆盖左油门为 0.0，否则使用传入动作
        if self.left_engine_fail:
            throttle_left = 0.0
        else:
            throttle_left = max(ACTION_LIMIT["throttle"][0], min(ACTION_LIMIT["throttle"][1], action["throttle_left"]))

        throttle_right = max(ACTION_LIMIT["throttle"][0], min(ACTION_LIMIT["throttle"][1], action["throttle_right"]))

        # 单发状态使用经过 MATLAB 时域验证的低层增稳器。智能体负责
        # 场景决策；增稳器负责抑制 1 Hz 控制延迟引起的滚转/偏航发散。
        engine_out_active_at_step_start = self.left_engine_fail
        if engine_out_active_at_step_start:
            state_before_step = self.get_state()
            stabilized = self._single_engine_stabilizer(state_before_step)
            aileron = stabilized["aileron"]
            elevator = stabilized["elevator"]
            rudder = stabilized["rudder"]
            throttle_left = 0.0
            throttle_right = stabilized["throttle_right"]
            logger.info(f"Single-engine stabilizer applied: {stabilized}")

        # -------------------------
        # 左发失效
        # -------------------------
        if self.left_engine_fail:
            throttle_left = 0.0

        # -------------------------
        # 1. 计算这一步的起始时间和停止时间
        # -------------------------
        start_time = self.time
        next_stop_time = self.time + STEP_TIME

        # -------------------------
        # 2. 核心修复代码：注入控制量 + 严格指定仿真时间区间 [start_time, next_stop_time]
        # -------------------------
        self.eng.workspace['AileronCmd'] = float(aileron)
        self.eng.workspace['ElevatorCmd'] = float(elevator)
        self.eng.workspace['RudderCmd'] = float(rudder)
        self.eng.workspace['Throttle_Left'] = float(throttle_left)
        self.eng.workspace['Throttle_Right'] = float(throttle_right)

        sim_prep_cmds = (
            f"simIn = Simulink.SimulationInput('{self.model}'); "
            f"simIn = simIn.setModelParameter('StartTime', '{start_time}'); "  # 👈 必须指定 StartTime!
            f"simIn = simIn.setModelParameter('StopTime', '{next_stop_time}'); "
            f"simIn = simIn.setVariable('AileronCmd', {float(aileron)}); "
            f"simIn = simIn.setVariable('ElevatorCmd', {float(elevator)}); "
            f"simIn = simIn.setVariable('RudderCmd', {float(rudder)}); "
            f"simIn = simIn.setVariable('Throttle_Left', {float(throttle_left)}); "
            f"simIn = simIn.setVariable('Throttle_Right', {float(throttle_right)}); "
        )
        self.eng.eval(sim_prep_cmds, nargout=0)

        # -------------------------
        # 3. 如果存在上一时刻状态，载入 xFinal 作为当前 step 的 InitialState
        # -------------------------
        if os.path.exists(self.state_file):
            self.eng.eval(
                f"load('{self.state_file}', 'xFinal'); "
                # f"simIn = simIn.setModelParameter('LoadInitialState', 'on'); "  # 👈 强制开启标志位
                f"simIn = simIn.setInitialState(xFinal);",
                nargout=0
            )

        self.last_altitude = self.current_altitude
        # -------------------------
        # 4. 执行单步仿真并保存最新的 xFinal 状态
        # -------------------------
        sim_run_cmds = (
            "simOut = sim(simIn); "
            "xFinal = simOut.xFinal; "
            f"save('{self.state_file}', 'xFinal');"
        )
        self.eng.eval(sim_run_cmds, nargout=0)

        # -------------------------
        # 5. 仿真成功后，Python 侧时间戳跟随累计
        # -------------------------
        self.time = next_stop_time
        if engine_out_active_at_step_start:
            self.engine_out_time += STEP_TIME
        state = self.get_state()
        self.current_altitude = state["altitude"]
        # 触发条件：未曾失效 且 高度下降到 91.4 米（300 英尺）以下
        if (not self.left_engine_fail) and (state["altitude"] <= 91.4):
            self.left_engine_fail = True
            self.engine_out_time = 0.0
            self._reset_single_engine_stabilizer()
            event = "LEFT_ENGINE_FAILURE"
            instruction = (
                "🚨 EMERGENCY: LEFT ENGINE FAILURE TRIGGERED AT 91.4m!\n"
                "Mandatory Action: Set throttle_left = 0.0 and initiate the "
                "single-engine go-around. The internal stabilizer will schedule "
                "right-engine thrust and coordinate rudder/aileron from measured rates."
            )
        elif self.left_engine_fail:
            event = "SINGLE_ENGINE_GO_AROUND"
            instruction = (
                "Executing single-engine go-around. Do not fight the internal "
                "rate-feedback stabilizer; climb steadily towards 152.4 m."
            )

        # -------------------------
        # 6. 获取最新状态与记录
        # -------------------------
        state = self.get_state()
        try:
            with open(self.log_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    round(self.time, 2),
                    round(state["altitude"], 2),
                    round(state["airspeed"], 2),
                    round(state["vertical_speed"], 2),
                    round(state["roll"], 5),
                    round(state["pitch"], 5),
                    round(state["roll_rate"], 5),
                    round(state["pitch_rate"], 5),
                    round(state["yaw_rate"], 5),
                    event,
                    round(aileron, 6),
                    round(elevator, 6),
                    round(rudder, 6),
                    round(throttle_left, 6),
                    round(throttle_right, 6)
                ])
        except Exception as e:
            logger.error(f"Failed to write telemetry log: {e}")

        # -------------------------
        # 6. 完成判定 (Done Condition)
        # -------------------------
        # 任务成功：处于复飞阶段 且 高度重新爬升回到 152.4 米以上
        done = self.left_engine_fail and (state["altitude"] >= self.target_altitude)

        if done:
            event = "GO_AROUND_SUCCESS"
            instruction = "Go-around successful! Target altitude reached on single engine."

        return {
            "done": done,
            "event": event,
            "instruction": instruction,
            "state": state
        }

    # =====================================================
    # 单发低层增稳器
    # =====================================================

    @staticmethod
    def _clamp(value, lower, upper):
        return min(max(value, lower), upper)

    def _reset_single_engine_stabilizer(self):
        self._se_previous_aileron = -0.019551264426
        self._se_previous_elevator = -0.0109658218634
        self._se_previous_rudder = -0.299092570837
        self._se_previous_throttle = 0.614702877432

    def _single_engine_stabilizer(self, state):
        """Return rate-limited single-engine controls for the current state.

        The control signs and the lateral control-effectiveness matrix were
        measured directly in Simulink around the engine-out trim point.
        """
        blend = self._clamp(self.engine_out_time / 6.0, 0.0, 1.0)

        descent_roll = 0.0136160413039
        engine_out_roll = 0.0848432053851
        descent_pitch = 0.0647610681203
        engine_out_pitch = 0.162303204528
        target_roll = descent_roll + blend * (engine_out_roll - descent_roll)
        target_pitch_nominal = (
            descent_pitch + blend * (engine_out_pitch - descent_pitch)
        )
        target_vertical_speed = -3.0 + blend * 4.5

        # Local measured one-second control effectiveness:
        # [dp] = [-0.923  -1.033] [d_aileron]
        # [dr]   [ 0.543  -1.796] [d_rudder ]
        roll_error = state["roll"] - target_roll
        p_command = self._clamp(-1.20 * roll_error, -0.12, 0.12)
        delta_p = 1.40 * (p_command - state["roll_rate"])
        delta_r = 1.40 * (0.0 - state["yaw_rate"])
        delta_aileron = (-1.7955 * delta_p + 1.033 * delta_r) / 2.217
        delta_rudder = (-0.5425 * delta_p - 0.923 * delta_r) / 2.217

        raw_aileron = self._clamp(
            -0.019551264426 + delta_aileron, -0.25, 0.25
        )
        raw_rudder = self._clamp(
            -0.299092570837 + delta_rudder, -0.50, 0.15
        )
        aileron = self._clamp(
            raw_aileron,
            self._se_previous_aileron - 0.04,
            self._se_previous_aileron + 0.04,
        )
        rudder = self._clamp(
            raw_rudder,
            self._se_previous_rudder - 0.05,
            self._se_previous_rudder + 0.05,
        )

        target_pitch = (
            target_pitch_nominal
            + 0.025 * (target_vertical_speed - state["vertical_speed"])
            + 0.010 * (45.4 - state["airspeed"])
        )
        target_pitch = self._clamp(target_pitch, 0.04, 0.21)
        q_command = self._clamp(
            0.65 * (target_pitch - state["pitch"]), -0.08, 0.08
        )
        raw_elevator = self._clamp(
            -0.00965061067912
            - 0.34 * (q_command - state["pitch_rate"]),
            -0.05,
            0.03,
        )
        elevator = self._clamp(
            raw_elevator,
            self._se_previous_elevator - 0.012,
            self._se_previous_elevator + 0.012,
        )

        raw_throttle = self._clamp(
            0.614702877432
            + 0.020 * (45.4 - state["airspeed"])
            + 0.012 * (target_vertical_speed - state["vertical_speed"]),
            0.45,
            0.78,
        )
        throttle_right = self._clamp(
            raw_throttle,
            self._se_previous_throttle - 0.06,
            self._se_previous_throttle + 0.06,
        )

        self._se_previous_aileron = aileron
        self._se_previous_elevator = elevator
        self._se_previous_rudder = rudder
        self._se_previous_throttle = throttle_right

        return {
            "aileron": aileron,
            "elevator": elevator,
            "rudder": rudder,
            "throttle_left": 0.0,
            "throttle_right": throttle_right,
            "target_roll": target_roll,
            "target_vertical_speed": target_vertical_speed,
        }

    # =====================================================
    # 获取飞机状态
    # =====================================================

    def get_state(self):
        # 1. 检查 simOut 是否存在
        is_exist = self.eng.eval("exist('simOut', 'var')", nargout=1)

        # 预定义一套完整的默认/初始状态字典（防止 KeyError）
        default_state = {
            "status": "reset",
            "time": self.time,
            "altitude": 152.4,
            "airspeed": 45.3883,  # 双发 -3 m/s 稳定下降配平空速
            "vertical_speed": -3.0,
            "roll": 0.01361604013039,
            "pitch": 0.0647610681203,
            "yaw": 0.0,
            "roll_rate": 0.0,
            "pitch_rate": 0.0,
            "yaw_rate": 0.0,
            "left_engine_fail": self.left_engine_fail,
            "flight_phase": "DESCENT" if not self.left_engine_fail else "GO_AROUND"
        }

        if is_exist == 0:
            self.last_altitude = DEFAULT_STATE["AltitudeMSL"]  # 恢复初始高度记录
            return default_state
        ze = float(self.eng.eval("simOut.Ze.Data(end)"))

        u = float(self.eng.eval("simOut.u.Data(end)"))
        v = float(self.eng.eval("simOut.v.Data(end)"))
        w = float(self.eng.eval("simOut.w.Data(end)"))

        phi = float(self.eng.eval("simOut.phi.Data(end)"))
        theta = float(self.eng.eval("simOut.theta.Data(end)"))
        psi = float(self.eng.eval("simOut.psi.Data(end)"))

        p = float(self.eng.eval("simOut.p.Data(end)"))
        q = float(self.eng.eval("simOut.q.Data(end)"))
        r = float(self.eng.eval("simOut.r.Data(end)"))

        altitude = -ze

        airspeed = (u ** 2 + v ** 2 + w ** 2) ** 0.5
        actual_vertical_speed = (self.current_altitude - self.last_altitude) / STEP_TIME
        logger.info(f"Actual vertical speed: {actual_vertical_speed}")
        return {

            "time": self.time,

            "altitude": altitude,

            "airspeed": airspeed,

            "vertical_speed": actual_vertical_speed,

            "roll": phi,

            "pitch": theta,

            "yaw": psi,

            "roll_rate": p,

            "pitch_rate": q,

            "yaw_rate": r,

            "left_engine_fail": self.left_engine_fail,

            "flight_phase": (
                "DESCENT"
                if not self.left_engine_fail
                else "GO_AROUND"
            )
        }

    # =====================================================
    # 关闭环境
    # =====================================================

    def close(self):

        logger.info("Flight Environment Closed")
