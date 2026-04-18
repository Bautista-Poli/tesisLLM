import pandas as pd

_LATERALIDAD = {"derecho", "derecha", "izquierdo", "izquierda", "bilateral", "ambos", "ambas"}

def normalizar_estudio(estudio_modelo: str | None, df_terminos: pd.DataFrame) -> str | None:
    if not estudio_modelo:
        return None
    todos = df_terminos["preferred_term"].tolist()
    if estudio_modelo in todos:
        return estudio_modelo
    estudio_lower = estudio_modelo.lower()
    candidatos = [
        t for t in todos
        if all(w in estudio_lower for w in t.lower().split())
    ]
    if candidatos:
        return min(candidatos, key=lambda t: len(t.split()))
    return estudio_modelo


def es_termino_paraguas(estudio: str, df_terminos: pd.DataFrame, umbral: int = 4) -> bool:
    palabras_comunes = {"radiografía", "radiografia", "simple", "de", "del", "la",
                        "el", "los", "las", "y", "con", "región", "hueso", "huesos"}

    modificadores_tecnicos = {
        "anteroposterior", "lateral", "oblicua", "oblicuo", "posteroanterior",
        "proyección", "proyecciones", "combinada", "frente", "perfil",
        "intensificador", "móvil", "bipedestación", "decúbito", "supino",
        "erecta", "carga", "flexión", "extensión", "ap", "pa",
        "contraste", "seriada", "seriado", "intravenoso"
    }

    palabras = set(estudio.lower().split()) - palabras_comunes
    if not palabras:
        return True

    todos = df_terminos["preferred_term"].tolist()
    estudio_lower = estudio.lower()

    hijos_especificos = 0
    for t in todos:
        t_lower = t.lower()
        if t_lower == estudio_lower:
            continue
        if not all(p in t_lower for p in palabras):
            continue
        extra = set(t_lower.split()) - set(estudio_lower.split()) - palabras_comunes
        if not extra:
            continue
        # ← CAMBIO: lateralidad sola tampoco cuenta como especificidad real
        if extra.issubset(modificadores_tecnicos | _LATERALIDAD):
            continue
        hijos_especificos += 1

    return hijos_especificos >= umbral
def obtener_preparacion(estudio: str, preparaciones: dict) -> dict | None:
    return preparaciones.get(estudio.strip().lower())


def estudio_requiere_turno(estudio: str, preparaciones: dict) -> bool:
    info = obtener_preparacion(estudio, preparaciones)
    return True if info is None else info["requiere_turno"]