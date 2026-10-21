# ─── CARGA DE CSVs Y BÚSQUEDAS TF-IDF ────────────────────────────────────────

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TOP_K = 3

# Palabras técnicas que el usuario rara vez menciona espontáneamente.
# Si un preferred_term las contiene y el usuario no las mencionó, se filtra.
_CALIFICADORES_TECNICOS = {
    "bipedestación", "anteroposterior", "lateral", "oblicua",
    "posteroanterior", "supino", "decúbito", "proyección",
    "combinada", "seriada", "fluoroscopia"
}


def cargar_terminos(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["texto_completo"] = (
        df["termino_busqueda"].fillna("") + " " +
        df["preferred_term"].fillna("") + " " +
        df["variantes_coloquiales"].fillna("")
    ).str.lower()
    return df


def cargar_coberturas(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["texto_completo"] = (
        df["nombre_oficial"].fillna("") + " " +
        df["sigla"].fillna("") + " " +
        df["variantes_coloquiales"].fillna("")
    ).str.lower()
    return df


def cargar_preparaciones(path: str) -> dict:
    try:
        df = pd.read_csv(path)
        resultado = {}
        for _, row in df.iterrows():
            key = str(row["preferred_term"]).strip().lower()
            resultado[key] = {
                "requiere_turno": str(row["requiere_turno"]).strip().lower() == "true",
                "preparacion":    str(row["preparacion"]).strip(),
                "tiempo_min":     row.get("tiempo_min", None),
            }
        return resultado
    except FileNotFoundError:
        print(f"  [AVISO: No se encontró '{path}'. Preparaciones no disponibles.]")
        return {}


def buscar_relevantes(query: str, df: pd.DataFrame, top_k: int = TOP_K) -> list:
    corpus = df["texto_completo"].tolist() + [query.lower()]
    vectorizer = TfidfVectorizer().fit(corpus)
    matriz = vectorizer.transform(corpus)
    similitudes = cosine_similarity(matriz[-1], matriz[:-1]).flatten()
    return similitudes.argsort()[-top_k:][::-1]


def buscar_terminos_relevantes(query: str, df: pd.DataFrame) -> str:
    indices = buscar_relevantes(query, df)
    query_words = set(query.lower().split())
    lineas = []
    for i in indices:
        row = df.iloc[i]
        term_words = set(row["preferred_term"].lower().split())
        # Filtrar términos con calificadores técnicos que el usuario no mencionó
        calificadores_presentes = term_words & _CALIFICADORES_TECNICOS
        if calificadores_presentes and not (calificadores_presentes & query_words):
            continue
        variantes = row["variantes_coloquiales"] if pd.notna(row["variantes_coloquiales"]) else "—"
        lineas.append(f'- preferred_term: "{row["preferred_term"]}" | variantes: {variantes}')

    # Fallback: si el filtro dejó menos de 2 resultados, mostrar los top sin filtrar
    if len(lineas) < 2:
        lineas = []
        for i in indices:
            row = df.iloc[i]
            variantes = row["variantes_coloquiales"] if pd.notna(row["variantes_coloquiales"]) else "—"
            lineas.append(f'- preferred_term: "{row["preferred_term"]}" | variantes: {variantes}')

    return "\n".join(lineas)


def buscar_coberturas_relevantes(query: str, df: pd.DataFrame) -> str:
    indices = buscar_relevantes(query, df, top_k=3)
    lineas = []
    for i in indices:
        row = df.iloc[i]
        variantes = row["variantes_coloquiales"] if pd.notna(row["variantes_coloquiales"]) else "—"
        lineas.append(f'- nombre_oficial: "{row["nombre_oficial"]}" | sigla: {row["sigla"]} | variantes: {variantes}')
    return "\n".join(lineas)