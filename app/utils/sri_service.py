# app/utils/sri_service.py
import json
import base64
import httpx
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate
from app.services.cliente_service import crear_cliente_core
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso, decrypt_password
from app.services.storage_service import upload_file, download_file, delete_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado
from app.core.database import get_redis
import pytz

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

URLS_SRI = {
    "1": {  # Pruebas
        "recepcion":    "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    },
    "2": {  # Producción
        "recepcion":    "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    }
}

NODE_SIGNER_URL       = "http://kipu_signer_node:3000/api/firmar"
NODE_PDF_URL          = "http://kipu_signer_node:3000/api/pdf"
SEMAFORO_KEY          = "kipu:semaforo:facturas_activas"
QUEUE_FACTURAS        = "kipu:queue:facturas_sri"
MAX_FACTURAS_SIMULTANEAS = 10


# =============================================================================
# HELPERS DE SEMÁFORO Y COLA
# =============================================================================

async def semaforo_adquirir(redis) -> bool:
    """
    Intenta adquirir un slot de procesamiento.
    Retorna True si hay capacidad, False si el servidor está saturado.
    """
    activas = await redis.incr(SEMAFORO_KEY)
    if activas > MAX_FACTURAS_SIMULTANEAS:
        await redis.decr(SEMAFORO_KEY)
        return False
    await redis.expire(SEMAFORO_KEY, 60)  # auto-expirar por si un request muere
    return True


async def semaforo_liberar(redis) -> None:
    """Libera el slot al terminar el procesamiento."""
    await redis.decr(SEMAFORO_KEY)


async def queue_push(redis, factura_id: str, emisor_id: int, xml_path: str, ambiente: int) -> None:
    """Encola una factura para ser procesada por el worker del SRI."""
    payload = json.dumps({
        "factura_id": factura_id,
        "emisor_id":  emisor_id,
        "xml_path":   xml_path,
        "ambiente":   ambiente,
        "retries":    0,
        "queued_at":  datetime.utcnow().isoformat()
    })
    await redis.rpush(QUEUE_FACTURAS, payload)


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

async def emitir_factura_core(factura_data: dict, emisor_id: int, db: AsyncSession):

    if not factura_data.get("establecimiento") or not factura_data.get("punto_emision"):
        raise HTTPException(status_code=400, detail="Los campos 'establecimiento' y 'punto_emision' son requeridos.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 0: Resolución de identidad del cliente
    # ─────────────────────────────────────────────────────────────
    cliente_id  = factura_data.get("cliente_id")
    cliente_obj = factura_data.get("cliente")

    cliente_emisor_id = None
    cliente_final = {
        "identificacion": None,
        "razon_social":   None,
        "email":          None,
        "direccion":      "S/N",
        "telefono":       "",
        "tipo_id":        "05"
    }

    if cliente_id and str(cliente_id).strip() != "":
        res_cli = await db.execute(text("""
            SELECT id, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono
            FROM clientes_emisor
            WHERE id = :cid AND emisor_id = :eid
        """), {"cid": cliente_id, "eid": emisor_id})
        row_cli = res_cli.fetchone()

        if row_cli:
            cliente_emisor_id             = row_cli.id
            cliente_final["identificacion"] = row_cli.identificacion
            cliente_final["razon_social"]   = row_cli.razon_social
            cliente_final["email"]          = row_cli.email
            cliente_final["direccion"]      = row_cli.direccion
            cliente_final["telefono"]       = row_cli.telefono
            cliente_final["tipo_id"]        = row_cli.tipo_identificacion_sri
        else:
            raise HTTPException(status_code=404, detail="El 'cliente_id' proporcionado no existe.")

    elif cliente_obj:
        cliente_final["identificacion"] = cliente_obj.get("identificacion")
        cliente_final["razon_social"]   = cliente_obj.get("razonSocial") or cliente_obj.get("nombre")
        cliente_final["email"]          = cliente_obj.get("email")
        cliente_final["direccion"]      = cliente_obj.get("direccion", "S/N")
        cliente_final["telefono"]       = cliente_obj.get("telefono", "")
        cliente_final["tipo_id"]        = cliente_obj.get("tipoId") or cliente_obj.get("tipo_id") or "05"

        try:
            nuevo_cliente = ClienteCreate(
                tipo_identificacion_sri = cliente_final["tipo_id"],
                identificacion          = cliente_final["identificacion"],
                razon_social            = cliente_final["razon_social"],
                direccion               = cliente_final["direccion"],
                email                   = cliente_final["email"] or "",
                telefono                = cliente_final["telefono"] or ""
            )
            res_creacion      = await crear_cliente_core(emisor_id, nuevo_cliente, db, lanzar_error_si_existe=False)
            cliente_emisor_id = res_creacion.get("uid")
        except Exception as e_cli:
            print(f"⚠️ Cliente no persistido, modo invitado: {e_cli}")

    if not cliente_final["identificacion"]:
        raise HTTPException(status_code=400, detail="Debe proporcionar un 'cliente_id' válido o un objeto 'cliente' completo.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 1: DB — validar créditos, obtener punto, generar datos
    # ─────────────────────────────────────────────────────────────
    try:
        # 1. Obtener emisor y bloquear créditos (FOR UPDATE evita race conditions)
        res_emisor = await db.execute(text("""
            SELECT e.*, c.balance_emision
            FROM emisores e
            JOIN user_credits c ON e.id = c.emisor_id
            WHERE e.id = :emisor_id FOR UPDATE
        """), {"emisor_id": emisor_id})
        emisor = res_emisor.fetchone()

        if not emisor or emisor.balance_emision <= 0:
            raise HTTPException(status_code=402, detail="Créditos insuficientes.")

        # 2. Obtener punto de emisión
        res_pto = await db.execute(text("""
            SELECT p.id as punto_id, p.codigo as punto_codigo,
                   e.codigo as estab_codigo,
                   e.direccion as direccion_establecimiento,
                   e.nombre_comercial as nombre_establecimiento
            FROM puntos_emision p
            JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE e.codigo = :estab AND p.codigo = :pto AND e.emisor_id = :emisor_id
        """), {
            "estab":     str(factura_data["establecimiento"]).zfill(3),
            "pto":       str(factura_data["punto_emision"]).zfill(3),
            "emisor_id": emisor_id
        })
        punto_emision = res_pto.fetchone()

        if not punto_emision:
            raise HTTPException(status_code=404, detail="Establecimiento y Punto no existen o no te pertenecen.")

        # 3. Secuencial atómico
        res_sec    = await db.execute(text("SELECT generar_secuencial(:pto_id)"), {"pto_id": punto_emision.punto_id})
        secuencial = str(res_sec.scalar()).zfill(9)

        # 4. Fechas y cálculos
        tz              = pytz.timezone('America/Guayaquil')
        ahora_ecuador   = datetime.now(tz)
        fecha_formato_clave = ahora_ecuador.strftime('%Y-%m-%d')
        fecha_formato_sri   = ahora_ecuador.strftime('%d/%m/%Y')

        calculos     = calcular_totales_e_impuestos(factura_data.get("items", []))
        clave_acceso = generar_clave_acceso(
            fecha             = fecha_formato_clave,
            tipo_comprobante  = '01',
            ruc               = emisor.ruc,
            ambiente          = emisor.ambiente,
            serie             = f"{punto_emision.estab_codigo}{punto_emision.punto_codigo}",
            secuencial        = secuencial
        )

        nombre_comercial_final = punto_emision.nombre_establecimiento or emisor.nombre_comercial or emisor.razon_social
        direccion_est_final    = punto_emision.direccion_establecimiento or emisor.direccion_matriz

        # 5. Construir XML object para Node.js
        xml_obj = {
            "factura": {
                "@id":      "comprobante",
                "@version": "1.1.0",
                "infoTributaria": {
                    "ambiente":        emisor.ambiente,
                    "tipoEmision":     "1",
                    "razonSocial":     emisor.razon_social,
                    "nombreComercial": nombre_comercial_final,
                    "ruc":             emisor.ruc,
                    "claveAcceso":     clave_acceso,
                    "codDoc":          "01",
                    "estab":           punto_emision.estab_codigo,
                    "ptoEmi":          punto_emision.punto_codigo,
                    "secuencial":      secuencial,
                    "dirMatriz":       emisor.direccion_matriz
                },
                "infoFactura": {
                    "fechaEmision":                 fecha_formato_sri,
                    "dirEstablecimiento":           direccion_est_final,
                    "obligadoContabilidad":         getattr(emisor, 'obligado_contabilidad', 'NO'),
                    "tipoIdentificacionComprador":  cliente_final["tipo_id"],
                    "razonSocialComprador":         cliente_final["razon_social"],
                    "identificacionComprador":      cliente_final["identificacion"],
                    "totalSinImpuestos":            calculos["totales"]["totalSinImpuestos"],
                    "totalDescuento":               calculos["totales"]["totalDescuento"],
                    "totalConImpuestos":            {"totalImpuesto": calculos["totalConImpuestosXml"]},
                    "propina":                      "0.00",
                    "importeTotal":                 calculos["totales"]["importeTotal"],
                    "moneda":                       "DOLAR",
                    "pagos": {
                        "pago": [{
                            "formaPago":    p.get("forma_pago", p.get("formaPago", "01")),
                            "total":        f"{float(p['total']):.2f}",
                            "plazo":        p.get("plazo", "0"),
                            "unidadTiempo": p.get("unidad_tiempo", p.get("unidadTiempo", "dias"))
                        } for p in factura_data.get("pagos", [])]
                    }
                },
                "detalles": {
                    "detalle": calculos["detallesXml"]
                }
            }
        }


    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ Error en Bloque 1: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bloque 1 Error: {str(e)}")
    
    # ─────────────────────────────────────────────────────────────
    # BLOQUE 2: Firmar XML en Node.js
    # ─────────────────────────────────────────────────────────────
    try:
        # Descargar P12 desde storage (MinIO hoy, R2 después — misma interfaz)
        p12_bytes  = download_file(emisor.p12_path)
        p12_base64 = base64.b64encode(p12_bytes).decode('utf-8')

        async with httpx.AsyncClient() as client:
            res_node = await client.post(
                NODE_SIGNER_URL,
                json={
                    "xmlObj":  xml_obj,
                    "emisor": {
                        "p12_pass":    decrypt_password(emisor.p12_pass),
                        "ruc":         emisor.ruc,
                        "razon_social": emisor.razon_social,
                        "ambiente":    emisor.ambiente
                    },
                    "p12Base64": p12_base64
                },
                timeout=25.0
            )

        signer_data = res_node.json()
        if not signer_data.get("ok"):
            raise ValueError(f"Node Error: {signer_data.get('error')}")

        xml_firmado_str = signer_data["xmlFirmado"]

    except Exception as e:
        await db.rollback()
        print(f"❌ Error en Bloque 1: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bloque 2 Error: {str(e)}")
    
    # ─────────────────────────────────────────────────────────────
    # BLOQUE 3: Guardar XML firmado, descontar crédito, INSERT factura
    # ─────────────────────────────────────────────────────────────
    xml_firmado_path  = None
    factura_id        = None
    factura_notificar = None

    try:
        # Path del XML firmado (temporal — se reemplaza por el autorizado)
        xml_firmado_path = f"{emisor.ruc}/facturas/{ahora_ecuador.year}/{ahora_ecuador.month:02d}/{clave_acceso}_firmado.xml"

        # 1. Subir XML firmado al storage
        upload_file(xml_firmado_path, xml_firmado_str.encode('utf-8'), "text/xml")

        # 2. Descontar crédito
        await db.execute(text("""
            UPDATE public.user_credits
            SET balance_emision = balance_emision - 1
            WHERE emisor_id = :eid
        """), {"eid": emisor_id})

        # 3. INSERT factura — sin pdf_path (PDF bajo demanda)
        res_insert = await db.execute(text("""
            INSERT INTO invoices_emitidas (
                emisor_id, punto_emision_id, cliente_emisor_id,
                secuencial, fecha_emision, clave_acceso, estado,
                identificacion_comprador, razon_social_comprador,
                importe_total, subtotal_iva, subtotal_0, valor_iva,
                xml_path, pdf_path, datos_factura, email_comprador
            ) VALUES (
                :emisor_id, :pto_id, :cliente_emisor_id,
                :sec, :fecha, :clave, 'FIRMADO',
                :id_comp, :razon_comp,
                :total, :sub_iva, :sub_0, :val_iva,
                :xml_path, NULL, :datos_fac, :email_comp
            ) RETURNING id
        """), {
            "emisor_id":        emisor_id,
            "pto_id":           punto_emision.punto_id,
            "cliente_emisor_id": cliente_emisor_id,
            "sec":              secuencial,
            "fecha":            ahora_ecuador.date(),
            "clave":            clave_acceso,
            "id_comp":          cliente_final["identificacion"],
            "razon_comp":       cliente_final["razon_social"],
            "email_comp":       cliente_final["email"],
            "total":            calculos["totales"]["importeTotal"],
            "sub_iva":          calculos["totales"]["subtotal_iva"],
            "sub_0":            calculos["totales"]["subtotal_0"],
            "val_iva":          calculos["totales"]["totalIva"],
            "xml_path":         xml_firmado_path,
            "datos_fac":        json.dumps(xml_obj["factura"])
        })

        factura_id = res_insert.scalar()
        await db.commit()

        # Datos para notificaciones y correos
        factura_notificar = {
            "id":                     str(factura_id),
            "clave_acceso":           clave_acceso,
            "email_comprador":        cliente_final["email"],
            "razon_social_comprador": cliente_final["razon_social"],
            "secuencial":             secuencial,
            "importe_total":          calculos["totales"]["importeTotal"],
            "xml_firmado_path":       xml_firmado_path,
            "ambiente":               emisor.ambiente,
            "ruc":                    emisor.ruc,
            "emisor_db_id":           str(emisor_id),
            "razon_social":           emisor.razon_social
        }

    except Exception as e:
        await db.rollback()
        print(f"❌ Error en Bloque 1: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bloque 3 Error: {str(e)}")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 4: ¿Flujo híbrido o cola?
    #
    # Si hay capacidad → intentar autorizar ahora (fast-track)
    # Si no hay capacidad → encolar para el worker
    # En ambos casos el worker recoge lo que no se autorizó
    # ─────────────────────────────────────────────────────────────
    res_tenant = await db.execute(text("""
        SELECT tenant_schema FROM public.emisor_tenant_map
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    tenant_row = res_tenant.fetchone()
    if tenant_row:
        await db.execute(text(f"SET search_path TO {tenant_row.tenant_schema}, public"))

    redis         = await get_redis()
    hay_capacidad = await semaforo_adquirir(redis)
    estado_final  = "FIRMADO"

    if hay_capacidad:
        try:
            urls    = URLS_SRI[str(emisor.ambiente)]
            xml_b64 = base64.b64encode(xml_firmado_str.encode('utf-8')).decode('utf-8')

            async with httpx.AsyncClient(timeout=10.0) as client_sri:

                # ── Recepción ──────────────────────────────────────
                soap_rec = (
                    f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                    f'xmlns:ec="http://ec.gob.sri.ws.recepcion">'
                    f'<soapenv:Body><ec:validarComprobante><xml>{xml_b64}</xml>'
                    f'</ec:validarComprobante></soapenv:Body></soapenv:Envelope>'
                )
                res_rec = await client_sri.post(
                    urls["recepcion"], content=soap_rec, headers={"Content-Type": "text/xml"}
                )

                if "RECIBIDA" in res_rec.text:
                    await db.execute(text("""
                        UPDATE invoices_emitidas
                        SET estado = 'RECIBIDA', fecha_envio_sri = NOW()
                        WHERE id = :fid
                    """), {"fid": factura_id})
                    await db.commit()

                    # Re-setear después del commit
                    if tenant_row:
                        await db.execute(text(f"SET search_path TO {tenant_row.tenant_schema}, public"))

                    await notificar_cambio_estado(factura_notificar, "RECIBIDA")

                    # ── Autorización (3 intentos rápidos) ──────────
                    soap_auth = (
                        f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                        f'xmlns:ec="http://ec.gob.sri.ws.autorizacion">'
                        f'<soapenv:Body><ec:autorizacionComprobante>'
                        f'<claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante>'
                        f'</ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>'
                    )

                    for pausa in [1.2, 1.8, 2.5]:
                        await asyncio.sleep(pausa)
                        try:
                            res_auth = await client_sri.post(
                                urls["autorizacion"], content=soap_auth, headers={"Content-Type": "text/xml"}
                            )

                            if "AUTORIZADO" in res_auth.text and "NO AUTORIZADO" not in res_auth.text:
                                root_auth      = ET.fromstring(res_auth.text)
                                auth_node      = root_auth.find(".//autorizacion")
                                fecha_auth     = None
                                xml_autorizado = xml_firmado_str

                                if auth_node is not None:
                                    fecha_auth     = auth_node.findtext("fechaAutorizacion")
                                    xml_autorizado = auth_node.findtext("comprobante") or xml_firmado_str

                                xml_auth_path = (
                                    f"{emisor.ruc}/facturas/"
                                    f"{ahora_ecuador.year}/{ahora_ecuador.month:02d}/"
                                    f"{clave_acceso}.xml"
                                )
                                upload_file(xml_auth_path, xml_autorizado.encode('utf-8'), "text/xml")

                                try:
                                    delete_file(xml_firmado_path)
                                except Exception:
                                    pass

                                # Re-setear antes del UPDATE
                                if tenant_row:
                                    await db.execute(text(f"SET search_path TO {tenant_row.tenant_schema}, public"))

                                await db.execute(text("""
                                    UPDATE invoices_emitidas
                                    SET estado             = 'AUTORIZADO',
                                        xml_path          = :xml_path,
                                        pdf_path          = NULL,
                                        fecha_autorizacion = NOW()
                                    WHERE id = :fid
                                """), {"xml_path": xml_auth_path, "fid": factura_id})
                                await db.commit()
                                await notificar_cambio_estado(factura_notificar, "AUTORIZADO")

                                if factura_notificar.get("email_comprador"):
                                    await mail_service.send_mail(
                                        to=factura_notificar["email_comprador"],
                                        subject=f"Factura Electrónica - {emisor.razon_social} - {secuencial}",
                                        html_content=(
                                            f"<h2>Su factura ha sido autorizada ✅</h2>"
                                            f"<p>Estimado/a {cliente_final['razon_social']},</p>"
                                            f"<p>Su comprobante <strong>{secuencial}</strong> "
                                            f"ha sido autorizado por el SRI.</p>"
                                            f"<p><a href='https://kipu.ec/facturas/{clave_acceso}'>"
                                            f"Ver y descargar factura</a></p>"
                                        )
                                    )

                                estado_final = "AUTORIZADO"
                                print(f"[FAST-TRACK] ⭐ AUTORIZADO: {clave_acceso}")
                                break

                        except Exception:
                            continue

                    if estado_final != "AUTORIZADO":
                        estado_final = "RECIBIDA"

                elif "DEVUELTA" in res_rec.text:
                    root_res      = ET.fromstring(res_rec.text)
                    lista_errores = [
                        {
                            "identificador":        msg.findtext("identificador"),
                            "mensaje":              msg.findtext("mensaje"),
                            "informacionAdicional": msg.findtext("informacionAdicional"),
                            "tipo":                 msg.findtext("tipo")
                        }
                        for msg in root_res.findall(".//mensaje")
                    ]

                    try:
                        delete_file(xml_firmado_path)
                    except Exception:
                        pass

                    # Re-setear antes del UPDATE
                    if tenant_row:
                        await db.execute(text(f"SET search_path TO {tenant_row.tenant_schema}, public"))

                    await db.execute(text("""
                        UPDATE invoices_emitidas
                        SET estado       = 'DEVUELTA',
                            mensajes_sri = :msg,
                            xml_path     = NULL
                        WHERE id = :fid
                    """), {"msg": json.dumps(lista_errores), "fid": factura_id})

                    await db.execute(text("""
                        UPDATE public.user_credits
                        SET balance_emision = balance_emision + 1
                        WHERE emisor_id = :eid
                    """), {"eid": emisor_id})

                    await db.commit()
                    await notificar_cambio_estado(factura_notificar, "DEVUELTA")
                    estado_final = "DEVUELTA"

                else:
                    estado_final = "FIRMADO"

        except Exception as e:
            print(f"[FAST-TRACK] ℹ️ SRI timeout para {clave_acceso}: {str(e)}")
            estado_final = "FIRMADO"

        finally:
            await semaforo_liberar(redis)

    else:
        await queue_push(redis, str(factura_id), emisor_id, xml_firmado_path, emisor.ambiente)
        estado_final = "FIRMADO"
        print(f"[Cola] Factura encolada por saturación: {clave_acceso}")

    # ─────────────────────────────────────────────────────────────
    # RESPUESTA FINAL
    # ─────────────────────────────────────────────────────────────
    return {
        "ok":          True,
        "id":          str(factura_id),
        "claveAcceso": clave_acceso,
        "estado":      estado_final,
        "mensaje":     "Factura autorizada exitosamente." if estado_final == "AUTORIZADO"
                       else "Comprobante recibido. Será autorizado en breve."
    }
