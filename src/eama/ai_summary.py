from __future__ import annotations

import os
import time

import pandas as pd
import requests

DEFAULT_MODEL = "gemini-3.6-flash"
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_SPACING_SECONDS = 4


class AISummaryError(Exception):
    """Raised when an AI-generated summary cannot be produced."""


def _get_gemini_config() -> tuple[str, str]:
    """Read Gemini API settings from environment variables.

    Set GEMINI_API_KEY (from aistudio.google.com/apikey, free tier)
    before using --ai-summaries. Optionally set EAMA_GEMINI_MODEL to
    override the default model if it becomes unavailable -- Google's
    free-tier model names change over time; check aistudio.google.com
    or the error message from a failed call for the current name.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise AISummaryError(
            "Missing GEMINI_API_KEY environment variable. Get a free "
            "key at aistudio.google.com/apikey and set it before "
            "using --ai-summaries."
        )
    model = os.environ.get("EAMA_GEMINI_MODEL", DEFAULT_MODEL)
    return api_key, model


def _build_prompt(alert: pd.Series) -> str:
    return (
        "You are writing a short business alert summary for a "
        "non-technical manager. Given this automated anomaly "
        "detection finding, write 2-3 plain-English sentences "
        "explaining what happened and one concrete recommended next "
        "step. Do not use markdown formatting. Be direct and specific "
        "with the numbers given.\n\n"
        f"Segment: {alert['dimension_value']} ({alert['dimension']})\n"
        f"Week ending: {alert['date']}\n"
        f"Metrics affected: {alert['metrics_affected']}\n"
        f"Underlying detail: {alert['summary']}\n"
    )


def generate_ai_summary(alert: pd.Series, _is_retry: bool = False) -> str:
    """Generate a natural-language summary for one business alert.

    Retries once automatically on a network/timeout error or a 503
    (server overloaded) response, since those are often transient on
    the free tier. Raises AISummaryError on final failure (missing
    key, repeated network issue, unexpected response shape) so the
    caller can decide whether to fall back to the template-based
    summary.
    """
    api_key, model = _get_gemini_config()

    url = GEMINI_ENDPOINT_TEMPLATE.format(model=model)

    payload = {
        "contents": [
            {"parts": [{"text": _build_prompt(alert)}]}
        ]
    }

    try:
        response = requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        if not _is_retry:
            time.sleep(2)
            return generate_ai_summary(alert, _is_retry=True)
        raise AISummaryError(f"Network error calling Gemini API: {error}") from error

    if response.status_code == 503 and not _is_retry:
        time.sleep(3)
        return generate_ai_summary(alert, _is_retry=True)

    if response.status_code == 429:
        raise AISummaryError(
            "Gemini API rate limit hit (free tier allows a limited "
            "number of requests per minute/day). Try again shortly, "
            "or reduce how many alerts request AI summaries at once."
        )

    if response.status_code == 400:
        raise AISummaryError(
            f"Gemini API rejected the request (HTTP 400): {response.text[:300]}"
        )

    if response.status_code == 403:
        raise AISummaryError(
            "Gemini API key was rejected (HTTP 403). Confirm "
            "GEMINI_API_KEY is correct and the key has API access "
            "enabled in Google AI Studio."
        )

    if response.status_code != 200:
        raise AISummaryError(
            f"Gemini API returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    try:
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError) as error:
        raise AISummaryError(
            f"Unexpected Gemini API response shape: {error}"
        ) from error

    return text.strip()


def enhance_alerts_with_ai_summaries(
    business_alerts: pd.DataFrame,
) -> tuple[pd.DataFrame, int, list[str]]:
    """Replace each alert's template summary with an AI-generated one.

    Falls back to the original template summary per-alert on any
    failure, so one bad request never breaks the whole run. A short
    pause between requests helps avoid tripping the Gemini free
    tier's per-minute rate limit on runs with several alerts. Returns
    the updated DataFrame, how many were successfully enhanced, and
    any error messages encountered.
    """
    if business_alerts.empty:
        return business_alerts, 0, []

    updated = business_alerts.copy()
    enhanced_count = 0
    errors: list[str] = []

    for position, (index, alert) in enumerate(business_alerts.iterrows()):
        if position > 0:
            time.sleep(REQUEST_SPACING_SECONDS)

        try:
            ai_text = generate_ai_summary(alert)
            updated.at[index, "summary"] = ai_text
            enhanced_count += 1
        except AISummaryError as error:
            errors.append(
                f"{alert['dimension_value']} ({alert['dimension']}): {error}"
            )

    return updated, enhanced_count, errors