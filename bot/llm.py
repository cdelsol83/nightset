"""Thin wrapper around the xAI Responses API with server-side web_search / x_search tools."""
import http.client
import json
import re
import time
import urllib.error
import urllib.request

import config

API_URL = "https://api.x.ai/v1/responses"
ATTEMPTS = 3


class LLMError(RuntimeError):
    pass


def ask(prompt, tools=("web_search",), system=None):
    """Return (text, citations). tools: any of "web_search", "x_search"."""
    if config.DEMO:
        import demo
        return demo.answer(prompt), ["https://example.com/demo-source"]
    if not config.XAI_API_KEY:
        raise LLMError("XAI_API_KEY is not set (or run with MOGUL_DEMO=1)")
    body = {"model": config.XAI_MODEL, "input": prompt, "tools": [{"type": t} for t in tools], "stream": True}
    if system:
        body["input"] = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return _call(body)
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == ATTEMPTS:
                raise LLMError(f"xAI API {e.code}: {e.read()[:500]!r}") from e
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError) as e:
            if attempt == ATTEMPTS:
                raise LLMError(f"xAI API unreachable after {ATTEMPTS} attempts: {e!r}") from e
        print(f"xAI call failed (attempt {attempt}/{ATTEMPTS}), retrying in {30 * attempt}s")
        time.sleep(30 * attempt)


def _call(body):
    """Stream the response so long web-search calls keep the connection busy."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {config.XAI_API_KEY}", "Content-Type": "application/json",
                 "Accept": "text/event-stream"},
    )
    deltas, final, other = [], None, []
    with urllib.request.urlopen(req, timeout=300) as r:  # timeout applies per read, not in total
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                other.append(line)
                continue
            if line == "data: [DONE]":
                continue
            event = json.loads(line[5:])
            if event.get("type") == "response.output_text.delta":
                deltas.append(event.get("delta", ""))
            elif event.get("type") == "response.completed":
                final = event.get("response", {})
            elif event.get("type") in ("response.failed", "error"):
                raise LLMError(f"xAI API error: {json.dumps(event)[:500]}")
    if final is None and not deltas and other:
        try:
            final = json.loads("\n".join(other))  # server answered without streaming
        except json.JSONDecodeError:
            pass
    if final is None:
        if not deltas:
            raise http.client.IncompleteRead(b"")  # stream ended early: retry
        return "".join(deltas), []
    return _text(final) or "".join(deltas), final.get("citations", [])


def _text(resp):
    return "".join(
        c.get("text", "")
        for item in resp.get("output", []) if item.get("type") == "message"
        for c in item.get("content", []) if c.get("type") == "output_text"
    )


def ask_json(prompt, tools=("web_search",)):
    """Ask for a JSON answer and parse the first JSON object/array in the reply."""
    text, citations = ask(prompt + "\n\nReply with JSON only, no prose.", tools)
    return extract_json(text), citations


def extract_json(text):
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise LLMError(f"no JSON in model reply: {text[:200]!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj
