#!/usr/bin/env python3
"""
OpenClaw API Config Reader — 共享模块

从 OpenClaw 网关配置中读取 LLM provider 的 API 密钥和端点，
供 C³ 技能的 LLM 检测层使用，避免在技能文件中硬编码或单独存储密钥。

读取优先级：
  1. 环境变量 OPENCLAW_API_KEY / OPENCLAW_BASE_URL
  2. OpenClaw 网关配置文件 (~/.openclaw/openclaw.json)
  3. 环境变量 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL（兼容旧配置）
  4. 如果都没有，返回空配置（调用方应降级为纯正则模式）
"""
import json
import os
import re
from pathlib import Path


def _read_openclaw_config() -> dict:
    """读取 OpenClaw 网关配置文件，返回解析后的 dict。读取失败返回空 dict。"""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # 尝试用正则作为后备（配置文件可能含注释或尾逗号）
        try:
            with open(config_path, encoding="utf-8") as f:
                raw = f.read()
            return {"_raw": raw}
        except OSError:
            return {}


def _extract_from_raw(raw_text: str, provider_hint: str = "") -> dict:
    """从原始配置文本中用正则提取 API 信息（后备方案）。"""
    result = {}
    # 尝试匹配 provider 块中的 apiKey 和 baseUrl
    providers_to_try = [provider_hint, "deepseek", "openai", "openrouter"]
    for prov in providers_to_try:
        if not prov:
            continue
        # 匹配 "providerName": { ... "apiKey": "xxx" ... "baseUrl": "xxx" ... }
        block_pattern = rf'"{re.escape(prov)}"\s*:\s*\{{([^}}]*)\}}'
        block_match = re.search(block_pattern, raw_text, re.DOTALL)
        if block_match:
            block = block_match.group(1)
            key_match = re.search(r'"apiKey"\s*:\s*"([^"]+)"', block)
            url_match = re.search(r'"baseUrl"\s*:\s*"([^"]+)"', block)
            if key_match:
                result["api_key"] = key_match.group(1)
            if url_match:
                result["base_url"] = url_match.group(1)
            if result:
                result.setdefault("provider", prov)
                return result

    # 全局搜索任何 apiKey（最后手段）
    key_match = re.search(r'"apiKey"\s*:\s*"([^"]+)"', raw_text)
    url_match = re.search(r'"baseUrl"\s*:\s*"([^"]+)"', raw_text)
    if key_match:
        result["api_key"] = key_match.group(1)
    if url_match:
        result["base_url"] = url_match.group(1)
    return result


def _extract_from_json(config: dict, provider_hint: str = "") -> dict:
    """从已解析的 JSON 配置中提取 API 信息。"""
    result = {}

    # 路径 1: providers.entries.<provider>.auth.apiKey
    providers = config.get("providers", {})
    if isinstance(providers, dict):
        entries = providers.get("entries", {})
        if isinstance(entries, dict):
            # 优先尝试指定的 provider
            candidates = []
            if provider_hint and provider_hint in entries:
                candidates.append(provider_hint)
            # 然后尝试常见的 provider
            for name in ["deepseek", "openai", "openrouter"]:
                if name in entries and name not in candidates:
                    candidates.append(name)
            # 最后兜底：取第一个有 apiKey 的
            for name, entry in entries.items():
                if name not in candidates:
                    candidates.append(name)

            for name in candidates:
                entry = entries.get(name, {})
                if not isinstance(entry, dict):
                    continue
                auth = entry.get("auth", {})
                if isinstance(auth, dict) and auth.get("apiKey"):
                    result["api_key"] = auth["apiKey"]
                    result["provider"] = name
                if entry.get("baseUrl"):
                    result["base_url"] = entry["baseUrl"]
                elif entry.get("baseURL"):
                    result["base_url"] = entry["baseURL"]
                if result:
                    return result

    # 路径 2: llm.apiKey / llm.baseUrl（旧版配置格式）
    llm = config.get("llm", {})
    if isinstance(llm, dict):
        if llm.get("apiKey"):
            result["api_key"] = llm["apiKey"]
        if llm.get("baseUrl"):
            result["base_url"] = llm["baseUrl"]
        if llm.get("model"):
            result["model"] = llm["model"]
        if result:
            return result

    return result


def get_api_config(provider_hint: str = "", model_hint: str = "") -> dict:
    """
    获取 LLM API 配置。返回 dict 包含：
      - api_key: str（可能为空）
      - base_url: str（有默认值）
      - model: str（有默认值）
      - provider: str（来源标识）

    调用方应检查 api_key 是否为空，为空时降级处理。
    """
    result = {
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": model_hint or "deepseek-chat",
        "provider": "unknown",
    }

    # 优先级 1: 环境变量 OPENCLAW_*
    env_key = os.environ.get("OPENCLAW_API_KEY", "")
    env_url = os.environ.get("OPENCLAW_BASE_URL", "")
    if env_key:
        result["api_key"] = env_key
        result["base_url"] = env_url or result["base_url"]
        result["provider"] = "env_openclaw"
        return result

    # 优先级 2: OpenClaw 网关配置
    config = _read_openclaw_config()
    if config:
        if "_raw" in config:
            extracted = _extract_from_raw(config["_raw"], provider_hint)
        else:
            extracted = _extract_from_json(config, provider_hint)

        if extracted.get("api_key"):
            result["api_key"] = extracted["api_key"]
            result["base_url"] = extracted.get("base_url", result["base_url"])
            result["model"] = extracted.get("model", result["model"])
            result["provider"] = extracted.get("provider", "openclaw_config")
            return result

    # 优先级 3: 兼容旧配置 DEEPSEEK_*
    env_key = os.environ.get("DEEPSEEK_API_KEY", "")
    env_url = os.environ.get("DEEPSEEK_BASE_URL", "")
    if env_key:
        result["api_key"] = env_key
        result["base_url"] = env_url or result["base_url"]
        result["provider"] = "env_deepseek"
        return result

    # 都没找到
    return result


if __name__ == "__main__":
    # 调试用：打印当前 API 配置（隐藏密钥）
    cfg = get_api_config()
    safe = {**cfg}
    if safe.get("api_key"):
        safe["api_key"] = safe["api_key"][:8] + "..." + safe["api_key"][-4:]
    print(json.dumps(safe, ensure_ascii=False, indent=2))
