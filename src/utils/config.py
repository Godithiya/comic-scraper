"""
Configuration manager for comic scraper
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """
    Configuration manager

    Loads and manages application configuration from YAML files.
    """

    DEFAULT_CONFIG = {
        "rate_limit": 2.0,
        "output_dir": "./downloads",
        "default_format": "images",
        "parallel_downloads": 5,
        "timeout": 30,
        "user_agent": None,
        "resume": False
    }

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".comic-scraper" / "config.yaml"
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Load configuration from file"""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                user_config = yaml.safe_load(f) or {}
                self.config.update(user_config)

    def save(self):
        """Save current configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
