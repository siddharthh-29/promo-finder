"""Model-agnostic LLM client. Swap models by changing env vars only:
  LLM_PROVIDER = openai (default; any OpenAI-compatible endpoint) | anthropic | mock
  LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
Gemini free tier : LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai  LLM_MODEL=gemini-2.5-flash
Groq             : LLM_BASE_URL=https://api.groq.com/openai/v1   LLM_MODEL=llama-3.3-70b-versatile
OpenRouter       : LLM_BASE_URL=https://openrouter.ai/api/v1
"""
import os, json, time, re, urllib.request, urllib.error


class LLMError(Exception): pass


def _post(url, headers, payload, retries=4):
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        headers["User-Agent"] = "PromoFinder/1.0"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:300]
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(4 * (attempt + 1)); continue     # free tiers rate-limit: back off
            raise LLMError(f"HTTP {e.code}: {body}")
        except Exception as e:
            if attempt < retries - 1: time.sleep(3); continue
            raise LLMError(str(e))


def extract_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try: return json.loads(text)
    except Exception: pass
    m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if m: return json.loads(m.group(1))
    raise LLMError("no JSON in model output")


class LLM:
    def __init__(self, provider=None, model=None, base_url=None, api_key=None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        self.model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL",
                         "https://generativelanguage.googleapis.com/v1beta/openai")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.calls = 0; self.in_chars = 0; self.out_chars = 0

    def json(self, system, user, mock_fn=None):
        self.calls += 1; self.in_chars += len(system) + len(user)
        if self.provider == "mock":
            out = mock_fn(user) if mock_fn else "{}"
        elif self.provider == "anthropic":
            r = _post("https://api.anthropic.com/v1/messages",
                      {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"},
                      {"model": self.model, "max_tokens": 3000, "system": system,
                       "messages": [{"role": "user", "content": user}]})
            out = r["content"][0]["text"]
        else:
            r = _post(f"{self.base_url}/chat/completions",
                      {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                      {"model": self.model, "temperature": 0.2,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]})
            out = r["choices"][0]["message"]["content"]
        self.out_chars += len(out)
        return extract_json(out)
