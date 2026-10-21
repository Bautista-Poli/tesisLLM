# ─── VALIDACIÓN DE DNI ────────────────────────────────────────────────────────

import re

DNI_REGEX = re.compile(r'^\d{7,8}$')

def validar_dni(valor: str | None) -> str | None:
    """
    Acepta solo DNIs de 7 u 8 dígitos exactos.
    Rechaza cualquier cosa con letras, símbolos, espacios o longitud incorrecta.
    """
    if valor is None:
        return None
    limpio = re.sub(r'[\.\s]', '', str(valor).strip())
    if DNI_REGEX.match(limpio):
        return limpio
    return None
