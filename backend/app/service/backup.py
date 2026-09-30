"""服务端实例的成组备份与恢复。"""

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.models import ServerIdentity


FILES = ("nexora.db", "server.crt", "server.key")
MAX_MANIFEST_SIZE = 64 * 1024
MAX_BACKUP_SIZE = 8 * 1024 * 1024 * 1024


def _instance_id(data_dir: Path) -> str:
    database = data_dir / "nexora.db"
    if not database.is_file():
        raise ValueError("实例数据库不存在")
    # 只读打开可防止路径写错时静默创建一个空数据库。
    # 备份路径不依赖当前服务环境；NullPool 确保 Windows 发布恢复目录前释放文件句柄。
    engine = create_engine(
        "sqlite://",
        poolclass=NullPool,
        creator=lambda: sqlite3.connect(database.as_uri() + "?mode=ro", uri=True),
    )
    try:
        with Session(engine) as session:
            # SQLite 完整性诊断没有 ORM 等价物；实例身份查询仍通过声明式模型。
            if session.connection().exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
                raise ValueError("实例数据库完整性检查失败")
            instance_id = session.scalar(select(ServerIdentity.id).limit(1))
            if instance_id is None:
                raise ValueError("实例身份不存在")
            return instance_id
    finally:
        engine.dispose()


def _verify_identity(data_dir: Path) -> str:
    for name in FILES:
        if not (data_dir / name).is_file():
            raise ValueError(f"实例文件缺失：{name}")
    instance_id = _instance_id(data_dir)
    certificate = x509.load_pem_x509_certificate((data_dir / "server.crt").read_bytes())
    private_key = serialization.load_pem_private_key((data_dir / "server.key").read_bytes(), password=None)
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if f"nexora-{instance_id}.local" not in names.get_values_for_type(x509.DNSName):
        raise ValueError("证书与实例数据库身份不匹配")
    if certificate.public_key().public_bytes(serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo) != private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo):
        raise ValueError("证书与私钥不匹配")
    return instance_id


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(data_dir: Path, destination: Path) -> str:
    """从运行中的 SQLite 获取一致快照，再与证书和私钥组成单一备份。"""
    data_dir = data_dir.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("备份文件已存在，不会覆盖")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexora-backup-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        source_db = data_dir / "nexora.db"
        if not source_db.is_file():
            raise ValueError("实例数据库不存在")
        # SQLite 在线备份 API 会取得一致快照，不能直接复制可能正在写入的数据库文件。
        with closing(sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(staging / "nexora.db")) as snapshot:
                source.backup(snapshot)
        for name in FILES[1:]:
            (staging / name).write_bytes((data_dir / name).read_bytes())
        instance_id = _verify_identity(staging)
        manifest = {
            "format": 1,
            "instance_id": instance_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sha256": {name: _sha256(staging / name) for name in FILES},
        }
        archive = staging / "bundle.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                             allowZip64=True) as target:
            target.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            for name in FILES:
                target.write(staging / name, name)
        # 同一文件系统内硬链接只会发布已完成的归档，并拒绝覆盖同名备份。
        os.chmod(archive, 0o600)
        os.link(archive, destination)
        return instance_id


def restore_backup(archive: Path, destination: Path) -> str:
    """先完整验证备份，只允许恢复到尚不存在的新数据目录。"""
    archive = archive.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("恢复目录已存在，请选择新的空目录以保留原数据")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexora-restore-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive) as source:
            names = source.namelist()
            if len(names) != 4 or set(names) != {"manifest.json", *FILES}:
                raise ValueError("备份文件结构无效")
            if source.getinfo("manifest.json").file_size > MAX_MANIFEST_SIZE:
                raise ValueError("备份清单过大")
            if sum(source.getinfo(name).file_size for name in FILES) > MAX_BACKUP_SIZE:
                raise ValueError("备份文件过大")
            manifest = json.loads(source.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("format") != 1 or not isinstance(
                    manifest.get("sha256"), dict):
                raise ValueError("备份版本或清单无效")
            for name in FILES:
                digest = hashlib.sha256()
                with source.open(name) as input_file, (staging / name).open("wb") as output:
                    for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
                os.chmod(staging / name, 0o600)
                if digest.hexdigest() != manifest["sha256"].get(name):
                    raise ValueError(f"备份校验失败：{name}")
        instance_id = _verify_identity(staging)
        if instance_id != manifest.get("instance_id"):
            raise ValueError("备份清单与实例身份不匹配")
        # 目录重命名是同一磁盘内的原子操作，验证失败不会留下半套实例文件。
        os.replace(staging, destination)
        return instance_id


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Nexora ERP 实例备份与恢复")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="生成数据库与证书的成组备份")
    backup.add_argument("--data-dir", required=True, type=Path)
    backup.add_argument("--output", required=True, type=Path)
    restore = commands.add_parser("restore", help="验证备份并恢复到新目录")
    restore.add_argument("--archive", required=True, type=Path)
    restore.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "backup":
        instance_id = create_backup(args.data_dir, args.output)
        print(f"备份已完成，实例：{instance_id}")
    else:
        instance_id = restore_backup(args.archive, args.data_dir)
        print(f"恢复已完成，实例：{instance_id}")


if __name__ == "__main__":
    main()
