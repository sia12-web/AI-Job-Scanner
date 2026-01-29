"""
Configuration management for Telegram sources.

Handles loading and saving of the telegram_sources.yaml file.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_sources(path: str) -> Dict[str, Any]:
    """
    Load Telegram sources from YAML file.

    Args:
        path: Path to telegram_sources.yaml

    Returns:
        Dictionary containing sources configuration with keys:
        - sources: List of source dictionaries
        - metadata: Metadata dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ValueError: If required fields are missing
    """
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Configuration file is empty: {path}")

    # Validate required top-level structure
    if "sources" not in data:
        raise ValueError("Missing required 'sources' key in configuration")

    if not isinstance(data["sources"], list):
        raise ValueError("'sources' must be a list")

    # Validate each source has required fields
    for idx, source in enumerate(data["sources"]):
        if not isinstance(source, dict):
            raise ValueError(f"Source at index {idx} is not a dictionary")

        required_fields = ["source_id", "display_name", "type"]
        for field in required_fields:
            if field not in source:
                raise ValueError(
                    f"Source at index {idx} missing required field: {field}"
                )

    return data


def save_sources(path: str, data: Dict[str, Any]) -> None:
    """
    Save Telegram sources to YAML file.

    Note: This will overwrite the existing file and may not preserve
    all comments. For production use, consider using a library that
    preserves comments like ruamel.yaml.

    Args:
        path: Path to save telegram_sources.yaml
        data: Dictionary containing sources configuration

    Raises:
        IOError: If file cannot be written
    """
    config_path = Path(path)

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_enabled_sources(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filter sources to only those that are enabled.

    Args:
        data: Configuration dictionary from load_sources()

    Returns:
        List of source dictionaries where enabled=true
    """
    sources = data.get("sources", [])

    return [
        source
        for source in sources
        if source.get("enabled", True)
    ]


def find_source_by_id(data: Dict[str, Any], source_id: str) -> Optional[Dict[str, Any]]:
    """
    Find a specific source by its source_id.

    Args:
        data: Configuration dictionary from load_sources()
        source_id: Unique source identifier

    Returns:
        Source dictionary if found, None otherwise
    """
    sources = data.get("sources", [])

    for source in sources:
        if source.get("source_id") == source_id:
            return source

    return None


def update_source_validation(
    data: Dict[str, Any],
    source_id: str,
    validation_status: str,
    last_validated_at: str,
    last_error: Optional[str] = None,
    resolved_entity_id: Optional[int] = None,
    resolved_entity_type: Optional[str] = None,
) -> bool:
    """
    Update validation fields for a specific source.

    Args:
        data: Configuration dictionary from load_sources()
        source_id: Unique source identifier
        validation_status: New validation status
        last_validated_at: ISO8601 timestamp
        last_error: Error message if validation failed
        resolved_entity_id: Telegram entity ID
        resolved_entity_type: Entity type (channel|group)

    Returns:
        True if source was found and updated, False otherwise
    """
    sources = data.get("sources", [])

    for source in sources:
        if source.get("source_id") == source_id:
            source["validation_status"] = validation_status
            source["last_validated_at"] = last_validated_at

            if last_error:
                source["last_error"] = last_error
            elif "last_error" in source:
                del source["last_error"]

            if resolved_entity_id:
                source["resolved_entity_id"] = resolved_entity_id

            if resolved_entity_type:
                source["resolved_entity_type"] = resolved_entity_type

            return True

    return False
