# app/api/v1/app/recibidas.py
from typing import Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from decimal import Decimal
import json

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.storage_service import upload_file

router = APIRouter()

# ── Schemas ────────────────────────────────────────────────────────────────────

class ImpuestoDetalle(BaseModel):
    codigoPorcentaje: str
    tarifa:           str
    baseImponible:    Decimal
    valor:            Decimal
    aplicaCredito:    bool = False  # el cliente lo define al registrar

class FacturaRecibidaCreate(BaseModel):
    # Proveedor
    ruc_proveedor:          str
    razon_social_proveedor: str
    contribuyente_especial: Optional[str] = None

    # Identificación
    clave_acceso:       str
    numero_autorizacion: Optional[str] = None
    numero_factura:     str
    fecha_emision:      date
    fecha_autorizacion: Optional[str] = None

    # Totales
    total_sin_impuestos: Decimal
    total_descuento:     Decimal = Decimal("0")
    subtotal_0:          Decimal = Decimal("0")
    subtotal_iva:        Decimal = Decimal("0")
    valor_iva:           Decimal = Decimal("0")
    importe_total:       Decimal

    # Impuestos detalle completo
    impuestos_detalle: list[ImpuestoDetalle] = []

    # Decisiones fiscales
    deducible_renta:        bool = True
    credito_tributario_iva: bool = False
    notas_cliente:          Optional[str] = None

    # Datos completos del comprobante (sin firma)
    datos_factura: dict

    # Fuente
    fuente: str = "MANUAL"  # MANUAL o CLAVE


class FacturaRecibidaUpdate(BaseModel):
    deducible_renta:        Optional[bool]            = None
    credito_tributario_iva: Optional[bool]            = None
    notas_cliente:          Optional[str]             = None
    impuestos_detalle:      Optional[list[ImpuestoDetalle]] = None


# ── POST / — Registrar factura recibida ───────────────────────────────────────

@router.post("", summary="Registrar factura recibida", status_code=201)
async def registrar_factura_recibida(
    data: FacturaRecibidaCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    # ── Verificar créditos de recepción ───────────────────────
    res_credits = await db.execute(text("""
        SELECT balance_recepcion FROM user_credits
        WHERE emisor_id = :eid FOR UPDATE
    """), {"eid": emisor_id})
    credits = res_credits.fetchone()
    if not credits or credits.balance_recepcion <= 0:
        raise HTTPException(status_code=402, detail="Créditos de recepción insuficientes.")

    # ── Verificar RUC del comprador = RUC del emisor ──────────
    res_emisor = await db.execute(text("""
        SELECT ruc FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    comprador_ruc = data.datos_factura.get("infoFactura", {}).get("identificacionComprador", "")
    if comprador_ruc != emisor.ruc:
        raise HTTPException(
            status_code=400,
            detail=f"Esta factura no está dirigida a tu RUC ({emisor.ruc})."
        )

    # ── Verificar duplicado ───────────────────────────────────
    res_dup = await db.execute(text("""
        SELECT id FROM invoices_recibidas
        WHERE clave_acceso = :ca AND emisor_id = :eid
    """), {"ca": data.clave_acceso, "eid": emisor_id})
    if res_dup.fetchone():
        raise HTTPException(status_code=409, detail="Esta factura ya fue registrada.")

    # ── Guardar XML/JSON en R2 ────────────────────────────────
    xml_path = None
    try:
        xml_path = f"{emisor.ruc}/recibidas/{data.clave_acceso}.json"
        upload_file(
            xml_path,
            json.dumps(data.datos_factura, ensure_ascii=False).encode("utf-8"),
            "application/json"
        )
    except Exception as e:
        print(f"⚠️ Error guardando en R2: {e}")

    # ── Insertar en DB ────────────────────────────────────────
    try:
        res = await db.execute(text("""
            INSERT INTO invoices_recibidas (
                emisor_id, ruc_proveedor, razon_social_proveedor, contribuyente_especial,
                clave_acceso, numero_autorizacion, numero_factura,
                fecha_emision, fecha_autorizacion,
                total_sin_impuestos, total_descuento,
                subtotal_0, subtotal_iva, valor_iva, importe_total,
                impuestos_detalle,
                deducible_renta, credito_tributario_iva, notas_cliente,
                xml_path, datos_factura, fuente, procesado
            ) VALUES (
                :eid, :ruc_prov, :razon_prov, :contrib_esp,
                :clave, :num_auth, :num_fac,
                :fecha_emision, :fecha_auth,
                :total_sin_imp, :total_desc,
                :sub_0, :sub_iva, :val_iva, :total,
                CAST(:impuestos AS jsonb),
                :ded_renta, :cred_iva, :notas,
                :xml_path, CAST(:datos AS jsonb), :fuente, false
            ) RETURNING id
        """), {
            "eid":          emisor_id,
            "ruc_prov":     data.ruc_proveedor,
            "razon_prov":   data.razon_social_proveedor,
            "contrib_esp":  data.contribuyente_especial,
            "clave":        data.clave_acceso,
            "num_auth":     data.numero_autorizacion or data.clave_acceso,
            "num_fac":      data.numero_factura,
            "fecha_emision": data.fecha_emision,
            "fecha_auth":   data.fecha_autorizacion,
            "total_sin_imp": data.total_sin_impuestos,
            "total_desc":   data.total_descuento,
            "sub_0":        data.subtotal_0,
            "sub_iva":      data.subtotal_iva,
            "val_iva":      data.valor_iva,
            "total":        data.importe_total,
            "impuestos":    json.dumps([i.model_dump() for i in data.impuestos_detalle]),
            "ded_renta":    data.deducible_renta,
            "cred_iva":     data.credito_tributario_iva,
            "notas":        data.notas_cliente,
            "xml_path":     xml_path,
            "datos":        json.dumps(data.datos_factura, default=str),
            "fuente":       data.fuente,
        })
        factura_id = res.scalar()

        # Descontar crédito de recepción
        await db.execute(text("""
            UPDATE user_credits
            SET balance_recepcion = balance_recepcion - 1
            WHERE emisor_id = :eid
        """), {"eid": emisor_id})

        await db.commit()

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

    return {
        "ok":      True,
        "id":      str(factura_id),
        "mensaje": "Factura recibida registrada correctamente."
    }


# ── GET / — Historial facturas recibidas ──────────────────────────────────────

@router.get("", summary="Historial de facturas recibidas")
async def historial_recibidas(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin:    Optional[str] = Query(None),
):
    emisor_id = auth_data["emisor_id"]

    # Defaults: últimos 45 días
    hoy = date.today()
    fi  = date.fromisoformat(fecha_inicio) if fecha_inicio else hoy - timedelta(days=45)
    ff  = date.fromisoformat(fecha_fin)    if fecha_fin    else hoy

    # Máximo 45 días
    if (ff - fi).days > 45:
        raise HTTPException(status_code=400, detail="El rango máximo es de 45 días.")

    res = await db.execute(text("""
        SELECT
            id, ruc_proveedor, razon_social_proveedor,
            numero_factura, fecha_emision, fecha_autorizacion,
            total_sin_impuestos, total_descuento,
            subtotal_0, subtotal_iva, valor_iva, importe_total,
            impuestos_detalle,
            deducible_renta, credito_tributario_iva,
            notas_cliente, fuente, created_at
        FROM invoices_recibidas
        WHERE emisor_id = :eid
          AND fecha_emision BETWEEN :fi AND :ff
        ORDER BY fecha_emision DESC, created_at DESC
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    rows = res.fetchall()

    # Resumen fiscal del período
    resumen = {
        "total_facturas":       len(rows),
        "total_sin_impuestos":  0,
        "total_descuento":      0,
        "subtotal_0":           0,
        "subtotal_iva":         0,
        "valor_iva":            0,
        "iva_credito_tributario": 0,
        "importe_total":        0,
    }

    facturas = []
    for r in rows:
        resumen["total_sin_impuestos"]    += float(r.total_sin_impuestos or 0)
        resumen["total_descuento"]        += float(r.total_descuento or 0)
        resumen["subtotal_0"]             += float(r.subtotal_0 or 0)
        resumen["subtotal_iva"]           += float(r.subtotal_iva or 0)
        resumen["valor_iva"]              += float(r.valor_iva or 0)
        resumen["importe_total"]          += float(r.importe_total or 0)
        if r.credito_tributario_iva:
            resumen["iva_credito_tributario"] += float(r.valor_iva or 0)

        facturas.append({
            "id":                    str(r.id),
            "ruc_proveedor":         r.ruc_proveedor,
            "razon_social_proveedor": r.razon_social_proveedor,
            "numero_factura":        r.numero_factura,
            "fecha_emision":         str(r.fecha_emision),
            "total_sin_impuestos":   float(r.total_sin_impuestos or 0),
            "total_descuento":       float(r.total_descuento or 0),
            "subtotal_0":            float(r.subtotal_0 or 0),
            "subtotal_iva":          float(r.subtotal_iva or 0),
            "valor_iva":             float(r.valor_iva or 0),
            "importe_total":         float(r.importe_total or 0),
            "impuestos_detalle":     r.impuestos_detalle or [],
            "deducible_renta":       r.deducible_renta,
            "credito_tributario_iva": r.credito_tributario_iva,
            "notas_cliente":         r.notas_cliente,
            "fuente":                r.fuente,
            "created_at":            str(r.created_at),
        })

    # Redondear resumen
    for k, v in resumen.items():
        if isinstance(v, float):
            resumen[k] = round(v, 2)

    return {
        "ok":       True,
        "resumen":  resumen,
        "data":     facturas,
        "periodo":  {"desde": str(fi), "hasta": str(ff)},
    }


# ── GET /{id} — Detalle de una factura recibida ───────────────────────────────

@router.get("/{factura_id}", summary="Detalle de factura recibida")
async def detalle_recibida(
    factura_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    res = await db.execute(text("""
        SELECT * FROM invoices_recibidas
        WHERE id = :id AND emisor_id = :eid
    """), {"id": factura_id, "eid": emisor_id})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    return {
        "ok": True,
        "data": {
            "id":                     str(row.id),
            "ruc_proveedor":          row.ruc_proveedor,
            "razon_social_proveedor": row.razon_social_proveedor,
            "contribuyente_especial": row.contribuyente_especial,
            "numero_factura":         row.numero_factura,
            "clave_acceso":           row.clave_acceso,
            "fecha_emision":          str(row.fecha_emision),
            "fecha_autorizacion":     str(row.fecha_autorizacion) if row.fecha_autorizacion else None,
            "total_sin_impuestos":    float(row.total_sin_impuestos or 0),
            "total_descuento":        float(row.total_descuento or 0),
            "subtotal_0":             float(row.subtotal_0 or 0),
            "subtotal_iva":           float(row.subtotal_iva or 0),
            "valor_iva":              float(row.valor_iva or 0),
            "importe_total":          float(row.importe_total or 0),
            "impuestos_detalle":      row.impuestos_detalle or [],
            "deducible_renta":        row.deducible_renta,
            "credito_tributario_iva": row.credito_tributario_iva,
            "notas_cliente":          row.notas_cliente,
            "fuente":                 row.fuente,
            "datos_factura":          row.datos_factura,
            "created_at":             str(row.created_at),
        }
    }


# ── PATCH /{id} — Editar decisiones fiscales ──────────────────────────────────

@router.patch("/{factura_id}", summary="Editar decisiones fiscales de factura recibida")
async def editar_recibida(
    factura_id: str,
    data: FacturaRecibidaUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    res = await db.execute(text("""
        SELECT id FROM invoices_recibidas
        WHERE id = :id AND emisor_id = :eid
    """), {"id": factura_id, "eid": emisor_id})
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    campos = []
    params = {"id": factura_id, "eid": emisor_id}

    if data.deducible_renta        is not None:
        campos.append("deducible_renta = :ded_renta")
        params["ded_renta"] = data.deducible_renta

    if data.credito_tributario_iva is not None:
        campos.append("credito_tributario_iva = :cred_iva")
        params["cred_iva"] = data.credito_tributario_iva

    if data.notas_cliente          is not None:
        campos.append("notas_cliente = :notas")
        params["notas"] = data.notas_cliente

    if data.impuestos_detalle      is not None:
        campos.append("impuestos_detalle = CAST(:impuestos AS jsonb)")
        params["impuestos"] = json.dumps([i.model_dump() for i in data.impuestos_detalle])

    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar.")

    try:
        await db.execute(text(f"""
            UPDATE invoices_recibidas
            SET {', '.join(campos)}
            WHERE id = :id AND emisor_id = :eid
        """), params)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

    return {"ok": True, "mensaje": "Factura actualizada correctamente."}