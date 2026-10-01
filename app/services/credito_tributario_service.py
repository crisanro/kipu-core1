# app/services/credito_tributario_service.py

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def obtener_sugerencia_625(db: AsyncSession, emisor_id: int, periodo_actual: date) -> Decimal:
    """
    Suma el saldo disponible de lotes de crédito tributario de compras
    cuya fecha_caducidad es menor o igual al período fiscal actual (cumplieron 5 años).
    """
    res = await db.execute(text("""
        SELECT COALESCE(SUM(monto_disponible), 0) AS total_caducado
        FROM credito_tributario_lotes
        WHERE emisor_id = :eid
          AND monto_disponible > 0
          AND fecha_caducidad <= :p_actual
    """), {"eid": emisor_id, "p_actual": periodo_actual})
    
    val = res.scalar() or Decimal("0.00")
    return Decimal(str(val))


async def registrar_lote_declaracion(
    db: AsyncSession,
    emisor_id: int,
    periodo_inicio: date,
    monto_credito_nuevo: Decimal
) -> None:
    """
    Se ejecuta al marcar una declaración como DECLARADA (POST /declarar).
    Si el período generó crédito tributario (Casillero 602 > 0),
    crea o actualiza la bolsa de crédito con caducidad exacta a 5 años (60 meses).
    """
    if monto_credito_nuevo <= 0:
        return

    caducidad = periodo_inicio + relativedelta(years=5)

    await db.execute(text("""
        INSERT INTO credito_tributario_lotes (
            emisor_id, periodo_origen, monto_original, monto_disponible, fecha_caducidad, origen
        ) VALUES (
            :eid, :periodo, :monto, :monto, :caducidad, 'DECLARACION'
        )
        ON CONFLICT (emisor_id, periodo_origen) DO UPDATE SET
            monto_original   = EXCLUDED.monto_original,
            monto_disponible = EXCLUDED.monto_disponible,
            updated_at       = NOW()
    """), {
        "eid": emisor_id,
        "periodo": periodo_inicio,
        "monto": monto_credito_nuevo,
        "caducidad": caducidad,
    })