# Errores de la config g en suite

17 errores en 80 casos (accuracy 0.79). Candidatos: TF-IDF char, k=5, tras el filtro de rag.py.

| Categoría | Cantidad | Ejemplos (input → predicho / esperado) |
|---|---|---|
| (a) correcto no estaba en los candidatos | 5 | «me mandaron a sacar unos rayos de la columna lumbar frente y» → radiografía de columna lumbar y pelvis / radiografía simple de columna lumbar, proyección combin<br>«la parte baja» → radiografía simple de vía respiratoria baja / radiografía simple de columna lumbar<br>«el derecho» → radiografía simple de húmero derecho / radiografía simple de hombro derecho |
| (b) estaba en los candidatos y eligió otro | 4 | «Radiografía de Columna Lumbar» → radiografía de columna lumbar y pelvis / radiografía simple de columna lumbar<br>«el cuello» → radiografía simple de cuello / radiografía simple de columna vertebral cervical<br>«Soy Bautista Alvarez, DNI 40123456, necesito placa de tórax,» → radiografía simple de tórax, vista posteroanterior / radiografía simple de tórax |
| (c) debía ser AMBIGUO | 8 | «Serie de Huesos Largos» → escanometría de miembros inferiores / AMBIGUO<br>«quiero sacar rayos x de espalda» → radiografía simple de columna vertebral completa / AMBIGUO<br>«me duele la pierna y necesito unos rayos» → radiografía simple de extremidad inferior / AMBIGUO |
| (d) marcó AMBIGUO sin serlo | 0 | — |
| (e) null mal | 0 | — |
| (f) parseo | 0 | — |
