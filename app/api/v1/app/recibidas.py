# app/api/v1/app/recibidas.py
from typing import Optional
from datetime import date, timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from decimal import Decimal
import json
from app.utils.xml_parser_recibidos import parsear_xml_recibido
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from app.services.storage_service import upload_file
from app.services.audit_service import audit_log

router = APIRouter()

# =============================================================================
# SCHEMAS — sin cambios
# =============================================================================
class ImpuestoDetalle(BaseModel):
    codigoPorcentaje: str
    tarifa:           str
    baseImponible:    Decimal
    valor:            Decimal
    aplicaCredito:    bool = False

class DocumentoRecibidoCreate(BaseModel):
    ruc_proveedor:          str
    razon_social_proveedor: str
    tipo_doc:               str     = "FAC"
    cod_doc:                str     = "01"
    clave_acceso:           str
    numero_doc:             str
    fecha_emision:          date
    fecha_autorizacion:     Optional[str]  = None
    importe_total:          Decimal
    impuestos_detalle:      list[ImpuestoDetalle] = []
    deducible_renta:        bool           = True
    credito_tributario_iva: bool           = False
    notas:                  Optional[str]  = None
    estado_pago:            Optional[str]  = "PENDIENTE"
    forma_pago:             Optional[str]  = None
    numero_comprobante_pago: Optional[str] = None
    fecha_pago:             Optional[date] = None
    datos:                  dict
    fuente:                 str = "MANUAL"

class DocumentoRecibidoUpdate(BaseModel):
    deducible_renta:         Optional[bool]               = None
    credito_tributario_iva:  Optional[bool]               = None
    notas:                   Optional[str]                = None
    impuestos_detalle:       Optional[list[ImpuestoDetalle]] = None
    items_detalle:           Optional[list[dict]]         = None
    estado_pago:             Optional[str]                = None
    forma_pago:              Optional[str]                = None
    numero_comprobante_pago: Optional[str]                = None
    fecha_pago:              Optional[date]               = None
    doc_origen_recibido_id:  Optional[str]                = None
    doc_origen_emitido_id:   Optional[str]                = None

class DocumentoFisicoCreate(BaseModel):
    ruc_proveedor:          str
    razon_social_proveedor: str
    tipo_doc:               str     = "FAC"
    cod_doc:                str     = "01"
    numero_doc:             str
    fecha_emision:          date
    subtotal_0:             Decimal = Decimal("0.00")
    subtotal_iva:           Decimal = Decimal("0.00")
    tarifa_iva:             int     = 15
    valor_iva:              Decimal = Decimal("0.00")
    importe_total:          Decimal
    deducible_renta:        bool    = True
    credito_tributario_iva: bool    = False
    notas:                  Optional[str] = None

# =============================================================================
# POST / — Registrar documento recibido
# =============================================================================

@router.post("", summary="Registrar documento recibido", status_code=201)
async def registrar_documento_recibido(
    data:       DocumentoRecibidoCreate,
    request:    Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "documentos")

    res_sub = await db.execute(text("""
        SELECT estado FROM subscriptions WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    sub = res_sub.fetchone()
    if not sub or sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=402, detail="Se requiere suscripción activa.")

    tipos_validos = ("FAC", "LIQ", "NCR", "NDB", "RET")
    if data.tipo_doc.upper() not in tipos_validos:
        raise HTTPException(status_code=400, detail=f"tipo_doc inválido.")

    res_emisor = await db.execute(text("SELECT ruc FROM emisores WHERE id = :eid"), {"eid": emisor_id})
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    comprador_ruc = (
        data.datos.get("infoFactura", {}).get("identificacionComprador") or
        data.datos.get("infoLiquidacionCompra", {}).get("identificacionComprador") or ""
    )
    if comprador_ruc and comprador_ruc != emisor.ruc:
        raise HTTPException(status_code=400, detail=f"Este documento no está dirigido a tu RUC ({emisor.ruc}).")

    res_dup = await db.execute(text("""
        SELECT id FROM documentos_recibidos WHERE clave_acceso = :ca AND emisor_id = :eid
    """), {"ca": data.clave_acceso, "eid": emisor_id})
    if res_dup.fetchone():
        raise HTTPException(status_code=409, detail="Este documento ya fue registrado.")

    fecha_auth_parsed = None
    if data.fecha_autorizacion:
        try:
            fecha_auth_parsed = datetime.fromisoformat(data.fecha_autorizacion)
        except Exception:
            fecha_auth_parsed = None

    xml_path = None
    try:
        xml_path = f"{emisor.ruc}/recibidas/{data.clave_acceso}.json"
        upload_file(xml_path, json.dumps(data.datos, ensure_ascii=False).encode("utf-8"), "application/json")
    except Exception as e:
        print(f"⚠️ Error guardando en R2: {e}")

    try:
        res = await db.execute(text("""
            INSERT INTO documentos_recibidos (
                emisor_id, ruc_proveedor, razon_social_proveedor,
                tipo_doc, cod_doc, clave_acceso, numero_doc,
                fecha_emision, fecha_autorizacion, importe_total,
                impuestos_detalle, deducible_renta, credito_tributario_iva, notas,
                estado_pago, forma_pago, numero_comprobante_pago, fecha_pago,
                datos, xml_path, fuente, procesado
            ) VALUES (
                :eid, :ruc_prov, :razon_prov,
                :tipo_doc, :cod_doc, :clave, :numero_doc,
                :fecha_emision, :fecha_auth, :total,
                CAST(:impuestos AS jsonb), :ded_renta, :cred_iva, :notas,
                :estado_pago, :forma_pago, :num_comp, :fecha_pago,
                CAST(:datos AS jsonb), :xml_path, :fuente, false
            ) RETURNING id
        """), {
            "eid": emisor_id, "ruc_prov": data.ruc_proveedor,
            "razon_prov": data.razon_social_proveedor,
            "tipo_doc": data.tipo_doc.upper(), "cod_doc": data.cod_doc,
            "clave": data.clave_acceso, "numero_doc": data.numero_doc,
            "fecha_emision": data.fecha_emision, "fecha_auth": fecha_auth_parsed,
            "total": data.importe_total,
            "impuestos": json.dumps([i.model_dump() for i in data.impuestos_detalle], default=str),
            "ded_renta": data.deducible_renta, "cred_iva": data.credito_tributario_iva,
            "notas": data.notas, "estado_pago": data.estado_pago,
            "forma_pago": data.forma_pago, "num_comp": data.numero_comprobante_pago,
            "fecha_pago": data.fecha_pago,
            "datos": json.dumps(data.datos, default=str),
            "xml_path": xml_path, "fuente": data.fuente,
        })
        doc_id = res.scalar()

        await audit_log(
            db         = db,
            auth_data = auth_data,
            accion    = "CREATE",
            entidad   = "doc_recibido",
            entidad_id = str(doc_id),
            detalle   = {
                "tipo_doc":    data.tipo_doc.upper(),
                "numero_doc":  data.numero_doc,
                "proveedor":   data.razon_social_proveedor,
                "total":       float(data.importe_total),
                "fuente":      data.fuente,
            },
            request   = request,
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

    return {"ok": True, "id": str(doc_id), "mensaje": "Documento recibido registrado correctamente."}
# =============================================================================
# POST /fisico
# =============================================================================
@router.post("/fisico", summary="Registrar documento físico (sin XML)", status_code=201)
async def registrar_documento_fisico(
    ruc_proveedor:          str        = Form(...),
    razon_social_proveedor: str        = Form(...),
    tipo_doc:               str        = Form("FAC"),
    numero_doc:             str        = Form(...),
    fecha_emision:          date       = Form(...),
    subtotal_0:             Decimal    = Form(Decimal("0.00")),
    subtotal_iva:           Decimal    = Form(Decimal("0.00")),
    tarifa_iva:             int        = Form(15),
    valor_iva:              Decimal    = Form(Decimal("0.00")),
    importe_total:          Decimal    = Form(...),
    deducible_renta:        bool       = Form(True),
    credito_tributario_iva: bool       = Form(False),
    notas:                  Optional[str]      = Form(None),
    imagen:                 Optional[UploadFile] = File(None),
    request:                Request    = None,
    auth_data:              dict       = Depends(verify_firebase_token),
    db:                     AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "documentos")

    res_sub = await db.execute(text("SELECT estado FROM subscriptions WHERE emisor_id = :eid"), {"eid": emisor_id})
    sub = res_sub.fetchone()
    if not sub or sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=402, detail="Se requiere suscripción activa.")

    tipos_validos = ("FAC", "LIQ", "NCR", "NDB", "RET")
    tipo_doc = tipo_doc.upper()
    if tipo_doc not in tipos_validos:
        raise HTTPException(status_code=400, detail=f"tipo_doc inválido.")

    cod_map = {"FAC": "01", "LIQ": "03", "NCR": "04", "NDB": "05", "RET": "07"}
    cod_doc = cod_map.get(tipo_doc, "01")

    res_emisor = await db.execute(text("SELECT ruc FROM emisores WHERE id = :eid"), {"eid": emisor_id})
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    clave_sintetica = f"FISICO-{emisor_id}-{numero_doc.replace('-','')}-{fecha_emision.strftime('%Y%m%d')}"

    res_dup = await db.execute(text("""
        SELECT id FROM documentos_recibidos
        WHERE numero_doc = :num AND ruc_proveedor = :ruc AND emisor_id = :eid
    """), {"num": numero_doc, "ruc": ruc_proveedor, "eid": emisor_id})
    if res_dup.fetchone():
        raise HTTPException(status_code=409, detail="Este documento ya fue registrado.")

    imagen_path = None
    if imagen and imagen.filename:
        extensiones_validas = (".jpg", ".jpeg", ".png", ".webp", ".pdf")
        ext = None
        for e in extensiones_validas:
            if imagen.filename.lower().endswith(e):
                ext = e
                break
        if not ext:
            raise HTTPException(status_code=400, detail="Formato no soportado. Usa JPG, PNG, WEBP o PDF.")
        img_bytes = await imagen.read()
        if len(img_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="La imagen no puede superar 10MB.")
        imagen_path = f"{emisor.ruc}/recibidas/fisicos/{clave_sintetica}{ext}"
        try:
            content_type = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}"
            upload_file(imagen_path, img_bytes, content_type)
        except Exception as e:
            print(f"⚠️ Error subiendo imagen: {e}")
            imagen_path = None

    impuestos_detalle = []
    if valor_iva > 0 and subtotal_iva > 0:
        impuestos_detalle.append({
            "codigoPorcentaje": str(tarifa_iva), "tarifa": str(tarifa_iva),
            "baseImponible": float(subtotal_iva), "valor": float(valor_iva),
            "aplicaCredito": credito_tributario_iva,
        })
    if subtotal_0 > 0:
        impuestos_detalle.append({
            "codigoPorcentaje": "0", "tarifa": "0",
            "baseImponible": float(subtotal_0), "valor": 0.0, "aplicaCredito": False,
        })

    datos = {
        "fuente": "FISICO", "subtotal_0": float(subtotal_0),
        "subtotal_iva": float(subtotal_iva), "tarifa_iva": tarifa_iva,
        "valor_iva": float(valor_iva), "importe_total": float(importe_total),
        "tiene_imagen": imagen_path is not None,
    }

    try:
        res = await db.execute(text("""
            INSERT INTO documentos_recibidos (
                emisor_id, ruc_proveedor, razon_social_proveedor,
                tipo_doc, cod_doc, clave_acceso, numero_doc, fecha_emision,
                importe_total, impuestos_detalle,
                deducible_renta, credito_tributario_iva, notas,
                estado_pago, datos, xml_path, fuente, procesado
            ) VALUES (
                :eid, :ruc_prov, :razon_prov,
                :tipo_doc, :cod_doc, :clave, :numero_doc, :fecha_emision,
                :total, CAST(:impuestos AS jsonb),
                :ded_renta, :cred_iva, :notas,
                'PENDIENTE', CAST(:datos AS jsonb), :xml_path, 'FISICO', false
            ) RETURNING id
        """), {
            "eid": emisor_id, "ruc_prov": ruc_proveedor.strip().upper(),
            "razon_prov": razon_social_proveedor.strip().upper(),
            "tipo_doc": tipo_doc, "cod_doc": cod_doc,
            "clave": clave_sintetica, "numero_doc": numero_doc.strip(),
            "fecha_emision": fecha_emision, "total": importe_total,
            "impuestos": json.dumps(impuestos_detalle, default=str),
            "ded_renta": deducible_renta, "cred_iva": credito_tributario_iva,
            "notas": notas, "datos": json.dumps(datos, default=str),
            "xml_path": imagen_path,
        })
        doc_id = res.scalar()

        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "CREATE",
            entidad   = "doc_recibido",
            entidad_id = str(doc_id),
            detalle   = {
                "tipo_doc":   tipo_doc,
                "numero_doc": numero_doc,
                "proveedor":  razon_social_proveedor,
                "total":      float(importe_total),
                "fuente":     "FISICO",
            },
            request   = request,
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

    return {"ok": True, "id": str(doc_id), "fuente": "FISICO", "mensaje": "Documento físico registrado correctamente."}

# =============================================================================
# POST /xml
# =============================================================================
@router.post("/xml", summary="Registrar documento recibido desde XML", status_code=201)
async def registrar_desde_xml(
    file:      UploadFile,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "documentos")

    res_sub = await db.execute(text("SELECT estado FROM subscriptions WHERE emisor_id = :eid"), {"eid": emisor_id})
    sub = res_sub.fetchone()
    if not sub or sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=402, detail="Se requiere suscripción activa.")

    if not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un XML.")

    xml_bytes = await file.read()
    try:
        xml_str = xml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        xml_str = xml_bytes.decode("latin-1")

    parsed = parsear_xml_recibido(xml_str)
    if parsed.get("errores") and not parsed.get("tipo_doc"):
        raise HTTPException(status_code=400, detail=parsed["errores"][0])

    res_emisor = await db.execute(text("SELECT ruc FROM emisores WHERE id = :eid"), {"eid": emisor_id})
    emisor = res_emisor.fetchone()

    datos = parsed.get("datos", {})
    info  = datos.get("infoFactura") or datos.get("infoLiquidacionCompra") or {}
    ruc_comprador = info.get("identificacionComprador") or info.get("identificacionProveedor") or ""
    if ruc_comprador and ruc_comprador != emisor.ruc:
        raise HTTPException(status_code=400, detail=f"Este documento no está dirigido a tu RUC ({emisor.ruc}).")

    clave = parsed.get("clave_acceso", "")
    if clave:
        res_dup = await db.execute(text("""
            SELECT id FROM documentos_recibidos WHERE clave_acceso = :ca AND emisor_id = :eid
        """), {"ca": clave, "eid": emisor_id})
        if res_dup.fetchone():
            raise HTTPException(status_code=409, detail="Este documento ya fue registrado.")

    xml_path = None
    try:
        xml_path = f"{emisor.ruc}/recibidas/{clave}.xml"
        upload_file(xml_path, xml_bytes, "text/xml")
    except Exception as e:
        print(f"⚠️ Error guardando XML en R2: {e}")

    # Convertir fechas a objetos date/datetime
    fecha_emision_parsed = parsed["fecha_emision"]
    if isinstance(fecha_emision_parsed, str):
        fecha_emision_parsed = date.fromisoformat(fecha_emision_parsed[:10])

    fecha_auth_parsed = parsed["fecha_autorizacion"]
    if isinstance(fecha_auth_parsed, str) and fecha_auth_parsed:
        try:
            fecha_auth_parsed = datetime.fromisoformat(fecha_auth_parsed)
        except Exception:
            fecha_auth_parsed = None

    try:
        res = await db.execute(text("""
            INSERT INTO documentos_recibidos (
                emisor_id, ruc_proveedor, razon_social_proveedor,
                tipo_doc, cod_doc, clave_acceso, numero_doc,
                fecha_emision, fecha_autorizacion, importe_total,
                items_detalle, impuestos_detalle,
                deducible_renta, credito_tributario_iva,
                datos, xml_path, fuente, procesado
            ) VALUES (
                :eid, :ruc_prov, :razon_prov,
                :tipo_doc, :cod_doc, :clave, :numero_doc,
                :fecha_emision, :fecha_auth, :total,
                CAST(:items AS jsonb), CAST(:impuestos AS jsonb),
                :ded_renta, :cred_iva,
                CAST(:datos AS jsonb), :xml_path, 'XML', false
            ) RETURNING id
        """), {
            "eid":           emisor_id,
            "ruc_prov":      parsed["ruc_proveedor"],
            "razon_prov":    parsed["razon_social_proveedor"],
            "tipo_doc":      parsed["tipo_doc"],
            "cod_doc":       parsed["cod_doc"],
            "clave":         clave,
            "numero_doc":    parsed["numero_doc"],
            "fecha_emision": fecha_emision_parsed,
            "fecha_auth":    fecha_auth_parsed,
            "total":         parsed["importe_total"],
            "items":         json.dumps(parsed["items_detalle"], default=str),
            "impuestos":     json.dumps(parsed["impuestos_detalle"], default=str),
            "ded_renta":     parsed["deducible_renta"],
            "cred_iva":      parsed["credito_tributario_iva"],
            "datos":         json.dumps(parsed["datos"], default=str),
            "xml_path":      xml_path,
        })
        doc_id = res.scalar()

        await audit_log(
            db         = db,
            auth_data  = auth_data,
            accion     = "CREATE",
            entidad    = "doc_recibido",
            entidad_id = str(doc_id),
            detalle    = {
                "tipo_doc":   parsed["tipo_doc"],
                "numero_doc": parsed["numero_doc"],
                "proveedor":  parsed["razon_social_proveedor"],
                "total":      float(parsed["importe_total"]),
                "fuente":     "XML",
            },
            request    = request,
        )
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

    return {
        "ok":       True,
        "id":       str(doc_id),
        "tipo_doc": parsed["tipo_doc"],
        "numero":   parsed["numero_doc"],
        "proveedor": parsed["razon_social_proveedor"],
        "total":    parsed["importe_total"],
        "items":    len(parsed["items_detalle"]),
        "errores":  parsed["errores"],
        "mensaje":  "Documento registrado correctamente.",
    }

# =============================================================================
# GET / — Historial — sin cambios, solo lectura
# =============================================================================
@router.get("", summary="Historial de documentos recibidos")
async def historial_recibidos(
    auth_data:    dict         = Depends(verify_firebase_token),
    db:           AsyncSession = Depends(get_db),
    tipo_doc:     Optional[str] = Query(None),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin:    Optional[str] = Query(None),
    estado_pago:  Optional[str] = Query(None),
    limit:        int           = Query(50, le=100),
    offset:       int           = Query(0),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "documentos")

    hoy = date.today()
    fi  = date.fromisoformat(fecha_inicio) if fecha_inicio else hoy - timedelta(days=45)
    ff  = date.fromisoformat(fecha_fin)    if fecha_fin    else hoy
    if (ff - fi).days > 45:
        raise HTTPException(status_code=400, detail="El rango máximo es 45 días.")

    filtros = "WHERE emisor_id = :eid AND fecha_emision BETWEEN :fi AND :ff"
    params  = {"eid": emisor_id, "fi": fi, "ff": ff}
    if tipo_doc:
        filtros += " AND tipo_doc = :tipo_doc"
        params["tipo_doc"] = tipo_doc.upper()
    if estado_pago:
        filtros += " AND estado_pago = :estado_pago"
        params["estado_pago"] = estado_pago.upper()
    params["limit"]  = limit
    params["offset"] = offset

    res = await db.execute(text(f"""
        SELECT
            id, ruc_proveedor, razon_social_proveedor,
            tipo_doc, cod_doc, numero_doc,
            fecha_emision, fecha_autorizacion,
            importe_total, impuestos_detalle, items_detalle,
            deducible_renta, credito_tributario_iva,
            estado_pago, forma_pago,
            numero_comprobante_pago, fecha_pago,
            notas, fuente, created_at
        FROM documentos_recibidos
        {filtros}
        ORDER BY fecha_emision DESC, created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    rows = res.fetchall()

    params_resumen = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    filtros_resumen = "WHERE emisor_id = :eid AND fecha_emision BETWEEN :fi AND :ff"
    if tipo_doc:
        filtros_resumen += " AND tipo_doc = :tipo_doc"
    if estado_pago:
        filtros_resumen += " AND estado_pago = :estado_pago"

    res_resumen = await db.execute(text(f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(importe_total), 0) AS importe_total,
            COALESCE(SUM(CASE WHEN deducible_renta THEN importe_total ELSE 0 END), 0) AS total_deducible,
            COALESCE((
                SELECT SUM((imp->>'valor')::numeric)
                FROM documentos_recibidos dr2,
                     jsonb_array_elements(dr2.impuestos_detalle) AS imp
                WHERE dr2.emisor_id = :eid AND dr2.fecha_emision BETWEEN :fi AND :ff
                AND (imp->>'aplicaCredito')::boolean = true
            ), 0) AS iva_credito_tributario,
            COALESCE((
                SELECT json_agg(json_build_object(
                    'tarifa', tarifa, 'subtotal', subtotal, 'iva', iva, 'con_credito', con_credito
                ) ORDER BY tarifa::numeric)
                FROM (
                    SELECT
                        (imp->>'tarifa') AS tarifa,
                        SUM((imp->>'baseImponible')::numeric) AS subtotal,
                        SUM((imp->>'valor')::numeric) AS iva,
                        SUM(CASE WHEN (imp->>'aplicaCredito')::boolean = true
                            THEN (imp->>'valor')::numeric ELSE 0 END) AS con_credito
                    FROM documentos_recibidos dr2,
                         jsonb_array_elements(dr2.impuestos_detalle) AS imp
                    WHERE dr2.emisor_id = :eid AND dr2.fecha_emision BETWEEN :fi AND :ff
                    GROUP BY (imp->>'tarifa')
                ) t
            ), '[]'::json) AS desglose_iva
        FROM documentos_recibidos {filtros_resumen}
    """), params_resumen)
    resumen_row = res_resumen.fetchone()

    return {
        "ok": True,
        "resumen": {
            "total_documentos":       int(resumen_row.total or 0),
            "importe_total":          float(resumen_row.importe_total or 0),
            "total_deducible":        float(resumen_row.total_deducible or 0),
            "iva_credito_tributario": float(resumen_row.iva_credito_tributario or 0),
            "desglose_iva":           resumen_row.desglose_iva or [],
        },
        "data": [
            {
                "id":                     str(r.id),
                "ruc_proveedor":          r.ruc_proveedor,
                "razon_social_proveedor": r.razon_social_proveedor,
                "tipo_doc":               r.tipo_doc,
                "numero_doc":             r.numero_doc,
                "fecha_emision":          str(r.fecha_emision),
                "importe_total":          float(r.importe_total),
                "impuestos_detalle":      r.impuestos_detalle or [],
                "items_detalle":          r.items_detalle or [],
                "deducible_renta":        r.deducible_renta,
                "credito_tributario_iva": r.credito_tributario_iva,
                "estado_pago":            r.estado_pago,
                "forma_pago":             r.forma_pago,
                "numero_comprobante_pago": r.numero_comprobante_pago,
                "fecha_pago":             str(r.fecha_pago) if r.fecha_pago else None,
                "notas":                  r.notas,
                "fuente":                 r.fuente,
                "created_at":             str(r.created_at),
            }
            for r in rows
        ],
        "periodo": {"desde": str(fi), "hasta": str(ff)},
    }

# =============================================================================
# GET /{id} — Detalle — solo lectura
# =============================================================================
@router.get("/{doc_id}", summary="Detalle de documento recibido")
async def detalle_recibido(
    doc_id:    str,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "documentos")

    res = await db.execute(text("""
        SELECT d.*,
            (
                SELECT json_build_object(
                    'id', de.id, 'numero_doc', de.numero_doc,
                    'estado_sri', de.estado_sri, 'clave_acceso', de.clave_acceso
                )
                FROM documentos_emitidos de
                WHERE de.doc_origen_recibido_id = d.id
                AND de.tipo_doc = 'RET' AND d.tipo_doc IN ('FAC', 'LIQ')
                LIMIT 1
            ) AS retencion_emitida
        FROM documentos_recibidos d
        WHERE d.id = :did AND d.emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})
    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    return {
        "ok": True,
        "data": {
            "id":                     str(doc.id),
            "ruc_proveedor":          doc.ruc_proveedor,
            "razon_social_proveedor": doc.razon_social_proveedor,
            "tipo_doc":               doc.tipo_doc,
            "cod_doc":                doc.cod_doc,
            "clave_acceso":           doc.clave_acceso,
            "numero_doc":             doc.numero_doc,
            "fecha_emision":          str(doc.fecha_emision),
            "fecha_autorizacion":     str(doc.fecha_autorizacion) if doc.fecha_autorizacion else None,
            "importe_total":          float(doc.importe_total),
            "impuestos_detalle":      doc.impuestos_detalle or [],
            "items_detalle":          doc.items_detalle or [],
            "deducible_renta":        doc.deducible_renta,
            "credito_tributario_iva": doc.credito_tributario_iva,
            "notas":                  doc.notas,
            "estado_pago":            doc.estado_pago,
            "forma_pago":             doc.forma_pago,
            "numero_comprobante_pago": doc.numero_comprobante_pago,
            "fecha_pago":             str(doc.fecha_pago) if doc.fecha_pago else None,
            "datos":                  doc.datos,
            "xml_path":               doc.xml_path,
            "fuente":                 doc.fuente,
            "created_at":             str(doc.created_at),
            "retencion_emitida":      doc.retencion_emitida,
        }
    }

# =============================================================================
# PATCH /{id}
# =============================================================================
@router.patch("/{doc_id}", summary="Actualizar documento recibido")
async def actualizar_recibido(
    doc_id:    str,
    data:      DocumentoRecibidoUpdate,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "documentos")

    res = await db.execute(text("""
        SELECT id FROM documentos_recibidos WHERE id = :did AND emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    campos = []
    params = {"did": doc_id, "eid": emisor_id}

    if data.deducible_renta is not None:
        campos.append("deducible_renta = :ded_renta"); params["ded_renta"] = data.deducible_renta
    if data.credito_tributario_iva is not None:
        campos.append("credito_tributario_iva = :cred_iva"); params["cred_iva"] = data.credito_tributario_iva
    if data.notas is not None:
        campos.append("notas = :notas"); params["notas"] = data.notas
    if data.impuestos_detalle is not None:
        campos.append("impuestos_detalle = CAST(:impuestos AS jsonb)")
        params["impuestos"] = json.dumps([i.model_dump() for i in data.impuestos_detalle], default=str)
    if data.items_detalle is not None:
        campos.append("items_detalle = CAST(:items AS jsonb)")
        params["items"] = json.dumps(data.items_detalle, default=str)
        params["ded_renta_calc"] = any(i.get("deducible_renta", False) for i in data.items_detalle)
        params["cred_iva_calc"]  = any(i.get("credito_tributario_iva", False) for i in data.items_detalle)
        campos.append("deducible_renta = :ded_renta_calc")
        campos.append("credito_tributario_iva = :cred_iva_calc")
    if data.estado_pago is not None:
        estados_validos = ("PENDIENTE", "PAGADO", "PARCIAL", "ANULADO")
        if data.estado_pago not in estados_validos:
            raise HTTPException(status_code=400, detail=f"estado_pago inválido.")
        campos.append("estado_pago = :estado_pago"); params["estado_pago"] = data.estado_pago
    if data.forma_pago is not None:
        campos.append("forma_pago = :forma_pago"); params["forma_pago"] = data.forma_pago
    if data.numero_comprobante_pago is not None:
        campos.append("numero_comprobante_pago = :num_comp"); params["num_comp"] = data.numero_comprobante_pago
    if data.fecha_pago is not None:
        campos.append("fecha_pago = :fecha_pago"); params["fecha_pago"] = data.fecha_pago
    if data.doc_origen_recibido_id is not None:
        campos.append("doc_origen_recibido_id = :doc_rec_id"); params["doc_rec_id"] = data.doc_origen_recibido_id
    if data.doc_origen_emitido_id is not None:
        campos.append("doc_origen_emitido_id = :doc_emi_id"); params["doc_emi_id"] = data.doc_origen_emitido_id

    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar.")

    campos.append("updated_at = NOW()")

    try:
        await db.execute(text(f"""
            UPDATE documentos_recibidos SET {', '.join(campos)}
            WHERE id = :did AND emisor_id = :eid
        """), params)

        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "UPDATE",
            entidad   = "doc_recibido",
            entidad_id = doc_id,
            detalle   = data.model_dump(exclude_none=True),
            request   = request,
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

    return {"ok": True, "mensaje": "Documento actualizado correctamente."}