from datetime import date

from app.backup import backup_db


def test_backup_creates_once_and_prunes(tmp_path):
    db = tmp_path / "study.db"
    db.write_bytes(b"conteudo")
    bdir = tmp_path / "backups"
    bdir.mkdir()
    for i in range(1, 17):
        (bdir / f"study-2026-10-{i:02d}.db").write_bytes(b"old")

    path = backup_db(db, bdir, date(2026, 11, 6), keep=14)

    assert path == bdir / "study-2026-11-06.db"
    assert path.read_bytes() == b"conteudo"
    files = sorted(bdir.glob("study-*.db"))
    assert len(files) == 14
    assert files[0].name == "study-2026-10-04.db"
    assert files[-1] == path
    # segunda chamada no mesmo dia não faz nada
    assert backup_db(db, bdir, date(2026, 11, 6), keep=14) is None


def test_backup_without_db_is_a_noop(tmp_path):
    assert backup_db(tmp_path / "nada.db", tmp_path / "b", date(2026, 11, 6)) is None
