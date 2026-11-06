"""Leitura mínima de arquivo .env (CHAVE=valor), sem dependências."""
from __future__ import annotations

import codecs
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    raw = path.read_bytes()
    # PowerShell 5.1 grava UTF-16; editores do Windows costumam gravar UTF-8 com BOM
    is_utf16 = raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE)
    text = raw.decode("utf-16") if is_utf16 else raw.decode("utf-8-sig")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values
