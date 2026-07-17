from typing import Optional
from pydantic import BaseModel


class EstablecimientoResumen(BaseModel):
    rbd: int
    nombre: str
    region_cod: Optional[int]
    region_nombre: Optional[str]
    comuna_cod: Optional[int]
    comuna_nombre: Optional[str]
    dependencia_nombre: Optional[str]
    rural: Optional[int]
    anio: int
    matricula_total: Optional[int]
    n_estudiantes: Optional[float]
    prom_gral_promedio: Optional[float]
    asistencia_promedio: Optional[float]
    tasa_aprobacion: Optional[float]
    rating: Optional[float]
    es_modalidad_especial: Optional[bool]


class EstablecimientoDetalle(EstablecimientoResumen):
    tasa_reprobacion: Optional[float]
    tasa_retiro: Optional[float]
    n_promovidos: Optional[float]
    n_reprobados: Optional[float]
    n_retirados: Optional[float]
    zona_pais: Optional[str]
    estado_estab: Optional[int]
    descripcion: Optional[str]
    ranking_regional: Optional[int]
    total_regional: Optional[int]
    ranking_nacional: Optional[int]
    total_nacional: Optional[int]


class ListadoResponse(BaseModel):
    total: int
    page: int
    page_size: int
    resultados: list[EstablecimientoResumen]


class ResumenAnio(BaseModel):
    anio: int
    total_establecimientos: int
    rating_promedio: Optional[float]
    prom_gral_promedio: Optional[float]
    asistencia_promedio: Optional[float]
    tasa_aprobacion_promedio: Optional[float]
    matricula_total: Optional[int]


class RankingRegion(BaseModel):
    region_cod: int
    region_nombre: str
    zona_pais: Optional[str]
    total_establecimientos: int
    rating_promedio: Optional[float]
    asistencia_promedio: Optional[float]
    tasa_aprobacion_promedio: Optional[float]


class RankingComuna(BaseModel):
    comuna_cod: int
    comuna_nombre: str
    region_cod: int
    region_nombre: str
    total_establecimientos: int
    rating_promedio: Optional[float]
    asistencia_promedio: Optional[float]
    tasa_aprobacion_promedio: Optional[float]


class SerieAnual(BaseModel):
    anio: int
    rating: Optional[float]
    prom_gral_promedio: Optional[float]
    asistencia_promedio: Optional[float]
    tasa_aprobacion: Optional[float]
    matricula_total: Optional[int]
