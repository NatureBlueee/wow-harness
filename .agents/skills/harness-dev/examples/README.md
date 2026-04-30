# harness-dev 代码示例库

这个目录包含 harness-dev skill 的代码示例，展示{{PROJECT_NAME}}/WOWOK 生态系统的工程实践。

## 示例列表

### 1. 投影函数示例（`projection_example.py`）

**核心概念**：投影即函数，Agent 无状态

展示：
- 无状态投影函数（Profile Data → HDC Vector）
- ProfileDataSource 接口设计（本质与实现分离）
- Edge Agent vs Service Agent（同样数据，不同透镜）

**关键代码**：
```python
def project_to_edge_agent(profile: ProfileData) -> HDCVector:
    """全维度投影 → Edge Agent"""
    return hdc_encode(profile, lens="full_dimension")

def project_to_service_agent(profile: ProfileData, focus: str) -> HDCVector:
    """聚焦投影 → Service Agent"""
    return hdc_encode(profile, lens=f"focus_on_{focus}")
```

**设计理念**：Design Log #003 - Projection as Function

### 2. Adapter 扩展示例（`adapter_example.py`）

**核心概念**：扩展协议（本质与实现分离）

展示：
- 继承 AgentAdapter 基类
- 实现 formulate_demand 和 generate_offer
- 优雅的错误处理

**关键代码**：
```python
class SecondMeAdapter(AgentAdapter):
    def formulate_demand(self, raw_input: str) -> Demand:
        """基于 SecondMe Profile 理解真实需求"""
        ...

    def generate_offer(self, demand: Demand) -> Offer:
        """基于 SecondMe 能力生成 Offer"""
        ...
```

**设计理念**：Adapter 模式，可插拔数据源

### 3. 测试编写示例（`test_example.py`）

**核心概念**：测试是思维清晰度的验证

展示：
- 正常情况测试（happy path）
- 边界情况测试（边界值、空输入）
- 异常情况测试（错误输入）
- Mock 外部依赖（不依赖真实 API）

**关键代码**：
```python
def test_project_to_vector_normal():
    """正常情况：投影成功"""
    mock_source = Mock(spec=ProfileDataSource)
    mock_source.get_profile.return_value = mock_profile

    vector = project_to_vector("user-123", "backend", mock_source)

    assert len(vector) == HDC_DIMENSION
    mock_source.get_profile.assert_called_once_with("user-123")
```

**设计理念**：测试即文档，易测试的代码 = 设计良好的代码

### 4. 状态机示例（`state_machine_example.py`）

**核心概念**：代码保障 > Prompt 保障

展示：
- 协商状态管理（状态枚举）
- 状态转移检查（异常抛出）
- 防止第一提案偏见（等待屏障）

**关键代码**：
```python
class NegotiationState(Enum):
    COLLECTING_OFFERS = "collecting_offers"
    READY_TO_AGGREGATE = "ready_to_aggregate"
    COMPLETED = "completed"

def submit_offer(self, agent_id: str, offer: Offer):
    """等待屏障：所有 Offer 都到达才聚合"""
    self._check_state(NegotiationState.COLLECTING_OFFERS, "submit_offer")

    self.offers[agent_id] = offer

    if len(self.offers) == len(self.expected_agents):
        self.state = NegotiationState.READY_TO_AGGREGATE
```

**设计理念**：Design Principle 0.5 - 代码保障 > Prompt 保障

**研究依据**：Microsoft 2025，第一提案偏见 10-30x

### 5. 可观测性示例（`observable_example.py`）

**核心概念**：可观测性是设计的一部分

展示：
- 结构化日志（JSON 格式，机器可读）
- 性能监控（timing decorator）
- 分布式追踪（trace_id 传播）

**关键代码**：
```python
class StructuredLogger:
    def info(self, message: str, **fields):
        log_entry = {
            "timestamp": time.time(),
            "level": "INFO",
            "message": message,
            "trace_id": get_trace_id(),
            **fields
        }
        self.logger.info(json.dumps(log_entry))

@timed(logger)
def project_to_vector(profile: ProfileData, lens: str) -> HDCVector:
    """自动记录执行时间"""
    ...
```

**设计理念**：看不到系统在做什么 = 无法判断正确性

### 6. 错误处理示例（`error_handling_example.py`）

**核心概念**：优雅降级、重试机制、自定义异常

展示：
- 优雅降级（实时数据 → 缓存 → 空数据）
- 重试机制（指数退避）
- 自定义异常（清晰的错误语义）

**关键代码**：
```python
@retry_with_backoff(max_retries=3, exceptions=(ServiceUnavailableError,))
def get_profile(self, user_id: str) -> ProfileData:
    """带降级策略的 Profile 获取"""
    try:
        return self._fetch_from_secondme(user_id)
    except ServiceUnavailableError:
        # 降级到缓存
        if user_id in self._cache:
            return self._cache[user_id]
        # 降级到空 Profile
        return ProfileData.empty(user_id)
```

**设计理念**：预期的错误捕获并处理，非预期的错误向上传播

## 运行示例

所有示例都可以独立运行：

```bash
cd /Users/nature/个人项目/{{PROJECT_NAME}}/.claude/skills/harness-dev/examples

# 运行投影函数示例
python projection_example.py

# 运行状态机示例
python state_machine_example.py

# 运行可观测性示例
python observable_example.py

# 运行错误处理示例
python error_handling_example.py

# 运行测试示例
pytest test_example.py -v
```

## 最佳实践总结

这些示例展示了 7 个核心工程信念：

1. **代码是思想的投影**：清晰的代码 = 清晰的理解
2. **本质与实现分离**：接口稳定，实现可插拔
3. **投影即函数，Agent 无状态**：无状态函数，极度简单
4. **代码保障 > Prompt 保障**：状态机防护，让 LLM 犯不了错
5. **复杂度预算是有限的**：函数 < 50 行，职责清晰
6. **可观测性是设计的一部分**：结构化日志、性能监控、分布式追踪
7. **测试是思维清晰度的验证**：易测试的代码 = 设计良好的代码

## 进一步阅读

- **harness-dev SKILL.md**：完整的工程主管指南
- **arch skill**：架构理念和设计原则
- **ARCHITECTURE_DESIGN.md**：{{PROJECT_NAME}}网络技术架构
- **MEMORY.md**：项目关键决策记录

## 问题反馈

如果你对这些示例有疑问，或者想看更多示例：
1. 问 harness-dev：代码实现、工程实践、测试策略
2. 问 arch：架构设计、设计原则、本质理解
