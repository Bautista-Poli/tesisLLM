"""
test_arbol_decision.py — Tests del flujo del árbol de decisión (menú clásico).

Ejecuta el playground como proceso, le envía respuestas por stdin y verifica
la salida. No requiere Ollama ni dependencias externas.

Correr todos:  python -m unittest discover -s modelos/arbol_decision/tests -t . -v
"""

import os
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODULO = "modelos.arbol_decision.playground_arbolDeDecision"


def correr_flujo(entradas: list[str]) -> str:
    """Corre el playground con las entradas dadas y devuelve la salida completa."""
    resultado = subprocess.run(
        [sys.executable, "-m", MODULO],
        input="\n".join(entradas) + "\n",
        capture_output=True,
        text=True,
        cwd=RAIZ,
        timeout=120,
    )
    return resultado.stdout + resultado.stderr


class TestArbolDecision(unittest.TestCase):

    def test_turno_por_estudio_tomografia(self):
        # DNI → confirma datos → particular → Estudios → Tomografía
        salida = correr_flujo(["30456789", "1", "2", "2", "1"])
        self.assertIn("Tu turno fue registrado correctamente", salida)
        self.assertIn("Gracias por contactarnos", salida)

    def test_radiologia_informativa(self):
        # DNI → confirma → particular → Estudios → Más opciones → Radiología
        salida = correr_flujo(["30456789", "1", "2", "2", "8", "2"])
        self.assertIn("sin turno previo", salida)
        self.assertIn("Gracias por contactarnos", salida)

    def test_datos_no_coinciden_deriva_a_recepcion(self):
        # DNI → "No, no son mis datos"
        salida = correr_flujo(["30456789", "2"])
        self.assertIn("acercate a la recepción", salida)

    def test_dni_invalido_se_vuelve_a_pedir(self):
        # Primero un DNI inválido, después uno válido
        salida = correr_flujo(["123", "30456789", "2"])
        self.assertIn("Por favor ingresá un DNI válido", salida)
        self.assertIn("acercate a la recepción", salida)


if __name__ == "__main__":
    unittest.main()
