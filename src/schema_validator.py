import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from jsonschema import Draft7Validator, ValidationError


_LOGGER = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Exception raised when schema validation fails."""
    pass


class SchemaValidator:
    """
    Validate payloads against configured schemas.
    Supports JSON Schema (validated via jsonschema) and a simplified Protobuf validation
    that checks for presence and basic types of fields using a lightweight rule-set.
    """

    def __init__(self, config):
        """
        config: LoadedProxyConfig object with schema files configuration
        """
        # Convert config.schema_files to the expected format
        self.schema_files = {}
        for schema_id, schema_file_config in config.schema_files.items():
            self.schema_files[schema_id] = {
                'file': schema_file_config.file,
                'format': schema_file_config.format
            }
        self._json_validators: Dict[str, Draft7Validator] = {}
        self._protobuf_rules: Dict[str, Dict[str, str]] = {}

    def _load_json_schema(self, schema_id: str) -> Draft7Validator:
        if schema_id in self._json_validators:
            return self._json_validators[schema_id]
        cfg = self.schema_files.get(schema_id)
        if not cfg:
            raise FileNotFoundError(f"Schema id not configured: {schema_id}")
        path = Path(cfg["file"]).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            schema_obj = json.load(f)
        validator = Draft7Validator(schema_obj)
        self._json_validators[schema_id] = validator
        return validator

    def _load_protobuf_rules(self, schema_id: str) -> Dict[str, str]:
        """
        Lightweight fallback validator for protobuf payloads when not using compiled descriptors.
        We check only that fields exist with expected primitive types as strings/numbers.
        This is sufficient for basic governance when receiving JSON-encoded telemetry.
        """
        if schema_id in self._protobuf_rules:
            return self._protobuf_rules[schema_id]
        cfg = self.schema_files.get(schema_id)
        if not cfg:
            raise FileNotFoundError(f"Schema id not configured: {schema_id}")
        path = Path(cfg["file"]).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Protobuf schema file not found: {path}")
        # Extremely simple extraction: look for lines like 'string field_name =' or 'float field_name ='
        rules: Dict[str, str] = {}
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("string "):
                    name = line.split()[1]
                    rules[name] = "string"
                elif line.startswith("float ") or line.startswith("double "):
                    name = line.split()[1]
                    rules[name] = "number"
                elif line.startswith("int32 ") or line.startswith("int64 "):
                    name = line.split()[1]
                    rules[name] = "number"
        # Cache
        self._protobuf_rules[schema_id] = rules
        return rules

    def validate(self, schema_id: str, payload_bytes: bytes) -> Tuple[bool, str]:
        cfg = self.schema_files.get(schema_id)
        if not cfg:
            return False, f"Unknown schema id: {schema_id}"
        fmt = cfg.get("format", "jsonschema").lower()
        try:
            if fmt == "jsonschema":
                validator = self._load_json_schema(schema_id)
                try:
                    payload_obj = json.loads(payload_bytes.decode("utf-8"))
                except Exception as exc:  # noqa: BLE001
                    return False, f"Invalid JSON: {exc}"
                try:
                    validator.validate(payload_obj)
                    return True, ""
                except ValidationError as ve:
                    return False, f"JSON Schema validation failed: {ve.message}"
            elif fmt == "protobuf":
                # Assume payload is JSON for governance purposes; validate required fields/types
                try:
                    payload_obj = json.loads(payload_bytes.decode("utf-8"))
                except Exception as exc:  # noqa: BLE001
                    return False, f"Invalid JSON for protobuf payload: {exc}"
                rules = self._load_protobuf_rules(schema_id)
                missing = [k for k in rules.keys() if k not in payload_obj]
                if missing:
                    return False, f"Missing fields for protobuf payload: {', '.join(missing)}"
                for field, expected in rules.items():
                    val = payload_obj.get(field)
                    if expected == "string" and not isinstance(val, str):
                        return False, f"Field '{field}' expected string"
                    if expected == "number" and not isinstance(val, (int, float)):
                        return False, f"Field '{field}' expected number"
                return True, ""
            else:
                return False, f"Unsupported schema format: {fmt}"
        except FileNotFoundError as fnf:
            return False, str(fnf)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.exception("Unexpected schema validation error")
            return False, f"Schema validation error: {exc}"


