"""Certificado y firma para QZ Tray (evita el cartel de sitio no confiable)."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from django.conf import settings


def get_qz_cert_dir() -> Path:
    return Path(settings.BASE_DIR) / "certs" / "qz"


def get_qz_cert_path() -> Path:
    return get_qz_cert_dir() / "digital-certificate.txt"


def get_qz_key_path() -> Path:
    return get_qz_cert_dir() / "private-key.pem"


def generate_qz_certificate(common_name: str = "TodoBrilla TPV") -> tuple[Path, Path]:
    cert_dir = get_qz_cert_dir()
    cert_dir.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TodoBrilla"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )

    key_path = get_qz_key_path()
    cert_path = get_qz_cert_path()
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def ensure_qz_certificate() -> None:
    if get_qz_cert_path().exists() and get_qz_key_path().exists():
        return
    generate_qz_certificate()


def get_qz_certificate_pem() -> str:
    ensure_qz_certificate()
    return get_qz_cert_path().read_text(encoding="utf-8")


def sign_qz_request(payload: str) -> str:
    ensure_qz_certificate()
    private_key = serialization.load_pem_private_key(
        get_qz_key_path().read_bytes(),
        password=None,
    )
    signature = private_key.sign(
        payload.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA512(),
    )
    return base64.b64encode(signature).decode("ascii")
