import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate, ClienteUpdate

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def validar_documento_ecuador(documento: str):
    documento = documento.replace("-", "").replace(".", "").replace(" ", "").strip()
    
    if not documento.isdigit():
        return False, "El documento debe contener solo números.", ""
    
    if len(documento) not in [10, 13]:
        return False, "Longitud no válida (debe ser 10 o 13 dígitos).", ""
        
    provincia = int(documento[0:2])
    if provincia < 1 or provincia > 24:
        return False, f"Provincia '{documento[0:2]}' no existe.", ""
        
    tercer_digito = int(documento[2])
    
    def validar_modulo_10(id_str):
        digitos = [int(x) for x in id_str[:9]]
        verificador_recibido = int(id_str[9])
        suma = 0
        for i, val in enumerate(digitos):
            prod = val * 2 if i % 2 == 0 else val * 1
            if prod > 9: prod -= 9
            suma += prod
        residuo = suma % 10
        verificador_calculado = 0 if residuo == 0 else 10 - residuo
        return verificador_calculado == verificador_recibido

    def validar_modulo_11(id_str):
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        digitos = [int(x) for x in id_str[:9]]
        verificador_recibido = int(id_str[9])
        suma = sum([val * coeficientes[i] for i, val in enumerate(digitos)])
        residuo = suma % 11
        verificador_calculado = 0 if residuo == 0 else 11 - residuo
        return verificador_calculado == verificador_recibido

    # VALIDACIÓN CÉDULA (05)
    if len(documento) == 10:
        if tercer_digito < 6:
            if validar_modulo_10(documento):
                return True, "", "05"
            return False, "Número de cédula inválido.", ""
        return False, "Cédula inválida (tercer dígito incorrecto).", ""
        
    # VALIDACIÓN RUC (04)
    elif len(documento) == 13:
        if not documento.endswith("001"):
            return False, "El RUC debe terminar en 001.", ""
            
        if tercer_digito < 6: # Natural
            es_valido = validar_modulo_10(documento[:10])
        elif tercer_digito == 9: # Jurídica
            es_valido = validar_modulo_11(documento[:10])
        elif tercer_digito == 6: # Pública
            es_valido = True
        else:
            return False, "Tercer dígito de RUC inválido.", ""
            
        if es_valido:
            return True, "", "04"
        return False, "El número de RUC no es válido.", ""


# ==========================================
# 1. CREAR CLIENTE
# ==========================================
async def crear_cliente_core(emisor_id: int, cliente: ClienteCreate, db: AsyncSession, lanzar_error_si_existe: bool = True):
    try:
        # Verificación de duplicados
        query_check = text("SELECT id FROM clientes_emisor WHERE emisor_id = :eid AND identificacion = :ident")
        res_check = await db.execute(query_check, {"eid": emisor_id, "ident": cliente.identificacion})
        row_existente = res_check.fetchone()
        
        if row_existente:
            if lanzar_error_si_existe:
                raise HTTPException(status_code=400, detail="EL CLIENTE YA EXISTE EN SU BASE DE DATOS.")
            return {"ok": True, "mensaje": "CLIENTE YA EXISTÍA", "uid": str(row_existente.id)}

        # --- NORMALIZACIÓN A MAYÚSCULAS ---
        razon_social_up = cliente.razon_social.strip().upper() if cliente.razon_social else "CLIENTE SIN NOMBRE"
        direccion_up = cliente.direccion.strip().upper() if cliente.direccion else "SIN DIRECCION"
        email_low = cliente.email.strip().lower() if cliente.email else None

        sujeto_global_id = None
        tipo_sri = cliente.tipo_identificacion_sri

        # Gestión en sujetos_global (Validación RUC/Cédula)
        if tipo_sri in ["04", "05"]:
            es_valido, error_msg, tipo_detectado = validar_documento_ecuador(cliente.identificacion)
            if not es_valido:
                raise HTTPException(status_code=400, detail=f"VALIDACIÓN SRI: {error_msg.upper()}")
            tipo_sri = tipo_detectado

            # Buscamos o creamos en global
            query_sg = text("SELECT id FROM sujetos_global WHERE identificacion = :ident AND tipo_identificacion_sri = :tipo")
            res_sg = await db.execute(query_sg, {"ident": cliente.identificacion, "tipo": tipo_sri})
            sg_row = res_sg.fetchone()

            if sg_row:
                sujeto_global_id = sg_row.id
            else:
                insert_sg = text("""
                    INSERT INTO sujetos_global (tipo_identificacion_sri, identificacion, razon_social)
                    VALUES (:tipo, :ident, :razon) RETURNING id
                """)
                res_ins = await db.execute(insert_sg, {"tipo": tipo_sri, "ident": cliente.identificacion, "razon": razon_social_up})
                sujeto_global_id = res_ins.scalar()

        # Inserción local
        insert_local = text("""
            INSERT INTO clientes_emisor (
                emisor_id, sujeto_global_id, tipo_identificacion_sri, 
                identificacion, razon_social, direccion, email, telefono, created_at
            ) VALUES (
                :eid, :sgid, :tipo, :ident, :razon, :dir, :email, :tel, NOW()
            ) RETURNING id
        """)
        
        res_v = await db.execute(insert_local, {
            "eid": emisor_id, "sgid": sujeto_global_id, "tipo": tipo_sri,
            "ident": cliente.identificacion, "razon": razon_social_up,
            "dir": direccion_up, "email": email_low, "tel": cliente.telefono
        })
        
        uid = res_v.scalar()
        await db.commit()
        return {"ok": True, "mensaje": "CLIENTE CREADO EXITOSAMENTE.", "uid": str(uid)}
        
    except Exception as e:
        await db.rollback()
        raise e
    


async def actualizar_cliente_core(emisor_id: int, cliente_id: str, datos: ClienteUpdate, db: AsyncSession):
    try:
        # Verificar existencia
        res = await db.execute(
            text("SELECT id FROM clientes_emisor WHERE id = :cid AND emisor_id = :eid"),
            {"cid": cliente_id, "eid": emisor_id}
        )
        if not res.fetchone():
            raise HTTPException(status_code=404, detail="EL CLIENTE NO EXISTE O NO LE PERTENECE.")

        campos_raw = datos.model_dump(exclude_unset=True)
        if not campos_raw:
            return {"ok": True, "mensaje": "SIN CAMBIOS DETECTADOS."}

        update_params = {"cid": cliente_id, "eid": emisor_id}
        set_parts = []

        for k, v in campos_raw.items():
            if k == "identificacion": continue # Bloqueado
            
            # --- NORMALIZACIÓN TOTAL ---
            if isinstance(v, str):
                if k in ["razon_social", "direccion"]:
                    val = v.strip().upper() # TODO A MAYÚSCULAS
                elif k == "email":
                    val = v.strip().lower() # Email minúsculas
                else:
                    val = v.strip()
            else:
                val = v
            
            set_parts.append(f"{k} = :{k}")
            update_params[k] = val

        sql = f"UPDATE clientes_emisor SET {', '.join(set_parts)}, updated_at = NOW() WHERE id = :cid AND emisor_id = :eid"
        await db.execute(text(sql), update_params)
        await db.commit()

        return {"ok": True, "mensaje": "DATOS ACTUALIZADOS EN MAYÚSCULAS CORRECTAMENTE."}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR AL ACTUALIZAR EL CLIENTE.")


# ==========================================
# 2. CONSULTAR UN CLIENTE ESPECÍFICO
# ==========================================
async def consultar_cliente_por_identificacion_core(emisor_id: int, identificacion: str, db: AsyncSession):
    # 1. Buscar en la base local del EMISOR
    query_local = text("""
        SELECT id as id_interno, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono
        FROM clientes_emisor
        WHERE emisor_id = :eid AND identificacion = :ident
    """)
    res_local = await db.execute(query_local, {"eid": emisor_id, "ident": identificacion})
    row = res_local.fetchone()

    if row:
        return {
            "ok": True,
            "vinculado_al_emisor": True,
            "data": dict(row._mapping)
        }

    # 2. Si no existe local, buscar en sujetos_global (Para autocompletar nombre de RUCs/Cédulas)
    query_global = text("""
        SELECT id as sujeto_global_id, tipo_identificacion_sri, identificacion, razon_social
        FROM sujetos_global
        WHERE identificacion = :ident
    """)
    res_global = await db.execute(query_global, {"ident": identificacion})
    row_g = res_global.fetchone()

    if row_g:
        return {
            "ok": True,
            "vinculado_al_emisor": False,
            "mensaje": "Encontrado en base unificada. Se registrará al emitir factura.",
            "data": dict(row_g._mapping)
        }

    raise HTTPException(status_code=404, detail="Cliente no encontrado.")


# ==========================================
# 3. VERIFICAR EXISTENCIA (LISTA DE COINCIDENCIAS)
# ==========================================
async def verificar_existencia_cliente_core(emisor_id: int, identificacion: str, db: AsyncSession):
    query = text("""
        SELECT id as uid, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono
        FROM clientes_emisor
        WHERE emisor_id = :eid AND identificacion = :ident
    """)
    
    res = await db.execute(query, {"eid": emisor_id, "ident": identificacion})
    rows = res.fetchall()

    if not rows:
        return {"existe": False, "coincidencias": []}

    return {
        "existe": True,
        "cantidad": len(rows),
        "coincidencias": [dict(r._mapping) for r in rows]
    }


# ==========================================
# 4. BÚSQUEDA MASIVA + CONSUMIDOR FINAL
# ==========================================
async def consultar_clientes_bulk_core(emisor_id: int, identificaciones: list[str], db: AsyncSession):
    try:
        resultados = []

        if identificaciones:
            query = text("""
                SELECT id as uid, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono
                FROM clientes_emisor
                WHERE emisor_id = :eid AND identificacion IN :idents
            """)
            
            res = await db.execute(query, {"eid": emisor_id, "idents": tuple(identificaciones)})
            resultados = [dict(r._mapping) for r in res.fetchall()]

        # AGREGAR SIEMPRE CONSUMIDOR FINAL (Exigencia del SRI)
        consumidor_final = {
            "uid": None,
            "tipo_identificacion_sri": "07",
            "identificacion": "9999999999999",
            "razon_social": "CONSUMIDOR FINAL",
            "direccion": "S/N",
            "email": "",
            "telefono": ""
        }
        resultados.append(consumidor_final)

        return {
            "ok": True,
            "total_encontrados": len(resultados),
            "data": resultados
        }

    except Exception as e:
        print(f"[Bulk Search Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno consultando clientes masivamente.")
    

# ==========================================
# 5. LISTAR TODOS LOS CLIENTES (Exclusivo App)
# ==========================================
async def consultar_todos_clientes_core(emisor_id: int, db: AsyncSession):
    try:
        query = text("""
            SELECT 
                id as uid, 
                tipo_identificacion_sri, 
                identificacion, 
                razon_social, 
                direccion, 
                email, 
                telefono,
                created_at
            FROM clientes_emisor
            WHERE emisor_id = :eid
            ORDER BY razon_social ASC
        """)
        
        res = await db.execute(query, {"eid": emisor_id})
        rows = res.fetchall()

        return {
            "ok": True,
            "total": len(rows),
            "data": [dict(r._mapping) for r in rows]
        }

    except Exception as e:
        print(f"Error consultando listado completo de clientes: {e}")
        raise HTTPException(status_code=500, detail="Error interno al obtener los clientes.")
    

# ==========================================
# 6. DETALLE DE CLIENTE Y SU HISTORIAL (Por UUID)
# ==========================================
async def consultar_detalle_cliente_core(emisor_id: int, cliente_id: str, db: AsyncSession):
    try:
        # 1. Obtenemos datos básicos del cliente
        query_cliente = text("""
            SELECT 
                id, tipo_identificacion_sri, identificacion, 
                razon_social, direccion, email, telefono
            FROM clientes_emisor
            WHERE id = :cid AND emisor_id = :eid
        """)
        res_cliente = await db.execute(query_cliente, {"cid": cliente_id, "eid": emisor_id})
        cliente = res_cliente.fetchone()

        if not cliente:
            raise HTTPException(status_code=404, detail="EL CLIENTE NO EXISTE O NO LE PERTENECE.")

        # 2. Obtenemos facturas con el número formateado (Est-Punto-Secuencial)
        # Usamos un JOIN con establecimientos y puntos_emision para armar el número completo
        query_facturas = text("""
            SELECT 
                i.id,
                e.codigo || '-' || p.codigo || '-' || i.secuencial AS numero_factura,
                i.importe_total,
                i.fecha_emision,
                i.estado
            FROM invoices i
            JOIN puntos_emision p ON i.punto_emision_id = p.id
            JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE i.cliente_emisor_id = :cid AND i.emisor_id = :eid
            ORDER BY i.fecha_emision DESC
        """)
        
        res_facturas = await db.execute(query_facturas, {"cid": cliente_id, "eid": emisor_id})
        facturas = res_facturas.fetchall()

        # 3. Procesamiento simplificado
        lista_facturas = []
        total_facturado = 0.0

        for f in facturas:
            monto = float(f.importe_total) if f.importe_total else 0.0
            total_facturado += monto
            
            lista_facturas.append({
                "id": str(f.id),
                "numero_factura": f.numero_factura,
                "importe_total": monto,
                "fecha_emision": f.fecha_emision.strftime('%Y-%m-%d') if f.fecha_emision else None,
                "estado": f.estado
            })

        return {
            "ok": True,
            "cliente": dict(cliente._mapping),
            "resumen": {
                "total_facturas": len(lista_facturas),
                "suma_facturada": round(total_facturado, 2)
            },
            "facturas": lista_facturas
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error consultando detalle cliente: {e}")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL CONSULTAR EL HISTORIAL.")
    

async def verificar_cliente_existente_flexible(emisor_id: int, busqueda: str, db: AsyncSession):
    """
    Busca un cliente por UUID (id) o por Identificación (Cédula/RUC).
    Retorna True/False y el UID encontrado.
    """
    try:
        # 1. Determinar si la búsqueda es un UUID o una Identificación
        es_uuid = False
        try:
            uuid.UUID(busqueda)
            es_uuid = True
        except ValueError:
            es_uuid = False

        # 2. Construir la consulta según el tipo de dato
        if es_uuid:
            sql = text("""
                SELECT id FROM clientes_emisor 
                WHERE emisor_id = :eid AND id = :busqueda
            """)
        else:
            # Si no es UUID, asumimos que es identificación (limpiamos el string por si acaso)
            ident_limpia = busqueda.replace("-", "").replace(".", "").strip()
            sql = text("""
                SELECT id FROM clientes_emisor 
                WHERE emisor_id = :eid AND identificacion = :busqueda
            """)
            busqueda = ident_limpia

        # 3. Ejecutar
        res = await db.execute(sql, {"eid": emisor_id, "busqueda": busqueda})
        row = res.fetchone()

        if row:
            return {
                "valido": True,
                "existe": True,
                "uid": str(row.id)
            }
        
        return {
            "valido": True, 
            "existe": False, 
            "uid": None
        }

    except Exception as e:
        print(f"Error en verificación flexible: {e}")
        return {"valido": False, "existe": False, "uid": None}
