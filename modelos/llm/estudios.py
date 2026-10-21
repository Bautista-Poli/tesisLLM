# estudios.py
import pandas as pd

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

def obtener_preparacion(estudio: str, preparaciones: dict) -> dict | None:
    return preparaciones.get(estudio.strip().lower())

def estudio_requiere_turno(estudio: str, preparaciones: dict) -> bool:
    info = obtener_preparacion(estudio, preparaciones)
    return True if info is None else info["requiere_turno"]