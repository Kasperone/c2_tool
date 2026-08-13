"""Active Directory enumeration module — gathers AD domain info, users, groups,
computers, and common misconfigurations.

Usage:
    ad_enum [all|domain|users|groups|computers|gpo|trusts|acl]
"""

import os
import sys
import subprocess
import re
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point. Usage: ad_enum [all|domain|users|groups|computers|gpo|trusts|acl]"""
    mode = args[0] if args else "all"

    try:
        if mode == "domain":
            return _enum_domain()
        elif mode == "users":
            return _enum_users()
        elif mode == "groups":
            return _enum_groups()
        elif mode == "computers":
            return _enum_computers()
        elif mode == "gpo":
            return _enum_gpo()
        elif mode == "trusts":
            return _enum_trusts()
        elif mode == "acl":
            return _enum_acl()
        elif mode == "all":
            sections = [
                "=== Domain Information ===",
                _enum_domain(),
                "\n=== User Enumeration ===",
                _enum_users(),
                "\n=== Group Enumeration ===",
                _enum_groups(),
                "\n=== Computer Enumeration ===",
                _enum_computers(),
                "\n=== GPO Enumeration ===",
                _enum_gpo(),
                "\n=== Trust Relationships ===",
                _enum_trusts(),
                "\n=== ACL / Permission Issues ===",
                _enum_acl(),
            ]
            return "\n".join(sections)
        else:
            return f"Unknown mode: {mode}\nUsage: ad_enum [all|domain|users|groups|computers|gpo|trusts|acl]"
    except Exception as e:
        return f"AD enumeration failed: {e}"


def _run_cmd(cmd: list[str] | str, shell: bool = False) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _is_windows_domain() -> bool:
    """Check if this host is in a Windows domain."""
    if sys.platform != "win32":
        return False
    domain = _run_cmd("wmic computersystem get domain", shell=True)
    return "Domain" in domain and domain.strip().split("\n")[-1].strip() != ""


def _is_linux_ad_member() -> bool:
    """Check if Linux host is AD-joined (via SSSD)."""
    if not _is_sssd_running():
        return False
    realm_info = _run_cmd("realm list 2>&1")
    return "realm" in realm_info.lower() and "realm" not in _run_cmd("echo $PATH").lower()


def _is_sssd_running() -> bool:
    """Check if SSSD service is running."""
    result = _run_cmd("systemctl is-active sssd 2>/dev/null", shell=True)
    return result == "active"


def _enum_domain() -> str:
    """Enumerate domain information."""
    lines = []

    if sys.platform == "win32":
        lines.append("  OS: Windows (Active Directory client)")

        # Get domain info
        domain = _run_cmd("systeminfo | findstr /B /C:\"Domain\"", shell=True)
        if domain:
            lines.append(f"  {domain.strip()}")

        # Get domain controller
        dc = _run_cmd("nltest /dclist:%windom%" % _run_cmd("echo %USERDNSDOMAIN%", shell=True), shell=True)
        if not dc:
            dc = _run_cmd("set logonserver", shell=True)
        if dc:
            lines.append(f"  Domain Controller: {dc.strip()}")

        # Get domain functional level
        dfl = _run_cmd("Get-ADDomain | fl Forest,Domain,DomainMode", shell=True)
        if dfl:
            lines.append(f"  Domain Functional Level:\n{dfl.strip()}")

        # Get NetBIOS domain name
        netbios = _run_cmd("echo %USERDOMAIN%", shell=True)
        if netbios:
            lines.append(f"  NetBIOS Domain: {netbios.strip()}")

    elif _is_linux_ad_member():
        lines.append("  OS: Linux (AD-joined via SSSD)")
        realm = _run_cmd("realm list", shell=True)
        if realm:
            lines.append(f"  {realm[:2000]}")
    else:
        return "  Not in an Active Directory environment"

    return "\n".join(lines) if lines else "  Domain enumeration failed"


def _enum_users() -> str:
    """Enumerate domain users and check for interesting properties."""
    lines = []

    if sys.platform != "win32":
        return "  User enumeration only supported on Windows domain joined hosts"

    # Get all domain users via dsquery
    users = _run_cmd("dsquery user -limit 0 2>&1", shell=True)
    if users and "dsquery" in users:
        lines.append(f"  Domain users (via dsquery):")
        for line in users.split("\n"):
            if line.strip().startswith("CN="):
                cn = line.strip().split("CN=")[1].split(",")[0]
                lines.append(f"    - {cn}")

    # Try PowerShell for more details
    ps_users = _run_cmd(
        "Get-ADUser -Filter * -Properties Description,LastLogonDate,PasswordLastSet,Enabled | "
        "Select-Object Name,Description,LastLogonDate,PasswordLastSet,Enabled | "
        "Format-List",
        shell=True
    )
    if ps_users:
        lines.append("\n  User Details (via PowerShell AD module):")
        lines.append(ps_users[:3000])

    # Check for users with password not required
    nopass = _run_cmd(
        "dsquery user -disabled -limit 0 2>&1", shell=True
    )
    if nopass:
        disabled = [l for l in nopass.split("\n") if l.strip().startswith("CN=")]
        if disabled:
            lines.append(f"\n  [!] Disabled accounts: {len(disabled)}")
            for acct in disabled[:20]:
                cn = acct.split("CN=")[1].split(",")[0]
                lines.append(f"    - {cn}")

    # Check for password expiry bypasses
    pw_policy = _run_cmd("net accounts", shell=True)
    if pw_policy:
        lines.append(f"\n  Password Policy:\n{pw_policy[:500]}")

    return "\n".join(lines) if lines else "  User enumeration failed"


def _enum_groups() -> str:
    """Enumerate groups, especially privileged ones."""
    lines = []

    if sys.platform != "win32":
        return "  Group enumeration only supported on Windows"

    # Get privileged groups
    priv_groups = ["Domain Admins", "Enterprise Admins", "Administrators",
                   "Domain Controllers", "Schema Admins", "Organization Management",
                   "Exchange Admins", "Backup Operators", "Print Operators",
                   "Remote Desktop Users"]

    for group_name in priv_groups:
        members = _run_cmd(
            f"net group \"{group_name}\" /domain 2>&1", shell=True
        )
        if members and members != "The command completed successfully" and "net" not in members.lower():
            lines.append(f"\n  [{group_name}]:")
            for line in members.split("\n"):
                line = line.strip()
                if line and line != group_name and "Command completed" not in line:
                    lines.append(f"    - {line}")

    # Get all domain groups
    all_groups = _run_cmd("dsquery group -limit 0 2>&1", shell=True)
    if all_groups:
        group_count = sum(1 for l in all_groups.split("\n") if l.strip().startswith("CN="))
        lines.append(f"\n  Total domain groups: {group_count}")

    return "\n".join(lines) if lines else "  Group enumeration failed"


def _enum_computers() -> str:
    """Enumerate domain computers and check for security issues."""
    lines = []

    if sys.platform != "win32":
        return "  Computer enumeration only supported on Windows"

    # Get all domain computers
    computers = _run_cmd("dsquery computer -limit 0 2>&1", shell=True)
    if computers:
        pc_list = [l for l in computers.split("\n") if l.strip().startswith("CN=")]
        lines.append(f"  Domain computers: {len(pc_list)}")
        for pc in pc_list[:30]:
            cn = pc.split("CN=")[1].split(",")[0]
            lines.append(f"    - {cn}")
        if len(pc_list) > 30:
            lines.append(f"    ... and {len(pc_list) - 30} more")

    # Check for computers with password not required
    unpass = _run_cmd("dsquery computer -disabled -limit 0 2>&1", shell=True)
    if unpass:
        disabled = [l for l in unpass.split("\n") if l.strip().startswith("CN=")]
        if disabled:
            lines.append(f"\n  [!] Disabled computer accounts: {len(disabled)}")

    # Check for weak SPNs
    spns = _run_cmd(
        'Get-ADComputer -Filter * -Properties ServicePrincipalName | '
        'Where-Object {$_.ServicePrincipalName -ne $null} | '
        'Select-Object Name,ServicePrincipalName | Format-List',
        shell=True
    )
    if spns:
        lines.append(f"\n  Service Principal Names:\n{spns[:2000]}")

    return "\n".join(lines) if lines else "  Computer enumeration failed"


def _enum_gpo() -> str:
    """Enumerate Group Policy Objects and their settings."""
    lines = []

    if sys.platform != "win32":
        return "  GPO enumeration only supported on Windows"

    # Get all GPOs
    gpos = _run_cmd("Get-GPO -All 2>&1", shell=True)
    if gpos:
        lines.append(f"  Group Policy Objects:\n{gpos[:3000]}")
    else:
        lines.append("  Could not enumerate GPOs (need Group Policy module)")

    # Check for GPOs with interesting settings
    # Check for constrained delegation
    unconstrained = _run_cmd(
        "Get-ADComputer -Filter {TrustedForDelegation -eq $true} | "
        "Select-Object Name,TrustedForDelegation",
        shell=True
    )
    if unconstrained and "Get-ADComputer" not in unconstrained:
        lines.append(f"\n  [!] Unconstrained Delegation:\n{unconstrained}")

    # Check for DCSync permissions
    lines.append("\n  Note: DCSync requires specific permissions — check for:")
    lines.append("    - Domain Admins group membership")
    lines.append("    - Enterprise Admins group membership")
    lines.append("    - WriteDACL on domain object")

    return "\n".join(lines) if lines else "  GPO enumeration failed"


def _enum_trusts() -> str:
    """Enumerate domain trust relationships."""
    lines = []

    if sys.platform != "win32":
        return "  Trust enumeration only supported on Windows"

    # Get trust relationships
    trusts = _run_cmd("nltest /domain_trusts 2>&1", shell=True)
    if trusts:
        lines.append("  Trust Relationships:")
        for line in trusts.split("\n"):
            line = line.strip()
            if line:
                lines.append(f"    - {line}")

    # Check for forest trusts
    forest = _run_cmd("nltest /trusted_domains 2>&1", shell=True)
    if forest and "trusted" in forest.lower():
        lines.append(f"\n  Trusted Domains:\n{forest}")

    return "\n".join(lines) if lines else "  Trust enumeration failed"


def _enum_acl() -> str:
    """Check for common ACL misconfigurations."""
    lines = []

    if sys.platform != "win32":
        return "  ACL enumeration only supported on Windows"

    # Check for users with DCSync permissions
    dcsync = _run_cmd(
        "Get-ADObject -Filter 'ObjectClass -eq \"domain\"' -Properties "
        "ntSecurityDescriptor | Select-Object -ExpandProperty "
        "ntSecurityDescriptor | Select-Object -ExpandProperty DiscretionaryAcl",
        shell=True
    )
    if dcsync:
        lines.append(f"  Domain ACL:\n{dcsync[:2000]}")

    # Check for password spray vectors
    lines.append("\n  [!] Password Spray Vectors:")
    lines.append("    - Users with empty descriptions (easy to guess)")
    lines.append("    - Accounts not requiring password change")
    lines.append("    - Service accounts with static passwords")

    # Check for Kerberoastable accounts
    kerberoast = _run_cmd(
        "Get-ADUser -Filter {ServicePrincipalName -like '*'} -Properties "
        "ServicePrincipalName | Select-Object Name,ServicePrincipalName",
        shell=True
    )
    if kerberoast and "Get-ADUser" not in kerberoast:
        accounts = [l for l in kerberoast.split("\n") if l.strip() and "Name" not in l]
        if accounts:
            lines.append(f"\n  [!] Kerberoastable accounts: {len(accounts)}")
            for acct in accounts[:20]:
                lines.append(f"    - {acct.strip()}")

    # Check for AS-REP Roasting
    asrep = _run_cmd(
        "Get-ADUser -Filter {DoesNotRequirePreAuth -eq $true} | "
        "Select-Object Name",
        shell=True
    )
    if asrep and "Get-ADUser" not in asrep:
        accounts = [l for l in asrep.split("\n") if l.strip() and "Name" not in l]
        if accounts:
            lines.append(f"\n  [!] AS-REP Roastable accounts: {len(accounts)}")
            for acct in accounts[:20]:
                lines.append(f"    - {acct.strip()}")

    return "\n".join(lines) if lines else "  ACL enumeration failed"
