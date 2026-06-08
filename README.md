# C³ — AI 能力认知校准器

一个 OpenClaw 技能插件，用于检测 AI 回复中的"能力错觉"，在必要时自动注入能力边界提示。

## 这东西解决什么问题

很多用户分不清"AI 在跟我聊天"和"AI 在帮我做事"的区别。当 AI 说"已为您预订成功"时，用户可能真的以为餐厅已经订好了——但实际上 AI 只是生成了一段文字。

C³ 在每次回复前自动检测 8 种常见的能力错觉模式（虚假执行、承诺担保、拟人化增信等），根据用户的 AI 认知水平、当前对话的语言和场景，动态生成合适的提示信息。

## 整体流程

```
用户输入 → 认知水平测试（首次）→ 确定 Tier 1-4
                ↓
LLM 生成草稿回复 → 正则 + LLM 混合检测 → 风险等级
                ↓
工具调用一致性检查 → 回复声称 vs 实际操作
                ↓
动态生成披露文本（语言 + 场景 + 认知等级）→ 注入 → 返回最终回复
```

## 快速上手

```bash
# 1. 安装
cp SKILL.md ~/.openclaw/skills/c3-capability-calibrator/
cp -r scripts/ ~/.openclaw/skills/c3-capability-calibrator/

# 2. 在 AGENTS.md 中添加触发规则
echo 'Before sending ANY reply, read ~/.openclaw/skills/c3-capability-calibrator/SKILL.md' >> ~/.openclaw/workspace/AGENTS.md
```

LLM 检测层会自动读取 OpenClaw 网关已配置的 API，无需额外设置密钥。

## 文件说明

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 技能指令文件，agent 每次回复前读取 |
| `scripts/judge.py` | 正则 + LLM 混合检测（Layer 1） |
| `scripts/detector.py` | 纯正则模式匹配（Layer 1a） |
| `scripts/consistency.py` | 工具调用一致性检查（Layer 2） |
| `scripts/disclosure.py` | 动态披露文本生成（语言 + 场景感知） |
| `scripts/test.py` | 用户 AI 认知水平评估（3 题定 Tier） |
| `scripts/behavior.py` | 长期行为追踪，动态调整 Tier |
| `scripts/openclaw_api.py` | 从 OpenClaw 网关读取 API 配置的公共模块 |

## 检测的 8 种模式

| 编号 | 模式 | 风险 | 例子 |
|---|---|---|---|
| P1 | 虚假执行 | 高 | "已为您预约成功" |
| P2 | 承诺担保 | 高 | "承担所有差价" |
| P3 | 拟人化 | 中 | "妥妥的" / "交给我" |
| P4 | 无条件迎合 | 低 | 对不可能的请求直接说"好的" |
| P5 | 权威伪装 | 中 | "根据系统记录" |
| P6 | 边界模糊 | 中 | "我会跟进的"（实际无法跟进） |
| P7 | 社会证明伪造 | 中 | "很多用户都选择了…" |
| P8 | 过度自信 | 低 | 不加限定的具体数字 |

## 动态披露生成

披露文本不是固定的模板，而是由 LLM 根据以下维度动态生成：

- **语言**：自动检测用户输入语言，用相同语言回复
- **场景**：从对话内容推断（预订、金融、医疗、法律、外卖等），结合具体场景说明 AI 的限制
- **用户认知等级**：Tier 1（专家）一句话带过，Tier 4（完全不了解）详细教育性解释
- **风险等级**：HIGH 必须明确声明"我无法实际执行此操作"

如果 LLM 不可用，自动降级为通用的兜底文本。

```
# 调用示例
echo '{"risk":"HIGH","patterns":["P1"],"tier":3,"lang":"zh","scenario":"booking","reply":"已为您预订成功"}' | python3 scripts/disclosure.py
```

## 用户认知分级

| Tier | 用户类型 | 触发范围 |
|---|---|---|
| 1 | 专家——清楚 agent 和 chatbot 的区别 | 仅 P1/P2 |
| 2 | 中级——大致了解 | P1-P6 |
| 3 | 新手——听说过但不清楚（默认） | P1-P8 全部 |
| 4 | 完全不了解——没听说过 agent | 全部 + 首次教育提示 |

## API 配置说明

LLM 检测层（`judge.py`）和披露生成层（`disclosure.py`）通过 `scripts/openclaw_api.py` 自动从 OpenClaw 网关配置中读取已有的 provider API 密钥和端点，不需要在技能文件中单独配置。

读取优先级：
1. 环境变量 `OPENCLAW_API_KEY` / `OPENCLAW_BASE_URL`
2. OpenClaw 网关配置文件（`~/.openclaw/openclaw.json`）
3. 环境变量 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`（兼容旧配置）

如果以上都没有找到可用的 API 配置，LLM 相关功能会自动降级为纯正则模式 / 通用兜底文本，不影响基本功能。

## 基于实证调查

本项目的设计基于一项面向 AI 用户的调查（N=47），主要发现：

- 46.81% 的用户对 AI agent 概念缺乏清晰认知
- 50% 的认知空白用户认为"对话即做事"
- 59.26% 的经验不足用户被拟人化表达增信
- 23.4% 曾因信任 AI 输出而做出错误决定

## 许可证

MIT
