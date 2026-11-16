# Contratos atípicos

Este modelo busca, entre los 913 contratos del IDU en SECOP II, los que se salen de lo habitual, y explica en
qué se diferencian de los contratos parecidos. En la web aparecen solo los que tienen obra en el mapa: una
etiqueta "Contrato atípico" en el listado, un anillo punteado alrededor del punto en el mapa y una fila en el
dashboard.

Que un contrato sea atípico no quiere decir que tenga algo irregular. Puede ser simplemente una obra más
grande o más compleja que las demás. Por eso la web no muestra el puntaje del modelo, no arma rankings, no
muestra datos del contratista y siempre acompaña la marca con esa aclaración.

```bash
docker compose run --rm etl
docker compose run --rm -e COMMIT_GIT=$(git rev-parse HEAD) ml atipicos
```

| Archivo | Qué hace |
|---|---|
| `ejecutar.py` | Script principal: revisa el commit, calcula, valida, imprime el resumen y guarda en la base |
| `datos.py` | Lee los contratos y arma las variables. Reutiliza `leer_contratos` del modelo de riesgo y la conexión de `comun/` |
| `modelo.py` | IsolationForest, sus parámetros y las semillas de validación |
| `motivos.py` | Compara cada contrato con su grupo y redacta los motivos |

## Datos y variables

Usa la misma vista que el modelo de riesgo, `v_ml_contratos`, y aparte toma de `clean_secop` el enlace de
cada proceso en SECOP (solo para poder revisarlos a mano). El modelo se entrena y califica con los 913
contratos, porque son la población contra la que se compara cada uno.

| Variable | Cómo se calcula |
|---|---|
| Valor | log(1 + valor del contrato) |
| Plazo pactado | En días, del texto `duraci_n_del_contrato`. No se usa la fecha de fin, porque ya incluye las prórrogas |
| Valor por día | log(1 + valor / plazo pactado) |
| Días adicionados | Días de prórroga registrados en SECOP |
| Tipo y modalidad | One-hot. Las categorías con menos de 10 contratos se agrupan, para que un contrato no quede marcado solo por tener una modalidad poco común |

A 194 contratos les falta el plazo pactado (`No definido` o el texto sin número). Para poder calificarlos se
les pone la mediana de su tipo y modalidad, pero ese plazo inventado nunca se usa como motivo ni se dibuja en
el gráfico.

## El modelo

Es un IsolationForest de scikit-learn con 500 árboles, una contaminación del 5 % (marca unos 45 de los 913) y
la semilla fija en 42. No se guarda el modelo entrenado: se vuelve a calcular en cada push, y lo que importa
(resultados, parámetros y validación) queda en la base.

## Los motivos

IsolationForest dice qué contratos están aislados, pero no por qué. El motivo se calcula aparte: cada variable
del contrato se compara con la mediana de los contratos de su mismo tipo y modalidad. Si ese grupo tiene menos
de 8 contratos, se compara con los de su mismo tipo, y si tampoco alcanza, con todos.

- En el valor, el plazo y el valor por día, una diferencia cuenta si el contrato tiene al menos el doble o la
  mitad de la mediana.
- En los días adicionados la mediana casi siempre es 0, así que la comparación lleva un colchón de 90 días y
  solo cuenta hacia arriba: hacen falta al menos 90 días adicionados para que sea un motivo. Tener menos
  prórroga que el resto no es un motivo.
- El valor por día es el cociente de los otros dos, así que solo se usa si ni el valor ni el plazo son motivo
  por sí solos.
- Se redactan las una a tres diferencias más grandes.

Algunos ejemplos reales:

- "Valor 14 veces mayor que la mediana de contratos de obra por licitación pública"
- "Plazo pactado de 43 meses, 3,3 veces lo habitual para contratos de otro tipo por contratación directa (13 meses)"
- "526 días adicionados; la mayoría de contratos de obra no tiene días adicionados"

Si el modelo aísla un contrato pero no se le encuentra ningún motivo claro, no se marca como atípico. En la
ejecución actual pasa con 9 de los 45: todos tienen valor 0 en SECOP (comodatos y similares). El bosque los
aísla por ese valor, pero frente a su grupo no hay una diferencia que se pueda explicar.

## Cómo sabemos si funciona

No hay etiquetas de "contrato atípico", así que no se puede medir un acierto. Hacemos dos cosas:

1. Repetimos el modelo con otras cinco semillas (7, 21, 123, 2024 y 31415) y medimos qué porcentaje de los
   contratos marcados sigue saliendo. Si en promedio baja del 70 %, el script lo advierte.
2. Imprimimos los diez contratos más atípicos con sus motivos y su enlace a SECOP para revisarlos a mano.

Las dos cosas quedan guardadas en la columna `validacion` de `ml_atipicos_ejecucion`.

Resultado actual:

| | |
|---|---|
| Contratos analizados | 913 |
| Aislados por IsolationForest | 45 |
| Atípicos (aislados y con al menos un motivo) | 36 |
| Atípicos con obra en el mapa | 4 contratos, que suman 11 obras |
| Estabilidad con otras semillas | 94 % en promedio (entre 89 % y 97 %); el 78 % sale con las cinco |

## Dónde quedan los resultados

| Tabla | Qué guarda |
|---|---|
| `ml_atipicos_ejecucion` | Una fila por ejecución: versión, fecha, commit de git, si fue exitosa, conteos, estabilidad, parámetros y validación. Si una ejecución falla, queda registrada con el error y sin resultados |
| `ml_atipicos_contrato` | Una fila por contrato en cada ejecución: referencia, tipo, modalidad, valor, plazo, días adicionados, si el modelo lo aisló, si quedó atípico, su puntaje y sus motivos |
| `v_atipicos_ejecucion_activa` | La última ejecución exitosa. Es lo único que lee el backend |

## Cuándo se ejecuta

En producción corre solo en cada push a `main`, desde `deploy/actualizar-modelos.sh` (ver
[ml/README.md](../README.md#en-producción)). Hay tres cosas que lo hacen seguro:

- **Una vez por commit.** El commit queda guardado en `ml_atipicos_ejecucion`. Si ya hay una ejecución exitosa
  para ese commit, por ejemplo porque alguien volvió a lanzar el workflow, no se hace nada. Un índice único y
  un candado en la base evitan duplicados aunque dos ejecuciones coincidan.
- **Una sola transacción.** La ejecución y los 913 resultados se guardan juntos o no se guarda nada. Si algo
  falla, la web sigue mostrando la ejecución anterior.
- **Sin tumbar el despliegue.** Si el modelo falla, el workflow lo muestra como advertencia, pero el sitio
  sigue en línea.

En local solo corre a mano. Sin `COMMIT_GIT` (y sin git disponible) no hay forma de saber si ya se corrió, así
que corre siempre.

## Limitaciones

- El modelo solo compara seis variables. No sabe nada del objeto del contrato ni de cómo se ejecutó, así que
  los motivos hay que leerlos con ese contexto.
- Los días adicionados pesan bastante: en 8 de los 10 contratos más atípicos aparecen entre los motivos. Esto
  se cruza con el modelo de riesgo, que estima justamente las prórrogas, y favorece a los contratos viejos,
  que han tenido más tiempo para prorrogarse.
- Algunos datos de SECOP parecen mal capturados, como consultorías con plazos pactados de 305 o 345 meses.
  Salen como atípicas y el modelo no las corrige; en parte sirve para encontrarlas.
- Muchas combinaciones de tipo y modalidad tienen pocos contratos. Para esas, la comparación se hace contra
  el tipo o contra todos, que es una referencia más gruesa.
- El 5 % de contaminación es una decisión nuestra. El modelo siempre aísla unos 45 contratos, aunque los datos
  cambien; el filtro de los motivos baja ese número, pero no lo vuelve una medida absoluta.
- La estabilidad dice que el resultado no depende del azar, no que sea correcto.
- En el gráfico del dashboard no aparecen 240 contratos: los que no tienen plazo pactado o tienen valor 0 no
  se pueden dibujar en escala logarítmica.
