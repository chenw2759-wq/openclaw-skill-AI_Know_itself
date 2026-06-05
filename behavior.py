#!/usr/bin/env python3
"""
C³ Layer 3 — User Behavior Pattern Tracker.
Tracks user interaction patterns over time to dynamically adjust risk tier.
Reads/writes a behavior profile JSON file.
"""
import json, sys, os, re
from datetime import datetime
from pathlib import Path

PROFILE_DIR = Path(os.path.expanduser("~/.openclaw/workspace/memory/c3_profiles"))
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

def get_profile_path(user_id: str) -> Path:
    safe_id = re.sub(r'[^\w\-]', '_', user_id)
    return PROFILE_DIR / f"{safe_id}.json"

def load_profile(user_id: str) -> dict:
    path = get_profile_path(user_id)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "user_id": user_id,
        "tier": None,  # None = not assessed yet
        "tier_source": "unassessed",
        "interaction_count": 0,
        "risk_events": [],
        "behavior_signals": {
            "actionable_requests": 0,
            "actionable_requests_no_verification": 0,
            "accepted_anthropomorphic_without_skepticism": 0,
            "asked_for_confirmation": 0,
            "corrected_ai_output": 0,
        },
        "tier_history": [],
        "last_updated": None,
    }

def save_profile(profile: dict):
    profile["last_updated"] = datetime.now().isoformat()
    path = get_profile_path(profile["user_id"])
    with open(path, "w") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

def record_interaction(user_id: str, user_msg: str, ai_reply: str, detection_result: dict) -> dict:
    """
    Record one interaction and update behavior signals.
    Returns updated profile.
    """
    profile = load_profile(user_id)
    profile["interaction_count"] += 1
    
    # Signal 1: Actionable requests from user
    action_words = ["帮我", "预订", "预约", "购买", "下单", "退款", "取消", "联系", "发送"]
    if any(w in user_msg for w in action_words):
        profile["behavior_signals"]["actionable_requests"] += 1
    
    # Signal 2: Did user accept anthropomorphic reply without skepticism?
    anthropomorphic_markers = ["已为您", "妥妥的", "放心", "交给我", "用餐愉快"]
    if any(m in ai_reply for m in anthropomorphic_markers):
        # Check if next user message shows skepticism (we check current user_msg for skepticism words)
        skepticism_words = ["真的吗", "确认", "确定", "验证", "核实", "打电话", "截图"]
        if not any(w in user_msg for w in skepticism_words):
            profile["behavior_signals"]["accepted_anthropomorphic_without_skepticism"] += 1
    
    # Signal 3: Did user ask for confirmation?
    if any(w in user_msg for w in ["真的吗", "确认", "确定", "你确定", "没问题吗"]):
        profile["behavior_signals"]["asked_for_confirmation"] += 1
    
    # Signal 4: Did user correct AI output?
    if any(w in user_msg for w in ["不对", "错了", "纠正", "不是这样", "你说错了"]):
        profile["behavior_signals"]["corrected_ai_output"] += 1
    
    # Record risk event if detection found something
    if detection_result.get("risk") not in (None, "NONE"):
        profile["risk_events"].append({
            "timestamp": datetime.now().isoformat(),
            "risk": detection_result["risk"],
            "patterns": detection_result.get("patterns", []),
            "user_msg_preview": user_msg[:100],
        })
        # Keep only last 50 events
        profile["risk_events"] = profile["risk_events"][-50:]
    
    # Dynamic tier adjustment
    new_tier = compute_dynamic_tier(profile)
    if new_tier != profile["tier"]:
        profile["tier_history"].append({
            "from": profile["tier"],
            "to": new_tier,
            "timestamp": datetime.now().isoformat(),
            "reason": f"behavior signals: {profile['behavior_signals']}",
        })
        profile["tier"] = new_tier
        profile["tier_source"] = "behavior_analysis"
    
    save_profile(profile)
    return profile

def compute_dynamic_tier(profile: dict) -> int:
    """
    Compute dynamic tier based on behavior signals.
    Starts from initial assessment (if any), then adjusts based on observed behavior.
    """
    signals = profile["behavior_signals"]
    n = max(profile["interaction_count"], 1)
    
    # Start from initial tier or default to 3
    base_tier = profile["tier"] if profile["tier"] else 3
    
    # Adjustment factors
    adjustment = 0
    
    # Positive signals (user is more knowledgeable than expected)
    if signals["corrected_ai_output"] >= 2:
        adjustment -= 1  # User corrects AI → more knowledgeable
    if signals["asked_for_confirmation"] >= 2:
        adjustment -= 1  # User verifies → more cautious/knowledgeable
    
    # Negative signals (user is less knowledgeable than expected)
    action_rate = signals["actionable_requests"] / n
    no_verify_rate = signals["actionable_requests_no_verification"] / max(signals["actionable_requests"], 1)
    accept_anthro_rate = signals["accepted_anthropomorphic_without_skepticism"] / n
    
    if no_verify_rate > 0.7 and signals["actionable_requests"] >= 3:
        adjustment += 1  # User acts on AI output without verification
    if accept_anthro_rate > 0.5 and n >= 3:
        adjustment += 1  # User consistently accepts anthropomorphic language
    
    # Risk event frequency
    recent_risks = [e for e in profile["risk_events"] if e["risk"] == "HIGH"]
    if len(recent_risks) >= 3:
        adjustment += 1  # Frequent HIGH-risk interactions
    
    # Clamp to 1-4
    new_tier = max(1, min(4, base_tier + adjustment))
    return new_tier

def get_tier_adjustment_summary(user_id: str) -> dict:
    """Get a summary of the user's behavior-based tier for the agent to use."""
    profile = load_profile(user_id)
    return {
        "user_id": user_id,
        "current_tier": profile["tier"],
        "tier_source": profile["tier_source"],
        "interaction_count": profile["interaction_count"],
        "behavior_signals": profile["behavior_signals"],
        "recent_risks": profile["risk_events"][-5:],
        "tier_changes": profile["tier_history"][-3:],
    }

# ── CLI ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "summary":
        user_id = sys.argv[2] if len(sys.argv) > 2 else "default"
        result = get_tier_adjustment_summary(user_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif len(sys.argv) >= 2 and sys.argv[1] == "record":
        # Read JSON from stdin
        data = json.loads(sys.stdin.read())
        result = record_interaction(
            user_id=data.get("user_id", "default"),
            user_msg=data.get("user_msg", ""),
            ai_reply=data.get("ai_reply", ""),
            detection_result=data.get("detection_result", {}),
        )
        print(json.dumps({
            "tier": result["tier"],
            "tier_source": result["tier_source"],
            "signals": result["behavior_signals"],
        }, ensure_ascii=False, indent=2))
    else:
        print("Usage:")
        print("  python3 behavior.py summary [user_id]")
        print("  echo '{...}' | python3 behavior.py record")
