import os
import time
import requests
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# Default prompt - can be overridden via env
_DEFAULT_PROMPT_VI = (
    "Bạn là trợ lý nghiên cứu. Sử dụng thông tin trong CONTEXT và LỊCH SỬ HỘI THOẠI (nếu có) để trả lời.\n"
    "- Bắt buộc trích dẫn theo [Title](URL) nếu có nguồn từ CONTEXT.\n"
    "- Nếu không có thông tin trong cả CONTEXT và LỊCH SỬ, hãy nói: \"Chưa đủ nguồn\".\n"
    "{memory}\n"
    "CONTEXT:\n{context}\n\nCÂU HỎI: {question}\n"
)

_DEFAULT_PROMPT_EN = (
    "You are a research assistant. Use information from CONTEXT and CONVERSATION HISTORY (if available) to answer.\n"
    "- Always cite sources using [Title](URL) format if information comes from CONTEXT.\n"
    "- If there is no information in both CONTEXT and HISTORY, say: \"Insufficient sources available.\"\n"
    "{memory}\n"
    "CONTEXT:\n{context}\n\nQUESTION: {question}\n"
)

# Use English by default for better LLM performance, can override via env
_USE_ENGLISH_PROMPT = os.getenv("USE_ENGLISH_PROMPT", "true").lower() == "true"
DEFAULT_PROMPT = _DEFAULT_PROMPT_EN if _USE_ENGLISH_PROMPT else _DEFAULT_PROMPT_VI


def call_ollama(
    prompt: str,
    *,
    model: Optional[str] = None,
    base: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    model = model or os.getenv("LLM_MODEL", "llama3")
    base = base or os.getenv("OLLAMA_BASE", "http://localhost:11434")
    timeout_sec = int(os.getenv("OLLAMA_TIMEOUT_SEC", "120"))
    max_retries = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))
    backoff_base = float(os.getenv("OLLAMA_BACKOFF_BASE", "2"))
    url = f"{base.rstrip('/')}/api/generate"
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            time.sleep(backoff_base * (2 ** attempt))
    raise RuntimeError(
        f"Failed to call Ollama at {base} after {max_retries+1} attempts. "
        f"Ensure 'ollama serve' is running and model '{model}' is pulled. Last error: {last_exc}"
    )


def call_gemini(
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    timeout: Optional[int] = None,
    max_retries: int = 3,
) -> str:
    """Call Google Gemini API with retry logic."""
    api_key = os.getenv("GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("GENAI_API_KEY is not set; cannot call Gemini API")

    try:
        import google.generativeai as genai
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("google-generativeai package is not installed") from exc

    genai.configure(api_key=api_key)
    model_name = model or os.getenv("GENAI_MODEL", "gemini-2.5-flash")
    timeout_sec = timeout or int(os.getenv("GENAI_TIMEOUT_SEC", "60"))

    last_exception = None
    for attempt in range(max_retries):
        try:
            gen_model = genai.GenerativeModel(model_name)
            response = gen_model.generate_content(
                prompt,
                generation_config={"temperature": temperature},
                request_options={"timeout": timeout_sec},
            )
            
            # Prefer the simple .text attribute when available
            text = getattr(response, "text", None)
            if text:
                return text.strip()

            # Fallback: extract text from candidates
            candidates = getattr(response, "candidates", []) or []
            parts = []
            for cand in candidates:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []) or []:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        parts.append(part_text)
            if parts:
                return "\n".join(parts).strip()

            raise RuntimeError("Gemini API returned no text content")
            
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                import logging
                logging.warning(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {exc}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise RuntimeError(f"Failed to call Gemini model '{model_name}' after {max_retries} attempts: {exc}") from exc
    
    raise RuntimeError(f"Failed to call Gemini model '{model_name}': {last_exception}") from last_exception


def call_openrouter(
    prompt: str,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    timeout: Optional[int] = None,
    max_retries: int = 3,
) -> str:
    """Call OpenRouter API with retry logic."""
    if OpenAI is None:
        raise RuntimeError("OpenAI SDK is not installed. Please run `pip install openai`.")

    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; cannot call OpenRouter API")

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = model or os.getenv("OPENROUTER_MODEL", "xiaomi/mimo-v2-flash:free")
    timeout_sec = timeout or int(os.getenv("OPENROUTER_TIMEOUT_SEC", "60"))

    client = OpenAI(base_url=base_url, api_key=api_key)

    last_exception = None
    for attempt in range(max_retries):
        try:
            extra_headers = {
                "HTTP-Referer": "https://github.com/qsang793/ai-research-agent",
                "X-Title": "AI Research Agent",
            }
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=timeout_sec,
                extra_headers=extra_headers,
                extra_body={"reasoning": {"enabled": False}},
            )
            return response.choices[0].message.content or ""
            
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                import logging
                logging.warning(f"OpenRouter API error (attempt {attempt + 1}/{max_retries}): {exc}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise RuntimeError(f"Failed to call OpenRouter model '{model}' after {max_retries} attempts: {exc}") from exc
    
    raise RuntimeError(f"Failed to call OpenRouter model '{model}': {last_exception}") from last_exception


def build_context(snippets: list[dict]) -> str:
    lines = []
    for s in snippets:
        title = (s.get("metadata") or {}).get("title") or "(no title)"
        url = (s.get("metadata") or {}).get("source_url") or ""
        text = s.get("text") or s.get("document") or s.get("doc") or s.get("content") or ""
        lines.append(f"[{title}]({url})\n{text}\n")
    return "\n".join(lines)


def generate_answer(
    question: str,
    topk_snippets: list[dict],
    prompt_template: Optional[str] = None,
    *,
    backend: Optional[str] = None,
    temperature: float = 0.2,
    memory_context: str = "",
) -> str:
    ctx = build_context(topk_snippets)
    
    # Format memory context
    memory_str = ""
    if memory_context:
        memory_str = f"\n--- LỊCH SỬ HỘI THOẠI LIÊN QUAN ---\n{memory_context}\n--- KẾT THÚC LỊCH SỬ ---\n"
    
    prompt = (prompt_template or DEFAULT_PROMPT).format(context=ctx, question=question, memory=memory_str)
    backend_choice = (backend or os.getenv("LLM_BACKEND", "ollama")).strip().lower()

    if backend_choice == "gemini":
        return call_gemini(prompt, temperature=temperature)
    
    if backend_choice == "openrouter":
        return call_openrouter(prompt, temperature=temperature)

    # default to ollama
    return call_ollama(prompt, temperature=temperature)


