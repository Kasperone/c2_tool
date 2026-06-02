#!/usr/bin/env python3
"""C2 Client entry point."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from c2.client.client import run_client

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config(config_path)
    run_client(cfg)
