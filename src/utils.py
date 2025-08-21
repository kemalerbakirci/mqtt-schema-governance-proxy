import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


_LOGGER = logging.getLogger(__name__)


def generate_unique_id(topic: str, payload: bytes) -> str:
    """
    Generate a deterministic unique id for a message using SHA1 of topic and payload.
    """
    sha1 = hashlib.sha1()
    sha1.update(topic.encode("utf-8"))
    sha1.update(payload)
    return sha1.hexdigest()


def utc_timestamp_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format with 'Z'."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_safe_load(raw: bytes | str) -> Optional[Any]:
    """
    Attempt to parse JSON from bytes or string. Return None if parsing fails.
    """
    try:
        if isinstance(raw, (bytes, bytearray)):
            return json.loads(raw.decode("utf-8"))
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - we want to be safe and swallow errors here
        _LOGGER.debug("json_safe_load failed: %s", exc)
        return None


def wildcard_to_regex(pattern: str) -> str:
    """
    Convert MQTT-like wildcard pattern to a regex.
    Supported wildcards:
      - '+' matches a single topic level (no slash)
      - '#' matches multi-level (can only appear at end)
    """
    # Escape regex special chars except wildcard markers
    escaped = "".join(
        [
            re.escape(ch) if ch not in {"+", "#", "/"} else ch
            for ch in pattern
        ]
    )
    # Replace MQTT wildcards with regex equivalents
    escaped = escaped.replace("+", "[^/]+")
    if "#" in escaped:
        # Only support trailing '#'
        if not escaped.endswith("#"):
            # Non-trailing '#' is not standard; make a conservative match
            escaped = escaped.replace("#", ".*")
        else:
            escaped = escaped[:-1] + ".*"
    return f"^{escaped}$"


def match_topic(pattern: str, topic: str) -> bool:
    """
    Match a topic against either a wildcard pattern or a regex.
    - If pattern starts with 'regex:' it is treated as a raw regex after the prefix
    - Otherwise, treat it as MQTT wildcard pattern
    """
    if pattern.startswith("regex:"):
        regex = pattern[len("regex:") :]
    else:
        regex = wildcard_to_regex(pattern)
    return re.match(regex, topic) is not None


def compile_regex(pattern: str) -> re.Pattern[str]:
    """Compile a regex or wildcard pattern into a regex Pattern."""
    if pattern.startswith("regex:"):
        raw = pattern[len("regex:") :]
    else:
        raw = wildcard_to_regex(pattern)
    return re.compile(raw)


def parse_schema_header(payload_obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract schema_id and device_id from a parsed JSON payload if present.
    Returns (schema_id, device_id).
    """
    schema_id = None
    device_id = None
    if isinstance(payload_obj, dict):
        schema_id = payload_obj.get("schema_id")
        device_id = payload_obj.get("device_id")
    return schema_id, device_id


