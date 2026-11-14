"""Gemini engine (Google AI Studio key). Same tools, prompt and guardrails as the
Claude engine in agent.py - only the transport differs.

Set GEMINI_API_KEY (or GOOGLE_API_KEY) from https://aistudio.google.com/apikey .
GEMINI_MODEL overrides the model; if it isn't available to the key, the newest
Flash model the key can see is picked automatically.
"""
from __future__ import annotations

import json
import os

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
THINKING = os.environ.get("GEMINI_THINKING", "low")  # low = snappy chat on mobile; "" to use the model default
_resolved: dict = {}
SESSIONS: dict[str, dict] = {}


def api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def available() -> bool:
    if not api_key():
        return False
    try:
        import google.genai  # noqa: F401
        return True
    except ImportError:
        return False


def _client():
    from google import genai
    from google.genai import types
    # 45 s per request; the SDK retries transient errors itself
    return genai.Client(api_key=api_key(), http_options=types.HttpOptions(timeout=45_000))


def _pick_model(client) -> str:
    """Newest Flash model that supports generateContent for this key."""
    if "model" in _resolved:
        return _resolved["model"]
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        name = (m.name or "").removeprefix("models/")
        if "generateContent" in actions and "flash" in name and not any(
                x in name for x in ("tts", "image", "live", "lite", "audio", "embedding")):
            names.append(name)
    if not names:
        raise RuntimeError("no Gemini Flash model available for this API key")
    _resolved["model"] = sorted(names, reverse=True)[0]
    return _resolved["model"]


def _config(system: str):
    from google.genai import types
    from .agent import TOOLS
    decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                       parameters_json_schema=t["input_schema"]) for t in TOOLS]
    kw = {}
    if THINKING and not _resolved.get("no_thinking_level"):
        kw["thinking_config"] = types.ThinkingConfig(thinking_level=THINKING)
    return types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=decls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **kw,
    )


def chat(customer_id: str, message: str, session_id: str, include_other_banks: bool,
         system: str, run_tool, strip, clean) -> dict:
    from google.genai import errors, types

    if len(SESSIONS) > 500:  # bound memory: drop the oldest conversation
        SESSIONS.pop(next(iter(SESSIONS)))
    sess = SESSIONS.setdefault(session_id, {"customer": customer_id, "contents": []})
    if sess["customer"] != customer_id or len(sess["contents"]) > 60:  # new customer or very long chat: start fresh
        sess.update(customer=customer_id, contents=[])
    contents = sess["contents"]
    start_len = len(contents)
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    client, cfg = _client(), _config(system)
    model = _resolved.get("model", MODEL)
    charts, tools_used = [], []
    try:
        for _ in range(8):
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            except errors.ClientError as e:
                if getattr(e, "code", None) == 400 and "thinking" in str(e).lower() and "thinking_config" in cfg.model_fields_set:
                    _resolved["no_thinking_level"] = True  # model doesn't take thinking_level
                    cfg = _config(system)
                elif getattr(e, "code", None) == 404 and "model" not in _resolved:
                    model = _pick_model(client)  # configured model unknown to this key
                else:
                    raise
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            cand = resp.candidates[0] if resp.candidates else None
            if cand is None or cand.content is None:
                break
            contents.append(cand.content)  # keep thought signatures intact
            calls = resp.function_calls or []
            if not calls:
                break
            parts = []
            for fc in calls:
                tools_used.append(fc.name)
                args = dict(fc.args or {})
                if fc.name == "query_spending":
                    args.setdefault("include_other_banks", include_other_banks)
                try:
                    out = {"result": clean(strip(run_tool(customer_id, fc.name, args, charts)))}
                except Exception as ex:  # report tool errors back to the model
                    out = {"error": f"{type(ex).__name__}: {ex}"}
                out = json.loads(json.dumps(out, default=str))
                parts.append(types.Part(function_response=types.FunctionResponse(id=fc.id, name=fc.name, response=out)))
            contents.append(types.Content(role="user", parts=parts))
        text = "".join(p.text for p in (cand.content.parts if cand and cand.content else [])
                       if getattr(p, "text", None) and not getattr(p, "thought", False))
    except Exception:
        del contents[start_len:]  # keep history consistent for the next turn
        raise
    _resolved.setdefault("model", model)
    return {"text": text, "charts": charts, "tools": tools_used, "model": model}
