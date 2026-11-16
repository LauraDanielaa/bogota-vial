"""
Modelo de contratos atípicos: IsolationForest sobre los 913 contratos de clean_secop.

Pasos:
    1. Si ya hay una ejecución exitosa para el commit de git actual, termina sin hacer nada
       (así corre una sola vez por push, aunque se vuelva a lanzar el workflow).
    2. Lee v_ml_contratos (la misma vista del modelo de riesgo) y arma las variables:
       valor (log), plazo pactado, valor por día de plazo, días adicionados, tipo y modalidad.
    3. Entrena IsolationForest (contaminación 5 %, semilla fija) con todos los contratos.
    4. Calcula los motivos comparando con la mediana de su tipo y modalidad. Un contrato que
       el modelo aísla pero que no tiene ningún motivo claro NO se marca como atípico.
    5. Validación (no hay etiquetas): repite con cinco semillas y mide qué porcentaje de los
       atípicos se mantiene; imprime los diez más atípicos con sus motivos y su enlace a SECOP.
    6. Escribe todo en una sola transacción: ml_atipicos_ejecucion y ml_atipicos_contrato.
       Si algo falla, no queda nada a medias y la web sigue mostrando la ejecución anterior.

No guarda el modelo entrenado: se vuelve a calcular en cada push y los resultados y las
métricas quedan en la base.

Commit: variable COMMIT_GIT (la pone el workflow de despliegue); si no está, se intenta
leer con git. Sin commit, la ejecución no se puede deduplicar y siempre corre.

Uso:  python ml/run_ml.py atipicos   |   docker compose run --rm -e COMMIT_GIT=$(git rev-parse HEAD) ml atipicos
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from psycopg2.errors import UniqueViolation
from psycopg2.extras import Json, execute_values

from atipicos import motivos as mot
from atipicos.datos import VISTA, leer, preparar
from atipicos.modelo import PARAMETROS, SEMILLA, SEMILLAS_VALIDACION, ajustar
from comun.db import conectar, existe_relacion, leer_sql

UMBRAL_ESTABILIDAD = 0.70
CANDADO = 862_421   # pg_advisory_xact_lock: dos ejecuciones nunca escriben a la vez
TABLAS = ("ml_atipicos_ejecucion", "ml_atipicos_contrato")


def commit_actual() -> str | None:
    c = os.environ.get("COMMIT_GIT", "").strip()
    if c:
        return c
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
                           capture_output=True, text=True, timeout=10, check=True)
        return r.stdout.strip() or None
    except Exception:
        return None


def ejecucion_del_commit(cur, commit: str):
    cur.execute(
        "SELECT version, ejecutado_en FROM ml_atipicos_ejecucion "
        "WHERE commit_git = %s AND exitosa ORDER BY ejecutado_en DESC LIMIT 1",
        (commit,),
    )
    return cur.fetchone()


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------
def calcular(conn) -> dict:
    df = preparar(leer(conn)).reset_index(drop=True)
    # Contratos con obra en el mapa (mismo cruce que el backend: v_obras_mapa + secop_id_contrato)
    con_obra = set(leer_sql(conn, "SELECT DISTINCT s.secop_id_contrato FROM v_obras_mapa m "
                                  "JOIN v_obras_seguimiento s USING (objectid) "
                                  "WHERE s.secop_id_contrato IS NOT NULL")["secop_id_contrato"])
    df["con_obra"] = df["id_contrato"].isin(con_obra)
    print(f"  Contratos: {len(df)} (plazo pactado sin dato, completado con la mediana de su grupo: "
          f"{int(df['plazo_imputado'].sum())}) · con obra en el mapa: {int(df['con_obra'].sum())}")

    marcado, puntaje = ajustar(df, SEMILLA)
    motivos = mot.calcular(df)
    tiene_motivo = np.array([len(m) > 0 for m in motivos])
    atipico = marcado & tiene_motivo
    df["marcado_modelo"], df["puntaje"], df["es_atipico"] = marcado, puntaje, atipico
    df["motivos"] = [m if a else [] for m, a in zip(motivos, atipico)]
    print(f"  IsolationForest aísla {int(marcado.sum())} contratos; "
          f"{int((marcado & ~tiene_motivo).sum())} sin un motivo claro no se marcan. "
          f"Atípicos: {int(atipico.sum())}")

    # ---------------- estabilidad con otras semillas ----------------
    base = set(df.loc[atipico, "id_contrato"])
    por_semilla, en_todas = [], set(base)
    for s in SEMILLAS_VALIDACION:
        m_s, _ = ajustar(df, s)
        otro = set(df.loc[m_s & tiene_motivo, "id_contrato"])
        en_todas &= otro
        por_semilla.append({"semilla": s, "n_atipicos": len(otro),
                            "se_mantienen": round(len(base & otro) / len(base), 4) if base else None})
    estabilidad = (round(float(np.mean([p["se_mantienen"] for p in por_semilla])), 4) if base else None)
    estable_todas = round(len(en_todas) / len(base), 4) if base else None

    top = df[df["es_atipico"]].sort_values("puntaje", ascending=False).head(10)
    top10 = [
        {"id_contrato": f["id_contrato"], "referencia": f["contrato"], "tipo": f["tipo_de_contrato"],
         "modalidad": f["modalidad_de_contratacion"], "con_obra": bool(f["con_obra"]),
         "motivos": [m["texto"] for m in f["motivos"]], "secop_url": f["secop_url"]}
        for _, f in top.iterrows()
    ]
    advertencia = None
    if estabilidad is not None and estabilidad < UMBRAL_ESTABILIDAD:
        advertencia = (f"ATENCIÓN: solo se mantiene en promedio el {100 * estabilidad:.0f} % de los atípicos al "
                       f"cambiar la semilla (umbral {100 * UMBRAL_ESTABILIDAD:.0f} %). Los resultados son poco estables.")
    return {
        "df": df,
        "n_marcados_modelo": int(marcado.sum()),
        "n_atipicos": int(atipico.sum()),
        "n_atipicos_con_obra": int((atipico & df["con_obra"]).to_numpy().sum()),
        "estabilidad": estabilidad,
        "validacion": {
            "semilla_base": SEMILLA,
            "por_semilla": por_semilla,
            "estabilidad_promedio": estabilidad,
            "se_mantienen_en_todas": estable_todas,
            "umbral_estabilidad": UMBRAL_ESTABILIDAD,
            "advertencia": advertencia,
            "marcados_sin_motivo": int((marcado & ~tiene_motivo).sum()),
            "plazos_imputados": int(df["plazo_imputado"].sum()),
            "top10": top10,
        },
    }


def imprimir_validacion(r: dict):
    v = r["validacion"]
    print()
    print("  Estabilidad (mismos atípicos con otras semillas):")
    for p in v["por_semilla"]:
        pct = "—" if p["se_mantienen"] is None else f"{100 * p['se_mantienen']:.0f} %"
        print(f"    semilla {p['semilla']:>6}: {p['n_atipicos']:>3} atípicos · se mantiene el {pct}")
    if r["estabilidad"] is not None:
        print(f"    Promedio: {100 * r['estabilidad']:.0f} % · en las cinco semillas: "
              f"{100 * v['se_mantienen_en_todas']:.0f} %")
    if v["advertencia"]:
        print(f"\n  {v['advertencia']}")
    print(f"\n  Los diez contratos más atípicos (para revisar a mano):")
    for i, t in enumerate(v["top10"], 1):
        obra = " · con obra en el mapa" if t["con_obra"] else ""
        print(f"\n  {i:>2}. {t['referencia']} · {t['tipo']} · {t['modalidad']}{obra}")
        for m in t["motivos"]:
            print(f"      - {m}")
        print(f"      {t['secop_url'] or 'sin enlace a SECOP'}")
    print()


# ---------------------------------------------------------------------------
# Escritura (una sola transacción)
# ---------------------------------------------------------------------------
def _num(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def guardar(conn, version: str, commit: str | None, r: dict) -> bool:
    """Escribe la ejecución y sus resultados. False si otra ejecución ya cubrió el commit."""
    df = r["df"]
    with conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (CANDADO,))
        if commit and ejecucion_del_commit(cur, commit):
            return False
        cur.execute(
            """
            INSERT INTO ml_atipicos_ejecucion (version, commit_git, exitosa, n_contratos, n_marcados_modelo,
                n_atipicos, n_atipicos_con_obra, estabilidad, parametros, validacion)
            VALUES (%s, %s, true, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (version, commit, len(df), r["n_marcados_modelo"], r["n_atipicos"], r["n_atipicos_con_obra"],
             r["estabilidad"], Json(PARAMETROS), Json(r["validacion"])),
        )
        ejecucion_id = cur.fetchone()[0]
        filas = [
            (ejecucion_id, f["id_contrato"], f["contrato"], f["tipo_de_contrato"], f["modalidad_de_contratacion"],
             _num(f["valor_contrato"]), None if f["plazo_imputado"] else int(f["plazo_dias"]),
             int(f["dias_adicionados"]), bool(f["marcado_modelo"]), bool(f["es_atipico"]),
             round(float(f["puntaje"]), 6), Json(f["motivos"]))
            for _, f in df.iterrows()
        ]
        execute_values(cur, """
            INSERT INTO ml_atipicos_contrato (ejecucion_id, id_contrato, referencia, tipo_de_contrato,
                modalidad_de_contratacion, valor_contrato, plazo_dias, dias_adicionados, marcado_modelo,
                es_atipico, puntaje, motivos)
            VALUES %s""", filas)
    return True


def registrar_fallo(version: str, commit: str | None, error: Exception):
    """Deja constancia del fallo (sin resultados). Si ni eso se puede, se ignora."""
    try:
        conn = conectar()
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ml_atipicos_ejecucion (version, commit_git, exitosa, error) VALUES (%s, %s, false, %s)",
                (version, commit, f"{type(error).__name__}: {error}"[:2000]),
            )
        conn.close()
    except Exception:
        pass


def main():
    conn = conectar()
    faltan = [t for t in (VISTA, "v_obras_mapa", "v_obras_seguimiento", *TABLAS) if not existe_relacion(conn, t)]
    if faltan:
        sys.exit(f"No existe {', '.join(faltan)}. Corre primero el ETL: docker compose run --rm etl")

    commit = commit_actual()
    if commit:
        with conn.cursor() as cur:
            previa = ejecucion_del_commit(cur, commit)
        conn.rollback()
        if previa:
            print(f"  Ya hay una ejecución exitosa para el commit {commit[:12]} (versión {previa[0]}). "
                  "No se vuelve a calcular.")
            conn.close()
            return
    else:
        print("  Sin commit de git (COMMIT_GIT vacío): la ejecución no se puede deduplicar.")

    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        r = calcular(conn)
        imprimir_validacion(r)
        if not guardar(conn, version, commit, r):
            print(f"  Otra ejecución ya guardó resultados para el commit {commit[:12]}. No se escribe nada.")
            return
    except UniqueViolation:
        print(f"  Otra ejecución ya guardó resultados para el commit {commit[:12] if commit else '—'}.")
        return
    except Exception as e:
        registrar_fallo(version, commit, e)
        raise
    finally:
        conn.close()

    estab = "—" if r["estabilidad"] is None else f"{100 * r['estabilidad']:.0f} %"
    print(f"  Versión {version} · commit {commit[:12] if commit else 'sin commit'}: {r['n_atipicos']} contratos "
          f"atípicos de {len(r['df'])}, {r['n_atipicos_con_obra']} con obra en el mapa · estabilidad {estab}")
