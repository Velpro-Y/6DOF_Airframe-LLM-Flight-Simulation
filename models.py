"""
==========================================================

FastAPI数据模型

==========================================================
"""

from pydantic import BaseModel, Field, field_validator
from typing import Union, Any


class Action(BaseModel):
    """
    LLM输出动作（增强容错版）
    """
    # 将类型声明改为 Any，或者保持 float 都可以。
    # 只要下面加了 before 验证器，Pydantic 就会在校验类型前先执行我们的清洗函数。
    aileron: Any = Field(default=0, ge=-1, le=1)
    elevator: Any = Field(default=0, ge=-1, le=1)
    rudder: Any = Field(default=0, ge=-1, le=1)

    throttle_left: float = Field(
        default=0.5,
        ge=0,
        le=1
    )

    throttle_right: float = Field(
        default=0.5,
        ge=0,
        le=1
    )

    left_engine_fail: bool = False

    # ==========================================
    # 🔥 核心新增：全面拦截并清洗 Dify 传过来的脏数据
    # ==========================================
    @field_validator('aileron', 'elevator', 'rudder', mode='before')
    @classmethod
    def clean_and_parse_float(cls, v: Any) -> float:
        # 如果大模型嘴碎，或者 Dify 序列化出错，传过来的是字符串（如 " -0.035 " 或 "-0.035"）
        if isinstance(v, str):
            # 1. 剔除所有可能误带的双引号、单引号和前后空格
            clean_str = v.replace('"', '').replace("'", "").strip()
            # 2. 移除负号和数字之间可能存在的死人空格（例如把 "- 0.03" 变成 "-0.03"）
            clean_str = clean_str.replace('- ', '-')
            try:
                return float(clean_str)
            except ValueError:
                # 如果真的碎到完全无法解析，返回默认值 0，保证系统绝不崩溃
                return 0.0
        # 如果本来就是数字，直接返回
        return float(v)


class AircraftState(BaseModel):
    """
    返回给LLM的状态
    """
    time: float
    altitude: float
    airspeed: float
    vertical_speed: float
    roll: float
    pitch: float
    yaw: float
    roll_rate: float
    pitch_rate: float
    yaw_rate: float
    throttle_left: float
    throttle_right: float
    left_engine_fail: bool


class ResetResponse(BaseModel):
    success: bool
    state: AircraftState


class StepResponse(BaseModel):
    success: bool
    state: AircraftState