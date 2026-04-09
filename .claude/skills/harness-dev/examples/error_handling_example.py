"""
错误处理模式示例

展示：
1. 优雅降级（Graceful Degradation）
2. 重试机制（Retry with Exponential Backoff）
3. 自定义异常（清晰的错误语义）

设计理念：
- 预期的错误：捕获并处理（如网络超时）
- 非预期的错误：向上传播（如逻辑错误）
- 失败时提供有用的错误信息（上下文）
"""

import time
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass
from functools import wraps
import random

logger = logging.getLogger(__name__)


# =============================================================================
# 自定义异常（清晰的错误语义）
# =============================================================================

class ToWowError(Exception):
    """{{PROJECT_NAME}}系统的基础异常"""
    pass


class ProfileDataSourceError(ToWowError):
    """Profile 数据源错误"""
    pass


class ProfileNotFoundError(ProfileDataSourceError):
    """Profile 不存在"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"Profile not found: user_id={user_id}")


class ProfileServiceUnavailableError(ProfileDataSourceError):
    """Profile 服务不可用"""
    def __init__(self, service_name: str, reason: str):
        self.service_name = service_name
        self.reason = reason
        super().__init__(
            f"Profile service unavailable: service={service_name}, reason={reason}"
        )


class ResonanceError(ToWowError):
    """共振检测错误"""
    pass


class InvalidVectorError(ResonanceError):
    """无效的向量"""
    def __init__(self, vector_dimension: int, expected_dimension: int):
        self.vector_dimension = vector_dimension
        self.expected_dimension = expected_dimension
        super().__init__(
            f"Invalid vector dimension: got {vector_dimension}, "
            f"expected {expected_dimension}"
        )


class LLMError(ToWowError):
    """LLM 调用错误"""
    pass


class LLMRateLimitError(LLMError):
    """LLM 速率限制"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"LLM rate limit exceeded, retry after {retry_after}s")


# =============================================================================
# 重试机制（Exponential Backoff）
# =============================================================================

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    重试装饰器（指数退避）

    用法：
        @retry_with_backoff(max_retries=3, exceptions=(NetworkError,))
        def call_external_api():
            ...

    参数：
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数（每次延迟 *= base）
        exceptions: 需要重试的异常类型

    设计：
        - 指数退避：避免雪崩效应
        - 最大延迟：避免等待过久
        - 可配置异常：只重试预期的错误（如网络错误），不重试逻辑错误
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries",
                            extra={
                                "function": func.__name__,
                                "attempts": max_retries + 1,
                                "error": str(e)
                            }
                        )
                        raise

                    # 指数退避
                    sleep_time = min(delay, max_delay)
                    logger.warning(
                        f"Function {func.__name__} failed, retrying in {sleep_time}s",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "error": str(e),
                            "retry_delay": sleep_time
                        }
                    )

                    time.sleep(sleep_time)
                    delay *= exponential_base

            # 不应该到这里
            raise last_exception

        return wrapper
    return decorator


# =============================================================================
# 优雅降级（Graceful Degradation）
# =============================================================================

@dataclass
class ProfileData:
    """Profile 数据"""
    user_id: str
    skills: list[str]
    experience: list[str]
    source: str  # "secondme", "claude", "fallback"


class ProfileDataSource:
    """
    Profile 数据源（带优雅降级）

    设计：
        - 优先：SecondMe（实时数据）
        - 降级 1：缓存（过期数据总比没有好）
        - 降级 2：空 Profile（最小可用）

    原则：
        - 不要让单点故障影响整个系统
        - 部分功能降级 > 完全不可用
    """

    def __init__(self, enable_cache: bool = True):
        self.enable_cache = enable_cache
        self._cache: dict[str, ProfileData] = {}

    @retry_with_backoff(
        max_retries=3,
        exceptions=(ProfileServiceUnavailableError,)
    )
    def get_profile(self, user_id: str) -> ProfileData:
        """
        获取 Profile（带优雅降级）

        降级策略：
            SecondMe → 缓存 → 空 Profile
        """
        logger.info(f"Fetching profile: user_id={user_id}")

        try:
            # 尝试从 SecondMe 获取
            profile = self._fetch_from_secondme(user_id)
            self._update_cache(user_id, profile)
            return profile

        except ProfileNotFoundError:
            # 用户不存在：无法降级，向上传播
            logger.error(f"Profile not found: user_id={user_id}")
            raise

        except ProfileServiceUnavailableError as e:
            # SecondMe 不可用：尝试降级
            logger.warning(
                f"SecondMe unavailable, trying fallback: {e}",
                extra={"user_id": user_id, "error": str(e)}
            )

            # 降级 1：缓存
            if self.enable_cache and user_id in self._cache:
                cached_profile = self._cache[user_id]
                logger.info(
                    f"Using cached profile: user_id={user_id}",
                    extra={"cache_age": "unknown"}
                )
                return cached_profile

            # 降级 2：空 Profile
            logger.warning(
                f"No cache available, using empty profile: user_id={user_id}"
            )
            return ProfileData(
                user_id=user_id,
                skills=[],
                experience=[],
                source="fallback"
            )

    def _fetch_from_secondme(self, user_id: str) -> ProfileData:
        """
        从 SecondMe 获取 Profile（模拟）

        模拟故障：
            - 30% 概率 Service Unavailable
            - 10% 概率 Not Found
        """
        # 模拟网络延迟
        time.sleep(0.1)

        # 模拟故障
        rand = random.random()
        if rand < 0.3:
            raise ProfileServiceUnavailableError(
                "SecondMe",
                "Connection timeout"
            )
        if rand < 0.4:
            raise ProfileNotFoundError(user_id)

        # 成功
        return ProfileData(
            user_id=user_id,
            skills=["Python", "FastAPI", "React"],
            experience=["Worked on project X", "Led team Y"],
            source="secondme"
        )

    def _update_cache(self, user_id: str, profile: ProfileData) -> None:
        """更新缓存"""
        if self.enable_cache:
            self._cache[user_id] = profile
            logger.debug(f"Cache updated: user_id={user_id}")


# =============================================================================
# LLM 调用错误处理
# =============================================================================

class LLMService:
    """
    LLM 服务（带错误处理）

    错误类型：
        - Rate Limit（429）：重试，指数退避
        - Server Error（500）：重试，但有最大次数
        - Invalid Request（400）：不重试，向上传播
    """

    @retry_with_backoff(
        max_retries=5,
        initial_delay=1.0,
        max_delay=60.0,
        exceptions=(LLMRateLimitError,)
    )
    def complete(self, prompt: str) -> str:
        """
        LLM 补全（带错误处理）
        """
        logger.info(f"LLM request: prompt_length={len(prompt)}")

        try:
            # 模拟 LLM 调用
            response = self._call_anthropic_api(prompt)
            logger.info(f"LLM response: length={len(response)}")
            return response

        except LLMRateLimitError as e:
            # Rate Limit：重试（decorator 会处理）
            logger.warning(f"LLM rate limit: {e}")
            raise

        except LLMError as e:
            # 其他 LLM 错误：不重试
            logger.error(f"LLM error: {e}")
            raise

    def _call_anthropic_api(self, prompt: str) -> str:
        """模拟 Anthropic API 调用"""
        time.sleep(0.2)

        # 模拟 Rate Limit（20% 概率）
        if random.random() < 0.2:
            raise LLMRateLimitError(retry_after=5)

        return "LLM response: ..."


# =============================================================================
# 使用示例
# =============================================================================

def demo_profile_fetching():
    """演示 Profile 获取（带降级）"""
    print("=== Profile 获取示例 ===\n")

    profile_source = ProfileDataSource(enable_cache=True)

    # 尝试获取 10 次（会遇到各种错误）
    for i in range(10):
        try:
            profile = profile_source.get_profile(f"user-{i}")
            print(f"User {i}: source={profile.source}, skills={len(profile.skills)}")

        except ProfileNotFoundError as e:
            print(f"User {i}: Not found")

        except Exception as e:
            print(f"User {i}: Unexpected error: {e}")


def demo_llm_calling():
    """演示 LLM 调用（带重试）"""
    print("\n=== LLM 调用示例 ===\n")

    llm_service = LLMService()

    try:
        response = llm_service.complete("Hello, how are you?")
        print(f"LLM Response: {response}")

    except LLMError as e:
        print(f"LLM Error: {e}")


# =============================================================================
# 错误处理最佳实践总结
# =============================================================================

"""
错误处理最佳实践：

1. **异常分类**：
   - 预期的错误：捕获并处理（如 NetworkError, RateLimitError）
   - 非预期的错误：向上传播（如 AssertionError, KeyError）
   - 业务错误：自定义异常（如 ProfileNotFoundError）

2. **自定义异常**：
   - 继承自基础异常（如 ToWowError）
   - 包含上下文信息（如 user_id, service_name）
   - 清晰的命名（如 ProfileServiceUnavailableError）

3. **重试策略**：
   - 只重试瞬时错误（如网络超时）
   - 指数退避（避免雪崩）
   - 最大重试次数（避免无限重试）
   - 记录重试日志（方便 debug）

4. **优雅降级**：
   - 定义降级策略（如 实时数据 → 缓存 → 空数据）
   - 部分功能降级 > 完全不可用
   - 记录降级日志（监控降级频率）

5. **错误上下文**：
   - 捕获异常时附加上下文（user_id, function, parameters）
   - 使用结构化日志（便于查询）
   - 不要吞掉异常（静默失败很危险）

6. **用户友好**：
   - 内部错误：详细日志（用于 debug）
   - 用户错误：友好提示（不暴露内部细节）
   - 例如：
     - 内部日志："SecondMe API timeout after 3 retries"
     - 用户提示："暂时无法获取您的资料，请稍后再试"

7. **监控告警**：
   - 错误率（如 > 1% 告警）
   - 降级频率（如 > 10% 告警）
   - 重试次数（如平均 > 2 次告警）
   - 特定错误（如 RateLimitError 频繁出现）
"""


# =============================================================================
# 运行示例
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    demo_profile_fetching()
    demo_llm_calling()

    print("\n=== 最佳实践总结 ===")
    print("1. 自定义异常：清晰的错误语义")
    print("2. 重试机制：指数退避，避免雪崩")
    print("3. 优雅降级：部分功能降级 > 完全不可用")
    print("4. 错误上下文：附加 user_id, function, parameters")
    print("5. 监控告警：错误率、降级频率、重试次数")
