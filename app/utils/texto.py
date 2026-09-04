# app/utils/texto.py
#
# Helpers de normalización de texto para Kipu.
# Fuente única de verdad para mayúsculas, limpieza de caracteres, etc.

import re
import unicodedata


def mayusculas(texto: str | None) -> str | None:
    """
    Normaliza texto a mayúsculas SRI-safe:
    - Elimina tildes y diacríticos
    - Solo permite A-Z, 0-9, espacios y . , - / # &
    - Colapsa espacios múltiples
    - Retorna None si el resultado está vacío
    """
    if not texto or not texto.strip():
        return None
    texto = unicodedata.normalize("NFD", texto.strip().upper())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^A-Z0-9\s\.\,\-\/\#\&]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto if texto else None