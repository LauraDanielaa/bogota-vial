# Riesgo de prórroga (riesgo de atraso)

Estima la probabilidad de que un contrato del IDU sea **prorrogado**, es decir, que tenga días adicionados en
SECOP II, y la lleva a cada obra del visor como un **riesgo de atraso**. Es una estimación estadística, no un dato
oficial del IDU.

```bash
docker compose run --rm etl                    # primero el ETL
docker compose run --rm ml riesgo_prorroga     # luego el modelo
```

## Datos

- Fuente: vista `v_ml_contratos` (`etl/sql/06_ml.sql`): los 913 contratos de `clean_secop` (sin prestación de
  servicios) unidos por `id_contrato` con columnas de `stg_secop_contratos` que `clean_secop` no trae
  (duración, si se puede prorrogar, categoría y código del proveedor).
- Etiqueta: `prorrogado = 1` si `dias_adicionados > 0`.
- **Vigentes** (sin días adicionados, ni terminados ni cerrados, y con fecha de fin posterior a la descarga):
  todavía podrían prorrogarse, así que **no se usan para entrenar**; solo reciben predicción.

## Variables

Solo información conocida al firmar el contrato:

| Variable | Origen |
|---|---|
| `tipo_de_contrato`, `modalidad_de_contratacion`, `origen_de_los_recursos` | clean_secop |
| `puede_prorrogarse` | `el_contrato_puede_ser_prorrogado` |
| `familia_categoria` | 4 primeros dígitos UNSPSC de `codigo_de_categoria_principal` |
| `log_valor` | log(1 + valor del contrato) |
| `duracion_dias`, `duracion_sin_dato` | texto de `duraci_n_del_contrato` (`24 Mes(es)` → 720 días) |
| `anio_firma`, `mes_firma` | fecha de firma |
| `contratos_previos`, `tasa_prorroga_previa`, `sin_historial` | historial del contratista: solo contratos firmados **antes** del que se evalúa |

**Prohibidas** (filtran la respuesta): `estado_contrato` ("Modificado" aparece en casi todos los prorrogados),
`fecha_fin` y cualquier duración calculada con ella (ya incluye la prórroga), la fecha de notificación de prórroga
y `ultima_actualizacion`. La vista no las expone y `entrenar.py` verifica con `assert` que ninguna entra al modelo.

## Entrenamiento

- Candidatos, todos con clases balanceadas: línea base (prevalencia), regresión logística, random forest y
  gradient boosting.
- Validación cruzada estratificada de 5 pliegues y validación temporal (entrena hasta 2023, prueba 2024+).
- Se elige el de mayor PR-AUC y se calibra (sigmoide). Las probabilidades de los contratos de entrenamiento son
  **fuera de pliegue**; las de los vigentes salen del modelo calibrado entrenado con todo.
- "Supera claramente a la línea base" = PR-AUC al menos 0,10 por encima en validación cruzada y 0,05 en la
  validación temporal. Si no, se avisa en consola, en `ml_prorroga_metricas.nota` y en la web.
- SHAP: los 3 factores con más peso de cada contrato, redactados en español
  (p. ej. "El contratista prorrogó el 67 % de sus 3 contratos anteriores").

## Riesgo por obra

Cada obra se cruza con su contrato por `secop_id_contrato` y recibe un nivel (función `clasificar_riesgo`), en orden:

1. **No aplica**: obra finalizada o caducada.
2. **Sin dato**: sin contrato en SECOP.
3. **Prorrogada**: su contrato ya tiene días adicionados (se guardan cuántos).
4. **Alto** (≥ 60 %), **Medio** (≥ 30 %) o **Bajo** según la probabilidad.

## Salidas

| Dónde | Qué |
|---|---|
| `ml/models/riesgo_prorroga/riesgo_prorroga_<versión>.joblib` | modelo calibrado + modelo explicado |
| `ml/models/riesgo_prorroga/riesgo_prorroga_<versión>.json` | métricas y variables |
| `ml_prorroga_metricas` | métricas de cada candidato por versión |
| `ml_prorroga_contrato` | probabilidad y factores de cada contrato |
| `ml_riesgo_obra` | nivel, probabilidad, días adicionados y factores de cada obra |

Cada corrida es una versión nueva (`AAAAMMDD-HHMMSS`); el backend usa la última (`v_prorroga_version_activa`).
El ETL no borra estas tablas. El riesgo por obra queda fijo hasta el siguiente entrenamiento.
