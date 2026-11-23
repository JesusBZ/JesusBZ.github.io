"""
Zero-Trust API Key Vault, Log Scrubbing Filter, and Runtime Security Configuration.
Never prints, serializes, or exposes secrets in logs, exceptions, or JSON artifacts.
"""
import hmac
import logging
import os
import re
from dataclasses import dataclass
from typing import Tuple

_REDACTED_LABEL = "[REDACTED_VAULT_SECRET]"

_SECRET_ENV_NAMES: Tuple[str, ...] = (
    "OKX_API_KEY",
    "OKX_API_SECRET",
    "OKX_API_PASSPHRASE",
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "RENDER_ADMIN_TOKEN",
    "INBOUND_FORM_ENDPOINT",
)

_SECRET_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"AIza[0-9A-Za-z\-_]{16,}"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"sk-[0-9A-Za-z\-_]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"gh[pousr]_[0-9A-Za-z]{20,}"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"glpat-[0-9A-Za-z\-_]{15,}"), "[REDACTED_GL_TOKEN]"),
    (re.compile(r"Bearer\s+[0-9A-Za-z._\-]{12,}", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"https?://app\.99inbound\.com/api/e/[A-Za-z0-9_\-]+", re.IGNORECASE), "[REDACTED_INBOUND_RELAY]"),
    (re.compile(r"https?://formsubmit\.co/[^\s\"'<>]+", re.IGNORECASE), "[REDACTED_FORMSUBMIT_RELAY]"),
    (re.compile(r"https?://formspree\.io/[^\s\"'<>]+", re.IGNORECASE), "[REDACTED_FORMSPREE_RELAY]"),
)

_DEFAULT_ALLOWED_ORIGINS: Tuple[str, ...] = (
    "https://jesusbz.github.io",
    "https://jesusbezerpa.github.io",
    "https://jesusbzerpa.github.io",
)

_LOCAL_DEV_ORIGINS: Tuple[str, ...] = (
    "http://localhost:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
)


class SecretValue:
    """Immutable vault container masking secrets in repr(), str(), and format()."""

    __slots__ = ("_val",)

    def __init__(self, value: str = "") -> None:
        object.__setattr__(self, "_val", str(value or "").strip())

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("SecretValue is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("SecretValue is immutable")

    def get_secret_value(self) -> str:
        return self._val

    def is_configured(self) -> bool:
        return len(self._val) > 0

    def __bool__(self) -> bool:
        return len(self._val) > 0

    def __repr__(self) -> str:
        return _REDACTED_LABEL

    def __str__(self) -> str:
        return _REDACTED_LABEL

    def __format__(self, format_spec: str) -> str:
        return _REDACTED_LABEL

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretValue):
            return hmac.compare_digest(self._val.encode("utf-8"), other._val.encode("utf-8"))
        return False


def scrub_secrets(text: str) -> str:
    """Redact credential tokens, relay URLs, and loaded environment secrets from text."""
    cleaned = str(text if text is not None else "")
    for pat, repl in _SECRET_PATTERNS:
        cleaned = pat.sub(repl, cleaned)

    for env_name in _SECRET_ENV_NAMES:
        raw_val = os.environ.get(env_name, "").strip()
        if len(raw_val) >= 8 and raw_val in cleaned:
            cleaned = cleaned.replace(raw_val, _REDACTED_LABEL)
    return cleaned


class SecretRedactingFilter(logging.Filter):
    """Logging filter preventing accidental secret disclosure in Render stdout logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub_secrets(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    scrub_secrets(a) if isinstance(a, (str, SecretValue)) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: scrub_secrets(v) if isinstance(v, (str, SecretValue)) else v
                    for k, v in record.args.items()
                }
        return True


@dataclass(frozen=True)
class VaultRuntimeConfig:
    execution_mode: str
    live_trading_armed: bool
    allowed_origins: Tuple[str, ...]
    okx_api_key: SecretValue
    okx_api_secret: SecretValue
    okx_api_passphrase: SecretValue
    bybit_api_key: SecretValue
    bybit_api_secret: SecretValue
    render_admin_token: SecretValue
    inbound_form_endpoint: SecretValue


def load_vault_config() -> VaultRuntimeConfig:
    """Load runtime credentials strictly from OS environment variables with safe paper-mode fail-closed defaults."""
    raw_mode = os.environ.get("EXECUTION_MODE", "paper").strip().lower()
    armed = os.environ.get("LIVE_TRADING_ARMED", "FALSE").strip().upper() == "TRUE"

    okx_k = SecretValue(os.environ.get("OKX_API_KEY", ""))
    okx_s = SecretValue(os.environ.get("OKX_API_SECRET", ""))
    okx_p = SecretValue(os.environ.get("OKX_API_PASSPHRASE", ""))
    byb_k = SecretValue(os.environ.get("BYBIT_API_KEY", ""))
    byb_s = SecretValue(os.environ.get("BYBIT_API_SECRET", ""))
    admin_tok = SecretValue(os.environ.get("RENDER_ADMIN_TOKEN", ""))
    inbound_ep = SecretValue(os.environ.get("INBOUND_FORM_ENDPOINT", ""))

    has_exchange_creds = (
        (okx_k.is_configured() and okx_s.is_configured() and okx_p.is_configured())
        or (byb_k.is_configured() and byb_s.is_configured())
    )

    if raw_mode in ("demo", "live") and armed and has_exchange_creds:
        effective_mode = raw_mode
    else:
        effective_mode = "paper"

    env_origins_raw = os.environ.get("ALLOWED_ORIGINS", "")
    parsed_origins = [
        o.strip().rstrip("/")
        for o in env_origins_raw.split(",")
        if o.strip()
    ]
    base_origins = parsed_origins if parsed_origins else list(_DEFAULT_ALLOWED_ORIGINS)
    merged_origins = []
    for origin in base_origins + list(_LOCAL_DEV_ORIGINS):
        norm_o = origin.rstrip("/")
        if norm_o and norm_o not in merged_origins:
            merged_origins.append(norm_o)

    return VaultRuntimeConfig(
        execution_mode=effective_mode,
        live_trading_armed=(effective_mode in ("demo", "live") and armed),
        allowed_origins=tuple(merged_origins),
        okx_api_key=okx_k,
        okx_api_secret=okx_s,
        okx_api_passphrase=okx_p,
        bybit_api_key=byb_k,
        bybit_api_secret=byb_s,
        render_admin_token=admin_tok,
        inbound_form_endpoint=inbound_ep,
    )


def verify_admin_token(provided: str, expected: SecretValue) -> bool:
    """Constant-time token comparison against vault secret."""
    exp_val = expected.get_secret_value()
    prov_val = str(provided or "").strip()
    if not exp_val or not prov_val:
        return False
    return hmac.compare_digest(prov_val.encode("utf-8"), exp_val.encode("utf-8"))
