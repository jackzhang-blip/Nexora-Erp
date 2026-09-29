"""备份必须同时保留数据库、证书和私钥，并拒绝损坏归档。"""

import json
import sqlite3
import zipfile

import pytest

from app.service import backup as backup_module
from app.service.backup import create_backup, restore_backup
from app.core.database import migrate
from app.server import ensure_certificate


def test_online_backup_restores_original_identity_and_snapshot(monkeypatch, tmp_path):
    data_dir = tmp_path / "source"
    data_dir.mkdir()
    monkeypatch.setenv("NEXORA_DB_PATH", str(data_dir / "nexora.db"))
    monkeypatch.setenv("NEXORA_INSTANCE_NAME", "备份测试")
    migrate()
    with sqlite3.connect(data_dir / "nexora.db") as db:
        instance_id = db.execute("SELECT id FROM server_identity").fetchone()[0]
        db.execute("INSERT INTO suppliers(name) VALUES ('备份前供应商')")
    ensure_certificate(data_dir, instance_id)

    archive = tmp_path / "instance.nexora-backup"
    assert create_backup(data_dir, archive) == instance_id
    with sqlite3.connect(data_dir / "nexora.db") as db:
        db.execute("INSERT INTO suppliers(name) VALUES ('备份后供应商')")

    restored = tmp_path / "restored"
    assert restore_backup(archive, restored) == instance_id
    assert (restored / "server.crt").read_bytes() == (data_dir / "server.crt").read_bytes()
    assert (restored / "server.key").read_bytes() == (data_dir / "server.key").read_bytes()
    with sqlite3.connect(restored / "nexora.db") as db:
        assert db.execute("SELECT name FROM suppliers ORDER BY id").fetchall() == [("备份前供应商",)]
    with pytest.raises(FileExistsError):
        restore_backup(archive, restored)
    with pytest.raises(FileExistsError):
        create_backup(data_dir, archive)


def test_backup_rejects_mismatched_key_and_tampered_archive(monkeypatch, tmp_path):
    data_dir = tmp_path / "source"
    data_dir.mkdir()
    monkeypatch.setenv("NEXORA_DB_PATH", str(data_dir / "nexora.db"))
    migrate()
    with sqlite3.connect(data_dir / "nexora.db") as db:
        instance_id = db.execute("SELECT id FROM server_identity").fetchone()[0]
    ensure_certificate(data_dir, instance_id)
    archive = tmp_path / "valid.nexora-backup"
    create_backup(data_dir, archive)

    tampered = tmp_path / "tampered.nexora-backup"
    with zipfile.ZipFile(archive) as original, zipfile.ZipFile(tampered, "w") as changed:
        manifest = json.loads(original.read("manifest.json"))
        manifest["sha256"]["nexora.db"] = "0" * 64
        changed.writestr("manifest.json", json.dumps(manifest))
        for name in ("nexora.db", "server.crt", "server.key"):
            changed.writestr(name, original.read(name))
    destination = tmp_path / "invalid-restore"
    with pytest.raises(ValueError, match="备份校验失败"):
        restore_backup(tampered, destination)
    assert not destination.exists()

    # 不允许仅有数据库和证书却配上其他实例的私钥。
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    ensure_certificate(other_dir, "00000000-0000-0000-0000-000000000000")
    (data_dir / "server.key").write_bytes((other_dir / "server.key").read_bytes())
    with pytest.raises(ValueError, match="证书与私钥不匹配"):
        create_backup(data_dir, tmp_path / "broken.nexora-backup")
    assert not (tmp_path / "broken.nexora-backup").exists()


def test_backup_closes_sqlite_handles_before_temporary_cleanup(monkeypatch, tmp_path):
    data_dir = tmp_path / "source"
    data_dir.mkdir()
    monkeypatch.setenv("NEXORA_DB_PATH", str(data_dir / "nexora.db"))
    migrate()
    with sqlite3.connect(data_dir / "nexora.db") as db:
        instance_id = db.execute("SELECT id FROM server_identity").fetchone()[0]
    ensure_certificate(data_dir, instance_id)

    opened = []
    closed = []
    original_connect = sqlite3.connect

    class TrackedConnection(sqlite3.Connection):
        def close(self):
            closed.append(self)
            super().close()

    def tracked_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs, factory=TrackedConnection)
        opened.append(connection)
        return connection

    # Windows 不允许删除仍被数据库连接占用的临时文件；逐个核对显式关闭。
    monkeypatch.setattr(backup_module.sqlite3, "connect", tracked_connect)
    create_backup(data_dir, tmp_path / "instance.nexora-backup")
    assert len(opened) == 3
    assert len(closed) == len(opened)
    assert all(connection in closed for connection in opened)
