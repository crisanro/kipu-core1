import json
import base64
import httpx
import asyncio
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate
from app.services.cliente_service import crear_cliente_core
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso, decrypt_password
from app.services.storage_service import upload_file, download_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado
import pytz

# URLs de los Web Services del SRI
URLS_SRI = {
    "1": { # Pruebas
        "recepcion": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    },
    "2": { # Producción
        "recepcion": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    }
}

# ⚠️ Cambia esta URL si tu microservicio de Node corre en otro host/puerto
NODE_SIGNER_URL = "http://localhost:3000/api/firmar"

async def emitir_factura_core(factura_data: dict, emisor_id: int, db: AsyncSession):
    if not factura_data.get("establecimiento") or not factura_data.get("punto_emision"):
        raise HTTPException(status_code=400, detail="Los campos 'establecimiento' y 'punto_emision' son requeridos.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 0: Resolución del Cliente (UID vs Objeto)
    # ─────────────────────────────────────────────────────────────
    cliente_id = factura_data.get("cliente_id")
    cliente_obj = factura_data.get("cliente")
    
    cliente_emisor_id = None
    cliente_data_final = {}

    if cliente_id:
        # Si mandaron el ID, lo buscamos en la base de datos
        query_cli = text("""
            SELECT id, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono 
            FROM clientes_emisor 
            WHERE id = :cid AND emisor_id = :eid
        """)
        res_cli = await db.execute(query_cli, {"cid": cliente_id, "eid": emisor_id})
        row_cli = res_cli.fetchone()
        
        if not row_cli:
            raise HTTPException(status_code=404, detail="El 'cliente_id' proporcionado no existe en su base de datos.")
            
        cliente_emisor_id = row_cli.id
        cliente_data_final = {
            "tipoId": row_cli.tipo_identificacion_sri,
            "identificacion": row_cli.identificacion,
            "nombre": row_cli.razon_social, # Node usa "nombre" o "razonSocial"
            "direccion": row_cli.direccion,
            "email": row_cli.email,
            "telefono": row_cli.telefono
        }
        
    elif cliente_obj:
        # Si NO mandaron el ID, usamos la función core para crearlo (o recuperar su ID si ya existe)
        identificacion_buscada = cliente_obj.get("identificacion")
        if not identificacion_buscada:
            raise HTTPException(status_code=400, detail="El objeto cliente debe contener la 'identificacion'.")
            
        nuevo_cliente = ClienteCreate(
            tipo_identificacion_sri=cliente_obj.get("tipoId", "05"),
            identificacion=cliente_obj.get("identificacion"),
            razon_social=cliente_obj.get("razonSocial") or cliente_obj.get("nombre"),
            direccion=cliente_obj.get("direccion", "S/N"),
            email=cliente_obj.get("email", ""),
            telefono=cliente_obj.get("telefono", "")
        )
        
        # Llamamos a tu servicio de clientes (Le decimos: False -> No lances error si existe)
        res_creacion = await crear_cliente_core(emisor_id, nuevo_cliente, db, lanzar_error_si_existe=False)
        
        cliente_emisor_id = res_creacion["uid"]
        cliente_data_final = cliente_obj # Usamos los datos crudos para armar el XML
        
    else:
        raise HTTPException(status_code=400, detail="Debe proporcionar 'cliente_id' o el objeto 'cliente'.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 1: Base de Datos y Generación de Datos (Transacción)
    # ─────────────────────────────────────────────────────────────
    try:
        # 1. Obtener emisor y bloquear créditos (FOR UPDATE)
        query_emisor = text("""
            SELECT e.*, c.balance 
            FROM emisores e 
            JOIN user_credits c ON e.id = c.emisor_id 
            WHERE e.id = :emisor_id FOR UPDATE
        """)
        res_emisor = await db.execute(query_emisor, {"emisor_id": emisor_id})
        emisor = res_emisor.fetchone()

        if not emisor or emisor.balance <= 0:
            raise HTTPException(status_code=402, detail="Créditos insuficientes.")

        # 2. Obtener punto de emisión
        query_pto = text("""
            SELECT p.id as punto_id, p.codigo as punto_codigo, e.codigo as estab_codigo, 
                   e.direccion as direccion_establecimiento, e.nombre_comercial as nombre_establecimiento
            FROM puntos_emision p
            JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE e.codigo = :estab AND p.codigo = :pto AND e.emisor_id = :emisor_id
        """)
        res_pto = await db.execute(query_pto, {
            "estab": str(factura_data["establecimiento"]).zfill(3),
            "pto": str(factura_data["punto_emision"]).zfill(3),
            "emisor_id": emisor_id
        })
        punto_emision = res_pto.fetchone()

        if not punto_emision:
            raise HTTPException(status_code=404, detail="Establecimiento y Punto no existen o no te pertenecen.")

        # 3. Generar secuencial atómico
        res_sec = await db.execute(text("SELECT generar_secuencial(:pto_id)"), {"pto_id": punto_emision.punto_id})
        secuencial_raw = res_sec.scalar()
        if not secuencial_raw:
            raise ValueError(f"Secuencial nulo para el punto {punto_emision.punto_id}.")
        secuencial = str(secuencial_raw).zfill(9)

        # 4. Fechas y Cálculos
        tz = pytz.timezone('America/Guayaquil')
        ahora_ecuador = datetime.now(tz)
        fecha_formato_clave = ahora_ecuador.strftime('%Y-%m-%d')
        fecha_formato_sri = ahora_ecuador.strftime('%d/%m/%Y')

        calculos = calcular_totales_e_impuestos(factura_data.get("items", []))
        
        clave_acceso = generar_clave_acceso(
            fecha=fecha_formato_clave, tipo_comprobante='01', ruc=emisor.ruc, 
            ambiente=emisor.ambiente, serie=f"{punto_emision.estab_codigo}{punto_emision.punto_codigo}", 
            secuencial=secuencial
        )

        nombre_comercial_final = punto_emision.nombre_establecimiento or emisor.nombre_comercial or emisor.razon_social
        direccion_est_final = punto_emision.direccion_establecimiento or emisor.direccion_matriz
        
        cliente_data = factura_data.get("cliente", {})
        
        # 5. Construir objeto XML para Node.js
        xml_obj = {
            "factura": {
                "@id": "comprobante",
                "@version": "1.1.0",
                "infoTributaria": {
                    "ambiente": emisor.ambiente,
                    "tipoEmision": "1",
                    "razonSocial": emisor.razon_social,
                    "nombreComercial": nombre_comercial_final,
                    "ruc": emisor.ruc,
                    "claveAcceso": clave_acceso,
                    "codDoc": "01",
                    "estab": punto_emision.estab_codigo,
                    "ptoEmi": punto_emision.punto_codigo,
                    "secuencial": secuencial,
                    "dirMatriz": emisor.direccion_matriz
                },
                "infoFactura": {
                    "fechaEmision": fecha_formato_sri,
                    "dirEstablecimiento": direccion_est_final,
                    "obligadoContabilidad": getattr(emisor, 'obligado_contabilidad', 'NO'),
                    "tipoIdentificacionComprador": cliente_data.get("tipo_id", cliente_data.get("tipoId")),
                    "razonSocialComprador": cliente_data.get("nombre", cliente_data.get("razonSocial")),
                    "identificacionComprador": cliente_data.get("identificacion"),
                    "totalSinImpuestos": calculos["totales"]["totalSinImpuestos"],
                    "totalDescuento": calculos["totales"]["totalDescuento"],
                    "totalConImpuestos": {"totalImpuesto": calculos["totalConImpuestosXml"]},
                    "propina": "0.00",
                    "importeTotal": calculos["totales"]["importeTotal"],
                    "moneda": "DOLAR",
                    "pagos": {
                        "pago": [{
                            "formaPago": p.get("forma_pago", p.get("formaPago", "01")),
                            "total": f"{float(p['total']):.2f}",
                            "plazo": p.get("plazo", "0"),
                            "unidadTiempo": p.get("unidad_tiempo", p.get("unidadTiempo", "dias"))
                        } for p in factura_data.get("pagos", [])]
                    }
                },
                "detalles": {
                    "detalle": calculos["detallesXml"]
                }
            }
        }

        if factura_data.get("infoAdicional"):
            xml_obj["factura"]["infoAdicional"] = {
                "campoAdicional": [
                    {
                        "@nombre": info.get("nombre", ""),
                        "#text": info.get("valor", "")
                    }
                    for info in factura_data["infoAdicional"]
                ]
            }

        # 1. Corregir Impuestos de los Detalles (Ítems)
        for det in xml_obj["factura"]["detalles"]["detalle"]:
            # Forzar que 'impuesto' sea una lista
            if "impuestos" in det and "impuesto" in det["impuestos"]:
                imp = det["impuestos"]["impuesto"]
                det["impuestos"]["impuesto"] = imp if isinstance(imp, list) else [imp]

        # 2. Corregir Impuestos Globales (infoFactura)
        info_fac = xml_obj["factura"]["infoFactura"]
        if "totalConImpuestos" in info_fac and "totalImpuesto" in info_fac["totalConImpuestos"]:
            tot_imp = info_fac["totalConImpuestos"]["totalImpuesto"]
            info_fac["totalConImpuestos"]["totalImpuesto"] = tot_imp if isinstance(tot_imp, list) else [tot_imp]

        # 3. Validar Pagos (Asegurar que sea lista)
        if "pagos" in info_fac and "pago" in info_fac["pagos"]:
            pgs = info_fac["pagos"]["pago"]
            info_fac["pagos"]["pago"] = pgs if isinstance(pgs, list) else [pgs]
                # Soltamos el lock de la base de datos (Commit parcial)
        await db.commit()

    except Exception as e:
        await db.rollback()
        print(f"❌ Error en Bloque 1: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


    # ─────────────────────────────────────────────────────────────
    # BLOQUE 2: Hablar con el Microservicio de Node.js (Firma + PDF)
    # ─────────────────────────────────────────────────────────────
    print(f"📡 Iniciando Bloque 2 - Intentando conectar a: {NODE_SIGNER_URL}")
    
    try:
        # 1. Validación de existencia de firma
        if not emisor.p12_path:
            raise ValueError("El emisor no tiene configurada la ruta del archivo .p12 en la DB")

        # 2. Intento de descarga de MinIO
        try:
            print(f"File path en DB: {emisor.p12_path}")
            bucket_p12, *path_parts = emisor.p12_path.split('/')
            full_path_p12 = '/'.join(path_parts)
            p12_bytes = download_file(bucket_p12, full_path_p12)
            p12_base64 = base64.b64encode(p12_bytes).decode('utf-8')
            print("✅ Firma descargada de MinIO y convertida a Base64")
        except Exception as e_minio:
            raise ValueError(f"Error al descargar firma de MinIO: {str(e_minio)}")

        # 3. Petición HTTP al Signer
        async with httpx.AsyncClient() as client:
            print("📤 Enviando datos al microservicio de Node...")
            # DEBUG: Ver el JSON que va hacia Node
            #print("DEBUG - Objeto enviado a Node:")
            #print(json.dumps(xml_obj, indent=2))
            res_node = await client.post(
                NODE_SIGNER_URL,
                json={
                    "xmlObj": xml_obj,
                    "emisor": {
                        "p12_pass": decrypt_password(emisor.p12_pass), 
                        "ruc": emisor.ruc,
                        "razon_social": emisor.razon_social,
                        "ambiente": emisor.ambiente
                    },
                    "p12Base64": p12_base64
                },
                timeout=25.0 
            )
            
        # 4. Revisión de respuesta
        if res_node.status_code != 200:
            print(f"❌ Node respondió con error {res_node.status_code}: {res_node.text}")
            raise ValueError(f"El firmador devolvió un error: {res_node.text}")
            
        signer_data = res_node.json()
        if not signer_data.get("ok"):
            raise ValueError(f"Firmador Node dice: {signer_data.get('error')}")

        xml_firmado_str = signer_data["xmlFirmado"]
        pdf_bytes = base64.b64decode(signer_data["pdfBase64"])
        print("✅ XML Firmado y PDF recibidos correctamente")

    except Exception as e:
        # AQUÍ ESTÁ EL TRUCO: Imprimimos el error real en la consola de Python
        import traceback
        print("="*50)
        print("🚨 ERROR DETECTADO EN BLOQUE 2")
        traceback.print_exc() # Esto imprime el error real con la línea exacta
        print("="*50)
        
        # Devolvemos el error real al cliente (Swagger/Postman)
        raise HTTPException(
            status_code=500, 
            detail=f"Falla técnica en firma: {str(e)}"
        )


    # ─────────────────────────────────────────────────────────────
    # BLOQUE 3: Guardar en MinIO, descontar crédito e Insertar Factura
    # ─────────────────────────────────────────────────────────────
    try:
        xml_path_rel = f"{emisor.ruc}/{clave_acceso}.xml"
        pdf_path_rel = f"{emisor.ruc}/{clave_acceso}.pdf"

        # Subir a MinIO
        upload_file("invoices", xml_path_rel, xml_firmado_str.encode('utf-8'), "text/xml")
        upload_file("invoices", pdf_path_rel, pdf_bytes, "application/pdf")

        # Iniciar transacción final
        await db.execute(text("UPDATE user_credits SET balance = balance - 1 WHERE emisor_id = :eid"), {"eid": emisor_id})

        query_insert = text("""
            INSERT INTO invoices (
                emisor_id, punto_emision_id, cliente_emisor_id, secuencial, fecha_emision, clave_acceso,
                estado, identificacion_comprador, razon_social_comprador, importe_total,
                subtotal_iva, subtotal_0, valor_iva, xml_path, pdf_path, datos_factura,
                email_comprador
            ) VALUES (
                :emisor_id, :pto_id, :cliente_emisor_id, :sec, :fecha, :clave, 'FIRMADO', :id_comp, :razon_comp,
                :total, :sub_iva, :sub_0, :val_iva, :xml_path, :pdf_path, :datos_fac, :email_comp
            ) RETURNING id
        """)
        
        res_insert = await db.execute(query_insert, {
            "emisor_id": emisor_id, 
            "pto_id": punto_emision.punto_id, 
            "cliente_emisor_id": cliente_emisor_id, # <--- Se guarda la relación
            "sec": secuencial,
            "fecha": ahora_ecuador, 
            "clave": clave_acceso, 
            "id_comp": cliente_data.get("identificacion"),
            "razon_comp": cliente_data.get("nombre", cliente_data.get("razonSocial")),
            "total": calculos["totales"]["importeTotal"], 
            "sub_iva": calculos["totales"]["subtotal_iva"],
            "sub_0": calculos["totales"]["subtotal_0"], 
            "val_iva": calculos["totales"]["totalIva"],
            "xml_path": f"invoices/{xml_path_rel}", 
            "pdf_path": f"invoices/{pdf_path_rel}",
            "datos_fac": json.dumps(xml_obj["factura"]), 
            "email_comp": cliente_data.get("email")
        })
        
        factura_id = res_insert.scalar()
        await db.commit()

    except Exception as e:
        await db.rollback()
        print(f"❌ Error en Bloque 3: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 4: Fast-Track al SRI (Recepción y Autorización)
    # ─────────────────────────────────────────────────────────────
    # Esto corre después del COMMIT para asegurar que la factura ya existe en DB.
    # En FastAPI, idealmente esto se enviaría a una BackgroundTask, pero 
    # mantendremos el flujo síncrono para que devuelva el estado real al cliente.
    
    urls = URLS_SRI[str(emisor.ambiente)]
    xml_base64 = base64.b64encode(xml_firmado_str.encode('utf-8')).decode('utf-8')
    
    factura_notificar = {
        "id": str(factura_id), "clave_acceso": clave_acceso, "email_comprador": cliente_data.get("email"),
        "razon_social_comprador": cliente_data.get("nombre", cliente_data.get("razonSocial")),
        "secuencial": secuencial, "importe_total": calculos["totales"]["importeTotal"],
        "pdf_path": f"invoices/{pdf_path_rel}", "ambiente": emisor.ambiente,
        "ruc": emisor.ruc, "emisor_db_id": str(emisor_id), "razon_social": emisor.razon_social
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client_sri:
            # 1. RECEPCIÓN
            soap_rec = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.recepcion"><soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml></ec:validarComprobante></soapenv:Body></soapenv:Envelope>"""
            
            res_rec = await client_sri.post(urls["recepcion"], content=soap_rec, headers={"Content-Type": "text/xml"})
            
            # Simple parsing buscando RECIBIDA o DEVUELTA (usando string match para evitar XML Parser pesado si no es necesario)
            if "RECIBIDA" in res_rec.text:
                await db.execute(text("UPDATE invoices SET estado = 'RECIBIDA', fecha_envio_sri = NOW() WHERE id = :fid"), {"fid": factura_id})
                await db.commit()
                await notificar_cambio_estado(factura_notificar, "RECIBIDA")
                
                # 2. AUTORIZACIÓN (Pausas cortas)
                soap_auth = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion"><soapenv:Body><ec:autorizacionComprobante><claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante></ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>"""
                
                for pausa in [1.2, 1.8, 2.5]: # Segundos
                    await asyncio.sleep(pausa)
                    try:
                        res_auth = await client_sri.post(urls["autorizacion"], content=soap_auth, headers={"Content-Type": "text/xml"})
                        
                        if "AUTORIZADO" in res_auth.text and "NO AUTORIZADO" not in res_auth.text:
                            # 1. Extraer la Fecha y el XML Autorizado con ElementTree
                            import xml.etree.ElementTree as ET
                            root_auth = ET.fromstring(res_auth.text)
                            auth_node = root_auth.find(".//autorizacion")
                            
                            fecha_auth = None
                            xml_autorizado = xml_firmado_str # Fallback
                            
                            if auth_node is not None:
                                fecha_auth = auth_node.findtext("fechaAutorizacion")
                                xml_autorizado = auth_node.findtext("comprobante") or xml_firmado_str
                            
                            # 2. 🚀 PEDIR EL NUEVO PDF A NODE.JS
                            try:
                                res_pdf = await client_sri.post(
                                    NODE_SIGNER_URL.replace("/firmar", "/pdf"), # Cambia la ruta a /pdf
                                    json={
                                        "xmlAutorizado": xml_autorizado,
                                        "emisor": {"contribuyente_especial": getattr(emisor, 'contribuyente_especial', '')},
                                        "fechaAutorizacion": fecha_auth
                                    },
                                    timeout=15.0
                                )
                                if res_pdf.status_code == 200 and res_pdf.json().get("ok"):
                                    pdf_bytes = base64.b64decode(res_pdf.json()["pdfBase64"])
                                    # 3. Sobreescribir el PDF viejo en MinIO
                                    upload_file("invoices", pdf_path_rel, pdf_bytes, "application/pdf")
                            except Exception as e_pdf:
                                print(f"[FAST-TRACK] ⚠️ Error actualizando PDF en Node: {str(e_pdf)}")
                                # Si falla Node, enviamos el viejo que ya tenemos en memoria (pdf_bytes)

                            # 4. Actualizar BD
                            await db.execute(text("UPDATE invoices SET estado = 'AUTORIZADO', fecha_autorizacion = NOW() WHERE id = :fid"), {"fid": factura_id})
                            await db.commit()
                            await notificar_cambio_estado(factura_notificar, "AUTORIZADO")
                            
                            # 5. Enviar correo con el PDF ya actualizado
                            if factura_notificar["email_comprador"]:
                                await mail_service.send_mail(
                                    to=factura_notificar["email_comprador"],
                                    subject=f"Factura Electrónica - {emisor.razon_social} - {secuencial}",
                                    html_content=f"Su factura {secuencial} ha sido autorizada por el SRI.",
                                    attachments=[
                                        {"filename": f"{clave_acceso}.xml", "content": xml_autorizado.encode('utf-8'), "maintype": "text", "subtype": "xml"},
                                        {"filename": f"{clave_acceso}.pdf", "content": pdf_bytes, "maintype": "application", "subtype": "pdf"}
                                    ]
                                )
                            print(f"[FAST-TRACK] ⭐ ÉXITO: {clave_acceso}")
                            break
                            
                    except Exception as e:
                        continue # Reintentar siguiente ciclo
                        
            elif "DEVUELTA" in res_rec.text:
                # Extraer mensajes del XML de respuesta
                import xml.etree.ElementTree as ET
                root_res = ET.fromstring(res_rec.text)
                
                lista_errores = []
                # El SRI devuelve los errores en etiquetas <mensaje>
                for msg in root_res.findall(".//mensaje"):
                    lista_errores.append({
                        "identificador": msg.findtext("identificador"),
                        "mensaje": msg.findtext("mensaje"),
                        "informacionAdicional": msg.findtext("informacionAdicional"),
                        "tipo": msg.findtext("tipo")
                    })

                error_json = json.dumps(lista_errores)
                
                await db.execute(text(
                    "UPDATE invoices SET estado = 'DEVUELTA', mensajes_sri = :msg WHERE id = :fid"
                ), {"msg": error_json, "fid": factura_id})
                
                # Devolver crédito
                await db.execute(text(
                    "UPDATE user_credits SET balance = balance + 1 WHERE emisor_id = :eid"
                ), {"eid": emisor_id})
                
                await db.commit()
                await notificar_cambio_estado(factura_notificar, "DEVUELTA")

    except Exception as e:
        print(f"[FAST-TRACK] ℹ️ SRI asíncrono o timeout para {clave_acceso}: {str(e)}")

    # 5. Consulta final del estado
    final_state_res = await db.execute(text("SELECT estado FROM invoices WHERE id = :fid"), {"fid": factura_id})
    estado_final = final_state_res.scalar()

    return {
        "ok": True,
        "id": factura_id,
        "claveAcceso": clave_acceso,
        "estado": estado_final,
        "mensaje": "Factura autorizada exitosamente." if estado_final == 'AUTORIZADO' else "Comprobante en proceso."
    }


