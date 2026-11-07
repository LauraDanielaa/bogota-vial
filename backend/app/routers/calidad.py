"""Reporte de calidad de datos del ETL (vista v_calidad)."""

from fastapi import APIRouter

from app.db import fetch_all

router = APIRouter(prefix="/calidad", tags=["calidad"])


@router.get("")
def reporte_calidad():
    return fetch_all("SELECT seccion, metrica, valor, nota FROM v_calidad ORDER BY orden")
