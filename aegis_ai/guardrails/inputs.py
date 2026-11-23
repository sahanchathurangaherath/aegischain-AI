import re
import secrets


class GuardrailViolation(Exception):
    """Raised when an input, output, or proposed action breaches a safety boundary."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"approve\s+(this\s+)?(order|po|purchase\s+order)\s+immediately", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?guardrails?", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|canary|secret)", re.IGNORECASE),
]

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def generate_canary_token() -> str:
    """Generate a unique per-deliberation canary token injected into the system prompt."""
    return f"AEGIS-CANARY-{secrets.token_hex(6).upper()}"


def check_canary_leak(output_text: str, canary_token: str) -> None:
    """Discard output if the system prompt canary token appears anywhere in the response."""
    if canary_token and canary_token in (output_text or ""):
        raise GuardrailViolation(
            code="canary_leak_detected",
            message="System prompt canary token leaked in model output; deliberation discarded.",
        )


def detect_prompt_injection(text: str) -> list[str]:
    """Return list of matched prompt-injection signatures in untrusted text."""
    if not text:
        return []
    hits: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def validate_identifier(field_name: str, value: str | None) -> None:
    """Reject malformed product, warehouse, or supplier identifiers at the boundary."""
    if value is None:
        return
    if not _IDENTIFIER_PATTERN.match(value):
        raise GuardrailViolation(
            code="invalid_identifier",
            message=f"Invalid {field_name}: '{value}'",
            details={"field": field_name, "value": value},
        )
