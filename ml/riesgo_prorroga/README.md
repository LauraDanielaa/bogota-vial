# Riesgo de atraso (modelo de prórroga)

Este modelo estima la probabilidad de que un contrato del IDU sea prorrogado, es decir, que termine con días
adicionados en SECOP II. Esa probabilidad se lleva a cada obra del mapa como su riesgo de atraso: alto, medio
o bajo. Es una estimación estadística hecha con contratos anteriores, no un dato oficial del IDU, y así se
presenta en la web.

```bash
docker compose run --rm etl                    # primero el ETL
docker compose run --rm ml riesgo_prorroga     # luego el modelo (un minuto, más o menos)
```

| Archivo | Qué hace |
|---|---|
| `entrenar.py` | Script principal: compara los modelos, calibra el elegido, explica cada predicción y guarda los resultados |
| `datos.py` | Lee los contratos y arma las variables; también define las columnas que el modelo no puede usar |
| `modelos.py` | Los cuatro modelos candidatos |
| `factores.py` | Calcula con SHAP los tres factores de cada contrato y los redacta en español |

## Con qué datos se entrena

La fuente es la vista `v_ml_contratos` de `etl/sql/06_ml.sql`: los 913 contratos de `clean_secop` (todos los
del IDU menos los de prestación de servicios), completados con algunas columnas de SECOP que `clean_secop` no
trae, como la duración pactada o si el contrato se puede prorrogar.

Un contrato cuenta como prorrogado si tiene días adicionados. Los contratos que todavía están vigentes y no se
han prorrogado no sirven para entrenar, porque aún no se sabe cómo terminan; esos solo reciben una predicción.
Con los datos actuales quedan 760 contratos para entrenar (275 prorrogados, el 36 %) y 153 vigentes.

## Variables

Solo usamos lo que se sabe el día en que se firma el contrato:

| Variable | De dónde sale |
|---|---|
| Tipo de contrato, modalidad y origen de los recursos | `clean_secop` |
| Si se puede prorrogar | `el_contrato_puede_ser_prorrogado` |
| Familia de la categoría | Los cuatro primeros dígitos del código UNSPSC |
| Valor | En escala logarítmica |
| Duración pactada | Del texto de SECOP (`24 Mes(es)` son 720 días), con una marca para cuando no viene |
| Año y mes de firma | Fecha de firma |
| Historial del contratista | Cuántos contratos tenía antes con el IDU y qué proporción de los ya terminados se prorrogó. Solo cuentan los firmados antes del contrato que se evalúa |

Hay columnas que delatan la respuesta y por eso están prohibidas: el estado del contrato ("Modificado"
aparece en casi todos los prorrogados), la fecha de fin y cualquier duración calculada con ella (ya incluye la
prórroga), la fecha de notificación de la prórroga y la última actualización. La vista no las expone y
`entrenar.py` comprueba con `assert` que ninguna haya entrado al modelo.

## Cómo se entrena

Comparamos cuatro modelos, todos con las clases balanceadas: una línea base que siempre predice la tasa general
de prórroga, regresión logística, random forest y gradient boosting. Cada uno se evalúa de dos formas:

- Validación cruzada estratificada de 5 pliegues.
- Validación temporal: se entrena con los contratos firmados hasta 2023 y se prueba con los de 2024 en adelante,
  que es lo más parecido a usarlo de verdad.

Se elige el de mayor PR-AUC en validación cruzada y se calibra con una sigmoide para que sus probabilidades
signifiquen algo. Las probabilidades de los contratos de entrenamiento salen fuera de pliegue (el modelo nunca
vio ese contrato); las de los vigentes salen del modelo entrenado con todo.

Exigimos que el modelo supere claramente a la línea base: al menos 0,10 de PR-AUC más en validación cruzada y
0,05 más en la validación temporal. Si no lo logra, se avisa en la consola, en la tabla de métricas y en la web.

Resultado actual:

| Modelo | PR-AUC (validación cruzada) | PR-AUC (2024 en adelante) |
|---|---|---|
| Línea base | 0,36 | 0,53 |
| Regresión logística | 0,71 | 0,82 |
| Random forest | 0,77 | 0,86 |
| Gradient boosting (elegido) | 0,78 | 0,85 |

Para explicar cada predicción usamos SHAP sobre el modelo sin calibrar (la calibración no cambia qué variables
empujan hacia arriba o hacia abajo) y redactamos los tres factores con más peso, por ejemplo: "El contratista
prorrogó el 67 % de sus 3 contratos anteriores".

## Del contrato a la obra

Cada obra se cruza con su contrato por `secop_id_contrato` y recibe un nivel con la función `clasificar_riesgo`.
Las reglas se aplican en este orden:

1. **No aplica**: la obra está finalizada o caducada.
2. **Sin dato**: la obra no tiene contrato en SECOP.
3. **Prorrogada**: el contrato ya tiene días adicionados. Esto es un hecho, no una estimación.
4. **Alto** desde 60 % de probabilidad, **medio** desde 30 % y **bajo** por debajo.

Con los datos actuales, de las 124 obras: 53 prorrogadas, 39 que no aplican, 19 en riesgo alto, 6 en riesgo
medio, 6 sin dato y 1 en riesgo bajo.

## Dónde quedan los resultados

| Dónde | Qué |
|---|---|
| `ml_prorroga_metricas` | Métricas de cada candidato en cada versión, y cuál se eligió |
| `ml_prorroga_contrato` | Probabilidad y factores de cada contrato |
| `ml_riesgo_obra` | Nivel, probabilidad, días adicionados y factores de cada obra |
| `ml/models/riesgo_prorroga/` | El modelo entrenado (`.joblib`) y sus métricas (`.json`), uno por versión |

Cada entrenamiento crea una versión nueva (`AAAAMMDD-HHMMSS`) y el backend usa la última
(`v_prorroga_version_activa`). El riesgo de cada obra no cambia hasta el siguiente entrenamiento, aunque se
vuelva a correr el ETL. En producción solo se entrena en el primer despliegue o cuando alguien lo pide (ver
[ml/README.md](../README.md#en-producción)).

## Limitaciones

- Predice prórrogas del contrato, no atrasos físicos de la obra. Son cosas relacionadas pero no iguales: un
  contrato puede prorrogarse por razones administrativas y una obra puede ir atrasada sin prórroga.
- Los umbrales de 30 % y 60 % son un punto de partida, no salen de un análisis de costos.
- Muchas obras comparten contrato, así que todas reciben el mismo riesgo.
- Los contratistas que llegan por primera vez al IDU no tienen historial, así que sobre ellos el modelo tiene
  menos información.
