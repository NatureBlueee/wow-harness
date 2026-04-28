"""
投影函数示例

展示{{PROJECT_NAME}}核心洞察："投影即函数，Agent 无状态"

关键要点：
1. Agent Vector 是计算结果，不是存储状态
2. ProfileDataSource 是可插拔的接口
3. Edge Agent 和 Service Agent 都是同一份 Profile Data 的投影
"""

from abc import ABC, abstractmethod
from typing import Protocol
from dataclasses import dataclass
import numpy as np


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class ProfileData:
    """用户 Profile 数据（来自 SecondMe / Claude / GPT / ...）"""
    user_id: str
    skills: list[str]
    experiences: list[str]
    interests: list[str]
    values: dict[str, float]  # 如 {"privacy": 0.9, "speed": 0.7}


@dataclass
class HDCVector:
    """HDC 超向量（10,000 维二进制向量）"""
    data: np.ndarray  # shape: (10000,), dtype: int8

    def __post_init__(self):
        assert self.data.shape == (10000,), "HDC vector must be 10,000 dim"
        assert self.data.dtype == np.int8, "HDC vector must be int8"


# ============================================================================
# ProfileDataSource 接口（可插拔）
# ============================================================================

class ProfileDataSource(Protocol):
    """
    Profile 数据源的抽象接口（本质）

    不同的数据源可以实现这个接口：
    - SecondMe Adapter
    - Claude Projects Adapter
    - GPT Memory Adapter
    - Template Adapter（黑客松场景）
    - Custom Adapter（用户自定义）
    """

    def get_profile(self, user_id: str) -> ProfileData:
        """获取用户 Profile"""
        ...

    def update_profile(self, user_id: str, experience_data: dict) -> None:
        """更新 Profile（回流协作数据）"""
        ...


# ============================================================================
# 具体实现（可替换）
# ============================================================================

class SecondMeAdapter:
    """SecondMe 数据源适配器"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_profile(self, user_id: str) -> ProfileData:
        """从 SecondMe API 获取 Profile"""
        # TODO: 调用 SecondMe API
        # response = secondme_api.get_profile(user_id, api_key=self.api_key)
        # return ProfileData(...)

        # Mock 示例数据
        return ProfileData(
            user_id=user_id,
            skills=["Python", "FastAPI", "React"],
            experiences=["Built e-commerce platform", "Led team of 5"],
            interests=["AI", "Web3", "Privacy"],
            values={"privacy": 0.9, "speed": 0.7, "collaboration": 0.8}
        )

    def update_profile(self, user_id: str, experience_data: dict) -> None:
        """回流协作数据到 SecondMe"""
        # TODO: 调用 SecondMe API
        # secondme_api.update_profile(user_id, experience_data, api_key=self.api_key)
        pass


class ClaudeAdapter:
    """Claude Projects 数据源适配器"""

    def get_profile(self, user_id: str) -> ProfileData:
        """从 Claude Projects 读取 Profile"""
        # TODO: 读取 Claude Projects 数据
        pass

    def update_profile(self, user_id: str, experience_data: dict) -> None:
        """更新 Claude Projects"""
        # TODO: 更新 Claude Projects
        pass


# ============================================================================
# 投影函数（核心逻辑，无状态）
# ============================================================================

def project(profile_data: ProfileData, lens: str) -> HDCVector:
    """
    投影函数：从 Profile Data 投影出 HDC Vector

    这是{{PROJECT_NAME}}的核心操作：
    - 丰富的东西（Profile Data）→ 透镜（lens）→ 聚焦的结果（HDC Vector）

    Args:
        profile_data: 用户 Profile 数据
        lens: 透镜类型
            - "full_dimension": 全维度投影 → Edge Agent
            - "focus_on_frontend": 聚焦前端 → Service Agent
            - "focus_on_backend": 聚焦后端 → Service Agent
            - ...

    Returns:
        HDC 向量（10,000 维二进制向量）
    """
    # TODO: 实现真实的 HDC 编码逻辑
    # 这里用随机向量作为示例
    vector_data = np.random.randint(0, 2, size=10000, dtype=np.int8)
    return HDCVector(data=vector_data)


# ============================================================================
# Agent 向量获取（使用投影函数）
# ============================================================================

def get_edge_agent_vector(
    user_id: str,
    data_source: ProfileDataSource
) -> HDCVector:
    """
    获取 Edge Agent 的 HDC 向量

    Edge Agent = 全维度投影（通才）

    关键：
    - 无状态：每次调用都重新投影
    - 不存储：不维护 Agent Vector，而是计算
    - 数据源驱动：Profile Data 变化 → 重新投影即可
    """
    profile_data = data_source.get_profile(user_id)
    return project(profile_data, lens="full_dimension")


def get_service_agent_vector(
    user_id: str,
    focus: str,
    data_source: ProfileDataSource
) -> HDCVector:
    """
    获取 Service Agent 的 HDC 向量

    Service Agent = 聚焦维度投影（专才）

    关键：
    - 同样无状态
    - 同一份 Profile Data，不同的透镜
    - Service Agent 不是"从 Edge Agent 分裂"，而是"新的投影"

    Args:
        user_id: 用户 ID
        focus: 聚焦维度（如 "frontend", "backend", "design"）
        data_source: Profile 数据源
    """
    profile_data = data_source.get_profile(user_id)
    lens = f"focus_on_{focus}"
    return project(profile_data, lens=lens)


# ============================================================================
# 协作数据回流
# ============================================================================

def record_collaboration_experience(
    user_id: str,
    experience_data: dict,
    data_source: ProfileDataSource
) -> None:
    """
    记录协作经验，回流到数据源

    关键：
    - {{PROJECT_NAME}}不维护 Profile Data
    - 协作数据回流到数据源（SecondMe / Claude / ...）
    - 数据源自己处理更新

    Args:
        user_id: 用户 ID
        experience_data: 协作经验数据
            例如：{
                "demand_id": "...",
                "role": "frontend",
                "collaboration_partners": [...],
                "outcome": "success",
                "feedback": "..."
            }
        data_source: Profile 数据源
    """
    data_source.update_profile(user_id, experience_data)


# ============================================================================
# 示例用法
# ============================================================================

if __name__ == "__main__":
    # 1. 创建数据源（可替换）
    data_source = SecondMeAdapter(api_key="test_key")

    # 2. 获取 Edge Agent Vector（全维度投影）
    edge_vector = get_edge_agent_vector("user123", data_source)
    print(f"Edge Agent Vector: {edge_vector.data[:10]}...")  # 前 10 维

    # 3. 获取 Service Agent Vector（聚焦维度投影）
    frontend_vector = get_service_agent_vector("user123", "frontend", data_source)
    print(f"Frontend Service Agent Vector: {frontend_vector.data[:10]}...")

    # 4. 记录协作经验（回流到数据源）
    experience = {
        "demand_id": "demand456",
        "role": "frontend",
        "collaboration_partners": ["user789"],
        "outcome": "success",
    }
    record_collaboration_experience("user123", experience, data_source)
    print("Collaboration experience recorded")

    # 5. 重新投影（Profile Data 已更新）
    new_edge_vector = get_edge_agent_vector("user123", data_source)
    print(f"Updated Edge Agent Vector: {new_edge_vector.data[:10]}...")

    # 关键：
    # - 没有"维护状态"
    # - 没有"防漂移机制"
    # - 只有"读取 + 投影"
    # - 极度简单！
