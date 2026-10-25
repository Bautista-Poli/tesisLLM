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

Las salidas (CSV, tablas y gráficos) se guardan en `modelos/llm/evaluacion/resultados/`.

### Sets etiquetados (`evaluacion/datos/`)

| Archivo | Contenido |
|---|---|
| `suite_etiquetada.csv` | Los 80 casos de la suite de tests con su `preferred_term` exacto, `AMBIGUO` o `null`. La columna `revisar` marca los casos con más de un término clínicamente válido; `check_estudio_en_suite` indica si el test original evalúa el estudio. |
| `heldout.csv` | 60 mensajes nuevos (claros, ambiguos, typos, fuera de dominio, multislot) con etiqueta exacta y `clave_laxa` para la métrica laxa. |

```bash
# Chequeo de contaminación del held-out: ninguna variante del CSV de >8 caracteres
# y ningún input repetido de la suite. Sale con código 1 si falla.
python3 -m modelos.llm.evaluacion.verificar_heldout
```

### Comparación de configuraciones

```bash
# a) TF-IDF palabras top-1   b) TF-IDF char 3-5 top-1   b2) TF-IDF char 3-5 + umbrales   (sin LLM)
# c) LLM + RAG palabras k=5  d) LLM + RAG char 3-5 k=5  e) LLM sin RAG   (requieren Ollama)
python3 -m modelos.llm.evaluacion.comparar_configuraciones
python3 -m modelos.llm.evaluacion.comparar_configuraciones --configs a b b2       # solo baselines
python3 -m modelos.llm.evaluacion.comparar_configuraciones --configs b2 --reusar  # recalcula sin volver a llamar al LLM
python3 -m modelos.llm.evaluacion.comparar_configuraciones --sets heldout --k 5
```

Reporta por configuración y set: recall@k de la recuperación, accuracy top-1 exacta, P/R/F1 macro (con `AMBIGUO` y `null` siempre incluidas como clases), F1 de `AMBIGUO` y de `null`, la métrica laxa anterior, latencia media por mensaje y la caída suite → heldout. Genera `comparacion_por_caso.csv`, `comparacion_resumen.csv` y `comparacion_resumen.md`.

b2) devuelve `null` si el coseno top-1 < `umbral_null` y `AMBIGUO` si el margen top1−top2 < `umbral_margen`; ambos umbrales se calibran solo sobre la suite (búsqueda en grilla, máxima accuracy), así que la cifra válida es la del held-out. `--reusar` toma de `comparacion_por_caso.csv` las predicciones de las configs que no se corren y recalcula todas las métricas con las etiquetas actuales.

Los defaults del sistema no cambian: `rag.TOP_K = 3` y el analizador por palabras. El analizador por n-gramas de caracteres es una opción de `rag.py` (`analizador="char"`).

### Evaluaciones anteriores (métrica laxa)

```bash
# TOP_K de la recuperación (requiere Ollama): recall@k, P/R/F1 de estudio y salidas
# con calificadores no mencionados (lateralidad, "seriada", "en carga").
python3 -m modelos.llm.evaluacion.evaluar_top_k              # k = 3 y 5
python3 -m modelos.llm.evaluacion.evaluar_top_k --k 3 5 7

# Baseline TF-IDF sin LLM: coseno top-1 y margen top1-top2 por caso, y curva
# precisión vs recall al variar el umbral de aceptación.
python3 -m modelos.llm.evaluacion.baseline_tfidf
```

En estas, un estudio es correcto si cumple todos los checks de `estudio` del caso de test; los casos que esperan `null` (zonas ambiguas, fuera de dominio) cuentan como negativos.
