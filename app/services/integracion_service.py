from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from datetime import datetime, timezone, date

# ==========================================
# 1. VALIDAR ESTRUCTURA (Establecimiento/Punto)
# ==========================================
async def validar_estructura_core(emisor_id: int, estab_codigo: str, punto_codigo: str, db: AsyncSession):
    # AJUSTE: Mantenemos la lógica de JOIN, pero nos aseguramos de que apunte a las tablas correctas
    query = text("""
        SELECT p.id, p.secuencial_actual, e.direccion
        FROM puntos_emision p
        JOIN establecimientos e ON p.establecimiento_id = e.id
        WHERE e.emisor_id = :eid
          AND e.codigo = :estab
          AND p.codigo = :punto
    """)
    res = await db.execute(query, {"eid": emisor_id, "estab": estab_codigo, "punto": punto_codigo})
    row = res.fetchone()

    if not row:
        raise HTTPException(
            status_code=404, 
            detail="La combinación de establecimiento y punto de emisión no existe para este emisor."
        )

    return {
        "ok": True, 
        "mensaje": "Estructura válida", 
        "data": dict(row._mapping)
    }


# ==========================================
# 2. OBTENER STATUS INTEGRAL DEL EMISOR
# ==========================================
async def obtener_status_core(emisor_id: int, db: AsyncSession):
    # AJUSTE 1: Tabla 'invoices' -> 'invoices_emitidas'
    # AJUSTE 2: Columna 'balance' -> 'balance_emision'
    query = text("""
        SELECT
            e.ruc, 
            e.razon_social, 
            e.nombre_comercial, 
            e.ambiente,
            e.p12_expiration,
            COALESCE(c.balance_emision, 0) AS creditos_disponibles,
            (
                SELECT json_agg(last_docs)
                FROM (
                    SELECT 
                        id, fecha_emision, estado, identificacion_comprador,
                        razon_social_comprador, importe_total AS total,
                        clave_acceso, created_at
                    FROM invoices_emitidas 
                    WHERE emisor_id = e.id
                    ORDER BY created_at DESC
                    LIMIT 20
                ) last_docs
            ) AS ultimas_facturas
        FROM emisores e
        LEFT JOIN user_credits c ON e.id = c.emisor_id
        WHERE e.id = :eid
    """)
    
    res = await db.execute(query, {"eid": emisor_id})
    row = res.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Emisor no encontrado")

    data = row._mapping

    # Lógica de Firma Electrónica
    expiracion = data["p12_expiration"]
    firma_valida = False
    
    if expiracion:
        # Conversión de 'date' a 'datetime' para comparación segura
        if isinstance(expiracion, date) and not isinstance(expiracion, datetime):
            expiracion = datetime.combine(expiracion, datetime.min.time())

        # Manejo de zona horaria UTC para comparación contra datetime.now(timezone.utc)
        if expiracion.tzinfo is None:
            expiracion = expiracion.replace(tzinfo=timezone.utc)
            
        firma_valida = expiracion > datetime.now(timezone.utc)

    # Cálculo de días restantes de forma segura
    dias_restantes = (expiracion - datetime.now(timezone.utc)).days if expiracion else 0

    return {
        "ok": True,
        "emisor": {
            "ruc": data["ruc"],
            "razon_social": data["razon_social"],
            "nombre_comercial": data["nombre_comercial"],
            "ambiente": "PRUEBAS" if data["ambiente"] == 1 else "PRODUCCIÓN", 
            "firma": {
                "valida": firma_valida,
                "vencimiento": expiracion.isoformat() if expiracion else None,
                "dias_restantes": dias_restantes
            },
        },
        "creditos": data["creditos_disponibles"],
        "historial": data["ultimas_facturas"] or [],
    }