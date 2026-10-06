"""Jev requests with exact cache identity and credential-free wire evidence.

Token-budget refusals belong to individual questions after request splitting.
They retain coverage without fabricating model answers or token accounting.
Probability categories are validated against each question's declared criteria.
Other unusable external responses still reject the classification as a whole.
"""

import json
import math
import os
import threading
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from leaf_dev.test_select.inputs import digest, write_json
from leaf_dev.test_select.planning import encode, plan

__all__ = ["Classification", "Client", "api_key", "plan"]


@dataclass
class Classification:
    answers: dict[str, dict]
    context_refusals: dict[str, dict]

    @classmethod
    def combine(cls, parts: Iterable["Classification"]) -> "Classification":
        answers, refusals = {}, {}
        for part in parts:
            answers.update(part.answers)
            refusals.update(part.context_refusals)
        return cls(answers, refusals)


def validate_response(response: dict, request: dict) -> dict:
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise TypeError("Jev response must contain an answers object")
    if response.get("model") and response["model"] != request["model"]:
        raise ValueError("Jev served a different model than the frozen policy")
    if set(response["answers"]) != set(request["questions"]):
        raise ValueError(
            "Jev response does not cover precisely the requested questions"
        )
    for name, answer in response["answers"].items():
        if not isinstance(answer, dict) or not isinstance(
            answer.get("probabilities"), dict
        ):
            raise TypeError("Jev answer must contain a probabilities object")
        probabilities = answer["probabilities"]
        if set(probabilities) != set(request["questions"][name]["criteria"]):
            raise ValueError("Jev returned different selection criteria")
        if any(
            type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
            for p in probabilities.values()
        ):
            raise ValueError("Jev returned an invalid probability")
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=0.02):
            raise ValueError("Jev probabilities are not normalized")
    if not isinstance(response.get("usage"), dict):
        raise TypeError("Jev response must contain token accounting")
    tokens = response["usage"].get("input_tokens")
    if type(tokens) is not int or tokens < 0:
        raise ValueError("Jev returned invalid token accounting")
    return response


def api_key() -> str:
    for name in ("TYPESAFE_API_KEY", "TYPESAFEAI_API_KEY"):
        if os.environ.get(name, "").strip():
            return os.environ[name].strip()
    path = Path.home() / ".local/share/jev/api-key"
    if path.exists() and path.read_text().strip():
        return path.read_text().strip()
    raise ValueError(
        "No Jev key; set TYPESAFE_API_KEY or use ~/.local/share/jev/api-key"
    )


class Client:
    def __init__(
        self,
        key: str,
        output: Path,
        *,
        endpoint: str = "https://api.typesafe.ai/v1/systemone",
    ):
        self.key, self.output, self.endpoint = key, output, endpoint
        self.lock = threading.Lock()
        self.attempts = self.calls = self.tokens = self.cached = self.splits = 0
        self.http_responses = self.unaccounted_responses = 0
        self.context_limit_responses = self.context_refused_questions = 0
        self.models = set()
        (output / "cache").mkdir(parents=True, exist_ok=True)

    def ask(self, request: dict) -> Classification:
        body = encode(request)
        fingerprint = digest(
            encode({"endpoint": self.endpoint, "body_sha256": digest(body)})
        )
        cache = self.output / "cache" / f"{fingerprint}.json"
        if cache.exists():
            saved = json.loads(cache.read_text())
            if saved["request_sha256"] != digest(body):
                raise ValueError("Cache request binding is invalid")
            response = validate_response(saved["response"], request)
            with self.lock:
                self.cached += 1
                if response.get("model"):
                    self.models.add(response["model"])
            return Classification(response["answers"], {})
        for attempt in range(4):
            with self.lock:
                self.attempts += 1
                with (self.output / "requests.jsonl").open("ab") as stream:
                    stream.write(body + b"\n")
            req = Request(
                self.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(req, timeout=60) as response:
                    with self.lock:
                        self.http_responses += 1
                    try:
                        received = json.load(response)
                    except (ValueError, HTTPException, OSError) as error:
                        with self.lock:
                            self.unaccounted_responses += 1
                        raise ValueError(
                            "Jev unreadable HTTP response; full-suite fallback"
                        ) from error
                # Received usage remains a fact when the answer is unusable.
                usage = received.get("usage") if isinstance(received, dict) else None
                tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
                with self.lock:
                    if type(tokens) is int and tokens >= 0:
                        self.tokens += tokens
                    else:
                        self.unaccounted_responses += 1
                result = validate_response(received, request)
            except HTTPError as error:
                try:
                    context_limit = (
                        error.code == 400
                        and "max_tokens_exceeded"
                        in error.read().decode(errors="replace")
                    )
                except (HTTPException, OSError) as read_error:
                    raise ValueError(
                        "Jev unreadable HTTP error response; full-suite fallback"
                    ) from read_error
                if context_limit:
                    with self.lock:
                        self.context_limit_responses += 1
                if context_limit and len(request["questions"]) == 1:
                    name = next(iter(request["questions"]))
                    refusal = {
                        "request_sha256": digest(body),
                        "request_bytes": len(body),
                        "http_status": error.code,
                        "error": "max_tokens_exceeded",
                    }
                    with self.lock:
                        self.context_refused_questions += 1
                        with (self.output / "context-refusals.jsonl").open(
                            "ab"
                        ) as stream:
                            stream.write(encode({"question": name, **refusal}) + b"\n")
                    return Classification({}, {name: refusal})
                if context_limit and len(request["questions"]) > 1:
                    names = list(request["questions"])
                    middle = (len(names) + 1) // 2
                    parts = [
                        self.ask(
                            {
                                **request,
                                "questions": {
                                    n: request["questions"][n] for n in group
                                },
                            }
                        )
                        for group in (names[:middle], names[middle:])
                    ]
                    with self.lock:
                        self.splits += 1
                    return Classification.combine(parts)
                if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise ValueError(
                        f"Jev HTTP {error.code}; full-suite fallback"
                    ) from error
            except (URLError, HTTPException, OSError):
                if attempt == 3:
                    raise ValueError(
                        "Jev network failure; full-suite fallback"
                    ) from None
            else:
                with self.lock:
                    self.calls += 1
                    if result.get("model"):
                        self.models.add(result["model"])
                    write_json(
                        cache, {"request_sha256": digest(body), "response": result}
                    )
                return Classification(result["answers"], {})
            time.sleep(0.5 * 2**attempt)
        raise AssertionError("Unreachable request state")

    def run(self, batches: list[dict]) -> Classification:
        with ThreadPoolExecutor(max_workers=4) as pool:
            return Classification.combine(pool.map(self.ask, batches))

    def metrics(self) -> dict:
        return {
            "http_attempts": self.attempts,
            "successful_calls": self.calls,
            "http_200_responses": self.http_responses,
            "http_200_responses_without_usable_token_accounting": self.unaccounted_responses,
            "cached_requests": self.cached,
            "input_tokens": self.tokens,
            "estimated_usd": self.tokens * 0.042 / 1_000_000,
            "splits": self.splits,
            "context_limit_http_responses": self.context_limit_responses,
            "context_refused_questions": self.context_refused_questions,
            "served_models": sorted(self.models),
        }
