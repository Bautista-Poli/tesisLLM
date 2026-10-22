# Modelo 1 — NLU con LLM

Extrae entidades (nombre, DNI, estudio, obra social, sede) del texto libre del usuario usando un LLM local (Ollama, `qwen2.5:7b`) con RAG sobre terminología SNOMED (TF-IDF + similitud coseno).

## Contenido

| Archivo | Función |
|---|---|
| `rag.py` | Carga de CSVs y búsqueda TF-IDF |
| `prompt.py` | Construcción del system prompt y preguntas de slot filling |
| `slots.py` | Slots obligatorios y fusión de datos |
| `validators.py` | Validación de DNI |
| `estudios.py` | Normalización de estudios y preparaciones |
| `ollama_client.py` | Cliente HTTP hacia Ollama |
| `extractor.py` | `ExtractorLLM`: extracción de slots (RAG + LLM + validación). Lo usa el playground |
| `playground_llm.py` | Conversación interactiva completa |
| `borrar.py` | Script auxiliar de exploración de términos |
| `tests/` | Suite de tests NLU con métricas F1 por campo |
| `evaluacion/` | Scripts de evaluación: TOP_K de la recuperación y baseline TF-IDF |

## Requisitos

- Dependencias: `pip install -r modelos/llm/requirements.txt`
- Ollama corriendo en `localhost:11434` con `ollama pull qwen2.5:7b`

## Comandos (desde la raíz del repo)

```bash
python3 -m modelos.llm.playground_llm                  # playground conversacional
python3 -m modelos.llm.tests.test_suite                 # suite completa de tests NLU
```

Filtrar tests por grupo: `python -m modelos.llm.tests.test_estudios ambiguos` (o `test_datos`, `test_bordes`).

## Evaluación

Las salidas (CSV y gráficos) se guardan en `modelos/llm/evaluacion/resultados/`.

```bash
# TOP_K de la recuperación (requiere Ollama). No cambia el default de rag.TOP_K.
# Reporta recall@k, precisión/recall/F1 de estudio y salidas con calificadores
# no mencionados (lateralidad, "seriada", "en carga").
python3 -m modelos.llm.evaluacion.evaluar_top_k              # k = 3 y 5
python3 -m modelos.llm.evaluacion.evaluar_top_k --k 3 5 7

# Baseline TF-IDF sin LLM: coseno top-1 y margen top1-top2 por caso, y curva
# precisión vs recall al variar el umbral de aceptación.
python3 -m modelos.llm.evaluacion.baseline_tfidf
```

Un estudio se considera correcto si cumple todos los checks de `estudio` del caso de test. Los casos que esperan `null` (zonas ambiguas, fuera de dominio) cuentan como negativos.
