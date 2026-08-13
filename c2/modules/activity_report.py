"""Activity report module — generates engagement reports from activity logs
using SQLite query aggregation.

Usage:
    activity_report [all|sessions|commands|timeline|export]
"""

import os
import sys
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point. Usage: activity_report [all|sessions|commands|timeline|export]"""
    mode = args[0] if args else "all"

    try:
        if mode == "sessions":
            return _report_sessions()
        elif mode == "commands":
            return _report_commands()
        elif mode == "timeline":
            return _report_timeline()
        elif mode == "export":
            return _report_export()
        elif mode == "all":
            sections = [
                "=== Session Summary ===",
                _report_sessions(),
                "\n=== Command Statistics ===",
                _report_commands(),
                "\n=== Activity Timeline ===",
                _report_timeline(),
            ]
            return "\n".join(sections)
        else:
            return f"Unknown mode: {mode}\nUsage: activity_report [all|sessions|commands|timeline|export]"
    except Exception as e:
        return f"Activity report failed: {e}"


def _get_db_path() -> Optional[str]:
    """Get the activity log database path from config."""
    # Try to load from config
    try:
        from config import load_config
        config = load_config()
        return config.logging.database if config.logging.database else "c2_activity.db"
    except Exception:
        return "c2_activity.db"


def _get_conn(db_path: str) -> Optional[sqlite3.Connection]:
    """Get a database connection."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _report_sessions() -> str:
    """Generate session summary report."""
    db_path = _get_db_path()
    conn = _get_conn(db_path)

    if not conn:
        return "  No activity log database found."

    try:
        # Count total sessions
        sessions = conn.execute("SELECT COUNT(*) as count FROM sessions").fetchone()
        total_sessions = sessions["count"] if sessions else 0

        # Get latest sessions
        latest = conn.execute(
            "SELECT session_id, client_name, hostname, account, last_seen "
            "FROM sessions ORDER BY last_seen DESC LIMIT 10"
        ).fetchall()

        lines = [f"  Total sessions: {total_sessions}"]

        if latest:
            lines.append("\n  Most recent sessions:")
            for s in latest:
                lines.append(
                    f"    - {s['client_name']} @ {s['hostname']} "
                    f"({s['account']}) - {s['last_seen']}"
                )

        # Session duration stats
        durations = conn.execute(
            "SELECT MAX(julianday(last_seen) - julianday(first_seen)) as days "
            "FROM sessions"
        ).fetchone()
        if durations and durations["days"]:
            lines.append(f"\n  Max session duration: {durations['days']:.1f} days")

        # Active sessions (connected in last 1 hour)
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        active = conn.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE last_seen > ?",
            (one_hour_ago,)
        ).fetchone()
        lines.append(f"  Active sessions (last 1h): {active['count']}")

        return "\n".join(lines)
    except Exception as e:
        return f"  Error generating session report: {e}"
    finally:
        conn.close()


def _report_commands() -> str:
    """Generate command statistics report."""
    db_path = _get_db_path()
    conn = _get_conn(db_path)

    if not conn:
        return "  No activity log database found."

    try:
        # Total commands
        total = conn.execute("SELECT COUNT(*) as count FROM commands").fetchone()
        total_commands = total["count"] if total else 0

        # Commands by status
        by_status = conn.execute(
            "SELECT status, COUNT(*) as count FROM commands GROUP BY status"
        ).fetchall()

        # Top commands
        top_cmds = conn.execute(
            "SELECT command, COUNT(*) as count FROM commands "
            "GROUP BY command ORDER BY count DESC LIMIT 10"
        ).fetchall()

        # Commands by session
        by_session = conn.execute(
            "SELECT session_id, COUNT(*) as count FROM commands "
            "GROUP BY session_id ORDER BY count DESC LIMIT 5"
        ).fetchall()

        lines = [f"  Total commands executed: {total_commands}"]

        if by_status:
            lines.append("\n  Commands by status:")
            for s in by_status:
                lines.append(f"    - {s['status']}: {s['count']}")

        if top_cmds:
            lines.append("\n  Top commands:")
            for c in top_cmds:
                cmd = c["command"][:60]
                lines.append(f"    - {cmd} ({c['count']}x)")

        if by_session:
            lines.append("\n  Commands by session:")
            for s in by_session:
                lines.append(f"    - Session {s['session_id']}: {s['count']}")

        # Commands in last 24 hours
        yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        recent = conn.execute(
            "SELECT COUNT(*) as count FROM commands WHERE timestamp > ?",
            (yesterday,)
        ).fetchone()
        lines.append(f"\n  Commands (last 24h): {recent['count']}")

        return "\n".join(lines)
    except Exception as e:
        return f"  Error generating command report: {e}"
    finally:
        conn.close()


def _report_timeline() -> str:
    """Generate activity timeline report."""
    db_path = _get_db_path()
    conn = _get_conn(db_path)

    if not conn:
        return "  No activity log database found."

    try:
        # Get recent events (last 50)
        events = conn.execute(
            "SELECT timestamp, event_type, detail "
            "FROM events ORDER BY timestamp DESC LIMIT 50"
        ).fetchall()

        # Recent commands (last 20)
        recent_cmds = conn.execute(
            "SELECT timestamp, command, status "
            "FROM commands ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()

        lines = []

        if events:
            lines.append("  Recent events:")
            for e in events:
                detail = e["detail"][:80] if e["detail"] else ""
                lines.append(f"    [{e['timestamp']}] {e['event_type']}: {detail}")

        if recent_cmds:
            lines.append("\n  Recent commands:")
            for c in recent_cmds:
                cmd = c["command"][:60]
                lines.append(f"    [{c['timestamp']}] {c['status']}: {cmd}")

        return "\n".join(lines) if lines else "  No timeline data found."
    except Exception as e:
        return f"  Error generating timeline: {e}"
    finally:
        conn.close()


def _report_export() -> str:
    """Export report data to a JSON file."""
    db_path = _get_db_path()
    conn = _get_conn(db_path)

    if not conn:
        return "  No activity log database found."

    try:
        import json

        export_dir = os.path.join(
            os.path.dirname(__file__), "..", "client", ".reports"
        )
        os.makedirs(export_dir, exist_ok=True)

        timestamp = int(time.time())
        filename = f"activity_report_{timestamp}.json"
        export_path = os.path.join(export_dir, filename)

        # Gather report data
        report = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "database": db_path,
            "sessions": {},
            "commands": {},
            "events": [],
        }

        # Session stats
        sessions = conn.execute("SELECT * FROM sessions ORDER BY last_seen DESC").fetchall()
        report["sessions"]["count"] = len(sessions)
        report["sessions"]["list"] = [dict(s) for s in sessions[:20]]

        # Command stats
        total_cmds = conn.execute("SELECT COUNT(*) as count FROM commands").fetchone()
        report["commands"]["total"] = total_cmds["count"] if total_cmds else 0

        recent_cmds = conn.execute(
            "SELECT * FROM commands ORDER BY timestamp DESC LIMIT 50"
        ).fetchall()
        report["commands"]["recent"] = [dict(c) for c in recent_cmds]

        # Events
        events = conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT 100"
        ).fetchall()
        report["events"] = [dict(e) for e in events]

        # Write report
        with open(export_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return f"Report exported: {export_path} ({_file_size(export_path)})"
    except Exception as e:
        return f"  Error exporting report: {e}"
    finally:
        conn.close()


def _file_size(filepath: str) -> str:
    """Return human-readable file size."""
    if not os.path.exists(filepath):
        return "unknown"
    size_bytes = os.path.getsize(filepath)
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
