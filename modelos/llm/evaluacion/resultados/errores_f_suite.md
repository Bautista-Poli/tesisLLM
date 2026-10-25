# Errores de la config f en suite

21 errores en 80 casos (accuracy 0.74). Candidatos: TF-IDF char, k=5, tras el filtro de rag.py.

| Categoría | Cantidad | Ejemplos (input → predicho / esperado) |
|---|---|---|
| (a) correcto no estaba en los candidatos | 5 | «me mandaron a sacar unos rayos de la columna lumbar frente y» → radiografía simple de columna lumbar / radiografía simple de columna lumbar, proyección combin<br>«la parte baja» → radiografía simple de vía respiratoria baja / radiografía simple de columna lumbar<br>«el derecho» → AMBIGUO / radiografía simple de hombro derecho |
| (b) estaba en los candidatos y eligió otro | 6 | «rayos de columna lumbar» → radiografía simple de columna vertebral lumbar y sacra / radiografía simple de columna lumbar<br>«necesito una placa de mano» → radiografía simple de tejido blando de mano / radiografía simple de mano<br>«Radiografía de Edad Ósea» → radiografía de codo para determinación de la edad ósea / radiografía de mano y muñeca para el estudio de edad ós |
| (c) debía ser AMBIGUO | 4 | «Serie de Huesos Largos» → escanometría de miembros inferiores / AMBIGUO<br>«me duele la pierna y necesito unos rayos» → radiografía simple de extremidad inferior / AMBIGUO<br>«me duele la cadera, quiero una placa» → radiografía simple de cadera / AMBIGUO |
| (d) marcó AMBIGUO sin serlo | 6 | «Radiografía de Articulaciones Sacroilíacas» → AMBIGUO / radiografía simple de ambas articulaciones sacroilíacas<br>«quiero sacar turno para una eco abdominal» → AMBIGUO / null<br>«necesito una resonancia de rodilla» → AMBIGUO / null |
| (e) null mal | 0 | — |
| (f) parseo | 0 | — |
