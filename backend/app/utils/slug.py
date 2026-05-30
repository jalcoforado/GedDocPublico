"""Slugify determinístico para chaves estáveis (ex.: ServicoDocumento.key).

Lower-case, sem acentos, separador `-`, ASCII. Idêntico ao slug de URL. Usado em
runtime (`services/servico.py`) e na migration 0026 (backfill) — manter
determinístico para que a key gerada seja a mesma em ambos os contextos.
"""
from __future__ import annotations

import re
import unicodedata


def slugify(text: str, *, max_length: int = 120) -> str:
    """Converte um texto em um slug estável: minúsculas, sem acentos, hífens
    como separador, somente `[a-z0-9-]`, sem hífens nas pontas, truncado em
    `max_length`."""
    if not text:
        return ""
    s = unicodedata.normalize("NFD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:max_length].rstrip("-")


def slugify_unique(text: str, existing: set[str], *, max_length: int = 120) -> str:
    """Como `slugify`, mas garante unicidade dentro de `existing`: se já houver
    colisão, sufixa `-2`, `-3`, ... (preservando `max_length`)."""
    base = slugify(text, max_length=max_length) or "item"
    if base not in existing:
        return base
    i = 2
    while True:
        suffix = f"-{i}"
        candidate = (base[: max_length - len(suffix)] + suffix).rstrip("-")
        if candidate not in existing:
            return candidate
        i += 1
