# app/services/declaraciones/obligaciones.py
#
# Qué declara cada empresa, deducido de sus datos:
#   - periodo_iva           MENSUAL | SEMESTRAL   (configurado en la empresa)
#   - obligado_contabilidad SI | NO
#   - regimen_rimpe         texto libre (emprendedor / negocio popular) o NULL
#   - tipo_emisor           NATURAL | JURIDICO
#
# Reglas:
#   IVA 104  → según periodo_iva. RIMPE negocio popular: no aplica.
#   ATS      → obligados a llevar contabilidad y sociedades.
#   Renta    → 102 (personas naturales) o 101 (sociedades).
#              CASILLEROS: persona natural no obligada, régimen general (Kipu puede calcularla).
#              INFORMATIVO: el resto (necesitan balance, o tienen régimen RIMPE).
#
# Si algo no cuadra (ej. RIMPE emprendedor configurado como mensual) se respeta
# la configuración pero se devuelve una advertencia para que el usuario la revise.

from dataclasses import dataclass, field, asdict
from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

REGIMEN_GENERAL          = "GENERAL"
REGIMEN_RIMPE_EMPRENDEDOR = "RIMPE_EMPRENDEDOR"
REGIMEN_RIMPE_POPULAR    = "RIMPE_NEGOCIO_POPULAR"


def normalizar_regimen(regimen_rimpe: str | None) -> str:
    r = (regimen_rimpe or "").upper()
    if "POPULAR" in r:
        return REGIMEN_RIMPE_POPULAR
    if "EMPRENDEDOR" in r:
        return REGIMEN_RIMPE_EMPRENDEDOR
    return REGIMEN_GENERAL


@dataclass
class Obligaciones:
    emisor_id:        int
    ruc:              str
    tipo_emisor:      str
    obligado:         bool
    regimen:          str
    en_produccion:    bool
    inicio:           date          # desde cuándo existen periodos
    iva:              str           # MENSUAL | SEMESTRAL | NO_APLICA
    ats:              bool
    renta_formulario: str           # "102" | "101"
    renta_modo:       str           # CASILLEROS | INFORMATIVO
    advertencias:     list[str] = field(default_factory=list)

    # ── Helpers ──────────────────────────────────────────────────────────────
    def aplica(self, tipo: str) -> bool:
        if tipo == "104":
            return self.iva != "NO_APLICA"
        if tipo == "ATS":
            return self.ats
        return tipo == "102"

    def tipo_periodo(self, tipo: str) -> str:
        if tipo == "102":
            return "ANUAL"
        if tipo == "104" and self.iva == "SEMESTRAL":
            return "SEMESTRAL"
        return "MENSUAL"

    def tipos_que_aplican(self) -> list[str]:
        return [t for t in ("104", "ATS", "102") if self.aplica(t)]

    def motivo_no_aplica(self, tipo: str) -> str | None:
        if not self.en_produccion:
            return "Las declaraciones aplican solo en ambiente de producción."
        if tipo == "104" and self.iva == "NO_APLICA":
            return "Como RIMPE negocio popular no declaras IVA."
        if tipo == "ATS" and not self.ats:
            return "El ATS aplica solo a obligados a llevar contabilidad y sociedades."
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["inicio"] = self.inicio.isoformat()
        d["tipos"]  = self.tipos_que_aplican() if self.en_produccion else []
        return d


def deducir(row) -> Obligaciones:
    """row: fila de emisores con los campos del SELECT de cargar_obligaciones."""
    regimen     = normalizar_regimen(row.regimen_rimpe)
    tipo_emisor = (row.tipo_emisor or "NATURAL").upper()
    obligado    = (row.obligado_contabilidad or "NO").upper() == "SI"
    periodo_iva = (row.periodo_iva or "MENSUAL").upper()
    advertencias: list[str] = []

    # IVA
    if regimen == REGIMEN_RIMPE_POPULAR:
        iva = "NO_APLICA"
    else:
        iva = periodo_iva if periodo_iva in ("MENSUAL", "SEMESTRAL") else "MENSUAL"
        if regimen == REGIMEN_RIMPE_EMPRENDEDOR and iva == "MENSUAL":
            advertencias.append(
                "Tu régimen es RIMPE emprendedor pero el IVA está configurado como mensual. "
                "Revisa la configuración si declaras semestralmente."
            )

    # ATS
    ats = obligado or tipo_emisor == "JURIDICO"

    # Renta
    renta_formulario = "101" if tipo_emisor == "JURIDICO" else "102"
    renta_modo = (
        "CASILLEROS"
        if tipo_emisor != "JURIDICO" and not obligado and regimen == REGIMEN_GENERAL
        else "INFORMATIVO"
    )

    creado = row.created_at.date() if row.created_at else date.today()
    inicio = row.fecha_inicio_produccion or creado

    return Obligaciones(
        emisor_id        = row.id,
        ruc              = row.ruc,
        tipo_emisor      = tipo_emisor,
        obligado         = obligado,
        regimen          = regimen,
        en_produccion    = row.ambiente == 2,
        inicio           = inicio,
        iva              = iva,
        ats              = ats,
        renta_formulario = renta_formulario,
        renta_modo       = renta_modo,
        advertencias     = advertencias,
    )


async def cargar_obligaciones(db: AsyncSession, emisor_id: int) -> Obligaciones | None:
    res = await db.execute(text("""
        SELECT id, ruc, tipo_emisor, obligado_contabilidad, regimen_rimpe,
               periodo_iva, ambiente, fecha_inicio_produccion, created_at
        FROM emisores
        WHERE id = :eid
    """), {"eid": emisor_id})
    row = res.fetchone()
    return deducir(row) if row else None