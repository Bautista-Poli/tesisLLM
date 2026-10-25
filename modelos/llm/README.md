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
| `heldout.csv` | Held-out 1: 60 mensajes nuevos (claros, ambiguos, typos, fuera de dominio, multislot) con etiqueta exacta y `clave_laxa` para la métrica laxa. Ya se usó para elegir la configuración: **no se evalúa nada más contra él**. |
| `heldout2.csv` | Held-out 2: plantilla de 35 filas (12 claros, 8 ambiguos, 5 typos, 5 multislot, 5 fuera de dominio) con solo `categoria` completa. Los mensajes y las etiquetas se escriben a mano. Es para una única evaluación final. |

En los casos `AMBIGUO`, la columna `tipo_ambiguedad` dice qué falta: `falta_lado` (zona par sin lado), `falta_segmento` (columna, espalda, brazo, pierna) o `zona_amplia` (sin zona o todo el cuerpo). No cambia la accuracy; se usa para reportar el F1 de `AMBIGUO` por tipo y, más adelante, para el diálogo.

**Regla de lateralidad.** Para las zonas pares (hombro, pie, cadera, rodilla, mano, codo, muñeca, tobillo), si el mensaje no dice el lado (derecho / izquierdo / ambos), la etiqueta es `AMBIGUO` con `falta_lado`. En el catálogo, una variante sin lado no puede apuntar a un estudio con lado. La zona en plural sin lado ("rodillas", "rayos de pies") se toma como ambos (pendiente de confirmar).

> Pendiente: el gestor de diálogo todavía hace la misma pregunta de aclaración para todo `AMBIGUO`. La pregunta según `tipo_ambiguedad` (qué lado / qué segmento / qué zona) se implementa después.

```bash
# Chequeo de contaminación: ninguna variante del catálogo de >8 caracteres, ningún input
# repetido de la suite, etiquetas en el catálogo y tipo_ambiguedad válido. Código 1 si falla.
python3 -m modelos.llm.evaluacion.verificar_heldout                    # held-out 1, catálogo v1
python3 -m modelos.llm.evaluacion.verificar_heldout --set heldout2     # held-out 2 contra v1 y v2.1, la suite,
                                                                       # el held-out 1, la plantilla y la regla de lateralidad

# Regla de lateralidad: etiquetas que la contradicen (con la propuesta de
# resultados/propuesta_lateralidad.csv) y variantes del catálogo v1 / v2.1 que la violan.
python3 -m modelos.llm.evaluacion.chequear_lateralidad
```

### Catálogos

| Versión | Archivo | Contenido |
|---|---|---|
| v1 | `CSVs/snomed_con_variantes.csv` | Original. **Es el de la configuración elegida.** |
| v2 | `CSVs/snomed_con_variantes_v2.csv` | Acciones (a) y (b) de `propuesta_variantes.csv`. No mejoró: en held-out 1, f baja de 0.70 a 0.65 e i de 0.73 a 0.68 (McNemar i vs i@v2, p≈0.45). |
| v2.1 | `CSVs/snomed_con_variantes_v2_1.csv` | Solo las acciones (a); las (b) no se eliminan. Mismos conceptId corregidos que v2, sin ".0". |

```bash
python3 -m modelos.llm.evaluacion.generar_catalogo_v2                  # v2
python3 -m modelos.llm.evaluacion.generar_catalogo_v2 --version v2.1
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

### Evaluación final sobre el held-out 2 (una sola vez)

Configuración elegida: **i) con catálogo v1**. La evaluación final compara i) con v1 contra i) con v2.1 sobre el held-out 2: accuracy estricta con IC 95% bootstrap (y el de la diferencia), F1 de `AMBIGUO` (total y por `tipo_ambiguedad`), F1 de `null` y McNemar exacto entre los dos. Antes de llamar al LLM corre `verificar_heldout --set heldout2` y no sigue si falla; si el resultado ya existe no vuelve a evaluar (`--forzar` lo pisa y queda anotado). Requiere Ollama.

```bash
python3 -m modelos.llm.evaluacion.evaluar_heldout2 --chequear   # solo prerequisitos, sin LLM
python3 -m modelos.llm.evaluacion.evaluar_heldout2              # la evaluación (genera heldout2_por_caso.csv y heldout2_resumen.md)
```

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
