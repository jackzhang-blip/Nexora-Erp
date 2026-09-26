"""桌面应用启动的 HTTPS 服务入口。"""

import argparse
import ipaddress
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .database import connection, migrate
from .main import app


def ensure_certificate(data_dir: Path, instance_id: str) -> tuple[Path, Path]:
    """为一个服务端实例创建并复用独立证书，避免每次启动改变身份。"""
    cert = data_dir / "server.crt"
    key = data_dir / "server.key"
    if cert.exists() != key.exists():
        raise RuntimeError("服务端证书或私钥缺失，请恢复原文件后重试")
    if cert.exists():
        # 检查证书是否对应当前数据库，防止误把另一实例的数据目录拼在一起。
        parsed = x509.load_pem_x509_certificate(cert.read_bytes())
        expected = f"nexora-{instance_id}.local"
        if expected not in parsed.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName):
            raise RuntimeError("服务端证书与数据库实例不匹配")
        return cert, key

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    hostname = f"nexora-{instance_id}.local"
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1825))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName(hostname), x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.IPAddress(ipaddress.ip_address("::1"))
        ]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(private_key, hashes.SHA256())
    )
    # 私钥先以仅本人可读写的权限创建；只在完整生成后写入证书。
    descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(private_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert, key


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexora ERP 本机服务")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口必须在 1 到 65535 之间")
    data_dir = Path(args.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["NEXORA_DB_PATH"] = str(data_dir / "nexora.db")
    os.environ["NEXORA_INSTANCE_NAME"] = args.name
    migrate()
    with connection() as db:
        instance_id = db.execute("SELECT id FROM server_identity LIMIT 1").fetchone()[0]
    cert, key = ensure_certificate(data_dir, instance_id)
    uvicorn.run(app, host="0.0.0.0", port=args.port,
                ssl_certfile=str(cert), ssl_keyfile=str(key), log_level="info")


if __name__ == "__main__":
    main()
