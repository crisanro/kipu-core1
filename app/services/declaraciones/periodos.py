# app/services/declaraciones/periodos.py
#
# Calendario tributario — lógica pura, sin base de datos.
#
# Un periodo existe por calendario (no porque haya documentos): si eres mensual,
# tienes 12 periodos de IVA al año aunque no hayas vendido nada, porque la
# declaración en cero también se presenta.
#
# Vencimientos según el 9.º dígito del RUC (10 al 28). Si cae sábado o domingo
# se corre al lunes. Los feriados NO están contemplados todavía.

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo

TZ_EC = ZoneInfo("America/Guayaquil")

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# 9.º dígito del RUC → día de vencimiento
DIA_VENCIMIENTO = {
    "1": 10, "2": 12, "3": 14, "4": 16, "5": 18,
    "6": 20, "7": 22, "8": 24, "9": 26, "0": 28,
}

TIPOS = ("104", "102", "ATS")


# =============================================================================
# FECHAS
# =============================================================================
def hoy_ec() -> date:
    return datetime.now(TZ_EC).date()


def sumar_meses(d: date, n: int) -> date:
    """Primer día del mes que está n meses después de d."""
    total = d.year * 12 + (d.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


def correr_a_habil(d: date) -> date:
    """Sábado o domingo → lunes siguiente."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def dia_por_ruc(ruc: str) -> int:
    noveno = ruc[8] if ruc and len(ruc) >= 9 else "1"
    return DIA_VENCIMIENTO.get(noveno, 28)


def fecha_larga(d: date) -> str:
    """7 de octubre de 2026"""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


# =============================================================================
# PERIODO
# =============================================================================
@dataclass(frozen=True)
class Periodo:
    tipo:         str   # "104" | "102" | "ATS"
    tipo_periodo: str   # "MENSUAL" | "SEMESTRAL" | "ANUAL"
    inicio:       date
    fin:          date

    @property
    def key(self) -> str:
        """Identificador usado en URLs y en el frontend: 2026-09 | 2026-07 | 2025"""
        if self.tipo_periodo == "ANUAL":
            return str(self.inicio.year)
        return self.inicio.strftime("%Y-%m")

    @property
    def nombre(self) -> str:
        if self.tipo_periodo == "ANUAL":
            return f"Año {self.inicio.year}"
        if self.tipo_periodo == "SEMESTRAL":
            n = "1er" if self.inicio.month == 1 else "2do"
            return f"{n} semestre {self.inicio.year}"
        return f"{MESES[self.inicio.month - 1]} de {self.inicio.year}"

    def en_curso(self, hoy: date) -> bool:
        """El periodo todavía no termina: se puede ver cómo va, pero no declarar."""
        return hoy <= self.fin

    def existe_para(self, desde: date, hoy: date) -> bool:
        """El periodo ya empezó y se superpone con la vida productiva del emisor."""
        return self.inicio <= hoy and self.fin >= desde


def crear_periodo(tipo: str, tipo_periodo: str, inicio: date) -> Periodo:
    if tipo_periodo == "ANUAL":
        ini = date(inicio.year, 1, 1)
        fin = date(inicio.year, 12, 31)
    elif tipo_periodo == "SEMESTRAL":
        if inicio.month <= 6:
            ini, fin = date(inicio.year, 1, 1), date(inicio.year, 6, 30)
        else:
            ini, fin = date(inicio.year, 7, 1), date(inicio.year, 12, 31)
    else:
        ini = date(inicio.year, inicio.month, 1)
        fin = date(inicio.year, inicio.month, monthrange(inicio.year, inicio.month)[1])
    return Periodo(tipo=tipo, tipo_periodo=tipo_periodo, inicio=ini, fin=fin)


def parse_periodo(tipo: str, tipo_periodo: str, key: str) -> Periodo:
    """'2026-09' | '2026' → Periodo. Lanza ValueError si el formato no es válido."""
    partes = key.strip().split("-")
    anio = int(partes[0])
    mes  = int(partes[1]) if len(partes) > 1 else 1
    if not (2000 <= anio <= 2100) or not (1 <= mes <= 12):
        raise ValueError("Periodo fuera de rango.")
    return crear_periodo(tipo, tipo_periodo, date(anio, mes, 1))


# =============================================================================
# VENCIMIENTO
# =============================================================================
def vencimiento(ruc: str, p: Periodo, tipo_emisor: str = "NATURAL") -> date:
    """
    104 mensual   → mes siguiente al periodo
    104 semestral → julio (S1) o enero del año siguiente (S2)
    ATS           → mes subsiguiente al periodo (el de enero vence en marzo)
    102 / 101     → marzo (personas naturales) o abril (sociedades) del año siguiente
    """
    dia = dia_por_ruc(ruc)

    if p.tipo == "102":
        mes_venc = date(p.inicio.year + 1, 4 if tipo_emisor == "JURIDICO" else 3, 1)
    elif p.tipo == "ATS":
        mes_venc = sumar_meses(p.inicio, 2)
    elif p.tipo_periodo == "SEMESTRAL":
        mes_venc = sumar_meses(p.fin, 1)
    else:
        mes_venc = sumar_meses(p.inicio, 1)

    ultimo = monthrange(mes_venc.year, mes_venc.month)[1]
    return correr_a_habil(date(mes_venc.year, mes_venc.month, min(dia, ultimo)))


# =============================================================================
# ESTADO
# =============================================================================
def estado(declarado: bool, en_curso: bool, dias_restantes: int) -> str:
    if declarado:            return "DECLARADO"
    if en_curso:             return "EN_CURSO"
    if dias_restantes < 0:   return "VENCIDO"
    if dias_restantes <= 3:  return "URGENTE"
    if dias_restantes <= 7:  return "PROXIMO"
    return "PENDIENTE"


# =============================================================================
# LISTADOS
# =============================================================================
def periodos_del_anio(tipo: str, tipo_periodo: str, anio: int, desde: date, hoy: date) -> list[Periodo]:
    """Periodos de un año que ya empezaron y que caen dentro de la vida productiva. Más reciente primero."""
    if tipo_periodo == "ANUAL":
        candidatos = [crear_periodo(tipo, "ANUAL", date(anio, 1, 1))]
    elif tipo_periodo == "SEMESTRAL":
        candidatos = [crear_periodo(tipo, "SEMESTRAL", date(anio, m, 1)) for m in (1, 7)]
    else:
        candidatos = [crear_periodo(tipo, "MENSUAL", date(anio, m, 1)) for m in range(1, 13)]
    return sorted(
        (p for p in candidatos if p.existe_para(desde, hoy)),
        key=lambda p: p.inicio, reverse=True,
    )


def periodo_a_declarar(tipo: str, tipo_periodo: str, hoy: date) -> Periodo:
    """El último periodo que ya terminó (el que toca declarar ahora)."""
    if tipo_periodo == "ANUAL":
        return crear_periodo(tipo, "ANUAL", date(hoy.year - 1, 1, 1))
    if tipo_periodo == "SEMESTRAL":
        inicio = date(hoy.year - 1, 7, 1) if hoy.month <= 6 else date(hoy.year, 1, 1)
        return crear_periodo(tipo, "SEMESTRAL", inicio)
    return crear_periodo(tipo, "MENSUAL", sumar_meses(date(hoy.year, hoy.month, 1), -1))