from pathlib import Path

import yaml
from ml_collections import ConfigDict


def get_config(config_path: Path | None = None) -> ConfigDict:
    """Load ingestion config from YAML into a ConfigDict.

    Args:
        config_path: Path to the YAML config file. Defaults to
            ``<project_root>/configs/config.yaml``.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "configs" / "config.yaml"

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return ConfigDict(raw)
