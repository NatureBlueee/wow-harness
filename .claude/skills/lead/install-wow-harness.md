# /lead install wow-harness

## 一句话

在用户的项目里安装 wow-harness 开发护栏。一条命令，三种深度，开箱即用。

## 使用方式

```bash
# 最常见：当前项目，默认 adapt 档
python3 scripts/install/phase2_auto.py --auto

# 指定档位
python3 scripts/install/phase2_auto.py --auto --tier=drop-in
python3 scripts/install/phase2_auto.py --auto --tier=adapt
python3 scripts/install/phase2_auto.py --auto --tier=mine --projects=/path/a,/path/b

# 多项目
python3 scripts/install/phase2_auto.py --auto --projects=/path/a,/path/b --scope=explicit

# 验证幂等性
python3 scripts/install/phase2_auto.py --auto --dry-run
```

## 三档安装光谱（ADR-043 §3.4.4）

| 档位 | 适合谁 | 读什么 | 做什么 |
|------|--------|--------|--------|
| **drop-in** | "我只要护栏，别碰我代码" | 只读 bundle 自身 | 复制 L0-L5 组件 + 16 条 hook matcher |
| **adapt** ⭐ 默认 | "看懂我项目就行" | README.md + docs/**/*.md (50KB) | drop-in + 按 stack 启/禁 rules |
| **mine** | "完全长进来" | adapt + 点名项目的 transcripts | adapt + crystal-learn 种子提案 |

**adapt 是默认档。** 绝大多数用户不需要碰这个参数。

## 显式点名（ADR-043 §3.4.5）

安装器会问你装到哪里：

1. 当前目录
2. 用户级全局（~/.claude/ plugin）
3. 显式点名几个项目

**mine + 全局 = 禁止**（隐私灾难，fail-closed）。mine 档必须显式点名。

## Gate 8 反思 loop（ADR-043 §3.4.6）

adapt 和 mine 档安装后，当你完成一个大 plan（lead state machine Gate 8 PASS），harness 会自动在后台启动一个 crystal-learn reflection agent。

这不是你需要记得做的事——它绑在 Gate 8 事件上，plan 完成就反思，不完成就不反思。

反思产物在 `.wow-harness/proposals/` 目录，下次开 session 时自然能看到。

## 安全模型

- **HMAC trust token**：安装过程用 `WOW_HARNESS_INSTALL_HMAC_KEY` 环境变量签名，30min 滑动窗口 + 6h 绝对上限
- **fail-closed**：key 缺失 / 过短 / 过期 = 自动中止，不降级
- **settings.json 原子追加**：用 json 库，不用 sed（INV-4 防护）
- **幂等**：第二次运行检测到已安装 → 跳过，不重复写

## 安装后验证

```bash
# 确认 hook 数量
python3 -c "import json; s=json.load(open('.claude/settings.json')); print(sum(len(e.get('hooks',[])) for stage in s.get('hooks',{}).values() for e in stage))"
# 预期输出: 16

# 确认 sanitize-on-read 工作
echo '{"tool_name":"Read","tool_input":{"file_path":"test.txt"}}' | python3 scripts/hooks/sanitize-on-read.py
# 预期: {"decision": "approve"}
```

## 这个 skill 不做什么

- 不碰 lead 的 8-gate 状态机核心逻辑
- 不自动扫描 ~/.claude/projects/ 推断项目（发现 = 未授权）
- 不装 OS-level daemon（没有 launchd/systemd/cron）
- 不在 drop-in 档读任何用户文件
