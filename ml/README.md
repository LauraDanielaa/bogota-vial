# ml

Modelos de machine learning de Bogotá Vial (p. ej. probabilidad de retraso de una obra).

```
ml/
├── notebooks/   exploración y prototipos (Jupyter)
├── src/         código de entrenamiento y features, reutilizable
└── models/      modelos entrenados (no se suben a git)
```

Los datos de entrada salen de PostGIS (tabla `obras_integradas` y vistas `v_*`).
Cuando un modelo esté listo, el backend lo puede cargar y exponer en un endpoint
(por ejemplo `GET /api/obras/{id}/riesgo`).
