"""
Adapter 扩展示例

展示如何扩展{{PROJECT_NAME}}协议以适配不同的场景和数据源

关键要点：
1. 继承 AgentAdapter 基类
2. 实现 formulate_demand 和 generate_offer
3. 错误处理和日志记录
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# 协议消息定义（来自 requirement_network）
# ============================================================================

@dataclass
class Demand:
    """需求对象"""
    demand_id: str
    user_id: str
    raw_text: str  # 用户原始输入
    enriched_text: str  # Agent 丰富化后的需求
    context: dict  # 额外上下文


@dataclass
class Offer:
    """Offer 对象"""
    offer_id: str
    agent_id: str
    demand_id: str
    content: str  # Offer 内容
    confidence: float  # 信心度 (0.0 ~ 1.0)
    metadata: dict  # 额外信息


# ============================================================================
# AgentAdapter 基类（协议接口）
# ============================================================================

class AgentAdapter(ABC):
    """
    Agent 适配器基类

    不同的 Agent 可以实现这个接口：
    - SecondMeAdapter：基于 SecondMe Profile
    - ClaudeAdapter：基于 Claude Projects
    - TemplateAdapter：基于场景模板（黑客松）
    - CustomAdapter：用户自定义逻辑
    """

    @abstractmethod
    def formulate_demand(self, user_id: str, raw_demand: str) -> Demand:
        """
        需求丰富化：用户原始表述 → 结构化需求

        Args:
            user_id: 用户 ID
            raw_demand: 用户原始输入（如 "我想做个健康 App"）

        Returns:
            Demand: 丰富化后的需求对象
        """
        pass

    @abstractmethod
    def generate_offer(self, demand: Demand) -> Optional[Offer]:
        """
        生成 Offer：基于 Agent 能力和需求，生成响应

        Args:
            demand: 需求对象

        Returns:
            Offer: Agent 的响应，如果不相关则返回 None
        """
        pass


# ============================================================================
# SecondMeAdapter（基于 SecondMe Profile）
# ============================================================================

class SecondMeAdapter(AgentAdapter):
    """
    SecondMe 数据源适配器

    特点：
    - 基于 SecondMe Profile（技能、经历、价值观）
    - 调用 LLM 做需求丰富化和 Offer 生成
    - 错误处理：API 失败时返回 None
    """

    def __init__(self, user_id: str, api_key: str, llm_service):
        self.user_id = user_id
        self.api_key = api_key
        self.llm_service = llm_service

    def formulate_demand(self, user_id: str, raw_demand: str) -> Demand:
        """
        需求丰富化

        步骤：
        1. 从 SecondMe 获取用户 Profile
        2. 用 LLM 丰富化需求（结合 Profile 上下文）
        3. 生成结构化 Demand 对象
        """
        logger.info(f"Formulating demand: user={user_id}, raw='{raw_demand}'")

        try:
            # 步骤 1: 获取 Profile
            profile = self._get_profile(user_id)
            logger.debug(f"Profile loaded: {len(profile.get('skills', []))} skills")

            # 步骤 2: LLM 丰富化
            prompt = f"""
            用户原始需求: {raw_demand}

            用户 Profile:
            - 技能: {', '.join(profile.get('skills', []))}
            - 经历: {', '.join(profile.get('experiences', []))}
            - 兴趣: {', '.join(profile.get('interests', []))}

            请丰富化这个需求，补充可能的场景、约束、期望。
            """
            enriched_text = self.llm_service.generate(prompt)
            logger.debug(f"Demand enriched: {len(enriched_text)} chars")

            # 步骤 3: 生成 Demand 对象
            demand = Demand(
                demand_id=f"demand_{user_id}_{hash(raw_demand)}",
                user_id=user_id,
                raw_text=raw_demand,
                enriched_text=enriched_text,
                context={
                    "profile_summary": profile,
                    "timestamp": "2026-02-07T12:00:00Z"
                }
            )

            logger.info(f"Demand formulated: {demand.demand_id}")
            return demand

        except Exception as e:
            logger.error(f"Failed to formulate demand: user={user_id}, error={e}")
            # 降级：返回基本 Demand（不丰富化）
            return Demand(
                demand_id=f"demand_{user_id}_{hash(raw_demand)}",
                user_id=user_id,
                raw_text=raw_demand,
                enriched_text=raw_demand,  # 降级：不丰富化
                context={}
            )

    def generate_offer(self, demand: Demand) -> Optional[Offer]:
        """
        生成 Offer

        步骤：
        1. 从 SecondMe 获取当前 Agent 的 Profile
        2. 计算共振度（HDC 或 LLM）
        3. 如果相关，用 LLM 生成 Offer
        4. 如果不相关，返回 None
        """
        logger.info(f"Generating offer: agent={self.user_id}, demand={demand.demand_id}")

        try:
            # 步骤 1: 获取 Agent Profile
            profile = self._get_profile(self.user_id)

            # 步骤 2: 计算共振度
            resonance_score = self._calculate_resonance(profile, demand)
            logger.debug(f"Resonance score: {resonance_score:.2f}")

            if resonance_score < 0.3:  # 阈值：低于 0.3 不响应
                logger.info(f"Resonance too low ({resonance_score:.2f}), skipping offer")
                return None

            # 步骤 3: LLM 生成 Offer
            prompt = f"""
            需求: {demand.enriched_text}

            你的能力:
            - 技能: {', '.join(profile.get('skills', []))}
            - 经历: {', '.join(profile.get('experiences', []))}

            请生成一个 Offer，说明你如何帮助解决这个需求。
            """
            offer_content = self.llm_service.generate(prompt)
            logger.debug(f"Offer generated: {len(offer_content)} chars")

            # 步骤 4: 生成 Offer 对象
            offer = Offer(
                offer_id=f"offer_{self.user_id}_{demand.demand_id}",
                agent_id=self.user_id,
                demand_id=demand.demand_id,
                content=offer_content,
                confidence=resonance_score,
                metadata={
                    "profile_summary": profile,
                    "timestamp": "2026-02-07T12:00:00Z"
                }
            )

            logger.info(f"Offer generated: {offer.offer_id}, confidence={resonance_score:.2f}")
            return offer

        except Exception as e:
            logger.error(f"Failed to generate offer: agent={self.user_id}, error={e}")
            return None

    def _get_profile(self, user_id: str) -> dict:
        """从 SecondMe API 获取 Profile（内部方法）"""
        # TODO: 调用 SecondMe API
        # response = secondme_api.get_profile(user_id, api_key=self.api_key)
        # return response.json()

        # Mock 示例数据
        return {
            "skills": ["Python", "FastAPI", "React"],
            "experiences": ["Built e-commerce platform", "Led team of 5"],
            "interests": ["AI", "Web3", "Privacy"]
        }

    def _calculate_resonance(self, profile: dict, demand: Demand) -> float:
        """计算共振度（内部方法）"""
        # TODO: 实现真实的 HDC 共振检测
        # 这里用简单的关键词匹配作为示例
        skills = set(profile.get("skills", []))
        demand_text = demand.enriched_text.lower()

        match_count = sum(1 for skill in skills if skill.lower() in demand_text)
        score = min(match_count / len(skills) if skills else 0, 1.0)

        return score


# ============================================================================
# TemplateAdapter（基于场景模板）
# ============================================================================

class TemplateAdapter(AgentAdapter):
    """
    模板适配器（用于黑客松等场景）

    特点：
    - 用户填写场景模板（5 个关键问题）
    - 不依赖 SecondMe（万能兜底）
    - 适合短期活动、快速注册
    """

    def __init__(self, user_id: str, template_data: dict):
        """
        Args:
            user_id: 用户 ID
            template_data: 模板数据
                例如：{
                    "skills": ["Python", "React"],
                    "availability": "本周末 2 天",
                    "role_preference": ["开发", "项目管理"],
                    "project_interest": "AI 健康助手",
                    "collaboration_style": "远程协作"
                }
        """
        self.user_id = user_id
        self.template_data = template_data

    def formulate_demand(self, user_id: str, raw_demand: str) -> Demand:
        """
        需求丰富化（基于模板）

        不调用 LLM，直接用模板数据补充需求
        """
        logger.info(f"Formulating demand (template): user={user_id}")

        # 直接用模板数据补充
        enriched_text = f"""
        {raw_demand}

        用户信息:
        - 可用时间: {self.template_data.get('availability', '未填写')}
        - 角色偏好: {', '.join(self.template_data.get('role_preference', []))}
        - 项目兴趣: {self.template_data.get('project_interest', '未填写')}
        """

        return Demand(
            demand_id=f"demand_{user_id}_{hash(raw_demand)}",
            user_id=user_id,
            raw_text=raw_demand,
            enriched_text=enriched_text.strip(),
            context={"template_data": self.template_data}
        )

    def generate_offer(self, demand: Demand) -> Optional[Offer]:
        """
        生成 Offer（基于模板）

        简单的关键词匹配，不调用 LLM
        """
        logger.info(f"Generating offer (template): agent={self.user_id}")

        # 简单的关键词匹配
        skills = set(self.template_data.get("skills", []))
        demand_text = demand.enriched_text.lower()

        match_count = sum(1 for skill in skills if skill.lower() in demand_text)
        if match_count == 0:
            return None  # 不相关

        # 生成简单的 Offer
        offer_content = f"""
        我可以帮助！

        我的技能: {', '.join(skills)}
        我的时间: {self.template_data.get('availability', '灵活')}
        我感兴趣的: {self.template_data.get('project_interest', '各类项目')}
        """

        return Offer(
            offer_id=f"offer_{self.user_id}_{demand.demand_id}",
            agent_id=self.user_id,
            demand_id=demand.demand_id,
            content=offer_content.strip(),
            confidence=min(match_count / len(skills), 1.0),
            metadata={"template_data": self.template_data}
        )


# ============================================================================
# 示例用法
# ============================================================================

if __name__ == "__main__":
    # Mock LLM Service
    class MockLLMService:
        def generate(self, prompt: str) -> str:
            return f"[LLM Response to: {prompt[:50]}...]"

    llm_service = MockLLMService()

    # 示例 1: SecondMeAdapter
    print("=== SecondMeAdapter ===")
    adapter1 = SecondMeAdapter("user123", "test_key", llm_service)

    demand1 = adapter1.formulate_demand("user123", "我想做个健康 App")
    print(f"Demand: {demand1.enriched_text[:100]}...")

    offer1 = adapter1.generate_offer(demand1)
    if offer1:
        print(f"Offer: {offer1.content[:100]}...")
    else:
        print("No offer (not relevant)")

    # 示例 2: TemplateAdapter
    print("\n=== TemplateAdapter ===")
    template_data = {
        "skills": ["Python", "React"],
        "availability": "本周末 2 天",
        "role_preference": ["开发"],
        "project_interest": "健康相关",
        "collaboration_style": "远程"
    }
    adapter2 = TemplateAdapter("user456", template_data)

    demand2 = adapter2.formulate_demand("user456", "黑客松项目，健康追踪")
    print(f"Demand: {demand2.enriched_text[:100]}...")

    offer2 = adapter2.generate_offer(demand2)
    if offer2:
        print(f"Offer: {offer2.content[:100]}...")
    else:
        print("No offer (not relevant)")

    # 关键：
    # - 两个 Adapter 实现了相同的接口
    # - 但行为完全不同（SecondMe 调用 LLM，Template 用简单逻辑）
    # - 调用方不需要知道具体实现（本质与实现分离）
