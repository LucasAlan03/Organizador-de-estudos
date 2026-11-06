"""Backup diário do arquivo SQLite."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path


def backup_db(
    db_path: Path, backup_dir: Path, today: date, keep: int = 14
) -> Path | None:
    """Copia o banco para `study-AAAA-MM-DD.db` (uma vez por dia) e poda os mais antigos.

    Devolve o caminho criado, ou None se não havia banco ou o backup de hoje já existe.
    """
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"study-{today.isoformat()}.db"
    if target.exists():
        return None
    shutil.copy2(db_path, target)
    backups = sorted(backup_dir.glob("study-*.db"))
    for old in backups[: max(len(backups) - keep, 0)]:
        old.unlink()
    return target
