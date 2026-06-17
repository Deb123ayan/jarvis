import yaml
import os
from pathlib import Path

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.data = {}
        self.load_env()
        self.load()

    def load_env(self):
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"\'')

    def load(self):
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.data = yaml.safe_load(f) or {}
        else:
            self.data = {}

    def get(self, key: str, default=None):
        env_key = key.split(".")[-1].upper()
        if env_key in os.environ:
            return os.environ[env_key]
        full_env_key = key.replace(".", "_").upper()
        if full_env_key in os.environ:
            return os.environ[full_env_key]

        keys = key.split(".")
        val = self.data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

config = Config()
