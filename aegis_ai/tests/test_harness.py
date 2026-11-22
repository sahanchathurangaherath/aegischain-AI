import httpx
import pytest
import respx

from config.settings import settings
from harness.context import build_context
from harness.loop import run_agent_loop
import harness.tools.erp_tools  # noqa: F401
from harness.tools.registry import dispatch_tool
from prompts.registry import load_prompt
from providers.llm import LLMResponse, ReplayProvider, ToolCall


def test_prompt_registry_loads_version_and_hash():
    artifact = load_prompt("system2_deliberate")
    assert artifact.prompt_id == "system2_deliberate"
    assert artifact.version == "1.0"
    assert len(artifact.sha256_short) == 8
    assert artifact.prompt_version == f"v1.0-{artifact.sha256_short}"


@pytest.mark.asyncio
async def test_write_tool_never_executes_inside_loop():
    """Structural permission enforcement: write tools return a proposal and never execute."""
    result = await dispatch_tool(
        "propose_purchase_order",
        {
            "product_code": "RM-STEEL-001",
            "warehouse_code": "WH-MAIN-01",
            "supplier_code": "SUP-001",
            "quantity": 250,
            "justification": "Critical stockout predicted in 3 days",
        },
    )
    assert result.ok is True
    assert result.proposed is True
    assert result.executed is False
    assert result.data["quantity"] == 250


def test_context_builder_conflict_resolution_and_delimiters():
    assembled = build_context(
        system_prompt="System rules",
        event_payload={"event_type": "BalanceBelowReorderPoint", "product_code": "RM-STEEL-001"},
        live_state={"lead_time_days": 14, "quantity_available": 10},
        entity_memory={"lead_time_days": 7, "supplier_code": "SUP-001"},
        episodic_items=[{"id": 42, "risk_level": "critical", "outcome": {"actual_stockout": True}}],
        semantic_chunks=[
            {
                "document_id": 9,
                "chunk_index": 2,
                "source_uri": "contracts/sup001.pdf",
                "chunk_text": "Minimum order quantity is 200 units.",
            }
        ],
    )
    assert len(assembled.conflicts) == 1
    assert assembled.conflicts[0]["field"] == "lead_time_days"
    assert assembled.conflicts[0]["resolution"] == "live_erp_wins"
    assert "<untrusted_document" in assembled.user_prompt
    assert "[Doc:9:Chunk:2]" in assembled.user_prompt
    assert "[Assessment:42]" in assembled.user_prompt


def test_context_builder_truncates_sections_independently():
    assembled = build_context(
        system_prompt="Short system prompt",
        event_payload={"event_type": "Test"},
        live_state={"notes": "A" * 5000},
        budget={"state": 50, "system": 400},
    )
    assert assembled.allocation["state"]["truncated"] is True
    assert assembled.allocation["system"]["truncated"] is False


@pytest.mark.asyncio
@respx.mock
async def test_agent_loop_end_to_end_with_replay_provider():
    """Deliberation loop runs read tool, proposes write without executing, and extracts citations."""
    base = settings.ERP_API_URL
    respx.get(f"{base}/inventory/products/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "product_code": "RM-STEEL-001",
                    "name": "Steel Plate",
                    "reorder_point": 100,
                    "safety_stock": 50,
                    "lead_time_days": 7,
                }
            ],
        )
    )
    respx.get(f"{base}/inventory/balances/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "product_code": "RM-STEEL-001",
                    "warehouse_code": "WH-MAIN-01",
                    "quantity_on_hand": 10,
                    "quantity_available": 10,
                    "quantity_reserved": 0,
                    "variance": 0,
                    "stock_health": "critical",
                }
            ],
        )
    )

    provider = ReplayProvider(
        responses=[
            LLMResponse(
                content="Checking live inventory balance first.",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="get_inventory_balance",
                        arguments={"product_code": "RM-STEEL-001", "warehouse_code": "WH-MAIN-01"},
                    )
                ],
                tokens_in=200,
                tokens_out=40,
                model_name="replay-v1",
            ),
            LLMResponse(
                content="Proposing emergency purchase order.",
                tool_calls=[
                    ToolCall(
                        id="c2",
                        name="propose_purchase_order",
                        arguments={
                            "product_code": "RM-STEEL-001",
                            "warehouse_code": "WH-MAIN-01",
                            "supplier_code": "SUP-001",
                            "quantity": 200,
                            "justification": "Stock at 10 units below safety stock of 50.",
                        },
                    )
                ],
                tokens_in=300,
                tokens_out=55,
                model_name="replay-v1",
            ),
            LLMResponse(
                content="Recommend approving PO for 200 units based on [Assessment:42] and [Doc:9:Chunk:2].",
                tool_calls=[],
                tokens_in=350,
                tokens_out=30,
                model_name="replay-v1",
            ),
        ]
    )

    prompt = load_prompt("system2_deliberate")
    assembled = build_context(
        system_prompt=prompt.system_prompt,
        event_payload={"product_code": "RM-STEEL-001"},
        live_state={"quantity_available": 10},
    )

    result = await run_agent_loop(
        event_id="22222222-2222-2222-2222-222222222222",
        trigger_reason="high_risk",
        prompt_version=prompt.prompt_version,
        assembled=assembled,
        provider=provider,
    )

    assert result.terminated_by == "completed"
    assert result.proposed_action is not None
    assert result.proposed_action["tool"] == "propose_purchase_order"
    assert result.proposed_action["payload"]["quantity"] == 200
    assert result.citations == ["Assessment:42", "Doc:9:Chunk:2"]
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0]["executed"] is True
    assert result.tool_calls[1]["proposed"] is True
    assert result.tool_calls[1]["executed"] is False


@pytest.mark.asyncio
async def test_agent_loop_enforces_max_steps_cap():
    looping_responses = [
        LLMResponse(
            content="Calling tool again",
            tool_calls=[
                ToolCall(
                    id=f"c{i}",
                    name="propose_purchase_order",
                    arguments={
                        "product_code": "RM-STEEL-001",
                        "warehouse_code": "WH-MAIN-01",
                        "supplier_code": "SUP-001",
                        "quantity": 100,
                        "justification": "Repeated call",
                    },
                )
            ],
            tokens_in=50,
            tokens_out=20,
            model_name="replay-v1",
        )
        for i in range(5)
    ]

    assembled = build_context(
        system_prompt="Test",
        event_payload={},
        live_state={},
    )

    result = await run_agent_loop(
        event_id="33333333-3333-3333-3333-333333333333",
        trigger_reason="high_risk",
        prompt_version="v1.0-test",
        assembled=assembled,
        provider=ReplayProvider(looping_responses),
        max_steps=2,
    )

    assert result.terminated_by == "max_steps"
    assert len(result.tool_calls) == 2
