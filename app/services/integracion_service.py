from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from datetime import datetime, timezone, date

async def validar_estructura_core(emisor_id: int, estab_codigo: str, punto_codigo: str, db: AsyncSession):
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


async def obtener_status_core(emisor_id: int, db: AsyncSession):
    # Usamos bindparam por seguridad extra aunque ya uses diccionarios
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

    # Mapping es más limpio en SQLAlchemy 2.0
    data = row._mapping

    # Lógica de Firma Electrónica
    expiracion = data["p12_expiration"]
    firma_valida = False
    
    if expiracion:
        # 2. CONVERSIÓN CRÍTICA: Si es un 'date', lo pasamos a 'datetime'
        if isinstance(expiracion, date) and not isinstance(expiracion, datetime):
            expiracion = datetime.combine(expiracion, datetime.min.time())

        # 3. Ahora sí podemos manejar la zona horaria de forma segura
        if expiracion.tzinfo is None:
            expiracion = expiracion.replace(tzinfo=timezone.utc)
            
        firma_valida = expiracion > datetime.now(timezone.utc)

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
                "dias_restantes": (expiracion - datetime.now(timezone.utc)).days if expiracion else 0
            },
        },
        "creditos": data["creditos_disponibles"],
        "historial": data["ultimas_facturas"] or [],
    }
