"""Gọi LLM qua HTTP (Gemini, Anthropic, hoặc API tương thích OpenAI)."""
import httpx

from .. import config


class LLMError(Exception):
    pass

def is_extractive() -> bool:
    return config.LLM_PROVIDER == "extractive"

def is_configured() -> bool:
    p = config.LLM_PROVIDER
    if p == "extractive":
        return True
    if p == "gemini":
        return bool(config.GEMINI_API_KEY)
    if p == "anthropic":
        return bool(config.ANTHROPIC_API_KEY)
    if p == "openai":
        return bool(config.OPENAI_API_KEY)
    return False


def provider_label() -> str:
    if not is_configured():
        return ""
    return {
        "extractive": "Bộ trả lời trích xuất (không dùng mô hình)",
        "gemini": f"Gemini ({config.GEMINI_MODEL})",
        "anthropic": f"Anthropic ({config.ANTHROPIC_MODEL})",
        "openai": f"OpenAI-compatible ({config.OPENAI_MODEL})",
    }[config.LLM_PROVIDER]


def generate(system: str, user: str, max_tokens: int = 900) -> str:
    if not is_configured():
        raise LLMError("Chưa cấu hình LLM.")
    p = config.LLM_PROVIDER
    try:
        with httpx.Client(timeout=90) as client:
            if p == "gemini":
                r = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent",
                    headers={"x-goog-api-key": config.GEMINI_API_KEY},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
                    },
                )
                r.raise_for_status()
                data = r.json()
                return "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"]).strip()

            if p == "anthropic":
                r = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": config.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": config.ANTHROPIC_MODEL,
                        "max_tokens": max_tokens,
                        "temperature": 0.1,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                r.raise_for_status()
                return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text").strip()

            if p == "openai":
                r = client.post(
                    f"{config.OPENAI_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                    json={
                        "model": config.OPENAI_MODEL,
                        "temperature": 0.1,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        raise LLMError(f"LLM trả về lỗi {e.response.status_code}.") from e
    except httpx.HTTPError as e:
        raise LLMError("Không kết nối được tới dịch vụ LLM.") from e
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError("Phản hồi từ LLM không đúng định dạng.") from e
    raise LLMError(f"Nhà cung cấp LLM không hợp lệ: {p}")
