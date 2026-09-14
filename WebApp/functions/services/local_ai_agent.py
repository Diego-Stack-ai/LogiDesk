"""Client Ollama locale per proposte di mapping LogiDesk, senza persistenza."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib.request import Request, urlopen

from .manual_ai_bridge import ManualBridgeValidationError, ValidatedBridgeResponse, validate_manual_response


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "qwen3.5:9b"


@dataclass(frozen=True)
class LocalAiResult:
    model: str
    elapsed_ns: int | None
    proposal: ValidatedBridgeResponse
    raw_json: str


class LocalAiProposalRejected(ValueError):
    def __init__(self, message: str, raw_json: str):
        super().__init__(message)
        self.raw_json = raw_json


def propose_mapping(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = 180,
    max_repair_attempts: int = 1,
    opener: Callable = urlopen,
) -> LocalAiResult:
    """Interroga solo Ollama su loopback e valida il risultato come proposta."""

    if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
        raise ValueError("L'agente locale accetta soltanto endpoint loopback.")
    current_prompt = prompt
    last_error = None
    raw = ""
    envelope = {}
    for attempt in range(max_repair_attempts + 1):
        body = json.dumps({
            "model": model, "prompt": current_prompt, "stream": False,
            "think": False, "format": "json", "keep_alive": "5m",
            "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 700},
        }).encode("utf-8")
        request = Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with opener(request, timeout=timeout_seconds) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        raw = envelope.get("response")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Ollama non ha restituito una proposta JSON.")
        try:
            proposal = validate_manual_response(raw)
            break
        except ManualBridgeValidationError as exc:
            last_error = exc
            if attempt >= max_repair_attempts:
                raise LocalAiProposalRejected(str(exc), raw) from exc
            current_prompt = (
                "Correggi esclusivamente il JSON seguente e restituisci solo JSON. "
                f"Errore del validatore: {exc}. Non cambiare le conclusioni semantiche.\n{raw}"
            )
    else:  # pragma: no cover
        raise LocalAiProposalRejected(str(last_error), raw)
    return LocalAiResult(
        model=str(envelope.get("model") or model),
        elapsed_ns=envelope.get("total_duration"),
        proposal=proposal,
        raw_json=raw,
    )
