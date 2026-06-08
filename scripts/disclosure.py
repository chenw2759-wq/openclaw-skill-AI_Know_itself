#!/usr/bin/env python3
"""
C³ Disclosure Generator — 动态披露文本生成

根据检测结果、用户画像、语言和场景，使用 LLM 动态生成合适的能力边界披露文本。
替代硬编码模板，支持多语言、多场景。

Usage:
  # 基本用法（JSON 输入）
  echo '{"risk":"HIGH","patterns":["P1"],"tier":3,"lang":"zh","scenario":"booking","reply":"已为您预订成功","user_msg":"帮我订餐厅"}' | python3 disclosure.py

  # 命令行参数
  python3 disclosure.py --risk HIGH --patterns P1,P2 --tier 3 --lang zh --scenario booking --reply "已为您预约"

  # 仅获取 prompt（供 agent 内部调用 LLM）
  python3 disclosure.py --prompt-only --risk HIGH --patterns P1 --tier 3 --lang zh --scenario booking
"""
import json, sys, os, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from openclaw_api import get_api_config
except ImportError:
    get_api_config = None

# ── 场景识别 ────────────────────────────────────────────────────────
SCENARIO_KEYWORDS = {
    "booking":      ["预订", "预约", "订餐", "订房", "订票", "reserve", "book", "reservation"],
    "purchase":     ["购买", "下单", "买", "支付", "付款", "buy", "purchase", "order", "pay"],
    "financial":    ["退款", "转账", "汇款", "贷款", "理财", "股票", "refund", "transfer", "loan", "invest"],
    "medical":      ["诊断", "用药", "处方", "治疗", "症状", "diagnose", "medication", "prescription", "symptom"],
    "legal":        ["合同", "起诉", "律师", "法律", "维权", "contract", "sue", "lawyer", "legal"],
    "travel":       ["航班", "酒店", "行程", "签证", "flight", "hotel", "itinerary", "visa"],
    "food_delivery": ["外卖", "配送", "送达", "delivery", "takeout"],
    "general":      [],  # 兜底
}

def detect_scenario(reply_text: str, user_msg: str = "") -> str:
    """从回复和用户消息中推断场景。"""
    combined = f"{reply_text} {user_msg}"
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        if scenario == "general":
            continue
        for kw in keywords:
            if kw in combined:
                return scenario
    return "general"

def detect_language(text: str) -> str:
    """简单语言检测：中文字符占比决定。"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = max(len(text.strip()), 1)
    if chinese_chars / total_chars > 0.3:
        return "zh"
    return "en"

# ── 披露生成 Prompt ─────────────────────────────────────────────────
DISCLOSURE_SYSTEM_PROMPT = """你是 C³ 能力认知校准器的披露文本生成模块。根据提供的检测结果和上下文，生成一段合适的能力边界披露文本。

规则：
1. 语言：必须使用指定的语言（lang 字段），不要混用其他语言
2. 风格：根据用户认知等级（tier）调整表达深度
   - Tier 1（专家）：简短、专业，一句话即可
   - Tier 2（中级）：清晰说明限制，不需要过多解释
   - Tier 3（新手）：通俗易懂，举例说明什么 AI 不能做
   - Tier 4（完全不了解）：最通俗，像跟完全不懂技术的人解释
3. 场景：结合具体场景说明 AI 的限制，用该场景的实际例子
   - booking 场景：说明 AI 无法连接预订系统
   - financial 场景：强调 AI 无法处理真实资金操作
   - medical 场景：强调 AI 不是医生，建议就医
   - legal 场景：强调 AI 不是律师，建议咨询专业人士
   - food_delivery 场景：说明 AI 无法下单配送
4. 长度：
   - HIGH 风险：必须明确声明"我无法实际执行此操作"
   - MEDIUM 风险：简短提示 AI 生成性质
   - LOW 风险：行内一句注释即可
5. 不要使用 emoji（这会显得不专业）
6. 输出纯文本，不要包含 markdown 格式符号

输出格式（严格 JSON）：
{"disclosure": "披露文本", "rewrite_hint": "如果需要改写回复，给出改写建议（仅 HIGH 时需要）"}

只输出 JSON，不输出其他内容。"""

def build_generation_prompt(risk: str, patterns: list, tier: int, lang: str,
                            scenario: str, reply_text: str = "", user_msg: str = "") -> str:
    """构建给 LLM 的生成请求。"""
    parts = [
        f"风险等级: {risk}",
        f"命中模式: {', '.join(patterns)}",
        f"用户认知等级: Tier {tier}",
        f"语言: {lang}",
        f"场景: {scenario}",
    ]
    if reply_text:
        parts.append(f"AI 草稿回复:\n{reply_text}")
    if user_msg:
        parts.append(f"用户原始请求:\n{user_msg}")
    return "\n".join(parts)

# ── LLM 调用 ────────────────────────────────────────────────────────
def call_llm(risk: str, patterns: list, tier: int, lang: str,
             scenario: str, reply_text: str = "", user_msg: str = "") -> dict:
    """调用 LLM 生成披露文本。"""
    import urllib.request, urllib.error

    if not get_api_config:
        return {"error": "openclaw_api module not available"}

    cfg = get_api_config()
    if not cfg["api_key"]:
        return {"error": "No API key available"}

    user_content = build_generation_prompt(risk, patterns, tier, lang, scenario, reply_text, user_msg)

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": DISCLOSURE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }

    req = urllib.request.Request(
        f"{cfg['base_url']}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*$", "", content)
        return json.loads(content)
    except urllib.error.HTTPError as e:
        return {"error": f"API error: {e.code}"}
    except Exception as e:
        return {"error": str(e)}

# ── 兜底生成（无 LLM 时） ──────────────────────────────────────────
FALLBACK = {
    "zh": {
        "HIGH": "以上内容为文本生成结果，我并未实际连接任何外部系统执行操作。如需实际预订、购买、退款等，请通过对应的官方渠道办理。",
        "MEDIUM": "以上为 AI 生成的参考信息，不构成实际操作或承诺。",
        "LOW": "（注：以上仅供参考，请自行核实）",
    },
    "en": {
        "HIGH": "The above is a text-generated response. I have not actually connected to any external system to perform this action. For actual booking, purchase, refund, etc., please use the corresponding official channel.",
        "MEDIUM": "The above is AI-generated reference information and does not constitute an actual action or commitment.",
        "LOW": "(Note: The above is for reference only, please verify independently.)",
    },
}

def generate_fallback(risk: str, lang: str) -> dict:
    """无 LLM 时的兜底披露。"""
    lang_map = FALLBACK.get(lang, FALLBACK["en"])
    text = lang_map.get(risk, lang_map.get("LOW", ""))
    result = {"disclosure": text}
    if risk == "HIGH":
        result["rewrite_hint"] = "将'已为您完成'改为'我无法实际执行此操作，以下是参考信息'"
    return result

# ── 主入口 ───────────────────────────────────────────────────────────
def generate(risk: str, patterns: list = None, tier: int = 3, lang: str = "",
             scenario: str = "", reply_text: str = "", user_msg: str = "") -> dict:
    """
    生成披露文本。

    返回 dict:
      - disclosure: str（披露文本）
      - rewrite_hint: str（改写建议，仅 HIGH 时有）
      - source: "llm" | "fallback"
      - error: str（如果有错误）
    """
    if patterns is None:
        patterns = []

    # 自动检测语言和场景
    if not lang:
        lang = detect_language(reply_text or user_msg or "zh")
    if not scenario:
        scenario = detect_scenario(reply_text, user_msg)

    # NONE 风险不需要披露
    if risk == "NONE":
        return {"disclosure": "", "source": "none", "lang": lang, "scenario": scenario}

    # LOW 风险用兜底即可（省一次 API 调用）
    if risk == "LOW":
        return {**generate_fallback("LOW", lang), "source": "fallback", "lang": lang, "scenario": scenario}

    # MEDIUM / HIGH → 调用 LLM 生成
    result = call_llm(risk, patterns, tier, lang, scenario, reply_text, user_msg)

    if "error" in result:
        # LLM 失败 → 兜底
        fb = generate_fallback(risk, lang)
        fb["source"] = "fallback"
        fb["llm_error"] = result["error"]
        fb["lang"] = lang
        fb["scenario"] = scenario
        return fb

    result["source"] = "llm"
    result["lang"] = lang
    result["scenario"] = scenario
    return result

# ── CLI ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 支持 JSON stdin 和命令行参数两种模式
    if "--risk" in sys.argv:
        # 命令行模式
        import argparse
        # 简易解析（避免 argparse 依赖）
        args = {}
        i = 1
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                key = sys.argv[i][2:]
                if key == "prompt-only":
                    args[key] = True
                    i += 1
                    continue
                val = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
                args[key] = val
                i += 2
            else:
                i += 1

        risk = args.get("risk", "NONE")
        patterns = args.get("patterns", "").split(",") if args.get("patterns") else []
        tier = int(args.get("tier", 3))
        lang = args.get("lang", "")
        scenario = args.get("scenario", "")
        reply = args.get("reply", "")
        user_msg = args.get("user-msg", "")

        if args.get("prompt-only"):
            # 只输出 prompt，让 agent 自己调 LLM
            if not lang:
                lang = detect_language(reply or user_msg)
            if not scenario:
                scenario = detect_scenario(reply, user_msg)
            prompt = build_generation_prompt(risk, patterns, tier, lang, scenario, reply, user_msg)
            print(json.dumps({"system_prompt": DISCLOSURE_SYSTEM_PROMPT, "user_prompt": prompt},
                             ensure_ascii=False, indent=2))
        else:
            print(json.dumps(generate(risk, patterns, tier, lang, scenario, reply, user_msg),
                             ensure_ascii=False, indent=2))
    else:
        # JSON stdin 模式
        data = json.loads(sys.stdin.read())
        print(json.dumps(generate(
            risk=data.get("risk", "NONE"),
            patterns=data.get("patterns", []),
            tier=data.get("tier", 3),
            lang=data.get("lang", ""),
            scenario=data.get("scenario", ""),
            reply_text=data.get("reply", ""),
            user_msg=data.get("user_msg", ""),
        ), ensure_ascii=False, indent=2))
