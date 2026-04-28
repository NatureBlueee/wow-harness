"""
可观测性设计示例

展示：
1. 结构化日志（JSON 格式，易于查询）
2. 性能监控（timing decorator）
3. 分布式追踪（trace ID 传播）

设计理念：
- 可观测性是设计的一部分，不是"加日志"
- 日志应该结构化（机器可读）
- 关键路径必须有监控
"""

import logging
import json
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional
from contextvars import ContextVar
import uuid

# =============================================================================
# 结构化日志
# =============================================================================

class StructuredLogger:
    """
    结构化日志记录器

    优点：
    - JSON 格式，易于查询（Elasticsearch, CloudWatch Logs Insights）
    - 自动附加 trace_id（分布式追踪）
    - 类型安全（field 有明确语义）
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, message: str, **fields):
        """记录 INFO 日志"""
        self._log("INFO", message, fields)

    def debug(self, message: str, **fields):
        """记录 DEBUG 日志"""
        self._log("DEBUG", message, fields)

    def warning(self, message: str, **fields):
        """记录 WARNING 日志"""
        self._log("WARNING", message, fields)

    def error(self, message: str, **fields):
        """记录 ERROR 日志"""
        self._log("ERROR", message, fields)

    def _log(self, level: str, message: str, fields: dict):
        """内部日志方法"""
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "trace_id": get_trace_id(),  # 分布式追踪
            **fields  # 自定义字段
        }

        log_line = json.dumps(log_entry)

        if level == "DEBUG":
            self.logger.debug(log_line)
        elif level == "INFO":
            self.logger.info(log_line)
        elif level == "WARNING":
            self.logger.warning(log_line)
        elif level == "ERROR":
            self.logger.error(log_line)


# =============================================================================
# 分布式追踪（Trace ID）
# =============================================================================

# ContextVar：线程安全的上下文变量（类似 thread-local，但支持 asyncio）
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str) -> None:
    """设置当前上下文的 trace_id"""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """获取当前上下文的 trace_id（如果没有则生成）"""
    trace_id = _trace_id_var.get()
    if trace_id is None:
        trace_id = str(uuid.uuid4())
        _trace_id_var.set(trace_id)
    return trace_id


def clear_trace_id() -> None:
    """清除 trace_id"""
    _trace_id_var.set(None)


# =============================================================================
# 性能监控（Timing Decorator）
# =============================================================================

def timed(logger: Optional[StructuredLogger] = None):
    """
    性能监控装饰器

    用法：
        @timed(logger)
        def my_function():
            ...

    会自动记录：
    - 函数名
    - 执行时间
    - 参数（可选）
    - 返回值（可选）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 记录开始
            start_time = time.time()
            func_name = func.__name__

            if logger:
                logger.debug(
                    f"Function started: {func_name}",
                    function=func_name,
                    args_count=len(args),
                    kwargs_count=len(kwargs)
                )

            try:
                # 执行函数
                result = func(*args, **kwargs)

                # 记录成功
                duration = time.time() - start_time
                if logger:
                    logger.info(
                        f"Function completed: {func_name}",
                        function=func_name,
                        duration_ms=round(duration * 1000, 2),
                        success=True
                    )

                return result

            except Exception as e:
                # 记录异常
                duration = time.time() - start_time
                if logger:
                    logger.error(
                        f"Function failed: {func_name}",
                        function=func_name,
                        duration_ms=round(duration * 1000, 2),
                        error=str(e),
                        error_type=type(e).__name__,
                        success=False
                    )
                raise

        return wrapper
    return decorator


# =============================================================================
# 使用示例
# =============================================================================

logger = StructuredLogger(__name__)


@timed(logger)
def project_to_vector(profile_data: dict, lens: str) -> list[float]:
    """
    投影函数示例（带监控）

    可观测性设计：
    1. 入口日志：记录调用参数
    2. 关键步骤日志：记录中间状态
    3. 性能监控：自动记录执行时间
    4. 异常日志：记录错误上下文
    """
    logger.info(
        "Projecting profile to vector",
        user_id=profile_data.get("user_id"),
        lens=lens,
        skills_count=len(profile_data.get("skills", []))
    )

    try:
        # 模拟 HDC 编码
        skills = profile_data.get("skills", [])
        vector = [hash(skill) % 1000 / 1000 for skill in skills]

        logger.debug(
            "HDC encoding completed",
            vector_dimension=len(vector),
            lens=lens
        )

        # 模拟慢操作
        time.sleep(0.1)

        logger.info(
            "Projection completed",
            user_id=profile_data.get("user_id"),
            vector_dimension=len(vector)
        )

        return vector

    except Exception as e:
        logger.error(
            "Projection failed",
            user_id=profile_data.get("user_id"),
            lens=lens,
            error=str(e)
        )
        raise


@timed(logger)
def aggregate_offers(offers: list[dict]) -> list[dict]:
    """
    聚合 Offer 示例（带监控）
    """
    logger.info(
        "Aggregating offers",
        offers_count=len(offers)
    )

    try:
        # 模拟 LLM 调用（慢操作）
        time.sleep(0.5)

        proposals = [
            {
                "title": "方案 1",
                "agents": [o["agent_id"] for o in offers]
            }
        ]

        logger.info(
            "Aggregation completed",
            proposals_count=len(proposals),
            agents_involved=len(offers)
        )

        return proposals

    except Exception as e:
        logger.error(
            "Aggregation failed",
            offers_count=len(offers),
            error=str(e)
        )
        raise


def simulate_negotiation():
    """
    模拟协商流程（展示分布式追踪）
    """
    # 生成 trace_id（在 API 入口设置）
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Negotiation started",
        demand_id="demand-001"
    )

    try:
        # Step 1: 投影（会继承 trace_id）
        profile = {"user_id": "user-001", "skills": ["Python", "FastAPI"]}
        vector = project_to_vector(profile, lens="backend")

        # Step 2: 聚合（会继承 trace_id）
        offers = [
            {"agent_id": "agent-001", "content": "..."},
            {"agent_id": "agent-002", "content": "..."}
        ]
        proposals = aggregate_offers(offers)

        logger.info(
            "Negotiation completed",
            demand_id="demand-001",
            proposals_count=len(proposals)
        )

    except Exception as e:
        logger.error(
            "Negotiation failed",
            demand_id="demand-001",
            error=str(e)
        )
        raise

    finally:
        clear_trace_id()


# =============================================================================
# 日志聚合查询示例
# =============================================================================

def demo_log_queries():
    """
    展示结构化日志的查询优势

    假设日志已存储到 Elasticsearch / CloudWatch Logs Insights
    """

    # 查询 1：找到特定 trace_id 的所有日志（分布式追踪）
    query_1 = """
    SELECT *
    FROM logs
    WHERE trace_id = 'abc-123'
    ORDER BY timestamp
    """

    # 查询 2：找到慢请求（性能监控）
    query_2 = """
    SELECT function, AVG(duration_ms) as avg_duration
    FROM logs
    WHERE level = 'INFO' AND duration_ms IS NOT NULL
    GROUP BY function
    HAVING avg_duration > 100
    ORDER BY avg_duration DESC
    """

    # 查询 3：找到错误率最高的函数
    query_3 = """
    SELECT function, COUNT(*) as error_count
    FROM logs
    WHERE level = 'ERROR'
    GROUP BY function
    ORDER BY error_count DESC
    """

    # 查询 4：分析某个用户的所有操作
    query_4 = """
    SELECT timestamp, function, message
    FROM logs
    WHERE user_id = 'user-001'
    ORDER BY timestamp
    """

    print("结构化日志查询示例：")
    print(f"1. 分布式追踪：{query_1}")
    print(f"2. 性能监控：{query_2}")
    print(f"3. 错误分析：{query_3}")
    print(f"4. 用户行为分析：{query_4}")


# =============================================================================
# 最佳实践总结
# =============================================================================

"""
可观测性最佳实践：

1. **日志级别**：
   - DEBUG: 详细信息（如向量维度、中间结果）
   - INFO: 关键操作（如 Agent 创建成功）
   - WARNING: 异常但可恢复的情况
   - ERROR: 错误（如数据源不可用）

2. **结构化字段**：
   - user_id: 用户标识（追踪用户行为）
   - function: 函数名（性能分析）
   - duration_ms: 执行时间（性能监控）
   - trace_id: 追踪 ID（分布式追踪）
   - error / error_type: 错误信息（错误分析）

3. **关键路径监控**：
   - 投影函数（高频调用）
   - LLM 调用（慢操作）
   - 数据库查询（慢操作）
   - 外部 API 调用（可能失败）

4. **分布式追踪**：
   - 在 API 入口生成 trace_id
   - 通过 ContextVar 传播（支持 asyncio）
   - 在 HTTP 头传递（跨服务）
   - 在所有日志中附加 trace_id

5. **性能监控**：
   - 使用 @timed 装饰器
   - 记录执行时间
   - 聚合分析（P50, P95, P99）
   - 设置性能预算（如 < 100ms）

6. **错误处理**：
   - 捕获异常并记录
   - 附加上下文（user_id, function, parameters）
   - 不要静默失败
   - 设置告警阈值（如错误率 > 1%）
"""


# =============================================================================
# 运行示例
# =============================================================================

if __name__ == "__main__":
    # 配置日志格式（输出到 stdout）
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s"  # 只输出消息（已经是 JSON）
    )

    print("=== 可观测性示例 ===\n")

    # 运行协商流程
    simulate_negotiation()

    print("\n=== 日志聚合查询示例 ===\n")
    demo_log_queries()

    print("\n提示：在生产环境中，这些日志会发送到 Elasticsearch 或 CloudWatch Logs")
    print("可以使用查询语言（如 Lucene, SQL）进行聚合分析")
