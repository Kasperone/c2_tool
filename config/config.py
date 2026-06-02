import os
import yaml


class Config:
    def __init__(self, data: dict | None = None):
        object.__setattr__(self, "_data", data or {})

    def __getattr__(self, name: str):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        data = object.__getattribute__(self, "_data")
        try:
            val = data[name]
        except KeyError:
            raise AttributeError(f"Config has no section '{name}'")
        if isinstance(val, dict):
            return Config(val)
        return val

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def __repr__(self):
        return f"Config({list(self._data.keys())})"


def load_config(path: str = None) -> Config:
    if path is None:
        path = os.environ.get("C2_CONFIG", "config.yaml")

    if not os.path.exists(path):
        default_path = os.path.join(os.path.dirname(__file__), "default.yaml")
        if os.path.exists(default_path):
            path = default_path
        else:
            raise FileNotFoundError(
                f"No config file found at '{path}' or default config"
            )

    with open(path) as f:
        data = yaml.safe_load(f)

    return Config(data)
