import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal
from pydantic import BaseModel, ValidationError


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any], Awaitable[dict[str, Any]]]
    access: Literal["read", "write"]
    timeout_s: float = 10.0
    est_cost: float = 0.0

    def to_llm_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
        }


@dataclass
class ToolResult:
    tool_name: str
    ok: bool
    data: dict[str, Any]
    proposed: bool = False
    executed: bool = True
    error: str | None = None


REGISTRY: dict[str, ToolSpec] = {}


def tool(
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
    access: Literal["read", "write"] = "read",
    timeout_s: float = 10.0,
    est_cost: float = 0.0,
):
    def decorator(fn: Callable[[Any], Awaitable[dict[str, Any]]]):
        REGISTRY[name] = ToolSpec(
            name=name,
            description=description,
            input_model=input_model,
            handler=fn,
            access=access,
            timeout_s=timeout_s,
            est_cost=est_cost,
        )
        return fn

    return decorator


def list_llm_tools(allowed_names: list[str] | None = None) -> list[dict[str, Any]]:
    specs = (
        [REGISTRY[n] for n in allowed_names if n in REGISTRY]
        if allowed_names is not None
        else list(REGISTRY.values())
    )
    return [spec.to_llm_tool() for spec in specs]


async def dispatch_tool(name: str, raw_args: dict[str, Any]) -> ToolResult:
    """Validate tool arguments and enforce read/write permission tiers in code."""
    spec = REGISTRY.get(name)
    if spec is None:
        return ToolResult(tool_name=name, ok=False, data={}, executed=False, error=f"Unknown tool: {name}")

    try:
        validated = spec.input_model.model_validate(raw_args)
    except ValidationError as exc:
        return ToolResult(tool_name=name, ok=False, data={}, executed=False, error=str(exc))

    # Structural permission enforcement: write tools NEVER execute inside the loop
    if spec.access == "write":
        return ToolResult(
            tool_name=name,
            ok=True,
            data=validated.model_dump(),
            proposed=True,
            executed=False,
        )

    try:
        output = await asyncio.wait_for(spec.handler(validated), timeout=spec.timeout_s)
        return ToolResult(tool_name=name, ok=True, data=output, proposed=False, executed=True)
    except TimeoutError:
        return ToolResult(
            tool_name=name,
            ok=False,
            data={},
            executed=True,
            error=f"Tool '{name}' timed out after {spec.timeout_s}s",
        )
    except Exception as exc:
        return ToolResult(tool_name=name, ok=False, data={}, executed=True, error=str(exc))
