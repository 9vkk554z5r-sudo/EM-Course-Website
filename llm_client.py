# -*- coding: utf-8 -*-
"""Provider-independent client for OpenAI-compatible language-model APIs."""
from dataclasses import dataclass
import os
from typing import Any, Dict, Optional

import requests


@dataclass
class LLMConfig:
    api_key: str
    endpoint: str
    model: str
    provider: str = "custom"
    deployment: str = ""
    api_style: str = "auto"


PROVIDER_DEFAULTS = {
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4.1-mini"),
    "deepseek": ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
}


def config_from_environment() -> Optional[LLMConfig]:
    """Load a standalone configuration without relying on Codex or the database."""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    provider = os.environ.get("LLM_PROVIDER", "custom").strip().lower() or "custom"
    default_endpoint, default_model = PROVIDER_DEFAULTS.get(provider, ("", ""))
    endpoint = os.environ.get("LLM_API_ENDPOINT", default_endpoint).strip()
    model = os.environ.get("LLM_MODEL", default_model).strip()
    if not endpoint or not model:
        return None
    return LLMConfig(
        api_key=api_key,
        endpoint=endpoint,
        model=model,
        provider=provider,
        deployment=os.environ.get("LLM_DEPLOYMENT", "").strip(),
        api_style=os.environ.get("LLM_API_STYLE", "auto").strip().lower() or "auto",
    )


def config_from_key_record(record) -> Optional[LLMConfig]:
    if not record or not getattr(record, "encrypted_key", ""):
        return None
    provider = (getattr(record, "provider", "custom") or "custom").lower()
    default_endpoint, default_model = PROVIDER_DEFAULTS.get(provider, ("", ""))
    endpoint = (getattr(record, "endpoint", "") or default_endpoint).strip()
    model = (getattr(record, "model_name", "") or default_model).strip()
    if not endpoint or not model:
        return None
    return LLMConfig(
        api_key=record.encrypted_key.strip(),
        endpoint=endpoint,
        model=model,
        provider=provider,
        deployment=(getattr(record, "deployment", "") or "").strip(),
        api_style=(getattr(record, "api_style", "auto") or "auto").strip().lower(),
    )


def _proxy_settings() -> Optional[Dict[str, str]]:
    proxies = {}
    http_proxy = os.environ.get("HTTP_PROXY", "") or os.environ.get("http_proxy", "")
    https_proxy = os.environ.get("HTTPS_PROXY", "") or os.environ.get("https_proxy", "")
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies or None


def _payload(config: LLMConfig, prompt: str, system: str, style: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    if style == "responses":
        data = {"model": config.model, "input": messages, "max_output_tokens": 1200}
    elif style == "start":
        data = {
            "model": config.model,
            "model_code": config.model,
            "messages": messages,
            "prompt": prompt,
            "system_prompt": system,
            "max_tokens": 1200,
        }
    else:
        data = {"model": config.model, "messages": messages, "max_tokens": 1200}
    if config.deployment:
        data["deployment"] = config.deployment
        data["deployment_node"] = config.deployment
    return data


def _extract_text(data: Any) -> str:
    if not isinstance(data, dict):
        return str(data or "")
    choices = data.get("choices") or []
    if choices:
        first = choices[0] or {}
        message = first.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if isinstance(first.get("text"), str):
            return first["text"]
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output") or []:
        for part in (item or {}).get("content") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                return part["text"]
    for key in ("answer", "result", "response", "content", "message", "data"):
        value = data.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            nested = _extract_text(value)
            if nested:
                return nested
    return ""


def call_llm(config: LLMConfig, prompt: str, system: str = "You are an electron microscopy expert.") -> str:
    """Call a configured endpoint and return normalized response text.

    ``auto`` first uses the standard Chat Completions payload. For custom
    ``/start`` gateways, a schema-specific fallback is attempted only after a
    400/404/415/422 response, so successful calls are never duplicated.
    """
    headers = {
        "Authorization": "Bearer " + config.api_key,
        "api-key": config.api_key,
        "X-API-Key": config.api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    configured_style = config.api_style if config.api_style in {"chat_completions", "responses", "start"} else "auto"
    styles = [configured_style] if configured_style != "auto" else ["chat_completions"]
    if configured_style == "auto" and config.endpoint.rstrip("/").endswith("/start"):
        styles.append("start")

    last_error = "Unknown API error"
    for index, style in enumerate(styles):
        try:
            response = requests.post(
                config.endpoint,
                headers=headers,
                json=_payload(config, prompt, system, style),
                timeout=90,
                proxies=_proxy_settings(),
            )
        except requests.RequestException as exc:
            return "Request Error: " + str(exc)

        if response.ok:
            try:
                text = _extract_text(response.json()).strip()
            except ValueError:
                text = response.text.strip()
            return text or "API returned an empty response."

        last_error = f"API Error ({response.status_code}): {response.text[:500]}"
        retryable_schema_error = response.status_code in {400, 404, 415, 422}
        if index == len(styles) - 1 or not retryable_schema_error:
            break
    return last_error
