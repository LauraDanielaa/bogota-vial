"""Modelos candidatos del riesgo de prórroga. Todos con clases balanceadas."""

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from riesgo_prorroga.datos import CATEGORICAS, NUMERICAS

SEMILLA = 42


class GradienteBalanceado(GradientBoostingClassifier):
    """GradientBoostingClassifier que balancea las clases por sí solo.

    GradientBoostingClassifier no tiene class_weight; aquí cada fit usa pesos
    'balanced'. Así funciona igual dentro de la validación cruzada y de la calibración
    (que no recibe los pesos y por eso devuelve probabilidades en la escala real).
    """

    def fit(self, X, y, sample_weight=None, monitor=None):
        if sample_weight is None:
            sample_weight = compute_sample_weight("balanced", y)
        return super().fit(X, y, sample_weight=sample_weight, monitor=monitor)


def preprocesador() -> ColumnTransformer:
    categoricas = Pipeline([
        ("imputar", SimpleImputer(strategy="constant", fill_value="Sin dato")),
        # Las categorías con menos de 10 contratos se agrupan en una sola
        ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=10, sparse_output=False)),
    ])
    numericas = Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("escalar", StandardScaler()),
    ])
    return ColumnTransformer(
        [("cat", categoricas, CATEGORICAS), ("num", numericas, NUMERICAS)],
        verbose_feature_names_out=False,
    )


def candidatos() -> dict:
    """nombre -> Pipeline sin entrenar."""
    estimadores = {
        "linea_base": DummyClassifier(strategy="prior"),
        "regresion_logistica": LogisticRegression(class_weight="balanced", C=0.5, max_iter=5000),
        "random_forest": RandomForestClassifier(
            n_estimators=500, min_samples_leaf=3, max_features="sqrt",
            class_weight="balanced", random_state=SEMILLA, n_jobs=-1,
        ),
        "gradient_boosting": GradienteBalanceado(
            n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, random_state=SEMILLA,
        ),
    }
    return {n: Pipeline([("prep", preprocesador()), ("modelo", e)]) for n, e in estimadores.items()}


NOMBRE_MODELO = {
    "linea_base": "Línea base (prevalencia)",
    "regresion_logistica": "Regresión logística",
    "random_forest": "Random forest",
    "gradient_boosting": "Gradient boosting",
}
