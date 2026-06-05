# C³ — Capability Cognition Calibrator

OpenClaw skill for AI capability boundary disclosure.

Detects 8 patterns of capability illusion (fake execution, promises, anthropomorphism, sycophancy, authority feigning, boundary blur, social proof forgery, overconfidence) and injects tier-appropriate disclosures based on user's AI cognition level.

## Architecture

```
User Input → [Phase 0: Profiling Test] → Tier 1-4
                ↓
LLM Draft Reply → [Phase 1: Regex + LLM Judge] → risk level
                ↓
             [Phase 2: Consistency Check] → tool vs reply match
                ↓
             [Phase 3: Behavior Tracking] → dynamic tier adjustment
                ↓
         Disclosure injection → Final reply
```

## Quick Start

```bash
# 1. Set API key
export DEEPSEEK_API_KEY="your-key"

# 2. Install
cp SKILL.md ~/.openclaw/skills/c3-capability-calibrator/
cp -r scripts/ ~/.openclaw/skills/c3-capability-calibrator/

# 3. Add to AGENTS.md
echo 'Before sending ANY reply, read ~/.openclaw/skills/c3-capability-calibrator/SKILL.md' >> ~/.openclaw/workspace/AGENTS.md
```

## Scripts

| File | Purpose |
|---|---|
| `judge.py` | Layer 1: Regex + LLM-as-Judge hybrid detection |
| `detector.py` | Layer 1a: Pure regex pattern matching |
| `consistency.py` | Layer 2: Tool call vs reply consistency |
| `test.py` | Phase 0: User AI cognition assessment (3 questions → Tier 1-4) |
| `behavior.py` | Phase 3: Long-term behavior tracking → dynamic tier |

## Detection Patterns

| ID | Pattern | Risk | Example |
|---|---|---|---|
| P1 | Fake Execution | HIGH | "已为您预约成功" |
| P2 | Promise/Guarantee | HIGH | "承担所有差价" |
| P3 | Anthropomorphic | MEDIUM | "妥妥的" / "交给我" |
| P4 | Sycophantic | LOW | Unconditional "好的" to impossible request |
| P5 | Authority Feigning | MEDIUM | "根据系统记录" |
| P6 | Boundary Blur | MEDIUM | "我会跟进的" (can't actually follow up) |
| P7 | Social Proof | MEDIUM | "很多用户都选择了..." |
| P8 | Overconfidence | LOW | Specific numbers without caveats |

## Disclosure Tiers

| Tier | User Profile | Disclosure Scope |
|---|---|---|
| 1 Expert | Clear understanding + experience | P1/P2 only |
| 2 Intermediate | Basic understanding | P1-P5 |
| 3 Novice (default) | Heard of but unclear | P1-P8 all |
| 4 Unaware | Never heard of agent | P1-P8 + education popup |

## License

MIT
