"""Layer 2 AI Pydantic Schema Validation Engine (ADR 0012, BR-010)."""

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import AISchemaValidationException
from app.core.logging import logger
from app.ports.llm import LLMCompletionRequest, LLMProvider

T = TypeVar("T", bound=BaseModel)


def clean_json_payload(raw_output: str) -> str:
    """Extract clean JSON payload string from LLM output, stripping markdown fences/text."""
    if not raw_output or not raw_output.strip():
        return ""

    text = raw_output.strip()

    # Extract content inside markdown code blocks ```json ... ``` or ``` ... ```
    code_block_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL | re.IGNORECASE
    )
    if code_block_match:
        text = code_block_match.group(1).strip()

    # If text is still not starting with { or [, attempt to extract outermost JSON object/array
    if not (text.startswith("{") or text.startswith("[")):
        obj_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if obj_match:
            text = obj_match.group(1).strip()

    return text


class AIValidationService:
    """Layer 2 AI Output Validation Engine enforcing Pydantic schema validation (ADR 0012)."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider

    async def validate_response(
        self,
        raw_output: str,
        schema_cls: type[T],
        prompt_context: str | None = None,
        max_retries: int = 1,
    ) -> T:
        """Pass raw LLM response through strict Pydantic schema validation.

        If validation fails, retries up to max_retries using LLM correction prompt.
        If persistent failure occurs, raises AISchemaValidationException (BR-010).
        """
        current_raw = raw_output
        last_invalid_params: list[dict[str, Any]] = []
        last_error_message = ""
        total_attempts = max_retries + 1

        for attempt in range(1, total_attempts + 1):
            cleaned = clean_json_payload(current_raw)
            if not cleaned:
                last_error_message = "Raw output contains no valid JSON object structure."
                last_invalid_params = [{"name": "raw_output", "reason": last_error_message}]
            else:
                try:
                    # Attempt Pydantic model validation from JSON string
                    validated_model = schema_cls.model_validate_json(cleaned)
                    logger.info(
                        "ai_layer2_schema_validation_success",
                        extra={
                            "schema": schema_cls.__name__,
                            "attempt": attempt,
                        },
                    )
                    return validated_model
                except ValidationError as val_err:
                    invalid_params: list[dict[str, Any]] = []
                    for err in val_err.errors():
                        loc_str = ".".join(str(item) for item in err.get("loc", []))
                        invalid_params.append(
                            {
                                "name": loc_str or "root",
                                "reason": err.get("msg", "Validation error"),
                            }
                        )
                    last_error_message = (
                        f"Pydantic schema validation failed with {len(invalid_params)} error(s)."
                    )
                    last_invalid_params = invalid_params
                except json.JSONDecodeError as json_err:
                    last_error_message = (
                        f"Invalid JSON format: {json_err.msg} at line {json_err.lineno} "
                        f"col {json_err.colno}."
                    )
                    last_invalid_params = [{"name": "json_syntax", "reason": last_error_message}]
                except Exception as exc:
                    last_error_message = f"Unexpected schema parsing error: {str(exc)}"
                    last_invalid_params = [{"name": "schema_parsing", "reason": last_error_message}]

            logger.warning(
                "ai_layer2_schema_validation_failure",
                extra={
                    "schema": schema_cls.__name__,
                    "attempt": attempt,
                    "max_attempts": total_attempts,
                    "error_summary": last_error_message,
                    "raw_preview": current_raw[:200] if current_raw else "",
                },
            )

            # Retry logic if retry attempts remain and LLM provider is available
            if attempt < total_attempts and self.llm_provider is not None:
                err_json = json.dumps(last_invalid_params, indent=2)
                correction_prompt = (
                    f"Your previous JSON response failed Layer 2 schema validation for "
                    f"target schema '{schema_cls.__name__}'.\n"
                    f"Errors:\n{err_json}\n\n"
                    f"Previous Output:\n{current_raw}\n\n"
                    f"Context:\n{prompt_context or 'None'}\n\n"
                    f"Please output strictly valid JSON matching schema '{schema_cls.__name__}' "
                    f"without conversational text."
                )
                try:
                    retry_request = LLMCompletionRequest(
                        prompt=correction_prompt,
                        system_prompt=(
                            "You are a strict JSON formatting model. Respond ONLY with valid JSON "
                            "matching the requested schema."
                        ),
                        temperature=0.0,
                    )
                    retry_response = await self.llm_provider.generate_text(retry_request)
                    current_raw = retry_response.content
                except Exception as llm_exc:
                    logger.error(
                        "ai_layer2_retry_invocation_failed",
                        extra={"error": str(llm_exc)},
                    )
                    break

        raise AISchemaValidationException(
            message=(
                f"LLM output failed Layer 2 Pydantic schema validation for '{schema_cls.__name__}'."
            ),
            detail=last_error_message,
            invalid_params=last_invalid_params,
            raw_output=current_raw,
            attempts=min(attempt, total_attempts),
        )
