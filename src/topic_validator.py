import logging
from typing import Iterable, List, Tuple, Union

from utils import match_topic


_LOGGER = logging.getLogger(__name__)


class TopicValidator:
    """Topic validator for MQTT messages."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
    
    def validate(self, topic: str, client_id: str = "") -> Tuple[bool, str]:
        """Validate topic for a client."""
        return validate_topic_for_client(client_id, topic, self.config.topic_patterns)


def validate_topic(topic: str, rules: Iterable[str]) -> Tuple[bool, str]:
    """
    Validate a topic string against a set of wildcard/regex rules.

    Returns (is_valid, reason). If valid, reason is an empty string.
    """
    for rule in rules:
        if match_topic(rule, topic):
            return True, ""
    reason = f"Topic '{topic}' does not match any allowed pattern"
    _LOGGER.info(reason)
    return False, reason


def validate_topic_for_client(
    client_id: str, topic: str, rules_config: Union[List[str], dict]
) -> Tuple[bool, str]:
    """
    Validate topic for a given client based on either:
      - a flat list of rules, or
      - a mapping {prefix_or_client: [rules...]}
    If a mapping is provided, the longest matching key prefix in client_id is selected.
    Fallback to a default key '*' if present, or all rules if it's a flat list.
    """
    selected_rules: Iterable[str]
    if isinstance(rules_config, dict):
        # Longest prefix match on client_id
        candidates = [(k, v) for k, v in rules_config.items() if client_id.startswith(k) or k == "*"]
        if not candidates:
            return False, f"No topic rules configured for client_id '{client_id}'"
        # choose the most specific (longest) key
        candidates.sort(key=lambda kv: len(kv[0]), reverse=True)
        selected_rules = candidates[0][1]
    else:
        selected_rules = rules_config
    return validate_topic(topic, selected_rules)


def topic_matches_pattern(topic: str, pattern: str) -> bool:
    """
    Check if a topic matches a pattern.
    Supports MQTT-style wildcards: + (single level), # (multi level)
    """
    return match_topic(pattern, topic)


def validate_topic_format(topic: str) -> Tuple[bool, str]:
    """
    Validate MQTT topic format according to MQTT specification.
    """
    if not topic:
        return False, "Topic cannot be empty"
    
    if len(topic) > 65535:
        return False, "Topic too long (max 65535 characters)"
    
    # Check for invalid characters
    if '\x00' in topic:
        return False, "Topic contains null character"
    
    # Check wildcard usage
    if '+' in topic:
        for level in topic.split('/'):
            if '+' in level and level != '+':
                return False, "Single-level wildcard '+' must occupy entire topic level"
    
    if '#' in topic:
        if not topic.endswith('#'):
            return False, "Multi-level wildcard '#' must be last character"
        if len(topic) > 1 and not topic.endswith('/#'):
            return False, "Multi-level wildcard '#' must be preceded by '/'"
    
    return True, "Valid topic format"


