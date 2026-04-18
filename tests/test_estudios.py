"""
test_estudios.py — Tests de extracción de estudios radiológicos.
Incluye: estudios específicos, estudios ambiguos y respuestas a aclaraciones.

Correr todos:  python -m tests.test_estudios
Correr grupo:  python -m tests.test_estudios ambiguos
Correr test:   python -m tests.test_estudios pierna_ambigua
"""

import sys
from tests._runner import correr_tests

TESTS = [

    # ── ESTUDIOS ESPECÍFICOS ──────────────────────────────────────────────────
    {
        "id": "torax_especifico", "grupo": "estudios",
        "descripcion": "Estudio específico claro → no debe marcar ambiguo",
        "input": "quiero sacar una placa de tórax",
        "checks": [
            ("estudio_ambiguo", False,  "debe ser False"),
            ("estudio", lambda v: v and "tórax" in v.lower(), "debe contener tórax"),
            ("estudio", lambda v: v and "seriada" not in v.lower(), "no debe ser seriada"),
        ]
    },
    {
        "id": "rodilla_especifica", "grupo": "estudios",
        "descripcion": "Rodilla derecha mencionada → no ambiguo, no agregar 'carga'",
        "input": "necesito rx de rodilla derecha",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "rodilla" in v.lower(), "debe contener rodilla"),
            ("estudio", lambda v: v and "carga" not in v.lower(), "no debe agregar 'en carga'"),
        ]
    },
    {
        "id": "columna_lumbar_especifica", "grupo": "estudios",
        "descripcion": "Columna lumbar específica → no ambiguo",
        "input": "rayos de columna lumbar",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("lumbar" in v.lower() or "sacra" in v.lower()),
             "debe resolver a lumbar o sacra")
        ]
    },
    {
        "id": "mano_especifica", "grupo": "estudios",
        "descripcion": "Mano sin lateralidad → no debe agregar 'derecha' ni 'izquierda'",
        "input": "necesito una placa de mano",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "mano" in v.lower(), "debe contener mano"),
            ("estudio", lambda v: v and "derecha" not in v.lower() and "izquierda" not in v.lower(),
             "no debe agregar lateralidad no mencionada"),
        ]
    },
    {
        "id": "torax_sin_turno", "grupo": "estudios",
        "descripcion": "Tórax no requiere turno según preparaciones",
        "input": "quiero una placa de tórax",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "tórax" in v.lower(), "debe contener tórax"),
        ]
    },
    {
        "id": "columna_cervical_especifica", "grupo": "estudios",
        "descripcion": "Columna cervical específica → no ambiguo",
        "input": "necesito rayos de la columna cervical",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "cervical" in v.lower(), "debe contener cervical"),
        ]
    },
    {
        "id": "codo_especifico", "grupo": "estudios",
        "descripcion": "Codo con lateralidad explícita → específico, no ambiguo",
        "input": "me lastimé el codo derecho, necesito una placa",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "codo" in v.lower(), "debe contener codo"),
        ]
    },
    {
        "id": "muneca_especifica", "grupo": "estudios",
        "descripcion": "Muñeca con lateralidad explícita → específica, no ambigua",
        "input": "tengo una fractura en la muñeca izquierda",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "muñeca" in v.lower(), "debe contener muñeca"),
        ]
    },
    {
        "id": "tobillo_especifico", "grupo": "estudios",
        "descripcion": "Tobillo con lateralidad explícita → específico, no ambiguo",
        "input": "me torcí el tobillo derecho",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "tobillo" in v.lower(), "debe contener tobillo"),
        ]
    },
    {
        "id": "columna_lumbar_con_contexto", "grupo": "estudios",
        "descripcion": "Columna lumbar con contexto médico → específica",
        "input": "me mandaron a sacar unos rayos de la columna lumbar frente y perfil",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "lumbar" in v.lower(), "debe contener lumbar"),
        ]
    },
    # ── NUEVOS TESTS DE LOS CASOS DEL PLAYGROUND ─────────────────────────────
    {
        "id": "edad_osea_infiere_mano",
        "grupo": "estudios",
        "descripcion": "Edad ósea → debe inferir mano/muñeca sin que se diga explícitamente",
        "input": "Radiografía de Edad Ósea",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("mano" in v.lower() or "muñeca" in v.lower() or "edad ósea" in v.lower()),
             "debe resolver a mano/muñeca o edad ósea"),
        ]
    },
    {
        "id": "espinograma_reconocido",
        "grupo": "estudios",
        "descripcion": "Espinograma reconocido por nombre técnico",
        "input": "Espinograma",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "espinograma" in v.lower(), "debe resolver a espinograma"),
        ]
    },
    {
        "id": "ortopantomografia_no_ambigua",
        "grupo": "estudios",
        "descripcion": "Ortopantomografía es estudio específico → no debe marcar ambiguo",
        "input": "ortopantomografía",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("panorám" in v.lower() or "ortopantomograf" in v.lower() or "dentadura" in v.lower()),
             "debe resolver a radiografía panorámica o similar"),
        ]
    },
    {
        "id": "rodilla_con_carga_explícita",
        "grupo": "estudios",
        "descripcion": "Rodillas con carga mencionada explícitamente → debe incluir 'carga'",
        "input": "Radiografía de Rodillas con Carga",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "rodilla" in v.lower(), "debe contener rodilla"),
            ("estudio", lambda v: v and "carga" in v.lower(), "debe incluir 'en carga' ya que el usuario lo mencionó"),
        ]
    },
    {
        "id": "sacroiliacas_bilateral",
        "grupo": "estudios",
        "descripcion": "Articulaciones sacroilíacas sin lateralidad → bilateral",
        "input": "Radiografía de Articulaciones Sacroilíacas",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "sacroilí" in v.lower(), "debe contener sacroilíacas"),
        ]
    },
    {
        "id": "columna_lumbar_nombre_medico",
        "grupo": "estudios",
        "descripcion": "Nombre médico formal de columna lumbar → no ambiguo",
        "input": "Radiografía de Columna Lumbar",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "lumbar" in v.lower(), "debe contener lumbar"),
        ]
    },
    {
        "id": "serie_huesos_largos_ambigua",
        "grupo": "ambiguos",
        "descripcion": "Serie de Huesos Largos → ambiguo o debe resolverse a escanometría",
        "input": "Serie de Huesos Largos",
        "checks": [
            ("estudio", lambda v: v is None or "escanometr" in (v or "").lower() or "longitud" in (v or "").lower(),
             "debe ser null (ambiguo) o resolverse a escanometría/medición de longitud"),
        ]
    },
    {
        "id": "cavum_rinofaringeo_no_pide_lateralidad",
        "grupo": "ambiguos",
        "descripcion": "Cavum rinofaríngeo no tiene lateralidad → no debe preguntar derecho/izquierdo",
        "input": "Radiografía de Cavum Rinofaríngeo",
        "checks": [
            ("estudio", lambda v: v and ("nasofaringe" in v.lower() or "cavum" in v.lower() or "rinofaringe" in v.lower()),
             "debe resolver a nasofaringe o similar"),
            ("pregunta_aclaracion", lambda v: v is None or ("derecho" not in (v or "").lower() and "izquierdo" not in (v or "").lower()),
             "no debe preguntar lateralidad — el cavum no tiene derecho/izquierdo"),
        ]
    },

    # ── ESTUDIOS AMBIGUOS ─────────────────────────────────────────────────────
    {
        "id": "espalda_ambigua", "grupo": "ambiguos",
        "descripcion": "Espalda sin especificar → debe marcar ambiguo",
        "input": "quiero sacar rayos x de espalda",
        "checks": [
            ("estudio_ambiguo", True,  "debe ser True"),
            ("estudio",         None,  "estudio debe ser null"),
            ("pregunta_aclaracion", lambda v: v and len(v) > 10, "debe generar pregunta"),
        ]
    },
    {
        "id": "pierna_ambigua", "grupo": "ambiguos",
        "descripcion": "Pierna sin especificar → debe marcar ambiguo",
        "input": "me duele la pierna y necesito unos rayos",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },
    {
        "id": "rayos_solos", "grupo": "ambiguos",
        "descripcion": "Rayos sin ninguna zona → debe marcar ambiguo",
        "input": "necesito hacerme unos rayos",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },
    {
        "id": "brazo_ambiguo", "grupo": "ambiguos",
        "descripcion": "Brazo sin especificar → debe marcar ambiguo",
        "input": "placa del brazo",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },
    {
        "id": "pie_ambiguo", "grupo": "ambiguos",
        "descripcion": "Pie sin especificar → debe marcar ambiguo",
        "input": "necesito rayos del pie",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },
    {
        "id": "cadera_ambigua", "grupo": "ambiguos",
        "descripcion": "Cadera sin especificar → debe marcar ambiguo",
        "input": "me duele la cadera, quiero una placa",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },
    {
        "id": "columna_sola_ambigua", "grupo": "ambiguos",
        "descripcion": "Columna sin zona → debe marcar ambiguo",
        "input": "necesito rayos de columna",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },
    {
        "id": "hombro_sin_lateralidad", "grupo": "ambiguos",
        "descripcion": "Hombro sin lateralidad → debe marcar ambiguo por falta de lado",
        "input": "me duele el hombro, quiero una placa",
        "checks": [
            ("estudio_ambiguo", True, "hombro sin lateralidad debe ser ambiguo"),
            ("estudio",         None, "estudio debe ser null hasta confirmar lateralidad"),
        ]
    },
    {
        "id": "rx_corta_sin_zona", "grupo": "ambiguos",
        "descripcion": "Mensaje muy corto 'rx' → debe marcar ambiguo",
        "input": "rx",
        "checks": [
            ("estudio_ambiguo", True, "debe ser True"),
            ("estudio",         None, "estudio debe ser null"),
        ]
    },

    # ── RESPUESTAS A ACLARACIONES ─────────────────────────────────────────────
    {
        "id": "aclaracion_lumbar", "grupo": "aclaraciones",
        "descripcion": "Respuesta 'lumbar' a pregunta de espalda → resolver estudio",
        "input": "la parte baja",
        "ultima_pregunta": "¿La radiografía es de la zona cervical (cuello), dorsal (parte media) o lumbar (parte baja)?",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("lumbar" in v.lower() or "sacra" in v.lower()),
             "debe resolver a lumbar o sacra"),
        ]
    },
    {
        "id": "aclaracion_tibia", "grupo": "aclaraciones",
        "descripcion": "Respuesta 'tibia' a pregunta de pierna → resolver estudio",
        "input": "es la tibia",
        "ultima_pregunta": "¿Es la pierna en sí (tibia/peroné), el muslo (fémur) o la rodilla?",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("tibia" in v.lower() or "peroné" in v.lower()),
             "debe resolver a tibia/peroné"),
        ]
    },
    {
        "id": "aclaracion_antebrazo", "grupo": "aclaraciones",
        "descripcion": "Respuesta 'antebrazo' a pregunta de brazo → resolver estudio",
        "input": "el antebrazo",
        "ultima_pregunta": "¿Es el brazo (húmero) o el antebrazo (radio y cúbito)?",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and (
                "radio" in v.lower() or "cúbito" in v.lower() or "antebrazo" in v.lower()
            ), "debe resolver a radio/cúbito"),
        ]
    },
    {
        "id": "aclaracion_cervical", "grupo": "aclaraciones",
        "descripcion": "Respuesta 'cuello' a pregunta de columna → resolver a cervical",
        "input": "el cuello",
        "ultima_pregunta": "¿Qué parte de la columna? ¿Lumbar (baja), dorsal (media) o cervical (cuello)?",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("cervical" in v.lower() or "cuello" in v.lower()),
             "debe resolver a cervical o cuello"),
        ]
    },
    {
        "id": "aclaracion_hombro_derecho", "grupo": "aclaraciones",
        "descripcion": "Respuesta 'el derecho' a pregunta de hombro → resolver con lateralidad",
        "input": "el derecho",
        "ultima_pregunta": "¿Es el hombro derecho o izquierdo?",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "derecho" in v.lower(),
            "debe incluir lateralidad derecha"),
        ]
    },
    {
        "id": "aclaracion_cadera_izquierda", "grupo": "aclaraciones",
        "descripcion": "Respuesta 'la izquierda' a pregunta de cadera → resolver con lateralidad",
        "input": "la cadera izquierda",  # ← cambiar input para dar más contexto
        "ultima_pregunta": "¿Es la cadera derecha o la izquierda?",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "izquierda" in v.lower(),
            "debe incluir lateralidad izquierda"),
        ]
    },
]

if __name__ == "__main__":
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    correr_tests(TESTS, "ESTUDIOS", filtro)
