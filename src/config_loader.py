from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


_LOGGER = logging.getLogger(__name__)


SUPPORTED_SCHEMA_FORMATS = {"jsonschema", "protobuf"}


@dataclass(frozen=True)
class SchemaFileConfig:
    file: str
    format: str


@dataclass(frozen=True)
class ProxyConfig:
    topic_patterns: List[str]
    schema_mappings: Dict[str, str]
    schema_files: Dict[str, SchemaFileConfig]
    
    def get_schema_for_topic(self, topic: str) -> Optional[str]:
        """Find the schema ID for a given topic based on schema mappings."""
        from utils import match_topic
        
        for pattern, schema_id in self.schema_mappings.items():
            if match_topic(pattern, topic):
                return schema_id
        return None


def _validate_config_dict(cfg: dict, base_dir: Path) -> ProxyConfig:
    if not isinstance(cfg, dict):
        raise ValueError("rules.yaml must be a mapping at top level")

    topic_patterns = cfg.get("topic_patterns")
    if not isinstance(topic_patterns, list) or not all(
        isinstance(p, str) for p in topic_patterns
    ):
        raise ValueError("topic_patterns must be a list of strings")

    schema_mappings = cfg.get("schema_mappings")
    if not isinstance(schema_mappings, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in schema_mappings.items()
    ):
        raise ValueError("schema_mappings must be a mapping of pattern -> schema_id")

    schema_files_raw = cfg.get("schema_files")
    if not isinstance(schema_files_raw, dict):
        raise ValueError("schema_files must be a mapping of schema_id -> {file, format}")

    schema_files: Dict[str, SchemaFileConfig] = {}
    for schema_id, ent in schema_files_raw.items():
        if not isinstance(ent, dict):
            raise ValueError(f"schema_files.{schema_id} must be a mapping")
        file_path = ent.get("file")
        fmt = ent.get("format")
        if not file_path or not isinstance(file_path, str):
            raise ValueError(f"schema_files.{schema_id}.file must be a string path")
        if not fmt or not isinstance(fmt, str):
            raise ValueError(f"schema_files.{schema_id}.format must be a string")
        fmt_lower = fmt.lower()
        if fmt_lower not in SUPPORTED_SCHEMA_FORMATS:
            raise ValueError(
                f"schema_files.{schema_id}.format must be one of {SUPPORTED_SCHEMA_FORMATS}"
            )
        # Normalize relative paths relative to config directory
        abs_path = str((base_dir / file_path).resolve())
        schema_files[schema_id] = SchemaFileConfig(file=abs_path, format=fmt_lower)

    # Ensure mappings refer to known schema ids
    unknown = [sid for sid in schema_mappings.values() if sid not in schema_files]
    if unknown:
        raise ValueError(
            f"schema_mappings refers to unknown schema ids: {', '.join(sorted(set(unknown)))}"
        )

    return ProxyConfig(
        topic_patterns=topic_patterns,
        schema_mappings=schema_mappings,
        schema_files=schema_files,
    )


def load_config(path: str | Path) -> ProxyConfig:
    """
    Load and validate the YAML configuration file.
    Returns a structured ProxyConfig object with normalized paths and formats.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    base_dir = path.parent
    config = _validate_config_dict(raw, base_dir)
    _LOGGER.info(
        "Loaded config: %d topic patterns, %d mappings, %d schemas",
        len(config.topic_patterns),
        len(config.schema_mappings),
        len(config.schema_files),
    )
    return config


