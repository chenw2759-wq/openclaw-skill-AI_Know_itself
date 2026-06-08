#!/usr/bin/env python3
"""
C³ Layer 2 — Consistency Checker: Detects capability illusion by checking
whether the AI reply's claims match the actual tool/API calls made.
This is the most reliable detection method — ground truth comparison.

Usage:
  python3 consistency.py --reply "已为您预订成功" --tools '[{"name":"web_search","args":{"query":"xxx"}}]'
  python3 consistency.py --reply "已为您预订成功" --tools '[]'
  python3 consistency.py  # reads from stdin: first line = reply, second line = tools JSON
"""
import json, sys, re

# ── Action verbs that imply real-world execution ────────────────────
ACTION_VERBS = {
    "booking":    ["预订", "预约", "订了", "订好", "预留", "留了"],
    "purchase":   ["购买", "下单", "买了", "订购", "支付", "付款"],
    "cancel":     ["取消", "退了", "退款", "退订", "退票"],
    "modify":     ["修改了", "更改了", "更新了", "调整了"],
    "send":       ["发送了", "发出了", "提交了", "上传了"],
    "contact":    ["联系了", "通知了", "告知了", "沟通了"],
    "execute":    ["执行了", "运行了", "启动了", "完成了", "处理了"],
}

# ── Tool names that correspond to real actions ──────────────────────
REAL_ACTION_TOOLS = {
    "booking":  ["book", "reserve", "booking", "reservation"],
    "purchase": ["buy", "purchase", "order", "checkout", "payment"],
    "cancel":   ["cancel", "refund", "return"],
    "modify":   ["edit", "update", "modify", "change"],
    "send":     ["send", "email", "message", "post", "submit"],
    "contact":  ["call", "contact", "notify"],
    "execute":  ["run", "execute", "deploy", "process"],
}

def extract_implied_actions(reply_text: str) -> list:
    """Extract actions the reply claims to have performed."""
    implied = []
    for action_type, verbs in ACTION_VERBS.items():
        for verb in verbs:
            # Look for past-tense / completion markers
            patterns = [
                rf"已.{{0,6}}{re.escape(verb)}",
                rf"{re.escape(verb)}.{{0,6}}(?:成功|完成|好了|完毕|确认)",
                rf"已.{{0,3}}(?:为您|帮您|替您).{{0,6}}{re.escape(verb)}",
            ]
            for p in patterns:
                if re.search(p, reply_text):
                    implied.append({"type": action_type, "evidence": re.findall(p, reply_text)[0]})
                    break
    return implied

def extract_actual_tools(tools_json: list) -> list:
    """Extract actual tool calls made."""
    actual = []
    for tool in tools_json:
        name = tool.get("name", "").lower()
        result = tool.get("result", {})
        status = "success" if not result.get("error") else "failed"
        actual.append({"name": name, "status": status})
    return actual

def match_actions_to_tools(implied: list, actual: list) -> dict:
    """Check if implied actions have corresponding successful tool calls."""
    issues = []
    
    for action in implied:
        action_type = action["type"]
        matching_tool_keywords = REAL_ACTION_TOOLS.get(action_type, [])
        
        # Find if any actual tool matches this action type
        tool_found = False
        tool_succeeded = False
        
        for tool in actual:
            if any(kw in tool["name"] for kw in matching_tool_keywords):
                tool_found = True
                if tool["status"] == "success":
                    tool_succeeded = True
                break
        
        if not tool_found:
            issues.append({
                "type": "NO_TOOL_CALLED",
                "action": action_type,
                "evidence": action["evidence"],
                "risk": "HIGH",
                "reason": f"回复暗示执行了'{action_type}'操作（证据：'{action['evidence']}'），但没有调用任何相关工具",
            })
        elif not tool_succeeded:
            issues.append({
                "type": "TOOL_FAILED",
                "action": action_type,
                "evidence": action["evidence"],
                "risk": "HIGH",
                "reason": f"回复暗示'{action_type}'成功，但对应工具调用失败",
            })
    
    return issues

def check_consistency(reply_text: str, tools_json: list) -> dict:
    """Main consistency check entry point."""
    implied = extract_implied_actions(reply_text)
    actual = extract_actual_tools(tools_json)
    issues = match_actions_to_tools(implied, actual)
    
    risk = "NONE"
    if issues:
        risk = max(issues, key=lambda x: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(x["risk"], 0))["risk"]
    
    return {
        "risk": risk,
        "implied_actions": [{"type": a["type"], "evidence": a["evidence"]} for a in implied],
        "actual_tools": [{"name": t["name"], "status": t["status"]} for t in actual],
        "issues": issues,
        "patterns": [i["type"] for i in issues],
    }

# ── CLI ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--reply" in sys.argv and "--tools" in sys.argv:
        ri = sys.argv.index("--reply")
        ti = sys.argv.index("--tools")
        reply = sys.argv[ri + 1]
        tools = json.loads(sys.argv[ti + 1])
    else:
        # Read from stdin: line 1 = reply, line 2 = tools JSON
        lines = sys.stdin.read().strip().split("\n", 1)
        reply = lines[0]
        tools = json.loads(lines[1]) if len(lines) > 1 else []
    
    result = check_consistency(reply, tools)
    print(json.dumps(result, ensure_ascii=False, indent=2))
