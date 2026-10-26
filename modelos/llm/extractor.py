"""
extractor.py — Extracción de entidades con LLM + RAG (Modelo 1).

Separada del playground para poder reutilizarla (tests, otros canales).
No guarda estado de conversación: el historial y el contexto los pasa quien llama.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from modelos.llm.estudios import normalizar_estudio
from modelos.llm.lateralidad import aplicar_a_slots
from modelos.llm.ollama_client import llamar_ollama, extraer_json
from modelos.llm.prompt import construir_system_prompt
from modelos.llm.rag import (
    cargar_terminos, cargar_coberturas, cargar_preparaciones,
    buscar_terminos_relevantes, buscar_coberturas_relevantes,
)
from modelos.llm.validators import validar_dni

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_TERMINOS    = os.path.join(RAIZ, "CSVs", "snomed_con_variantes.csv")
CSV_PREPARACION = os.path.join(RAIZ, "CSVs", "preparaciones_radiologia.csv")
CSV_COBERTURAS  = os.path.join(RAIZ, "CSVs", "coberturas_medicas.csv")

HISTORIAL_MAX = 6  # últimos 3 turnos (usuario + asistente)


@dataclass
class Extraccion:
    slots:              dict
    respuesta_raw:      str
    t_rag:              float
    t_llm:              float
    dni_descartado:     str | None = None   # DNI del LLM que no pasó la validación
    estudio_original:   str | None = None   # estudio tal como lo devolvió el LLM, si fue normalizado


class ExtractorLLM:
    """
    Extrae slots de un mensaje de usuario usando Ollama + RAG sobre los CSVs.

    regla_lateralidad: aplica la regla post-LLM de lateralidad.py (zona par sin lado
    → estudio ambiguo con tipo_ambiguedad = falta_lado). Apagada por defecto.
    """

    def __init__(self, regla_lateralidad: bool = False) -> None:
        self.regla_lateralidad = regla_lateralidad
        # Si falta el CSV de estudios, la excepción se propaga: sin terminología no hay extracción.
        self.df_terminos = cargar_terminos(CSV_TERMINOS)
        try:
            self.df_coberturas = cargar_coberturas(CSV_COBERTURAS)
        except FileNotFoundError:
            self.df_coberturas = None
        self.preparaciones = cargar_preparaciones(CSV_PREPARACION)

    def extraer(
        self,
        texto: str,
        slots_llenos: list[str],
        ultima_pregunta: str,
        historial: list[dict],
    ) -> Extraccion:
        """
        Devuelve los slots extraídos del texto.

        historial : mensajes previos {"role", "content"}. Se agregan en el lugar
                    el turno del usuario y la respuesta del modelo, solo si la
                    llamada al LLM tuvo éxito.
        Lanza excepción si Ollama falla o la respuesta no tiene JSON válido.
        """
        t0 = time.perf_counter()
        contexto_estudios = buscar_terminos_relevantes(texto, self.df_terminos)
        contexto_coberturas = (
            buscar_coberturas_relevantes(texto, self.df_coberturas)
            if self.df_coberturas is not None else "No disponible."
        )
        t_rag = time.perf_counter() - t0

        system_prompt = construir_system_prompt(
            contexto_estudios, contexto_coberturas, ultima_pregunta, slots_llenos
        )
        mensajes = [{"role": "system", "content": system_prompt}]
        mensajes += historial[-HISTORIAL_MAX:]
        mensajes.append({"role": "user", "content": texto})

        t0 = time.perf_counter()
        respuesta_raw = llamar_ollama(mensajes)
        slots = extraer_json(respuesta_raw)
        t_llm = time.perf_counter() - t0

        historial.append({"role": "user", "content": texto})
        historial.append({"role": "assistant", "content": respuesta_raw})

        dni_raw = slots.get("dni")
        dni_valido = validar_dni(dni_raw)
        dni_descartado = dni_raw if dni_raw and not dni_valido else None
        slots["dni"] = dni_valido

        estudio_original = None
        if slots.get("estudio") and not slots.get("estudio_ambiguo"):
            original = slots["estudio"]
            normalizado = normalizar_estudio(original, self.df_terminos)
            if normalizado != original:
                estudio_original = original
            slots["estudio"] = normalizado
            if self.regla_lateralidad:
                aplicar_a_slots(slots, texto)

        return Extraccion(
            slots=slots,
            respuesta_raw=respuesta_raw,
            t_rag=t_rag,
            t_llm=t_llm,
            dni_descartado=dni_descartado,
            estudio_original=estudio_original,
        )
