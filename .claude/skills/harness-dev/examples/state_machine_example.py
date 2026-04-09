"""
状态机模式示例：协商状态管理

展示：
1. 状态机如何控制协商流程
2. 如何防止第一提案偏见（等待屏障）
3. 代码保障 > Prompt 保障（Design Principle 0.5）

设计理念：
- 程序层控制流程（状态转移、等待屏障）
- 能力层提供智能（LLM 聚合 Offer）
- 结构性偏见用代码消除，不依赖 prompt
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class Demand:
    """需求对象"""
    id: str
    content: str
    context: dict


@dataclass
class Offer:
    """Agent 提供的 Offer"""
    agent_id: str
    content: str
    capabilities: List[str]
    estimated_time: int  # hours


@dataclass
class Proposal:
    """聚合后的方案"""
    title: str
    description: str
    participating_agents: List[str]
    estimated_time: int


# =============================================================================
# 状态机定义
# =============================================================================

class NegotiationState(Enum):
    """
    协商状态枚举

    设计原则：用代码定义状态转移规则，而不是依赖 LLM "理解"流程
    """
    INITIALIZED = "initialized"           # 初始化
    BROADCASTING = "broadcasting"         # 正在广播需求
    COLLECTING_OFFERS = "collecting_offers"  # 等待 Offer（关键：等待屏障）
    READY_TO_AGGREGATE = "ready_to_aggregate"  # 可以聚合
    AGGREGATING = "aggregating"          # 正在聚合
    GAP_IDENTIFICATION = "gap_identification"  # 识别缺口
    COMPLETED = "completed"              # 完成
    FAILED = "failed"                    # 失败


# =============================================================================
# 状态机实现
# =============================================================================

class NegotiationEngine:
    """
    协商引擎（状态机）

    核心设计：
    1. 等待屏障：确保所有 Offer 收集完毕才聚合（防止第一提案偏见）
    2. 状态检查：每个操作都检查状态，确保流程正确
    3. 异常处理：状态错误时抛出异常，而不是"尝试恢复"
    """

    def __init__(self, demand: Demand, expected_agents: List[str]):
        self.demand = demand
        self.expected_agents = set(expected_agents)
        self.state = NegotiationState.INITIALIZED
        self.offers: Dict[str, Offer] = {}
        self.proposals: List[Proposal] = []

        logger.info(
            f"Negotiation initialized: demand={demand.id}, "
            f"expected_agents={len(expected_agents)}"
        )

    # =========================================================================
    # 状态转移方法
    # =========================================================================

    def start_broadcast(self) -> None:
        """
        开始广播需求

        状态转移：INITIALIZED → BROADCASTING → COLLECTING_OFFERS
        """
        self._check_state(NegotiationState.INITIALIZED, "start_broadcast")

        logger.info(f"Broadcasting demand: {self.demand.id}")
        self.state = NegotiationState.BROADCASTING

        # 实际广播逻辑（这里简化）
        # 在真实系统中，会通过 OpenAgents 广播
        self._broadcast_to_agents()

        self.state = NegotiationState.COLLECTING_OFFERS
        logger.info("Now collecting offers (waiting barrier active)")

    def submit_offer(self, agent_id: str, offer: Offer) -> None:
        """
        提交 Offer

        关键设计：等待屏障（Waiting Barrier）
        - 只有所有 expected_agents 都提交后，才能进入 READY_TO_AGGREGATE
        - 这样 LLM 无法"先看到哪个 Offer"，消除第一提案偏见

        研究依据：Microsoft 2025，第一提案偏见 10-30x
        """
        self._check_state(NegotiationState.COLLECTING_OFFERS, "submit_offer")

        # 权限检查
        if agent_id not in self.expected_agents:
            raise UnauthorizedError(
                f"Agent {agent_id} not invited to this negotiation"
            )

        # 重复检查
        if agent_id in self.offers:
            logger.warning(f"Agent {agent_id} already submitted offer, replacing")

        self.offers[agent_id] = offer
        logger.info(
            f"Offer received: agent={agent_id}, "
            f"progress={len(self.offers)}/{len(self.expected_agents)}"
        )

        # 等待屏障：所有 Offer 都到达才转移状态
        if len(self.offers) == len(self.expected_agents):
            self.state = NegotiationState.READY_TO_AGGREGATE
            logger.info("All offers received, ready to aggregate")

    def aggregate_proposals(self) -> List[Proposal]:
        """
        聚合方案

        设计原则：代码保障 > Prompt 保障
        - 代码确保：所有 Offer 都已收集（状态机检查）
        - LLM 提供：智能聚合（涌现方案）

        研究依据：DeepMind 2025，辩论是净负面 -3.5%，但聚合是正面 +57-81%
        """
        self._check_state(NegotiationState.READY_TO_AGGREGATE, "aggregate_proposals")

        self.state = NegotiationState.AGGREGATING
        logger.info(f"Aggregating {len(self.offers)} offers")

        try:
            # 并行聚合（不是顺序辩论）
            # 注意：这里的 LLM 调用是"一次性"的，所有 Offer 同时输入
            self.proposals = self._llm_aggregate_offers(list(self.offers.values()))

            self.state = NegotiationState.COMPLETED
            logger.info(f"Aggregation completed: {len(self.proposals)} proposals")

            return self.proposals

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            self.state = NegotiationState.FAILED
            raise

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _check_state(self, expected: NegotiationState, operation: str) -> None:
        """
        状态检查（代码保障）

        如果状态不对，抛出异常，而不是尝试"智能恢复"
        """
        if self.state != expected:
            raise InvalidStateError(
                f"Cannot {operation} in state {self.state.value}, "
                f"expected {expected.value}"
            )

    def _broadcast_to_agents(self) -> None:
        """广播需求（实际实现中调用 OpenAgents）"""
        # 简化版本：实际会通过 OpenAgents 消息传递
        pass

    def _llm_aggregate_offers(self, offers: List[Offer]) -> List[Proposal]:
        """
        LLM 聚合 Offer（能力层）

        关键：所有 Offer 一次性输入，LLM 看到的是"一个整体"，不是"先后顺序"
        """
        # 简化版本：实际会调用 Anthropic API
        # 真实实现见 mods/requirement_network/mod.py

        # 伪代码：
        # prompt = f"""
        # 需求：{self.demand.content}
        #
        # 以下是所有参与方的 Offer（无顺序）：
        # {json.dumps(offers)}
        #
        # 请设计 1-3 个方案，整合这些 Offer。
        # """
        # response = anthropic_client.complete(prompt)
        # return parse_proposals(response)

        # 这里返回 mock 数据
        return [
            Proposal(
                title="方案 1：全栈协作",
                description="整合前端和后端 Agent 的能力",
                participating_agents=[o.agent_id for o in offers],
                estimated_time=sum(o.estimated_time for o in offers)
            )
        ]

    # =========================================================================
    # 状态查询
    # =========================================================================

    def get_progress(self) -> dict:
        """获取协商进度"""
        return {
            "state": self.state.value,
            "offers_received": len(self.offers),
            "offers_expected": len(self.expected_agents),
            "proposals_generated": len(self.proposals)
        }

    def is_complete(self) -> bool:
        """是否完成"""
        return self.state == NegotiationState.COMPLETED


# =============================================================================
# 异常定义
# =============================================================================

class InvalidStateError(Exception):
    """状态错误"""
    pass


class UnauthorizedError(Exception):
    """未授权"""
    pass


# =============================================================================
# 使用示例
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 1. 初始化协商
    demand = Demand(
        id="demand-001",
        content="需要前端和后端开发者协作开发一个 Dashboard",
        context={"deadline": "2 weeks", "budget": "medium"}
    )

    engine = NegotiationEngine(
        demand=demand,
        expected_agents=["agent-frontend", "agent-backend"]
    )

    # 2. 开始广播
    engine.start_broadcast()

    # 3. Agent 提交 Offer（可能是异步的、无序的）
    engine.submit_offer(
        "agent-backend",
        Offer(
            agent_id="agent-backend",
            content="我可以提供 FastAPI 后端开发",
            capabilities=["Python", "FastAPI", "PostgreSQL"],
            estimated_time=40
        )
    )

    # 注意：此时还不能聚合，因为只收到 1/2 Offer
    try:
        engine.aggregate_proposals()  # 会抛出异常
    except InvalidStateError as e:
        logger.info(f"Expected error: {e}")

    # 4. 第二个 Agent 提交 Offer
    engine.submit_offer(
        "agent-frontend",
        Offer(
            agent_id="agent-frontend",
            content="我可以提供 React 前端开发",
            capabilities=["React", "TypeScript", "TailwindCSS"],
            estimated_time=30
        )
    )

    # 5. 现在可以聚合了（等待屏障打开）
    proposals = engine.aggregate_proposals()

    logger.info(f"Final proposals: {len(proposals)}")
    for i, proposal in enumerate(proposals):
        logger.info(f"Proposal {i+1}: {proposal.title}")

    # 6. 检查进度
    progress = engine.get_progress()
    logger.info(f"Progress: {progress}")
