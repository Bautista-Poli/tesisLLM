# ─── CLIENTE OLLAMA ───────────────────────────────────────────────────────────

import json
import re
import requests

OLLAMA_URL      = "http://localhost:11434/api/chat"
MODEL           = "qwen2.5:7b"



def llamar_ollama(messages: list, formato: dict | None = None) -> str:
    """formato: JSON schema opcional para restringir la salida (parámetro `format` de Ollama)."""
    system = [m for m in messages if m["role"] == "system"]
    historia = [m for m in messages if m["role"] != "system"]
    historia_recortada = historia[-6:]  # solo últimos 3 turnos
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.0, "top_p": 1.0}
    }
    if formato is not None:
        payload["format"] = formato
    resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def extraer_json(texto: str) -> dict:
    texto = texto.strip()
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No se encontró JSON válido en: {texto}")
