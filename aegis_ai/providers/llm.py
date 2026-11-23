from dataclasses import dataclass, field
import json
from typing import Any, Protocol
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model_name: str = ""


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse: ...


def _sanitize_gemini_schema(schema: Any) -> Any:
    """Convert Pydantic JSON Schema to a dict accepted by google-genai <=1.20 types.Schema."""
    if not isinstance(schema, dict):
        return schema

    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "exclusiveMinimum":
            if "minimum" not in schema:
                cleaned["minimum"] = value + 1 if schema.get("type") == "integer" else value
            continue
        if key == "exclusiveMaximum":
            if "maximum" not in schema:
                cleaned["maximum"] = value - 1 if schema.get("type") == "integer" else value
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {k: _sanitize_gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            cleaned[key] = _sanitize_gemini_schema(value)
        elif key in ("anyOf", "any_of") and isinstance(value, list):
            cleaned[key] = [_sanitize_gemini_schema(item) for item in value]
        else:
            cleaned[key] = value
    return cleaned


class GeminiProvider:
    """Google Gemini provider backed by the official `google-genai` SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        from google import genai

        key = api_key or settings.GEMINI_API_KEY
        if not key:
            raise ValueError("GEMINI_API_KEY must be set when LLM_PROVIDER='gemini'")
        self.model = model or settings.LLM_MODEL
        self.client = genai.Client(api_key=key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        from google.genai import types

        system_parts = [m.content for m in messages if m.role == "system"]
        system_instruction = "\n\n".join(system_parts) if system_parts else None

        contents: list[types.Content] = []
        for msg in messages:
            if msg.role == "system":
                continue
            role = "model" if msg.role == "assistant" else "user"
            text = f"[Tool {msg.name} output]: {msg.content}" if msg.role == "tool" else msg.content
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

        gemini_tools = None
        if tools:
            use_json_schema = "parameters_json_schema" in types.FunctionDeclaration.model_fields
            declarations = [
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    **(
                        {"parameters_json_schema": t["parameters"]}
                        if use_json_schema
                        else {"parameters": _sanitize_gemini_schema(t["parameters"])}
                    ),
                )
                for t in tools
            ]
            gemini_tools = [types.Tool(function_declarations=declarations)]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        text_content = response.text or ""
        parsed_calls: list[ToolCall] = []
        if response.function_calls:
            for idx, fc in enumerate(response.function_calls):
                parsed_calls.append(
                    ToolCall(
                        id=getattr(fc, "id", None) or f"call_{idx}",
                        name=fc.name,
                        arguments=dict(fc.args or {}),
                    )
                )

        usage = response.usage_metadata
        tokens_in = int(getattr(usage, "prompt_token_count", 0) or 0)
        tokens_out = int(getattr(usage, "candidates_token_count", 0) or 0)
        est_cost = round((tokens_in * 0.00000015) + (tokens_out * 0.00000060), 6)

        return LLMResponse(
            content=text_content,
            tool_calls=parsed_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=est_cost,
            model_name=self.model,
        )


class OllamaProvider:
    """Local Ollama provider using /api/chat over httpx."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        ollama_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if ollama_tools:
            payload["tools"] = ollama_tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        parsed_calls: list[ToolCall] = []
        for idx, tc in enumerate(msg.get("tool_calls", [])):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            parsed_calls.append(
                ToolCall(id=f"ollama_{idx}", name=fn.get("name", ""), arguments=args)
            )

        return LLMResponse(
            content=msg.get("content", ""),
            tool_calls=parsed_calls,
            tokens_in=int(data.get("prompt_eval_count", 0)),
            tokens_out=int(data.get("eval_count", 0)),
            cost_usd=0.0,
            model_name=self.model,
        )


class ReplayProvider:
    """Deterministic cassette provider for fast offline CI tests and evals."""

    def __init__(self, responses: list[LLMResponse] | None = None):
        self._responses = list(responses or [])
        self._index = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return LLMResponse(
            content="ReplayProvider default conclusion [Assessment:0].",
            tool_calls=[],
            tokens_in=100,
            tokens_out=25,
            cost_usd=0.0,
            model_name="replay-v1",
        )


def get_provider() -> LLMProvider:
    providers: dict[str, type[LLMProvider]] = {
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
        "replay": ReplayProvider,
    }
    provider_cls = providers.get(settings.LLM_PROVIDER)
    if provider_cls is None:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
    return provider_cls()
