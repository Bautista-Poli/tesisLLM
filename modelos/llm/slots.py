# ─── SISTEMA DE SLOTS ─────────────────────────────────────────────────────────

SLOTS_VACIOS = {
    "nombre_completo":  None,
    "dni":              None,
    "estudio":          None,
    "obra_social":      None,
    "sede":             None,
    "dias_disponibles": None,
    "horario":          None,
}

SLOTS_OBLIGATORIOS = ["nombre_completo", "dni", "estudio", "obra_social", "sede"]


def slots_faltantes(slots: dict) -> list:
    return [k for k in SLOTS_OBLIGATORIOS if not slots.get(k)]


def fusionar_slots(slots: dict, nuevos: dict) -> dict:
    resultado = slots.copy()
    for k, v in nuevos.items():
        if k in ("estudio_ambiguo", "pregunta_aclaracion", "tipo_ambiguedad", "_turno_chequeado"):
            continue
        if v is not None and resultado.get(k) is None:
            resultado[k] = v
    return resultado
