"""
test_lateralidad.py — Tests unitarios de la regla post-LLM de lateralidad.

No requieren Ollama.

Correr:  python3 -m unittest modelos.llm.tests.test_lateralidad -v
"""

import unittest

from modelos.llm.lateralidad import AMBIGUO, FALTA_LADO, aplicar_a_clase, aplicar_a_slots, falta_lado


class TestFaltaLado(unittest.TestCase):

    def test_zona_par_sin_lado_es_ambiguo(self):
        self.assertTrue(falta_lado("radiografía simple de mano", "necesito una placa de mano"))
        self.assertTrue(falta_lado("radiografía simple de hombro", "me duele el hombro, quiero una placa"))
        self.assertTrue(falta_lado("radiografía simple de cadera", "me duele la cadera"))

    def test_todas_las_zonas_pares(self):
        estudios = ["radiografía simple de hombro", "radiografía simple de pie", "radiografía simple de cadera",
                    "radiografía simple de región de rodilla", "radiografía simple de mano",
                    "radiografía simple de codo", "radiografía simple de muñeca",
                    "radiografía simple de región de tobillo", "radiografía simple de primer dedo de pie",
                    "radiografía simple de dedo de la mano"]
        for e in estudios:
            with self.subTest(estudio=e):
                self.assertTrue(falta_lado(e, "necesito una placa"))

    def test_mensaje_con_lado_no_aplica(self):
        for texto in ("rx de rodilla derecha", "la rodilla izquierda", "rallos de la rodiya isquierda",
                      "rayos de la rodilla izq", "rodilla dcha", "rayos de ambas rodillas",
                      "placa bilateral de rodilla", "las dos rodillas"):
            with self.subTest(texto=texto):
                self.assertFalse(falta_lado("radiografía simple de región de rodilla", texto))

    def test_plural_de_la_zona_no_aplica(self):
        self.assertFalse(falta_lado("radiografía simple de mano", "una radiografía de las manos"))
        self.assertFalse(falta_lado("radiografía simple de región de rodilla en carga", "Radiografía de Rodillas con Carga"))

    def test_plural_de_otra_zona_no_cuenta(self):
        self.assertTrue(falta_lado("radiografía simple de mano", "me duelen los pies y la mano"))

    def test_estudio_con_lado_no_aplica(self):
        self.assertFalse(falta_lado("radiografía simple de región de rodilla derecha", "rx de rodilla"))
        self.assertFalse(falta_lado("radiografía simple de ambas manos", "rx de mano"))
        self.assertFalse(falta_lado("radiografía simple bilateral de pies", "placa de pie"))

    def test_zona_no_par_no_aplica(self):
        for e in ("radiografía simple de tórax", "radiografía simple de columna lumbar", "radiografía de fémur",
                  "radiografía simple de pelvis", "espinograma"):
            with self.subTest(estudio=e):
                self.assertFalse(falta_lado(e, "necesito una placa"))

    def test_sin_estudio_o_ya_ambiguo_no_aplica(self):
        self.assertFalse(falta_lado(None, "placa de mano"))
        self.assertFalse(falta_lado("", "placa de mano"))
        self.assertFalse(falta_lado(AMBIGUO, "placa de mano"))
        self.assertFalse(falta_lado("null", "placa de mano"))

    def test_tildes_y_mayusculas(self):
        self.assertTrue(falta_lado("radiografía simple de muñeca", "Tengo una fractura en la MUÑECA"))
        self.assertFalse(falta_lado("radiografía simple de muñeca", "la muñeca IZQUIERDA"))

    def test_palabras_parecidas_no_son_lado_ni_zona(self):
        # "dedos" no es "dos" ni plural de lado; "de" no es "der"; "piel" no es "pie"
        self.assertTrue(falta_lado("radiografía simple de todos los dedos de mano", "rx de los dedos de la mano"))
        self.assertFalse(falta_lado("radiografía simple de pulgar", "rx de los pulgares"))
        self.assertFalse(falta_lado("radiografía simple de tejido blando de tórax", "una lesión en la piel"))


class TestAplicar(unittest.TestCase):

    def test_aplicar_a_clase(self):
        self.assertEqual(aplicar_a_clase("radiografía simple de mano", "placa de mano"), (AMBIGUO, FALTA_LADO))
        self.assertEqual(aplicar_a_clase("radiografía simple de mano derecha", "placa de mano"),
                         ("radiografía simple de mano derecha", ""))
        self.assertEqual(aplicar_a_clase("null", "placa de mano"), ("null", ""))

    def test_aplicar_a_slots_marca_ambiguo(self):
        slots = {"estudio": "radiografía simple de codo", "estudio_ambiguo": False, "dni": "30456789"}
        aplicar_a_slots(slots, "me lastimé el codo")
        self.assertIsNone(slots["estudio"])
        self.assertTrue(slots["estudio_ambiguo"])
        self.assertEqual(slots["tipo_ambiguedad"], FALTA_LADO)
        self.assertEqual(slots["dni"], "30456789")

    def test_aplicar_a_slots_sin_cambios(self):
        for slots, texto in (({"estudio": "radiografía simple de codo derecho", "estudio_ambiguo": False}, "codo"),
                             ({"estudio": "radiografía simple de codo", "estudio_ambiguo": False}, "codo izquierdo"),
                             ({"estudio": None, "estudio_ambiguo": True}, "me duele la pierna")):
            with self.subTest(texto=texto):
                antes = dict(slots)
                self.assertEqual(aplicar_a_slots(slots, texto), antes)
                self.assertNotIn("tipo_ambiguedad", slots)


if __name__ == "__main__":
    unittest.main()
