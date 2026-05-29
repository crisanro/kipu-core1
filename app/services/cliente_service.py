# app/services/cliente_service.py — OPTIMIZADO con cache
import uuid
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate, ClienteUpdate
from datetime import date, datetime
from app.core.cache import cache_get, cache_set, cache_delete, cache_clear_prefix, CK, TTL


# ── Helpers de invalidación ────────────────────────────────────────────────────

async def _invalidar_clientes(emisor_id: int):
    """Borra el listado general de clientes del cache."""
    await cache_delete(CK.fmt(CK.CLIENTES, eid=emisor_id))

async def _invalidar_detalle_cliente(emisor_id: int, cliente_id: str):
    """Borra el detalle de un cliente específico."""
    await cache_delete(CK.fmt(CK.CLIENTE_DETALLE, eid=emisor_id, cid=cliente_id))


# ── Validación Ecuador (sin cambios) ──────────────────────────────────────────

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

    if len(documento) == 10:
        if tercer_digito < 6:
            if validar_modulo_10(documento):
                return True, "", "05"
            return False, "Número de cédula inválido.", ""
        return False, "Cédula inválida (tercer dígito incorrecto).", ""
    elif len(documento) == 13:
        if not documento.endswith("001"):
            return False, "El RUC debe terminar en 001.", ""
        if tercer_digito < 6:
            es_valido = validar_modulo_10(documento[:10])
        elif tercer_digito == 9:
            es_valido = validar_modulo_11(documento[:10])
        elif tercer_digito == 6:
            es_valido = True
        else:
            return False, "Tercer dígito de RUC inválido.", ""
        if es_valido:
            return True, "", "04"
        return False, "El número de RUC no es válido.", ""
    return False, "Documento no reconocido.", ""


# ── 1. CREATE / UPDATE ─────────────────────────────────────────────────────────

async def crear_cliente_core(emisor_id: int, cliente: ClienteCreate, db: AsyncSession, lanzar_error_si_existe: bool = True):
    try:
        # Verificar si ya existe
        res_check = await db.execute(
            text("SELECT id FROM clientes_emisor WHERE emisor_id = :eid AND identificacion = :ident"),
            {"eid": emisor_id, "ident": cliente.identificacion}
        )
        row_existente = res_check.fetchone()
        if row_existente:
            if lanzar_error_si_existe:
                raise HTTPException(status_code=400, detail="EL CLIENTE YA EXISTE EN SU BASE DE DATOS.")
            return {"ok": True, "mensaje": "CLIENTE YA EXISTÍA", "uid": str(row_existente.id)}

        razon_social_up = cliente.razon_social  # ya viene en mayúsculas del schema
        direccion_up = cliente.direccion.strip().upper() if cliente.direccion and cliente.direccion.strip() else ""
        email_low    = cliente.email.strip().lower() if cliente.email and cliente.email.strip() else ""
        telefono     = cliente.telefono.strip() if cliente.telefono and cliente.telefono.strip() else ""
        tipo_sri        = cliente.tipo_identificacion_sri
        sujeto_global_id = None

        # Validación y sujeto_global solo para cédula y RUC
        if tipo_sri in ["04", "05"]:
            es_valido, error_msg, tipo_detectado = validar_documento_ecuador(cliente.identificacion)
            if not es_valido:
                raise HTTPException(status_code=400, detail=f"VALIDACIÓN SRI: {error_msg.upper()}")
            tipo_sri = tipo_detectado

            res_sg = await db.execute(text("""
                INSERT INTO sujetos_global (tipo_identificacion_sri, identificacion, codigo_pais, razon_social)
                VALUES (:tipo, :ident, 'EC', :razon)
                ON CONFLICT (identificacion, tipo_identificacion_sri) DO UPDATE
                    SET razon_social = EXCLUDED.razon_social,
                        ultima_sincronizacion = NOW()
                RETURNING id
            """), {"tipo": tipo_sri, "ident": cliente.identificacion, "razon": razon_social_up})
            sujeto_global_id = res_sg.scalar()

        # Pasaporte (06) y Exterior (08) — sin validación de formato ni sujeto_global
        # elif tipo_sri in ["06", "08"]: pass  ← no hace falta, sigue con sujeto_global_id=None

        res_v = await db.execute(text("""
            INSERT INTO clientes_emisor (
                emisor_id, sujeto_global_id, tipo_identificacion_sri,
                identificacion, razon_social, direccion, email, telefono, created_at
            ) VALUES (
                :eid, :sgid, :tipo, :ident, :razon, :dir, :email, :tel, NOW()
            ) RETURNING id
        """), {
            "eid": emisor_id, "sgid": sujeto_global_id, "tipo": tipo_sri,
            "ident": cliente.identificacion, "razon": razon_social_up,
            "dir": direccion_up, "email": email_low, "tel": telefono
        })
        uid = res_v.scalar()
        await db.commit()
        await _invalidar_clientes(emisor_id)
        return {"ok": True, "mensaje": "CLIENTE CREADO EXITOSAMENTE.", "uid": str(uid)}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error creando cliente: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL CREAR EL CLIENTE.")


async def actualizar_cliente_core(emisor_id: int, cliente_id: str, datos: ClienteUpdate, db: AsyncSession):
    try:
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
            if k == "identificacion":
                continue
            if isinstance(v, str):
                if k in ["razon_social", "direccion"]:
                    val = v.strip().upper() if v.strip() else ""
                elif k == "email":
                    val = v.strip().lower() if v.strip() else ""
                else:
                    val = v.strip() if v.strip() else ""
            elif v is None:
                val = ""  # ← nunca guardar NULL, siempre string vacío
            else:
                val = v
            set_parts.append(f"{k} = :{k}")
            update_params[k] = val

        sql = f"UPDATE clientes_emisor SET {', '.join(set_parts)} WHERE id = :cid AND emisor_id = :eid"
        await db.execute(text(sql), update_params)
        await db.commit()

        # Invalidar listado + detalle del cliente modificado
        await _invalidar_clientes(emisor_id)
        await _invalidar_detalle_cliente(emisor_id, cliente_id)

        return {"ok": True, "mensaje": "DATOS ACTUALIZADOS CORRECTAMENTE."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error actualizando cliente: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL ACTUALIZAR EL CLIENTE.")


# ── 2. CONSULTAS ───────────────────────────────────────────────────────────────

async def consultar_cliente_por_identificacion_core(emisor_id: int, identificacion: str, db: AsyncSession):
    """Busca 1 cliente. Primero en la DB local, luego en sujetos_global."""
    # OPTIMIZACIÓN: una sola query con LEFT JOIN en lugar de 2 queries secuenciales
    res = await db.execute(text("""
        SELECT
            ce.id, ce.tipo_identificacion_sri, ce.identificacion,
            ce.razon_social, ce.direccion, ce.email, ce.telefono,
            true AS vinculado_al_emisor
        FROM clientes_emisor ce
        WHERE ce.emisor_id = :eid AND ce.identificacion = :ident

        UNION ALL

        SELECT
            sg.id, sg.tipo_identificacion_sri, sg.identificacion,
            sg.razon_social, NULL AS direccion, NULL AS email, NULL AS telefono,
            false AS vinculado_al_emisor
        FROM sujetos_global sg
        WHERE sg.identificacion = :ident
          AND NOT EXISTS (
              SELECT 1 FROM clientes_emisor ce2
              WHERE ce2.emisor_id = :eid AND ce2.identificacion = :ident
          )
        LIMIT 1
    """), {"eid": emisor_id, "ident": identificacion})

    row = res.mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    data = dict(row)
    data["id"] = str(data["id"])
    vinculado = data.pop("vinculado_al_emisor")

    return {
        "ok": True,
        "vinculado_al_emisor": vinculado,
        "mensaje": "Encontrado en emisor." if vinculado else "Encontrado en base unificada.",
        "data": data
    }


async def verificar_existencia_cliente_core(emisor_id: int, identificacion: str, db: AsyncSession):
    query = text("""
        SELECT id as uid, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono
        FROM clientes_emisor
        WHERE emisor_id = :eid AND identificacion = :ident
    """)
    res  = await db.execute(query, {"eid": emisor_id, "ident": identificacion})
    rows = res.mappings().fetchall()

    if not rows:
        return {"existe": False, "coincidencias": []}
    return {"existe": True, "cantidad": len(rows), "coincidencias": [dict(r) for r in rows]}


async def consultar_clientes_bulk_core(emisor_id: int, terminos: list[str], db: AsyncSession):
    try:
        uuids_validos = []
        for t in terminos:
            try:
                uuids_validos.append(str(uuid.UUID(t)))
            except ValueError:
                continue

        resultados = []
        if uuids_validos:
            query = text("""
                SELECT id as uid, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono
                FROM clientes_emisor
                WHERE emisor_id = :eid AND id::text IN :uids
            """).bindparams(bindparam("uids", expanding=True))
            res = await db.execute(query, {"eid": emisor_id, "uids": uuids_validos})
            for r in res.mappings().fetchall():
                d = dict(r)
                d["uid"] = str(d["uid"])
                resultados.append(d)

        # Consumidor Final siempre al final
        resultados.append({
            "uid": "cliente-final", "tipo_identificacion_sri": "07",
            "identificacion": "9999999999999", "razon_social": "CONSUMIDOR FINAL",
            "direccion": "S/N", "email": "", "telefono": ""
        })
        return {"ok": True, "total_encontrados": len(resultados), "data": resultados}

    except Exception as e:
        print(f"❌ [Bulk Search Error] {e}")
        raise HTTPException(status_code=500, detail="Error al buscar clientes.")


async def consultar_todos_clientes_core(emisor_id: int, db: AsyncSession):
    """Lista completa de clientes — CON CACHE (TTL 3 min)."""
    cache_key = CK.fmt(CK.CLIENTES, eid=emisor_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        query = text("""
            SELECT id as uid, tipo_identificacion_sri, identificacion,
                   razon_social, direccion, email, telefono, created_at
            FROM clientes_emisor
            WHERE emisor_id = :eid
            ORDER BY razon_social ASC
        """)
        res  = await db.execute(query, {"eid": emisor_id})
        rows = res.mappings().fetchall()

        # Convertir UUIDs a string para que sea serializable por JSON
        data = []
        for r in rows:
            d = dict(r)
            d["uid"] = str(d["uid"])
            data.append(d)

        result = {"ok": True, "total": len(data), "data": data}
        await cache_set(cache_key, result, TTL.CLIENTES_LISTA)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al obtener listado de clientes.")


# ── 3. DETALLE + HISTORIAL — CON CACHE ────────────────────────────────────────

async def consultar_detalle_cliente_core(emisor_id: int, cliente_id: str, db: AsyncSession):
    """Detalle completo del cliente + historial de facturas — CON CACHE (TTL 5 min)."""
    cache_key = CK.fmt(CK.CLIENTE_DETALLE, eid=emisor_id, cid=cliente_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        query = text("""
            SELECT
                c.id, c.tipo_identificacion_sri, c.identificacion, c.razon_social,
                c.direccion, c.email, c.telefono,
                i.id AS factura_id,
                est.codigo || '-' || p.codigo || '-' || i.secuencial AS numero_factura,
                i.importe_total,
                i.fecha_emision,
                i.estado
            FROM clientes_emisor c
            LEFT JOIN invoices_emitidas i   ON i.cliente_emisor_id = c.id AND i.emisor_id = :eid
            LEFT JOIN puntos_emision p       ON i.punto_emision_id  = p.id
            LEFT JOIN establecimientos est   ON p.establecimiento_id = est.id
            WHERE c.id = :cid AND c.emisor_id = :eid
            ORDER BY i.created_at DESC
        """)
        res  = await db.execute(query, {"cid": cliente_id, "eid": emisor_id})
        rows = res.mappings().fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="EL CLIENTE NO EXISTE.")

        first = rows[0]
        cliente = {
            "id":                      str(first["id"]),
            "tipo_identificacion_sri": first["tipo_identificacion_sri"],
            "identificacion":          first["identificacion"],
            "razon_social":            first["razon_social"],
            "direccion":               first["direccion"],
            "email":                   first["email"],
            "telefono":                first["telefono"],
        }

        lista_facturas  = []
        total_facturado = 0.0

        for f in rows:
            if f["factura_id"] is None:
                continue
            monto = float(f["importe_total"]) if f["importe_total"] else 0.0
            lista_facturas.append({
                "id":             str(f["factura_id"]),
                "numero_factura": f["numero_factura"],
                "importe_total":  monto,
                "fecha_emision":  f["fecha_emision"].strftime('%Y-%m-%d') if f["fecha_emision"] else None,
                "estado":         f["estado"]
            })
            if f["estado"] == "AUTORIZADO":
                total_facturado += monto

        result = {
            "ok": True,
            "cliente": cliente,
            "resumen": {
                "total_facturas": len(lista_facturas),
                "suma_facturada": round(total_facturado, 2)
            },
            "facturas": lista_facturas
        }

        await cache_set(cache_key, result, TTL.CLIENTE_DETALLE)
        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="ERROR AL CONSULTAR HISTORIAL.")


async def verificar_cliente_existente_flexible(emisor_id: int, busqueda: str, db: AsyncSession):
    try:
        es_uuid = False
        try:
            uuid.UUID(busqueda)
            es_uuid = True
        except ValueError:
            pass

        if es_uuid:
            sql = text("SELECT id FROM clientes_emisor WHERE emisor_id = :eid AND id = :busqueda")
        else:
            busqueda = busqueda.replace("-", "").replace(".", "").strip()
            sql = text("SELECT id FROM clientes_emisor WHERE emisor_id = :eid AND identificacion = :busqueda")

        res = await db.execute(sql, {"eid": emisor_id, "busqueda": busqueda})
        row = res.fetchone()

        if row:
            return {"valido": True, "existe": True, "uid": str(row.id)}
        return {"valido": True, "existe": False, "uid": None}

    except Exception:
        return {"valido": False, "existe": False, "uid": None}
