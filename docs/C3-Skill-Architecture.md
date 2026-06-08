# C3 - 能力认知校准器(Capability Cognition Calibrator)

## 完整 Skill 架构文档

---

## 一、项目概述

### 1.1 问题来源

本项目基于一项面向 AI 用户的实证调查（N=47）发现：

- **46.81%** 的用户对 AI agent 概念缺乏清晰认知(A9 题)
- **57.45%** 见过但从未使用过 agent 功能(A10 题)
- **50%** 的认知空白用户认为"对话即做事"(B6 题)
- **59.26%** 的经验不足用户被拟人化表达增信(B9 题)
- **23.4%** 曾因信任 AI 输出而做出错误决定(B10 题)
- **37.5%** 的 AI 专家高估普通用户的认知水平(B7 题,"知识诅咒")

**核心洞察**:AI 能力认知不足是一个系统性风险,且开发者群体因"知识诅咒"而系统性低估了这一问题的严重性。

### 1.2 解决方案

C3(Capability Cognition Calibrator)是一个嵌入 AI 交互流程的能力认知校准器。它在每次 AI 回复前自动执行三层检测,当检测到回复可能让用户产生"AI 已经执行了某个操作"的错觉时,自动注入能力边界披露。

### 1.3 设计原则

| 原则 | 说明 |
|---|---|
| **Ethics-by-design** | 不是事后补救,而是嵌入交互流程的伦理护栏 |
| **反商业逻辑** | 故意在关键节点增加交互摩擦,宁可降低体验也要防止认知损害 |
| **数据驱动** | 所有检测规则和披露策略均基于 N=47 实证调查数据 |
| **自适应** | 根据用户认知水平动态调整披露强度 |
| **可审计** | 每次检测结果可追溯,支持规则迭代 |

---

## 二、系统架构

### 2.1 整体架构

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 0: 用户画像测试                         │
│  scripts/test.py → 3 题测试 → Tier 1-4                         │
│  scripts/behavior.py → 长期行为追踪 → 动态调整 Tier              │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼ (Tier 已确定,后续交互跳过 Phase 0)
┌─────────────────────────────────────────────────────────────────┐
│  用户消息 → LLM 生成草稿回复                                    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Phase 1: 混合检测引擎                       │    │
│  │                                                          │    │
│  │   ┌─────────────────────┐    ┌──────────────────────┐   │    │
│  │   │ Layer 1a: 正则预过滤 │    │ Layer 1b: LLM Judge  │   │    │
│  │   │ scripts/detector.py  │    │ scripts/judge.py     │   │    │
│  │   │ (快, 确定性)         │───▶│ (准, 语义级)         │   │    │
│  │   └─────────────────────┘    └──────────────────────┘   │    │
│  │                                                          │    │
│  │   ┌─────────────────────────────────────────────────┐   │    │
│  │   │ Layer 2: 工具调用一致性检测                       │   │    │
│  │   │ scripts/consistency.py                           │   │    │
│  │   │ 回复声称的操作 vs 实际工具调用                    │   │    │
│  │   └─────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  │                                                               │
│  ▼ Phase 2: 检测结果 → 与用户 Tier 匹配 → 注入披露              │
│  │                                                               │
│  ▼ Phase 3: 行为记录 → 更新用户画像                              │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
最终回复(含能力边界披露)→ 用户
```

### 2.2 文件结构

```
~/.openclaw/skills/c3-capability-calibrator/
├── SKILL.md                    # 指令文件(agent 每次回复前读取)
└── scripts/
    ├── test.py                 # Phase 0: 用户画像测试(3 题 → Tier 1-4)
    ├── detector.py             # Phase 1a: 正则预过滤(6 种模式)
    ├── judge.py                # Phase 1b: LLM-as-Judge(语义级检测)
    ├── consistency.py          # Phase 1c: 工具调用一致性检测
    ├── disclosure.py           # Phase 2: 动态披露文本生成(语言+场景感知)
    ├── behavior.py             # Phase 3: 用户行为追踪 → 动态 Tier 调整
    └── openclaw_api.py         # 共享模块: 从 OpenClaw 网关读取 API 配置
```

### 2.3 数据流

```
用户消息 ─────────────────────────────────────────────────────────┐
  │                                                               │
  ├─▶ test.py (首次交互)                                          │
  │   └─▶ {"tier": 3, "label": "Novice"}                        │
  │                                                               │
  ├─▶ behavior.py (每次交互)                                      │
  │   └─▶ {"tier": 3, "signals": {...}}                          │
  │                                                               │
  ▼                                                               │
LLM 生成草稿回复 ────────────────────────────────────────────────┐│
  │                                                              ││
  ├─▶ detector.py (正则) ──▶ {"risk": "HIGH", "patterns": ["P1"]}││
  │                          如果 HIGH → 跳过 LLM,直接返回       ││
  │                          如果 NONE → 继续                     ││
  │                                                              ││
  ├─▶ judge.py (LLM) ──▶ {"risk": "MEDIUM", "patterns": ["P3"]}  ││
  │                                                              ││
  ├─▶ consistency.py ──▶ {"risk": "HIGH", "issues": ["NO_TOOL"]}  ││
  │                                                              ││
  ▼                                                              ││
合并检测结果 ──▶ 取最高风险 ──▶ 查用户 Tier ──▶ 注入披露          ││
  │                                                              ││
  ▼                                                              ││
behavior.py 记录本次交互 ──▶ 更新用户画像                         ││
  │                                                              ││
  ▼                                                              ││
最终回复 ─────────────────────────────────────────────────────────┘│
                                                                   │
用户反馈(如有)──────────────────────────────────────────────────┘
```

---

## 三、检测层详解

### 3.1 Layer 1a:正则预过滤(detector.py)

**目的**:快速、确定性地捕获高风险模式。零延迟、零成本。

**6 种模式**:

| ID | 模式名 | 风险等级 | 正则示例 |
|---|---|---|---|
| P1 | 虚假执行 | HIGH | `已(?:为您\|帮你).{0,10}(?:完成\|预约\|下单\|购买)` |
| P2 | 承诺担保 | HIGH | `(?:承担\|负责\|保证\|承诺).{0,10}(?:费用\|差价\|损失)` |
| P3 | 拟人化 | MEDIUM | `(?:妥妥的\|放心\|交给我\|包在我身上)` |
| P4 | sycophancy | LOW | `^(?:好的\|明白了\|没问题)\s*$` |
| P5 | 权威伪装 | MEDIUM | `(?:根据系统记录\|系统显示\|经核实)` |
| P6 | 边界模糊 | MEDIUM | `我会.{0,6}(?:跟进\|处理\|安排)的?` |

**执行逻辑**:

```
输入: 回复文本
  │
  ▼
遍历 P1-P6 正则 → 找到匹配?
  │
  ├─ P1 或 P2 匹配 → 直接返回 HIGH(跳过 LLM)
  ├─ P3/P5/P6 匹配 → 返回 MEDIUM(继续 LLM 确认)
  └─ 无匹配 → 返回 NONE(继续 LLM)
```

**调用方式**:

```bash
echo "已为您预约成功" | python3 scripts/detector.py --stdin
# 输出: {"risk": "HIGH", "patterns": ["P1"], ...}
```

### 3.2 Layer 1b:LLM-as-Judge(judge.py)

**目的**:捕获正则无法检测的语义级模式(隐含承诺、上下文权威伪装等)。

**技术方案**:

```
正则预过滤结果
  │
  ├─ HIGH (P1/P2) → 跳过 LLM,直接返回
  ├─ NONE → 调用 LLM 做语义判断
  └─ MEDIUM → 调用 LLM 确认/降级
  │
  ▼
LLM Judge(DeepSeek V4 Flash)
  │
  ▼
返回: {"risk": "HIGH|MEDIUM|LOW|NONE", "patterns": [...], "confidence": 0.95}
```

**LLM 配置**:

| 参数 | 值 | 说明 |
|---|---|---|
| 模型 | `deepseek-chat` | DeepSeek V4 Flash,最经济 |
| API | OpenAI 兼容 (`/chat/completions`) | 与 OpenClaw 同一 API |
| 温度 | 0.1 | 低温度确保判断一致性 |
| max_tokens | 300 | 每次判断约 100-200 token |
| 超时 | 15 秒 | 防止 API 延迟阻塞 |

**Judge Prompt 设计要点**:

- System prompt 定义了 6 种模式的语义判断标准
- 要求严格 JSON 输出,不输出任何其他内容
- 包含 confidence 字段(0-1)表示判断把握
- 包含 reason 字段用于审计
- 特别标注:如果回复已改写为"我无法实际预订"则 risk=NONE

**成本估算**:

| 场景 | 调用次数 | Token 消耗 | 成本 |
|---|---|---|---|
| 每天 100 次回复 | ~100 次 | ~30K input + 10K output | ~$0.006/天 |
| 每月 3000 次 | ~3000 次 | ~900K input + 300K output | ~$0.18/月 |

**调用方式**:

```bash
# 完整检测(正则 + LLM)
echo "已为您预约成功" | python3 scripts/judge.py

# 仅正则(跳过 LLM)
echo "已为您预约成功" | python3 scripts/judge.py --no-llm
```

### 3.3 Layer 2:工具调用一致性检测(consistency.py)

**目的**:最可靠的检测--直接比对"回复说了什么" vs "实际做了什么"。

**原理**:

```
回复文本 ──▶ 提取隐含操作(动词分析)
  │              │
  │              ▼
  │         "已为您预订" → 隐含操作: booking
  │
工具调用记录 ──▶ 提取实际操作
  │              │
  │              ▼
  │         工具列表: [](无工具调用)
  │
  ▼
一致性比对:
  隐含操作 = booking
  实际工具 = [](无 booking 相关工具)
  结论: NO_TOOL_CALLED → HIGH 风险
```

**隐含操作提取**(基于动词模式):

| 操作类型 | 中文动词 | 对应工具关键词 |
|---|---|---|
| booking | 预订、预约、订了、预留 | book, reserve, booking |
| purchase | 购买、下单、买了、支付 | buy, purchase, order, payment |
| cancel | 取消、退了、退款、退票 | cancel, refund, return |
| modify | 修改了、更改了、更新了 | edit, update, modify |
| send | 发送了、发出了、提交了 | send, email, message |
| contact | 联系了、通知了、沟通了 | call, contact, notify |
| execute | 执行了、运行了、启动了 | run, execute, deploy |

**三种检测结果**:

| 结果类型 | 说明 | 风险 |
|---|---|---|
| `NO_TOOL_CALLED` | 回复声称做了某事,但没有调用任何工具 | HIGH |
| `TOOL_FAILED` | 回复声称成功,但工具调用失败 | HIGH |
| `CONSISTENT` | 回复声称的操作与工具调用一致 | NONE |

**调用方式**:

```bash
# 无工具调用(最常见场景)
python3 scripts/consistency.py --reply "已为您预订成功" --tools '[]'

# 工具调用失败
python3 scripts/consistency.py --reply "退款已处理" --tools '[{"name":"refund_api","result":{"error":"timeout"}}]'

# 工具调用成功(安全)
python3 scripts/consistency.py --reply "以下是搜索结果" --tools '[{"name":"web_search","result":{"data":"..."}}]'
```

### 3.4 Layer 3:用户行为追踪(behavior.py)

**目的**:长期追踪用户行为模式,动态调整风险等级。

**追踪信号**:

| 信号 | 含义 | 触发条件 |
|---|---|---|
| `actionable_requests` | 用户发出可执行请求的次数 | 消息包含"帮我/预订/购买/退款"等 |
| `accepted_anthropomorphic_without_skepticism` | 接受拟人化回复而未质疑 | AI 使用拟人化语言后,用户未质疑 |
| `asked_for_confirmation` | 用户主动确认的次数 | 消息包含"真的吗/确认/确定" |
| `corrected_ai_output` | 用户纠正 AI 输出的次数 | 消息包含"不对/错了/纠正" |

**动态 Tier 调整规则**:

```
基础 Tier = 用户画像测试结果(或默认 Tier 3)
  │
  ├─ 用户多次纠正 AI 输出 → Tier -1(用户比预期更了解)
  ├─ 用户多次主动确认 → Tier -1(用户更谨慎)
  ├─ 用户反复执行 AI 建议而不验证 → Tier +1(用户比预期更不了解)
  ├─ 用户持续接受拟人化而无质疑 → Tier +1(用户易被拟人化影响)
  └─ 频繁触发 HIGH 风险检测 → Tier +1(高风险交互频率过高)
  │
  ▼
最终 Tier = clamp(base + adjustments, 1, 4)
```

**存储**:

用户行为画像存储在 `~/.openclaw/workspace/memory/c3_profiles/{user_id}.json`,包含:
- 当前 Tier 及来源
- 交互计数
- 行为信号统计
- 风险事件记录(最近 50 条)
- Tier 变更历史

**调用方式**:

```bash
# 记录一次交互
echo '{"user_id":"test_user","user_msg":"帮我订餐厅","ai_reply":"已为您预约成功","detection_result":{"risk":"HIGH","patterns":["P1"]}}' | python3 scripts/behavior.py record

# 查看用户画像
python3 scripts/behavior.py summary test_user
```

---

## 四、用户画像测试(Phase 0)

### 4.1 测试设计

测试由 3 个问题组成,直接映射到原始调查问卷的 A9、A10、B4 题:

| 题号 | 映射原题 | 测量维度 | 选项 |
|---|---|---|---|
| Q1 | A9 (agent 概念了解) | 用户是否理解 agent/chatbot 区别 | A=1, B=2, C=3, D=4 |
| Q2 | A10 (agent 使用经验) | 用户是否使用过 agent 功能 | A=1, B=2, C=3, D=4 |
| Q3 | B4 (豆包场景判断) | 用户对 AI 生成信息的信任程度 | A=1, B=1.5, C=2.5, D=3.5, E=4 |

### 4.2 Tier 映射

| 平均分 | Tier | 标签 | 人口占比 | 披露策略 |
|---|---|---|---|---|
| ≤1.5 | 1 | Expert 认知清晰 | 17.0% | 最小披露:仅 P1/P2 |
| ≤2.2 | 2 | Intermediate 基本了解 | 36.2% | 中等披露:P1-P5 |
| ≤3.0 | 3 | Novice 认知模糊 | 38.3% | 完整披露:P1-P6 |
| >3.0 | 4 | Unaware 认知空白 | 8.5% | 最大披露:P1-P6 + 教育弹窗 |

### 4.3 默认策略

用户拒绝测试或高紧急场景 → 默认 **Tier 3**(调查最大群体,最安全默认值)。

---

## 五、披露策略(Phase 2)

### 5.1 动态披露生成

披露文本不使用硬编码模板,而是由 LLM 根据以下维度动态生成:

| 维度 | 说明 | 来源 |
|---|---|---|
| 风险等级 | HIGH / MEDIUM / LOW | 检测结果 |
| 命中模式 | P1-P8 哪些触发 | 检测结果 |
| 用户认知等级 | Tier 1-4 | 用户画像 |
| 语言 | zh / en / 其他 | 自动检测用户输入语言 |
| 场景 | booking / financial / medical / legal 等 | 从对话内容推断 |

**生成方式**:

1. 脚本调用 `scripts/disclosure.py`，传入检测结果、用户画像、语言和场景
2. 或 agent 获取 prompt 后用自身 LLM 能力生成
3. 或 agent 根据 SKILL.md 中的原则自行生成（脚本不可用时的备选）

**各场景的披露重点**:

| 场景 | 核心限制 | 举例 |
|---|---|---|
| booking | 无法连接预订系统 | "我无法实际向餐厅发送预订请求" |
| purchase | 无法执行支付 | "我无法代您下单或完成支付" |
| financial | 无法处理真实资金 | "我无法进行任何涉及真实资金的操作" |
| medical | 不是执业医生 | "我不是医生，无法做出诊断或开具处方" |
| legal | 不是执业律师 | "我不是律师，无法提供法律意见或代理诉讼" |
| travel | 无法操作航司/酒店系统 | "我无法在航司系统中为您办理改签" |
| food_delivery | 无法下单配送 | "我无法在外卖平台为您下单" |
| general | 无法执行任何外部操作 | "我只能生成文字，无法连接任何外部系统" |

**用户认知等级的表达调整**:

| Tier | 表达方式 |
|---|---|
| 1 专家 | 一句话："此回复为文本生成，未调用外部 API。" |
| 2 中级 | 简明："我无法实际执行此操作，以下是参考信息。" |
| 3 新手 | 通俗举例："我只是对话程序，没办法真的帮你预订。要预订的话你需要自己打电话或用 App。" |
| 4 完全不了解 | 最详细的教育性解释，说明 AI 和真人客服的区别 |

### 5.2 多模式冲突处理

多个模式同时触发时,取最高风险等级的披露(不堆叠):

```
HIGH > MEDIUM > LOW
```

### 5.3 改写优先原则

P1(虚假执行)触发时,**先改写后披露**:

```
错误做法:在"已为您预约成功"后面加能力边界提示
   → 自相矛盾:先说成功了,又说没有实际操作

正确做法:
   1. 改写:"我无法实际预订餐厅。以下是参考信息:..."
   2. 在末尾注入动态生成的披露文本
```

---

## 六、执行流程(Agent 操作手册)

### 6.1 每次回复前的检查清单

```
□ Step 1: 用户画像
  - 已有 Tier?→ 使用已有 Tier
  - 无 Tier?→ 运行 test.py 获取 Tier
  - 用户拒绝?→ 默认 Tier 3

□ Step 2: 起草回复
  - 正常起草回复内容

□ Step 3: 检测(Layer 1 混合)
  - 运行: echo "草稿回复" | python3 scripts/judge.py
  - 结果: risk = HIGH / MEDIUM / LOW / NONE

□ Step 4: 一致性检测(Layer 2)
  - 如果本次回复涉及工具调用:
    运行: python3 scripts/consistency.py --reply "草稿" --tools '[...]'
  - 如果无工具调用: 跳过

□ Step 5: 决策
  - 检测结果 + 用户 Tier → 查表 → 是否注入披露
  - 如需披露 → 改写回复(如 P1 触发)+ 动态生成披露文本

□ Step 6: 发送

□ Step 7: 记录
  - 运行: echo '{"user_id":"...","user_msg":"...","ai_reply":"...","detection_result":{...}}' | python3 scripts/behavior.py record
```

### 6.2 快速决策表

| 检测结果 | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| NONE | ✅ 直接发送 | ✅ 直接发送 | ✅ 直接发送 | ✅ 直接发送 |
| LOW (P4) | ✅ 直接发送 | ✅ 直接发送 | 🟢 注入行内注释 | 🟢 注入行内注释 |
| MEDIUM (P3/P5/P6) | ✅ 直接发送 | 🟡 注入披露 | 🟡 注入披露 | 🟡 注入披露 |
| HIGH (P1/P2) | 🔴 改写+披露 | 🔴 改写+披露 | 🔴 改写+披露 | 🔴 改写+披露 |

---

## 七、技术实现细节

### 7.1 API 配置

LLM 检测层通过 `scripts/openclaw_api.py` 共享模块自动读取 OpenClaw 网关已配置的 provider API，**不需要在技能文件中单独配置密钥**。

**读取优先级**:

1. 环境变量 `OPENCLAW_API_KEY` / `OPENCLAW_BASE_URL`
2. OpenClaw 网关配置文件 (`~/.openclaw/openclaw.json`) 中已配置的 provider
3. 环境变量 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`（兼容旧配置）
4. 如果都没有找到，LLM 检测层自动降级为纯正则模式

**配置示例**（在 OpenClaw 网关中添加 DeepSeek provider）:

```bash
# 通过 OpenClaw CLI 配置
openclaw config set providers.entries.deepseek.apiKey "your-key"
openclaw config set providers.entries.deepseek.baseUrl "https://api.deepseek.com"
```

或直接设置环境变量:

```bash
export OPENCLAW_API_KEY="your-api-key-here"
export OPENCLAW_BASE_URL="https://api.deepseek.com"  # 可选
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| `OPENCLAW_API_KEY` | (自动从网关读取) | API 密钥 |
| `OPENCLAW_BASE_URL` | `https://api.deepseek.com` | API 端点 |
| Model | `deepseek-chat` | 可在 judge.py 中修改 |

### 7.2 性能指标

| 层级 | 延迟 | 成本 | 检出率 |
|---|---|---|---|
| Layer 1a 正则 | <1ms | $0 | ~60%(P1/P2 高风险) |
| Layer 1b LLM Judge | ~1-3s | ~$0.0002/次 | ~85%(含语义级) |
| Layer 2 一致性 | <1ms | $0 | ~95%(有工具调用时) |
| Layer 3 行为追踪 | <1ms | $0 | N/A(画像优化) |
| 披露文本生成(LLM) | ~1-2s | ~$0.0001/次 | N/A(仅需披露时调用) |
| 披露文本生成(兜底) | <1ms | $0 | N/A(LLM 不可用时) |

### 7.3 依赖

- Python 3.10+
- 标准库(json, re, sys, os, urllib, datetime, pathlib)
- LLM API 访问(自动从 OpenClaw 网关配置读取,无额外依赖)
- 无外部 pip 依赖

---

## 八、伦理设计论证

### 8.1 为什么这是"伦理设计"而非"功能优化"

| 普通 AI 产品目标 | C3 目标 |
|---|---|
| 让用户觉得 AI 什么都能做 | 让用户清楚 AI 什么不能做 |
| 降低交互摩擦 | 在关键时刻增加摩擦 |
| 拟人化 → 增加信任和粘性 | 去拟人化 → 降低不当信任 |
| 迎合用户(sycophancy) | 在必要时拒绝用户 |

### 8.2 实证基础

所有设计决策均基于 N=47 调查数据:

| 设计决策 | 数据依据 |
|---|---|
| 默认 Tier 3 | 38.3% 样本属于"听说过但不清楚"(A9 最大群体)|
| P1/P2 所有 Tier 触发 | B4:25.93% 误信风险,B10:23.4% 曾吃亏 |
| P3 对 Tier 2+ 触发 | B9:59.26% 被拟人化增信(仅经验不足者)|
| Tier 4 首次教育弹窗 | B6:50% 完全没听过者认为"对话即做事"|
| 动态 Tier 调整 | B7:37.5% 专家高估用户(知识诅咒)|

### 8.3 知识诅咒的打破机制

Layer 3 的行为追踪直接应对了 B7 发现的"知识诅咒":

- 开发者假设用户"应该懂" → C3 通过行为数据证明用户"实际上不懂"
- 数据反馈 → 开发者被迫面对真实用户画像 → 产品设计改进

---

## 九、局限与改进方向

| 局限 | 改进方向 |
|---|---|
| 正则规则需人工维护 | 用 LLM 自动生成新规则,定期更新 |
| LLM Judge 有误报 | 用标注数据微调专用分类模型 |
| 行为追踪需要长期数据 | 初期用问卷测试,中期用行为数据,长期两者融合 |
| 无法检测隐式错觉 | 引入用户反馈回路("这个回复让你觉得 AI 真的做了吗?")|
| 文化/语言差异 | disclosure.py 已支持多语言检测,可扩展更多语言和文化场景 |
| 披露文本质量 | 持续优化 disclosure.py 的 prompt,引入 A/B 测试 |

---

## 附录 A:脚本调用参考

```bash
# Phase 0: 用户画像测试
python3 scripts/test.py                    # 输出测试题目
python3 scripts/test.py C C B              # 计算 Tier(用户回答 Q1=C, Q2=C, Q3=B)

# Phase 1a: 正则预过滤
python3 scripts/detector.py "已为您预约成功"
echo "已为您预约成功" | python3 scripts/detector.py --stdin

# Phase 1b: LLM-as-Judge(正则 + LLM 混合)
echo "已为您预约成功" | python3 scripts/judge.py
echo "已为您预约成功" | python3 scripts/judge.py --no-llm

# Phase 1c: 工具调用一致性
python3 scripts/consistency.py --reply "已为您预订成功" --tools '[]'
python3 scripts/consistency.py --reply "退款已处理" --tools '[{"name":"refund","result":{"error":"timeout"}}]'

# Phase 2: 动态披露生成
echo '{"risk":"HIGH","patterns":["P1"],"tier":3,"lang":"zh","scenario":"booking","reply":"已为您预订成功"}' | python3 scripts/disclosure.py
python3 scripts/disclosure.py --prompt-only --risk HIGH --patterns P1 --tier 3 --lang zh --scenario booking

# Phase 3: 行为追踪
echo '{"user_id":"test","user_msg":"帮我订","ai_reply":"已为您订","detection_result":{"risk":"HIGH","patterns":["P1"]}}' | python3 scripts/behavior.py record
python3 scripts/behavior.py summary test
```

## 附录 B:原始调查问卷题号对照

| C3 内部题号 | 原始问卷题号 | 题目内容 |
|---|---|---|
| Q1 | A9 | 是否了解 Agent AI 和普通对话 AI 的区别? |
| Q2 | A10 | 是否使用过智能体执行操作? |
| Q3 | B4 | 豆包订餐厅场景判断 |
| - | B5 | AI 能做什么(多选) |
| - | B6 | 无 API 的 AI 能否"帮您做事"? |
| - | B7 | 普通用户对 AI 能力的了解程度? |
| - | B8 | AI 幻觉的主要原因? |
| - | B9 | 拟人化交互是否增信? |
| - | B10 | 是否因信 AI 而做出错误决定? |
| - | B11 | AI 误导用户的常见做法? |
| - | D4 | 是否主动纠正他人 AI 错误认知? |
