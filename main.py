from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import db_cursor
from .schemas import (
    ListadoResponse, EstablecimientoResumen, EstablecimientoDetalle,
    ResumenAnio, RankingRegion, RankingComuna, SerieAnual,
)

app = FastAPI(
    title="API Calificacion de Establecimientos Educacionales (MINEDUC)",
    description=(
        "Rating 1-7 de establecimientos educacionales chilenos (educacion regular, "
        "ninos y jovenes), 2020-2025, calculado a partir de datos abiertos de MINEDUC "
        "(Rendimiento por Estudiante + Resumen de Matricula)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESUMEN_COLS = """
    rbd, nombre, region_cod, region_nombre, comuna_cod, comuna_nombre,
    dependencia_nombre, rural, anio, matricula_total, n_estudiantes,
    prom_gral_promedio, asistencia_promedio, tasa_aprobacion, rating,
    es_modalidad_especial
"""


@app.get("/api/anios", tags=["Metadatos"])
def listar_anios():
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT DISTINCT anio FROM rendimiento_anual ORDER BY anio"
        ).fetchall()
    return [r["anio"] for r in rows]


@app.get("/api/regiones", tags=["Metadatos"])
def listar_regiones():
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT DISTINCT region_cod, region_nombre, zona_pais
               FROM dim_establecimiento
               WHERE region_cod IS NOT NULL
               ORDER BY region_cod"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/comunas", tags=["Metadatos"])
def listar_comunas(region_cod: Optional[int] = None):
    query = """SELECT DISTINCT comuna_cod, comuna_nombre, region_cod, region_nombre
               FROM dim_establecimiento WHERE comuna_cod IS NOT NULL"""
    params = []
    if region_cod is not None:
        query += " AND region_cod = ?"
        params.append(region_cod)
    query += " ORDER BY comuna_nombre"
    with db_cursor() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/dependencias", tags=["Metadatos"])
def listar_dependencias():
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT DISTINCT dependencia_cod, dependencia_nombre FROM dim_establecimiento ORDER BY dependencia_cod"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/establecimientos", response_model=ListadoResponse, tags=["Establecimientos"])
def listar_establecimientos(
    anio: int = Query(2025, description="Ano academico"),
    region_cod: Optional[int] = None,
    comuna_cod: Optional[int] = None,
    dependencia_cod: Optional[int] = None,
    rural: Optional[int] = Query(None, description="0=urbano, 1=rural"),
    search: Optional[str] = Query(None, description="Busca por nombre de establecimiento"),
    incluir_modalidad_especial: bool = Query(False, description="Incluir escuelas hospitalarias / de lenguaje / etc, excluidas del ranking por defecto"),
    solo_calificados: bool = Query(True, description="Solo establecimientos con rating calculado"),
    sort: str = Query("rating_desc", pattern="^(rating_desc|rating_asc|nombre)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    where = ["anio = ?"]
    params: list = [anio]

    if region_cod is not None:
        where.append("region_cod = ?")
        params.append(region_cod)
    if comuna_cod is not None:
        where.append("comuna_cod = ?")
        params.append(comuna_cod)
    if dependencia_cod is not None:
        where.append("dependencia_cod = ?")
        params.append(dependencia_cod)
    if rural is not None:
        where.append("rural = ?")
        params.append(rural)
    if search:
        where.append("nombre LIKE ?")
        params.append(f"%{search.upper()}%")
    if not incluir_modalidad_especial:
        where.append("es_modalidad_especial = 0")
    if solo_calificados:
        where.append("rating IS NOT NULL")

    where_sql = " AND ".join(where)
    order_sql = {
        "rating_desc": "rating DESC",
        "rating_asc": "rating ASC",
        "nombre": "nombre ASC",
    }[sort]

    with db_cursor() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) c FROM rendimiento_anual WHERE {where_sql}", params
        ).fetchone()["c"]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""SELECT {RESUMEN_COLS} FROM rendimiento_anual
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        ).fetchall()

    return ListadoResponse(
        total=total,
        page=page,
        page_size=page_size,
        resultados=[EstablecimientoResumen(**dict(r)) for r in rows],
    )


@app.get("/api/establecimientos/{rbd}", response_model=EstablecimientoDetalle, tags=["Establecimientos"])
def detalle_establecimiento(rbd: int, anio: int = Query(2025)):
    with db_cursor() as conn:
        row = conn.execute(
            "SELECT * FROM rendimiento_anual WHERE rbd = ? AND anio = ?", (rbd, anio)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Establecimiento/anio no encontrado")

        data = dict(row)

        ranking_regional = ranking_nacional = total_regional = total_nacional = None
        if data.get("rating") is not None and data.get("region_cod") is not None:
            reg_rows = conn.execute(
                """SELECT rbd, rating FROM rendimiento_anual
                   WHERE anio = ? AND region_cod = ? AND rating IS NOT NULL
                   ORDER BY rating DESC""",
                (anio, data["region_cod"]),
            ).fetchall()
            reg_rbds = [r["rbd"] for r in reg_rows]
            if rbd in reg_rbds:
                ranking_regional = reg_rbds.index(rbd) + 1
                total_regional = len(reg_rbds)

            nac_rows = conn.execute(
                """SELECT rbd FROM rendimiento_anual
                   WHERE anio = ? AND rating IS NOT NULL
                   ORDER BY rating DESC""",
                (anio,),
            ).fetchall()
            nac_rbds = [r["rbd"] for r in nac_rows]
            if rbd in nac_rbds:
                ranking_nacional = nac_rbds.index(rbd) + 1
                total_nacional = len(nac_rbds)

        data["ranking_regional"] = ranking_regional
        data["total_regional"] = total_regional
        data["ranking_nacional"] = ranking_nacional
        data["total_nacional"] = total_nacional

    return EstablecimientoDetalle(**data)


@app.get("/api/establecimientos/{rbd}/historico", response_model=list[SerieAnual], tags=["Establecimientos"])
def historico_establecimiento(rbd: int):
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT anio, rating, prom_gral_promedio, asistencia_promedio,
                      tasa_aprobacion, matricula_total
               FROM rendimiento_anual WHERE rbd = ? ORDER BY anio""",
            (rbd,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Establecimiento no encontrado")
    return [SerieAnual(**dict(r)) for r in rows]


@app.get("/api/stats/resumen", response_model=ResumenAnio, tags=["Estadisticas"])
def resumen_nacional(anio: int = Query(2025)):
    with db_cursor() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS total_establecimientos,
                   AVG(rating) AS rating_promedio,
                   AVG(prom_gral_promedio) AS prom_gral_promedio,
                   AVG(asistencia_promedio) AS asistencia_promedio,
                   AVG(tasa_aprobacion) AS tasa_aprobacion_promedio,
                   SUM(matricula_total) AS matricula_total
               FROM rendimiento_anual
               WHERE anio = ? AND es_modalidad_especial = 0""",
            (anio,),
        ).fetchone()
    return ResumenAnio(anio=anio, **dict(row))


@app.get("/api/ranking/regiones", response_model=list[RankingRegion], tags=["Ranking"])
def ranking_regiones(anio: int = Query(2025)):
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT region_cod, region_nombre, zona_pais,
                      COUNT(*) AS total_establecimientos,
                      AVG(rating) AS rating_promedio,
                      AVG(asistencia_promedio) AS asistencia_promedio,
                      AVG(tasa_aprobacion) AS tasa_aprobacion_promedio
               FROM rendimiento_anual
               WHERE anio = ? AND es_modalidad_especial = 0 AND region_cod IS NOT NULL
               GROUP BY region_cod, region_nombre, zona_pais
               ORDER BY rating_promedio DESC""",
            (anio,),
        ).fetchall()
    return [RankingRegion(**dict(r)) for r in rows]


@app.get("/api/ranking/comunas", response_model=list[RankingComuna], tags=["Ranking"])
def ranking_comunas(anio: int = Query(2025), region_cod: Optional[int] = None):
    where = ["anio = ?", "es_modalidad_especial = 0", "comuna_cod IS NOT NULL"]
    params: list = [anio]
    if region_cod is not None:
        where.append("region_cod = ?")
        params.append(region_cod)
    where_sql = " AND ".join(where)

    with db_cursor() as conn:
        rows = conn.execute(
            f"""SELECT comuna_cod, comuna_nombre, region_cod, region_nombre,
                       COUNT(*) AS total_establecimientos,
                       AVG(rating) AS rating_promedio,
                       AVG(asistencia_promedio) AS asistencia_promedio,
                       AVG(tasa_aprobacion) AS tasa_aprobacion_promedio
                FROM rendimiento_anual
                WHERE {where_sql}
                GROUP BY comuna_cod, comuna_nombre, region_cod, region_nombre
                ORDER BY rating_promedio DESC""",
            params,
        ).fetchall()
    return [RankingComuna(**dict(r)) for r in rows]


@app.get("/", tags=["Metadatos"])
def root():
    return {
        "nombre": "API Calificacion Establecimientos Educacionales MINEDUC",
        "docs": "/docs",
        "anios_disponibles": "/api/anios",
    }
