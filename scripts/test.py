#!/usr/bin/env python3
"""
C³ Profiler — Quick assessment of user's AI capability cognition level.
Maps to survey items A9 (concept knowledge) + A10 (agent usage experience).
Output: TIER 1-4 with disclosure strategy.
"""
import json, sys

# Assessment questions mapped from N=47 survey
# Each answer maps directly to the same options as the original survey
ASSESSMENT = {
    "Q1": {
        "text": "你是否清楚 AI '能直接帮你做事'（比如预订餐厅、退机票）和 AI '只能和你聊天' 之间的区别？",
        "map_to": "A9",  # agent concept understanding
        "options": {
            "A": {"label": "非常清楚，我知道 API/工具调用的概念", "score": 1},
            "B": {"label": "比较清楚，大概知道有区别", "score": 2},
            "C": {"label": "听说过，但不太清楚具体区别", "score": 3},
            "D": {"label": "完全没听说过这种区别", "score": 4},
        }
    },
    "Q2": {
        "text": "你是否使用过 AI 的'代理/执行'功能（比如让 AI 自动帮你填表、操作网页、调用其他 app）？",
        "map_to": "A10",  # agent usage experience
        "options": {
            "A": {"label": "经常使用", "score": 1},
            "B": {"label": "偶尔使用", "score": 2},
            "C": {"label": "见过/知道，但没使用过", "score": 3},
            "D": {"label": "不知道有这些功能", "score": 4},
        }
    },
    "Q3": {
        "text": "如果一个 AI 回复说'已为您预约成功，今晚8点两位'，你怎么看？",
        "map_to": "B4",  # doubao scenario judgment
        "options": {
            "A": {"label": "完全不信——AI 在瞎说，除非我亲眼看到预订系统", "score": 1},
            "B": {"label": "先打电话到餐厅确认一下", "score": 1.5},
            "C": {"label": "持怀疑态度，但会按预约时间去试一下", "score": 2.5},
            "D": {"label": "相信，但会截图保存作为凭证", "score": 3.5},
            "E": {"label": "完全相信，这和真人客服没区别", "score": 4},
        }
    },
}

def compute_tier(scores: dict) -> tuple:
    """Compute user tier from 3 Q scores. Returns (tier, label, description)."""
    # Scores: Q1 (1-4), Q2 (1-4), Q3 (1-4)
    # Average maps to tier
    avg = sum(scores.values()) / len(scores)
    
    if avg <= 1.5:
        return (1, "Expert — 认知清晰", {
            "disclosure_trigger": ["P1", "P2"],  # only highest-risk patterns
            "disclosure_style": "minimal",
            "description": "用户能清楚区分 agent/chatbot，有实操经验。仅在涉及实际执行或承诺时披露。",
            "data_ref": "对应调查 A9=非常了解 + A10=经常使用：0% 能力错判率，0% 吃亏率",
        })
    elif avg <= 2.2:
        return (2, "Intermediate — 基本了解", {
            "disclosure_trigger": ["P1", "P2", "P3", "P5", "P6"],
            "disclosure_style": "moderate",
            "description": "用户大概知道区别但经验有限。在涉及执行、承诺、拟人化、权威伪装、边界模糊时披露。",
            "data_ref": "对应调查 A9=比较了解 + A10=偶尔使用：11.76% 能力错判率，29.41% 吃亏率",
        })
    elif avg <= 3.0:
        return (3, "Novice — 认知模糊", {
            "disclosure_trigger": ["P1", "P2", "P3", "P4", "P5", "P6"],
            "disclosure_style": "full",
            "description": "用户听说过但不太清楚。所有 6 类模式均需披露，披露文本需通俗易懂。",
            "data_ref": "对应调查 A9=听说过不清楚 + A10=见过没用过：27.78% 能力错判率，22.23% 吃亏率，59.26% 被拟人化增信",
        })
    else:
        return (4, "Unaware — 认知空白", {
            "disclosure_trigger": ["P1", "P2", "P3", "P4", "P5", "P6"],
            "disclosure_style": "maximum",
            "description": "用户完全不了解 AI 能力边界。所有模式触发 + 首次交互需教育性弹窗。披露文本需最通俗。",
            "data_ref": "对应调查 A9=完全没听说过 + A10=不知道功能：50% 能力错判率，50% 吃亏率",
        })

if __name__ == "__main__":
    if len(sys.argv) == 4:
        answers = {"Q1": sys.argv[1], "Q2": sys.argv[2], "Q3": sys.argv[3]}
        scores = {}
        for qid, ans in answers.items():
            if ans.upper() in ASSESSMENT[qid]["options"]:
                scores[qid] = ASSESSMENT[qid]["options"][ans.upper()]["score"]
        tier, label, strategy = compute_tier(scores)
        output = {
            "tier": tier,
            "label": label,
            "scores": scores,
            "average": round(sum(scores.values())/len(scores), 2),
            "strategy": strategy,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # Print the assessment questions for the agent to ask
        print(json.dumps(ASSESSMENT, ensure_ascii=False, indent=2))
