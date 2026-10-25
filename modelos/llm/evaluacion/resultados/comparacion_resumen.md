# Comparación de configuraciones — estudio

Casos por set: suite = 80 (23 clases), heldout = 60 (33 clases). Todas las configuraciones se evalúan sobre los mismos casos.

## Resumen

| Config | Acc. suite | Acc. held-out | F1 AMBIGUO (s / h) | F1 null (s / h) | Errores parseo (s / h) | Latencia mediana (s / h) |
|---|---|---|---|---|---|---|
| a) TF-IDF palabras top-1 | 0.21 | 0.32 | 0.00 / 0.00 | 0.00 / 0.00 | 0 / 0 | 11 ms / 11 ms |
| b) TF-IDF char 3-5 top-1 | 0.24 | 0.45 | 0.00 / 0.00 | 0.00 / 0.00 | 0 / 0 | 88 ms / 89 ms |
| b2) TF-IDF char 3-5 + umbrales | 0.69 | 0.53 | 0.50 / 0.33 | 0.86 / 0.40 | 0 / 0 | 90 ms / 91 ms |
| c) LLM + RAG palabras | 0.69 | 0.65 | 0.40 / 0.41 | 0.97 / 0.82 | 0 / 0 | 2.94 s / 3.35 s |
| d) LLM + RAG char 3-5 | 0.72 | 0.70 | 0.46 / 0.50 | 0.93 / 0.75 | 1 / 0 | 6.02 s / 3.46 s |
| e) LLM sin RAG | 0.51 | 0.22 | 0.58 / 0.75 | 0.94 / 0.53 | 0 / 1 | 1.79 s / 1.83 s |
| f) d + salida restringida | 0.72 | 0.72 | 0.48 / 0.52 | 0.94 / 0.75 | 0 / 0 | 4.04 s / 4.15 s |
| f@v2) d + salida restringida [v2] | 0.74 | 0.67 | 0.42 / 0.43 | 0.92 / 0.67 | 0 / 0 | 3.84 s / 4.07 s |
| g) f + ambigüedad genérica + few-shot | 0.75 | 0.67 | 0.29 / 0.15 | 1.00 / 0.95 | 0 / 0 | 3.92 s / 3.97 s |
| i) f + few-shot fuera de dominio | 0.79 | 0.75 | 0.42 / 0.59 | 1.00 / 1.00 | 0 / 0 | 3.92 s / 4.04 s |
| i@v2) f + few-shot fuera de dominio [v2] | 0.75 | 0.70 | 0.35 / 0.59 | 0.99 / 0.95 | 0 / 0 | 3.89 s / 4.04 s |

## Métricas por configuración

| Config | Set | recall@k recup. | Accuracy | P macro | R macro | F1 macro | F1 AMBIGUO | F1 null | F1 laxa | Latencia media | Errores |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a) TF-IDF palabras top-1 | suite | 0.52 (k=1) | 0.21 | 0.70 | 0.66 | 0.66 | 0.00 | 0.00 | 0.69 | 11 ms | 0 |
| a) TF-IDF palabras top-1 | heldout | 0.50 (k=1) | 0.32 | 0.58 | 0.52 | 0.54 | 0.00 | 0.00 | 0.53 | 11 ms | 0 |
| b) TF-IDF char 3-5 top-1 | suite | 0.61 (k=1) | 0.24 | 0.76 | 0.71 | 0.71 | 0.00 | 0.00 | 0.69 | 89 ms | 0 |
| b) TF-IDF char 3-5 top-1 | heldout | 0.70 (k=1) | 0.45 | 0.68 | 0.70 | 0.68 | 0.00 | 0.00 | 0.65 | 89 ms | 0 |
| b2) TF-IDF char 3-5 + umbrales | suite | 0.61 (k=1) | 0.69 | 0.71 | 0.72 | 0.71 | 0.50 | 0.86 | 0.70 | 91 ms | 0 |
| b2) TF-IDF char 3-5 + umbrales | heldout | 0.70 (k=1) | 0.53 | 0.59 | 0.59 | 0.59 | 0.33 | 0.40 | 0.64 | 92 ms | 0 |
| c) LLM + RAG palabras | suite | 0.64 (k=5) | 0.69 | 0.76 | 0.69 | 0.71 | 0.40 | 0.97 | 0.78 | 3.04 s | 0 |
| c) LLM + RAG palabras | heldout | 0.76 (k=5) | 0.65 | 0.77 | 0.72 | 0.73 | 0.41 | 0.82 | 0.73 | 4.01 s | 0 |
| d) LLM + RAG char 3-5 | suite | 0.85 (k=5) | 0.72 | 0.73 | 0.68 | 0.70 | 0.46 | 0.93 | 0.81 | 6.37 s | 1 |
| d) LLM + RAG char 3-5 | heldout | 0.89 (k=5) | 0.70 | 0.80 | 0.78 | 0.78 | 0.50 | 0.75 | 0.80 | 3.59 s | 0 |
| e) LLM sin RAG | suite | — | 0.51 | 0.11 | 0.11 | 0.11 | 0.58 | 0.94 | 0.40 | 1.75 s | 0 |
| e) LLM sin RAG | heldout | — | 0.22 | 0.05 | 0.03 | 0.04 | 0.75 | 0.53 | 0.30 | 1.71 s | 1 |
| f) d + salida restringida | suite | 0.85 (k=5) | 0.72 | 0.74 | 0.68 | 0.70 | 0.48 | 0.94 | 0.82 | 4.32 s | 0 |
| f) d + salida restringida | heldout | 0.89 (k=5) | 0.72 | 0.80 | 0.79 | 0.79 | 0.52 | 0.75 | 0.81 | 4.17 s | 0 |
| f@v2) d + salida restringida [v2] | suite | 0.88 (k=5) | 0.74 | 0.80 | 0.75 | 0.77 | 0.42 | 0.92 | 0.88 | 4.10 s | 0 |
| f@v2) d + salida restringida [v2] | heldout | 0.86 (k=5) | 0.67 | 0.80 | 0.77 | 0.77 | 0.43 | 0.67 | 0.80 | 4.13 s | 0 |
| g) f + ambigüedad genérica + few-shot | suite | 0.85 (k=5) | 0.75 | 0.87 | 0.76 | 0.79 | 0.29 | 1.00 | 0.82 | 4.29 s | 0 |
| g) f + ambigüedad genérica + few-shot | heldout | 0.89 (k=5) | 0.67 | 0.80 | 0.76 | 0.76 | 0.15 | 0.95 | 0.77 | 3.98 s | 0 |
| i) f + few-shot fuera de dominio | suite | 0.85 (k=5) | 0.79 | 0.84 | 0.78 | 0.80 | 0.42 | 1.00 | 0.85 | 4.34 s | 0 |
| i) f + few-shot fuera de dominio | heldout | 0.89 (k=5) | 0.75 | 0.80 | 0.79 | 0.79 | 0.59 | 1.00 | 0.80 | 4.05 s | 0 |
| i@v2) f + few-shot fuera de dominio [v2] | suite | 0.88 (k=5) | 0.75 | 0.85 | 0.76 | 0.79 | 0.35 | 0.99 | 0.84 | 4.23 s | 0 |
| i@v2) f + few-shot fuera de dominio [v2] | heldout | 0.86 (k=5) | 0.70 | 0.76 | 0.74 | 0.73 | 0.59 | 0.95 | 0.81 | 4.00 s | 0 |

## F1 de AMBIGUO por tipo_ambiguedad

AMBIGUO vs resto, sin los AMBIGUO de los otros tipos (n = casos AMBIGUO del tipo). La predicción no trae tipo: los falsos positivos de AMBIGUO cuentan en todos los tipos.

| Config | Set | F1 AMBIGUO | falta_lado | falta_segmento | zona_amplia | falta_zona |
|---|---|---|---|---|---|---|
| a) TF-IDF palabras top-1 | suite | 0.00 | 0.00 (n=5) | 0.00 (n=2) | 0.00 (n=3) | 0.00 (n=2) |
| a) TF-IDF palabras top-1 | heldout | 0.00 | 0.00 (n=3) | 0.00 (n=3) | 0.00 (n=2) | 0.00 (n=4) |
| b) TF-IDF char 3-5 top-1 | suite | 0.00 | 0.00 (n=5) | 0.00 (n=2) | 0.00 (n=3) | 0.00 (n=2) |
| b) TF-IDF char 3-5 top-1 | heldout | 0.00 | 0.00 (n=3) | 0.00 (n=3) | 0.00 (n=2) | 0.00 (n=4) |
| b2) TF-IDF char 3-5 + umbrales | suite | 0.50 | 0.44 (n=5) | 0.31 (n=2) | 0.15 (n=3) | 0.00 (n=2) |
| b2) TF-IDF char 3-5 + umbrales | heldout | 0.33 | 0.31 (n=3) | 0.17 (n=3) | 0.18 (n=2) | 0.00 (n=4) |
| c) LLM + RAG palabras | suite | 0.40 | 0.00 (n=5) | 0.29 (n=2) | 0.25 (n=3) | 0.50 (n=2) |
| c) LLM + RAG palabras | heldout | 0.41 | 0.00 (n=3) | 0.13 (n=3) | 0.14 (n=2) | 0.42 (n=4) |
| d) LLM + RAG char 3-5 | suite | 0.46 | 0.14 (n=5) | 0.33 (n=2) | 0.17 (n=3) | 0.33 (n=2) |
| d) LLM + RAG char 3-5 | heldout | 0.50 | 0.00 (n=3) | 0.36 (n=3) | 0.00 (n=2) | 0.57 (n=4) |
| e) LLM sin RAG | suite | 0.58 | 0.50 (n=5) | 0.00 (n=2) | 0.27 (n=3) | 0.29 (n=2) |
| e) LLM sin RAG | heldout | 0.75 | 0.50 (n=3) | 0.67 (n=3) | 0.00 (n=2) | 0.73 (n=4) |
| f) d + salida restringida | suite | 0.48 | 0.15 (n=5) | 0.36 (n=2) | 0.18 (n=3) | 0.36 (n=2) |
| f) d + salida restringida | heldout | 0.52 | 0.00 (n=3) | 0.40 (n=3) | 0.00 (n=2) | 0.62 (n=4) |
| f@v2) d + salida restringida [v2] | suite | 0.42 | 0.15 (n=5) | 0.36 (n=2) | 0.00 (n=3) | 0.36 (n=2) |
| f@v2) d + salida restringida [v2] | heldout | 0.43 | 0.00 (n=3) | 0.20 (n=3) | 0.00 (n=2) | 0.57 (n=4) |
| g) f + ambigüedad genérica + few-shot | suite | 0.29 | 0.00 (n=5) | 0.00 (n=2) | 0.00 (n=3) | 1.00 (n=2) |
| g) f + ambigüedad genérica + few-shot | heldout | 0.15 | 0.00 (n=3) | 0.00 (n=3) | 0.00 (n=2) | 0.40 (n=4) |
| i) f + few-shot fuera de dominio | suite | 0.42 | 0.00 (n=5) | 0.33 (n=2) | 0.29 (n=3) | 0.57 (n=2) |
| i) f + few-shot fuera de dominio | heldout | 0.59 | 0.00 (n=3) | 0.50 (n=3) | 0.00 (n=2) | 1.00 (n=4) |
| i@v2) f + few-shot fuera de dominio [v2] | suite | 0.35 | 0.00 (n=5) | 0.40 (n=2) | 0.00 (n=3) | 0.67 (n=2) |
| i@v2) f + few-shot fuera de dominio [v2] | heldout | 0.59 | 0.00 (n=3) | 0.50 (n=3) | 0.00 (n=2) | 1.00 (n=4) |

## Caída suite → heldout (heldout − suite)

| Config | Δ Accuracy | Δ F1 macro | Δ F1 laxa |
|---|---|---|---|
| a) TF-IDF palabras top-1 | +0.10 | -0.13 | -0.16 |
| b) TF-IDF char 3-5 top-1 | +0.21 | -0.03 | -0.04 |
| b2) TF-IDF char 3-5 + umbrales | -0.15 | -0.12 | -0.06 |
| c) LLM + RAG palabras | -0.04 | +0.03 | -0.05 |
| d) LLM + RAG char 3-5 | -0.03 | +0.08 | -0.01 |
| e) LLM sin RAG | -0.30 | -0.07 | -0.10 |
| f) d + salida restringida | -0.01 | +0.09 | -0.00 |
| f@v2) d + salida restringida [v2] | -0.07 | +0.00 | -0.07 |
| g) f + ambigüedad genérica + few-shot | -0.08 | -0.03 | -0.05 |
| i) f + few-shot fuera de dominio | -0.04 | -0.01 | -0.05 |
| i@v2) f + few-shot fuera de dominio [v2] | -0.05 | -0.05 | -0.03 |

## Few-shot

Los ejemplos salen de la suite, así que en la suite esos casos están vistos. Accuracy en la suite sin esos casos:

- g) f + ambigüedad genérica + few-shot — ejemplos: torax_especifico, rodilla_especifica, pierna_ambigua, fuera_dominio_resonancia → 0.75 (con ellos: 0.75)
- i) f + few-shot fuera de dominio — ejemplos: fuera_dominio_resonancia, fuera_dominio_ecografia, fuera_dominio_laboratorio → 0.78 (con ellos: 0.79)
- i@v2) f + few-shot fuera de dominio [v2] — ejemplos: fuera_dominio_resonancia, fuera_dominio_ecografia, fuera_dominio_laboratorio → 0.74 (con ellos: 0.75)

## Calibración de b2 (solo sobre la suite)

- umbral_null = 0.2297 (coseno top-1 por debajo → null)
- umbral_margen = 0.0186 (margen top1−top2 por debajo → AMBIGUO)
- Orden: primero null, después AMBIGUO, si no top-1.
- Grilla: puntos medios entre los valores observados en la suite (80 casos), más 0 y un valor sobre el máximo. Criterio: máxima accuracy estricta; desempate por F1 macro y por umbrales más chicos.
- Accuracy en la suite con estos umbrales: 0.70 (dentro de la muestra de calibración: es optimista). La cifra válida es la del held-out.
- **Accuracy estricta en held-out: 0.53**

## Recuperación TF-IDF (solo casos que esperan un término exacto)

| Catálogo | Analizador | Set | recall@1 | recall@5 crudo | recall@5 contexto LLM |
|---|---|---|---|---|---|
| v1 | palabras | suite | 0.52 | 0.64 | 0.61 |
| v1 | char | suite | 0.58 | 0.85 | 0.82 |
| v1 | palabras | heldout | 0.50 | 0.79 | 0.76 |
| v1 | char | heldout | 0.71 | 0.92 | 0.89 |
| v2 | palabras | suite | 0.52 | 0.79 | 0.76 |
| v2 | char | suite | 0.58 | 0.88 | 0.85 |
| v2 | palabras | heldout | 0.47 | 0.82 | 0.79 |
| v2 | char | heldout | 0.74 | 0.89 | 0.87 |
| v2.1 | palabras | suite | 0.52 | 0.79 | 0.76 |
| v2.1 | char | suite | 0.58 | 0.85 | 0.82 |
| v2.1 | palabras | heldout | 0.47 | 0.82 | 0.79 |
| v2.1 | char | heldout | 0.76 | 0.92 | 0.89 |

## Definiciones

- **Accuracy**: predicción == preferred_term esperado (texto exacto). AMBIGUO y null son clases.
- **P/R/F1 macro**: promedio sobre las clases del gold más AMBIGUO y null, que se incluyen siempre aunque no se predigan (una clase sin aciertos aporta 0). Cada clase pesa igual, sin importar cuántos casos tenga.
- **F1 laxa**: métrica anterior (checks de los tests en la suite; `clave_laxa` en el heldout).
- **recall@k recup.**: el término esperado está entre los candidatos (k=1 para TF-IDF top-1; k=5 sobre el contexto que recibe el LLM, después del filtro de calificadores de rag.py).
- **Errores de parseo**: la salida del LLM no se pudo leer como JSON; el caso cuenta como null.
- Clase predicha por el LLM: AMBIGUO si `estudio_ambiguo` es true o `estudio` es "AMBIGUO"; si no, el estudio o null.
- Los baselines a) y b) siempre devuelven un término: nunca predicen AMBIGUO ni null.
- **Latencia**: tiempo por mensaje (recuperación + LLM cuando corresponde).
