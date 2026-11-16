# Contratos atípicos

Señala los contratos del IDU que **se salen de lo habitual** frente a los demás contratos del IDU en SECOP II,
y explica en español en qué se diferencian. Es un modelo **no supervisado**: no hay etiquetas de "contrato
atípico", así que no se puede medir su acierto, solo su estabilidad y revisar a mano sus resultados.

> Que un contrato sea atípico **no** significa que haya una irregularidad; puede deberse al tamaño o la
> complejidad de la obra. Por eso la web nunca usa palabras como "irregular" o "sospechoso", no muestra el
> puntaje ni rankings, y no muestra datos del contratista.

```bash
docker compose run --rm etl                                              # primero el ETL
docker compose run --rm -e COMMIT_GIT=$(git rev-parse HEAD) ml atipicos  # luego el modelo
```

## Archivos

| Archivo | Qué hace |
|---|---|
| `ejecutar.py` | Script principal (`main()`): revisa el commit, calcula, valida, imprime y escribe en la base |
| `datos.py` | Lee los contratos y arma las variables (reutiliza `riesgo_prorroga.datos.leer_contratos` y `comun.db`) |
| `modelo.py` | IsolationForest, sus parámetros y las semillas de validación |
| `motivos.py` | Compara cada contrato con su grupo de referencia y redacta los motivos |

## Datos

- Fuente: la vista del modelo de riesgo, `v_ml_contratos` (`etl/sql/06_ml.sql`): los **913 contratos** de
  `clean_secop`. De `clean_secop` se toma aparte el enlace del proceso en SECOP II, solo para revisar a mano.
- Se entrena y se califica con los 913, porque son la población de referencia. En la web solo aparecen los
  que tienen obra en el mapa (`v_obras_mapa` cruzada por `secop_id_contrato`); todas las obras de un
  contrato atípico llevan la marca.

## Variables

| Variable | Origen |
|---|---|
| `log_valor` | log(1 + valor del contrato) |
| `plazo_dias` | plazo **pactado**, del texto `duraci_n_del_contrato` (`24 Mes(es)` → 720 días). No usa `fecha_fin`, que ya incluye las prórrogas |
| `log_valor_dia` | log(1 + valor / plazo pactado) |
| `dias_adicionados` | días de prórroga registrados en SECOP |
| `tipo_de_contrato`, `modalidad_de_contratacion` | one-hot; las categorías con menos de 10 contratos se agrupan, para que nadie quede marcado solo por ser de una modalidad poco común |

194 contratos no traen el plazo pactado (`No definido` o sin número): se completa con la mediana de su tipo y
modalidad para que el modelo los pueda calificar, pero ese plazo nunca se usa como motivo ni se dibuja.

## Modelo

`IsolationForest` de scikit-learn: 500 árboles, **contaminación 5 %** (marca ~45 de 913) y **semilla fija 42**.
Cada ejecución entrena con todos los contratos y no guarda el modelo: se vuelve a calcular en cada push.

## Motivos

IsolationForest no dice por qué aísla un contrato. Por eso, aparte, cada variable del contrato se compara con
la **mediana de los contratos de su mismo tipo y modalidad** (si ese grupo tiene menos de 8 contratos, con la
de su tipo; si tampoco, con la de todos):

- Valor, plazo pactado y valor por día: es un motivo claro si es al menos **el doble o la mitad** de la mediana.
- Días adicionados: como en casi todos los grupos la mediana es 0, se compara con un colchón de 90 días y solo
  hacia arriba (con mediana 0, hacen falta al menos 90 días adicionados).
- El valor por día solo es motivo si ni el valor ni el plazo lo son por sí solos (si no, repite lo mismo).
- Se redactan las **una a tres diferencias más grandes**, por ejemplo:
  - *Valor 14 veces mayor que la mediana de contratos de obra por licitación pública*
  - *Plazo pactado de 43 meses, 3,3 veces lo habitual para contratos de otro tipo por contratación directa (13 meses)*
  - *526 días adicionados; la mayoría de contratos de obra no tiene días adicionados*

**Un contrato que el modelo aísla pero que no tiene ningún motivo claro no se marca como atípico** (en la
ejecución de referencia, 9 de 45: todos con valor 0 en SECOP, como los comodatos, que el bosque aísla por su
valor pero para los que no hay una diferencia que se pueda explicar frente a su grupo).

## Validación

Como no hay etiquetas:

1. **Estabilidad**: se repite el modelo con cinco semillas distintas (7, 21, 123, 2024, 31415) y se mide qué
   porcentaje de los atípicos se mantiene. Si el promedio es menor al 70 %, se imprime una advertencia y queda
   en `validacion.advertencia`.
2. **Revisión a mano**: se imprimen los diez contratos más atípicos con sus motivos y su enlace a SECOP.

Todo queda en la columna `validacion` (JSON) de `ml_atipicos_ejecucion`.

Ejecución de referencia (commit `1c1d818`, datos de noviembre de 2026):

| | |
|---|---|
| Contratos analizados | 913 |
| Aislados por IsolationForest | 45 |
| **Atípicos** (aislados y con motivo claro) | **36** |
| Atípicos con obra en el mapa | 4 contratos → 11 obras |
| Estabilidad con otras semillas | 94 % en promedio (89 %–97 %); 78 % se mantiene en las cinco |

## Salidas

| Tabla | Qué guarda |
|---|---|
| `ml_atipicos_ejecucion` | Una fila por ejecución: versión, fecha, **commit de git**, `exitosa`, conteos, estabilidad, parámetros y validación (por semilla y los diez más atípicos). Las fallidas quedan con `exitosa = false` y el error, sin resultados |
| `ml_atipicos_contrato` | Una fila por contrato y ejecución: referencia, tipo, modalidad, valor, plazo, días adicionados, `marcado_modelo`, `es_atipico`, `puntaje` y `motivos` (JSON) |
| `v_atipicos_ejecucion_activa` | La última ejecución exitosa: la única que lee el backend |

El ETL crea las tablas si no existen y nunca las borra.

## Cuándo se ejecuta

- **Producción**: en cada push a `main`, el job de despliegue (`.github/workflows/deploy.yml`), después de
  levantar los contenedores y verificar la API, corre `deploy/calcular-atipicos.sh <commit>`: ETL y luego este
  modelo.
- **Una sola vez por push**: el commit queda en `ml_atipicos_ejecucion`. Si ya hay una ejecución exitosa para
  ese commit (p. ej. se volvió a lanzar el workflow), el script de despliegue no corre ni el ETL, y este script
  termina sin hacer nada. Un índice único y un candado de la base evitan duplicados si dos ejecuciones coinciden.
- **Una sola transacción**: la ejecución y los 913 resultados se escriben juntos. Si algo falla, no queda nada a
  medias y la web sigue mostrando la ejecución anterior; el paso del workflow falla con una advertencia
  visible, pero el despliegue no se cae.
- **Local**: solo a mano, con el comando de arriba. No corre con `docker compose up` ni en los pull requests.
  Sin `COMMIT_GIT` (y sin git disponible) la ejecución no se puede deduplicar y corre siempre.

## Limitaciones

- **Atípico no es irregular.** El modelo solo dice que un contrato es distinto de los demás en seis variables;
  no sabe nada de su objeto, su complejidad ni su ejecución. Los motivos hay que leerlos con ese contexto.
- **Los días adicionados pesan mucho.** Más de la mitad de los diez más atípicos lo son, en parte, por sus
  prórrogas. Eso se cruza con el modelo de riesgo de atraso (que estima justamente las prórrogas) y hace que
  los contratos viejos y ya prorrogados tengan más opciones de quedar marcados que los recientes.
- **Errores de captura en SECOP.** Algunos plazos pactados son poco creíbles (p. ej. consultorías de 305 o
  345 meses) y salen como atípicos. El modelo no los corrige: precisamente ayuda a encontrarlos.
- **Grupos pequeños.** Hay muchas combinaciones de tipo y modalidad con pocos contratos; para ellas la
  comparación se hace con el tipo o con todos los contratos, que es una referencia más gruesa.
- **Plazos imputados.** 194 contratos sin plazo pactado se califican con un plazo supuesto (la mediana de su
  grupo); su plazo y su valor por día nunca son motivo y no aparecen en el gráfico de dispersión.
- **Contaminación fija.** El 5 % es una decisión, no un dato: siempre habrá ~45 contratos aislados aunque los
  datos cambien. El filtro de "motivo claro" baja ese número, pero no lo vuelve una medida absoluta.
- **Sin etiquetas** no hay precisión ni recall: la estabilidad solo dice que el resultado no depende del azar,
  no que sea correcto.
- **Cada push recalcula con los datos que haya en el servidor.** Si `data/` no cambia, el resultado es el mismo
  en cada push (semilla fija); cambia la fecha de la ejecución.
