# -*- coding: utf-8 -*-
"""
Fechas de entrega comprometidas (regla acordada con el usuario el 2026-10-13).

- eDist: lo que entra hasta las 9:00 de un dia habil se entrega ese mismo dia;
  lo que entra despues (9:01 en adelante, noche, fin de semana, feriado) se
  entrega el dia habil siguiente. La hora de entrada es la de deteccion: cuando
  V2.0 crea el pedido en Odoo (BMG manda OrderDate sin hora).
- POD de <= POD_COPIAS_MAX_MISMO_DIA ejemplares (por libro/linea): misma regla,
  pero la hora de entrada es cuando el libro entra a produccion (V2.0 crea la
  OF, que es despues de la validacion si la tuvo).
- POD de mas ejemplares (y cualquier otro tipo que no sea eDist): la fecha de
  BMG o DIAS_HABILES_POD_GRANDE dias habiles desde que entra a produccion, la
  que sea MAS PROXIMA.
- Dia habil = lunes a viernes, salvo los feriados no laborables de
  FERIADOS_NO_LABORABLES.

El contenedor corre en UTC, asi que todo se calcula en hora de Uruguay (UTC-3
fijo: Uruguay no tiene horario de verano desde 2015). No se usa zoneinfo
porque la imagen python:3.11-slim no trae tzdata.
"""
from datetime import datetime, date, timedelta, timezone

from . import mapeos

TZ_UY = timezone(timedelta(hours=-3))


def ahora_uy():
    return datetime.now(TZ_UY)


def a_hora_uy(momento):
    """Datetime (o string 'YYYY-MM-DD HH:MM:SS') de Odoo, que esta en UTC sin tz, a hora de Uruguay."""
    if isinstance(momento, str):
        momento = datetime.strptime(momento[:19], '%Y-%m-%d %H:%M:%S')
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(TZ_UY)


def es_habil(dia):
    return dia.weekday() < 5 and (dia.month, dia.day) not in mapeos.FERIADOS_NO_LABORABLES


def siguiente_habil(dia):
    dia = dia + timedelta(days=1)
    while not es_habil(dia):
        dia += timedelta(days=1)
    return dia


def sumar_habiles(dia, cantidad):
    for _ in range(cantidad):
        dia = siguiente_habil(dia)
    return dia


def dia_de_corte(momento_uy):
    """Dia habil en que se entrega algo que entro en `momento_uy`, con corte a las 9:00.

    Hasta las 9:00 (incluye 9:00:xx) de un dia habil -> ese mismo dia.
    Despues, o si el dia no es habil -> el dia habil siguiente.
    """
    hora, minuto = mapeos.HORA_CORTE_ENTREGA
    antes_del_corte = (momento_uy.hour, momento_uy.minute) <= (hora, minuto)
    if es_habil(momento_uy.date()) and antes_del_corte:
        return momento_uy.date()
    return siguiente_habil(momento_uy.date())


def fecha_entrega_pod(momento_produccion_uy, copias, fecha_bmg_yyyymmdd):
    """Fecha de entrega de un libro POD que entra a produccion en `momento_produccion_uy`."""
    base = dia_de_corte(momento_produccion_uy)
    if copias is not None and copias <= mapeos.POD_COPIAS_MAX_MISMO_DIA:
        return base
    tope = sumar_habiles(base, mapeos.DIAS_HABILES_POD_GRANDE)
    try:
        fecha_bmg = datetime.strptime(fecha_bmg_yyyymmdd, '%Y%m%d').date()
    except (TypeError, ValueError):
        return tope
    return min(fecha_bmg, tope)
