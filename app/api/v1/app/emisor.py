import time
import httpx
import base64
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Importaciones de tu core
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.emisor import OnboardingRequest, EmisorUpdate
from app.services.storage_service import upload_file, delete_file
from app.utils.crypto import encrypt_password

router = APIRouter()

# --- CONFIGURACIÓN ---
NODE_VALIDATOR_URL = os.getenv("NODE_VALIDATOR_URL", "http://localhost:3000/api/validar-p12")

def validar_ruc_ecuador(ruc: str):
    """
    Valida estrictamente un RUC de 13 dígitos para el onboarding.
    Retorna (bool, mensaje_error)
    """
    ruc = ruc.strip()
    
    if not ruc.isdigit() or len(ruc) != 13:
        return False, "El RUC debe tener exactamente 13 dígitos numéricos."
    
    if not ruc.endswith("001"):
        return False, "El RUC debe terminar en 001."
        
    provincia = int(ruc[0:2])
    if provincia < 1 or provincia > 24:
        return False, "Los dos primeros dígitos (provincia) son inválidos."
        
    tercer_digito = int(ruc[2])
    
    # --- PERSONA NATURAL (Menor a 6) ---
    if tercer_digito < 6:
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        digitos = [int(x) for x in ruc[:9]]
        suma = 0
        for i, d in enumerate(digitos):
            p = d * coeficientes[i]
            suma += p if p < 10 else p - 9
        verificador = 0 if suma % 10 == 0 else 10 - (suma % 10)
        if verificador != int(ruc[9]):
            return False, "El número de cédula base del RUC es incorrecto."
            
    # --- PERSONA JURÍDICA (9) ---
    elif tercer_digito == 9:
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        digitos = [int(x) for x in ruc[:9]]
        suma = sum(d * coeficientes[i] for i, d in enumerate(digitos))
        verificador = 0 if suma % 11 == 0 else 11 - (suma % 11)
        if verificador != int(ruc[9]):
            return False, "El RUC jurídico no supera la validación de módulo 11."

    # --- ENTIDAD PÚBLICA (6) ---
    elif tercer_digito == 6:
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        digitos = [int(x) for x in ruc[:8]]
        suma = sum(d * coeficientes[i] for i, d in enumerate(digitos))
        verificador = 0 if suma % 11 == 0 else 11 - (suma % 11)
        if verificador != int(ruc[8]):
            return False, "El RUC público no supera la validación de módulo 11."
    
    else:
        return False, "El tercer dígito del RUC es inválido."
            
    return True, ""


@router.post("/onboarding", summary="Registro inicial (Onboarding)", status_code=201)
async def onboarding(
    data: OnboardingRequest, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    if auth_data.get("emisor_id"):
        return {"ok": False, "mensaje": "Tu cuenta ya tiene una empresa vinculada."}

    es_valido, mensaje_error = validar_ruc_ecuador(data.ruc)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)

    try:
        # Convertimos textos a MAYÚSCULAS para cumplir estándar SRI
        razon_social_up = data.razon_social.upper()
        nombre_comercial_up = (data.nombre_comercial or data.razon_social).upper()
        direccion_up = data.direccion_matriz.upper()

        query_emisor = text("""
            INSERT INTO emisores (
                ruc, razon_social, nombre_comercial, 
                direccion_matriz, obligado_contabilidad, contribuyente_especial, 
                ambiente
            )
            VALUES (:ruc, :rs, :nc, :dir, :obl, :ce, 1) 
            RETURNING id
        """)
        
        res_emisor = await db.execute(query_emisor, {
            "ruc": data.ruc,
            "rs": razon_social_up,
            "nc": nombre_comercial_up,
            "dir": direccion_up,
            "obl": (data.obligado_contabilidad or 'NO').upper(),
            "ce": (data.contribuyente_especial or '').upper()
        })
        new_emisor_id = res_emisor.scalar()

        # Perfil también en Mayúsculas
        full_name_up = (data.full_name if data.full_name else data.razon_social).upper()

        query_profile = text("""
            INSERT INTO profiles (firebase_uid, emisor_id, email, full_name, role)
            VALUES (:uid, :eid, :email, :fname, 'admin')
        """)
        await db.execute(query_profile, {
            "uid": auth_data["uid"], 
            "eid": new_emisor_id, 
            "email": auth_data["email"].lower(), # El email es lo único que dejamos en minúsculas
            "fname": full_name_up
        })

        # Créditos
        await db.execute(text("INSERT INTO user_credits (emisor_id, balance) VALUES (:eid, 10)"), {"eid": new_emisor_id})
        await db.execute(text("""
            INSERT INTO credit_transactions (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES (:eid, 'BONO', 10, 0.00, 'SISTEMA', 'REGALO POR APERTURA DE CUENTA')
        """), {"eid": new_emisor_id})
        
        await db.commit()
        return {"ok": True, "mensaje": "EMPRESA Y PERFIL CONFIGURADOS CORRECTAMENTE.", "emisor_id": new_emisor_id}
        
    except Exception as e:
        await db.rollback()
        if "23505" in str(e):
            raise HTTPException(status_code=400, detail="EL RUC INGRESADO YA ESTÁ REGISTRADO.")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL PROCESAR EL REGISTRO.")


@router.post("/firma", summary="Subir firma electrónica (P12)")
async def upload_p12(
    password: str = Form(...), 
    file: UploadFile = File(...), 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")
    
    # 1. Obtener RUC
    res_emisor = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), 
        {"eid": emisor_id}
    )
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")
    
    # 2. Validar archivo
    if not file.filename.lower().endswith('.p12'):
        raise HTTPException(status_code=400, detail="EL ARCHIVO DEBE SER UN FORMATO .P12 VÁLIDO.")

    file_bytes = await file.read()
    p12_base64 = base64.b64encode(file_bytes).decode('utf-8')

    # 3. Validación en Node.js
    async with httpx.AsyncClient() as client:
        try:
            res_node = await client.post(
                NODE_VALIDATOR_URL, 
                json={"p12Base64": p12_base64, "password": password, "ruc": emisor.ruc},
                timeout=20.0
            )
            val = res_node.json()
        except Exception as e:
            print(f"❌ Error conexión Node.js: {str(e)}")
            raise HTTPException(status_code=500, detail="ERROR AL CONECTAR CON EL VALIDADOR.")
        
    if not val.get("ok"):
        err_msg = val.get("mensaje", "CERTIFICADO INVÁLIDO.").upper()
        raise HTTPException(status_code=400, detail=err_msg)

    # --- AQUÍ DEFINIMOS LAS VARIABLES PARA QUE ESTÉN DISPONIBLES EN TODO EL BLOQUE ---
    p12_path_completo = None 

    try:
        # 4. Limpieza Storage
        if emisor.p12_path:
            try:
                path_parts = emisor.p12_path.split('/')
                delete_file(path_parts[0], "/".join(path_parts[1:]))
            except: pass

        # 5. Subida a MinIO
        file_name = f"{emisor.ruc}/CERTIFICADO_{int(time.time()*1000)}.p12"
        # Asignamos valor a la variable definida arriba
        p12_path_completo = upload_file('certificates', file_name, file_bytes, 'application/x-pkcs12')

        # 6. Preparar datos para DB
        pass_enc = encrypt_password(password)
        
        # Leemos la fecha de donde sea que venga (tu log mostró que viene en datos.vence)
        raw_exp = val.get("expiration") or val.get("datos", {}).get("vence")
        if not raw_exp:
            raise ValueError("No se encontró la fecha de expiración en la respuesta.")
        
        # Convertimos el string ISO a un objeto DATE real de Python
        # Tomamos los primeros 10 caracteres 'YYYY-MM-DD' y lo convertimos
        fecha_objeto = datetime.strptime(str(raw_exp)[:10], '%Y-%m-%d').date()

        # 7. Update en Base de Datos
        query_update = text("""
            UPDATE public.emisores 
            SET 
                p12_path = :path, 
                p12_pass = :pass, 
                p12_expiration = :exp, 
                updated_at = NOW()
            WHERE id = :eid
        """)
        
        await db.execute(query_update, {
            "path": p12_path_completo,
            "pass": pass_enc,
            "exp": fecha_objeto,
            "eid": emisor_id
        })
        
        await db.commit()
        return {"ok": True, "mensaje": "FIRMA VINCULADA CORRECTAMENTE."}
        
    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="ERROR AL GUARDAR EN BASE DE DATOS.")
    

@router.delete("/firma", summary="Eliminar firma electrónica")
async def remove_p12(
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina los archivos de la firma en Storage y limpia los campos en la DB.
    """
    emisor_id = auth_data.get("emisor_id")
    
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    # 1. Obtener la ruta del archivo antes de borrar los datos de la DB
    res = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), 
        {"eid": emisor_id}
    )
    emisor = res.fetchone()

    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    try:
        # 2. Si hay un archivo en Storage, lo eliminamos
        if emisor.p12_path:
            try:
                # Separamos bucket de la ruta (ej: 'certificates/1234567890001/archivo.p12')
                path_parts = emisor.p12_path.split('/')
                bucket = path_parts[0]
                real_path = "/".join(path_parts[1:])
                
                delete_file(bucket, real_path)
                print(f"🗑️ Archivo P12 eliminado de Storage para el RUC: {emisor.ruc}")
            except Exception as e:
                print(f"⚠️ Aviso: No se pudo eliminar el archivo físico (tal vez ya no existía): {str(e)}")

        # 3. Limpiar los campos en la Base de Datos
        query_cleanup = text("""
            UPDATE emisores 
            SET 
                p12_path = NULL, 
                p12_pass = NULL, 
                p12_expiration = NULL, 
                updated_at = NOW()
            WHERE id = :eid
        """)
        
        await db.execute(query_cleanup, {"eid": emisor_id})
        await db.commit()

        return {
            "ok": True, 
            "mensaje": "LA FIRMA ELECTRÓNICA Y SUS DATOS HAN SIDO ELIMINADOS CORRECTAMENTE."
        }

    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR AL ELIMINAR FIRMA: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="ERROR INTERNO AL INTENTAR ELIMINAR LOS DATOS DE LA FIRMA."
        )


@router.get("/config", summary="Obtener configuración fiscal y de firma")
async def get_config(
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        return {"ok": True, "configurado": False, "mensaje": "Pendiente de configuración inicial (Onboarding)."}

    res = await db.execute(text("""
        SELECT ruc, razon_social, nombre_comercial, direccion_matriz, contribuyente_especial, 
               obligado_contabilidad, ambiente, p12_path, p12_expiration, created_at
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    data = res.fetchone()

    # Lógica de estado de la firma
    expiracion = data.p12_expiration
    nombre_firma = data.p12_path.split('/')[-1] if data.p12_path else 'No configurada'
    
    firma_info = {
        "configurada": bool(data.p12_path),
        "nombre": nombre_firma,
        "expiracion": expiracion,
        "estado": 'PENDIENTE',
        "mensaje_vencimiento": 'Firma no cargada'
    }

    if expiracion:
        # 'expiracion' es un objeto datetime.date
        hoy = datetime.utcnow().date()  # Convertimos 'hoy' a date para poder comparar
        dias_restantes = (expiracion - hoy).days
        fecha_fmt = expiracion.strftime("%d/%m/%Y")

        if dias_restantes <= 0:
            firma_info.update({"estado": 'EXPIRADA', "mensaje_vencimiento": f"Expirada el {fecha_fmt}"})
        elif dias_restantes <= 30:
            firma_info.update({"estado": 'ALERTA', "mensaje_vencimiento": f"Próxima a vencer ({dias_restantes} días)"})
        else:
            firma_info.update({"estado": 'VIGENTE', "mensaje_vencimiento": f"Vigente hasta el {fecha_fmt}"})

    return {
        "ok": True, 
        "configurado": True,
        "data": {
            "legal": dict(data._mapping),
            "firma": firma_info
        }
    }


@router.patch("/config", summary="Actualizar configuración del emisor")
async def update_config(
    data: EmisorUpdate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    # Filtramos y convertimos a MAYÚSCULAS dinámicamente
    update_data = {}
    for k, v in data.model_dump().items():
        if v is not None:
            # Si el valor es texto, lo hacemos MAYÚSCULAS
            update_data[k] = v.upper() if isinstance(v, str) else v
    
    if not update_data:
        return {"ok": True, "mensaje": "NO SE DETECTARON CAMBIOS POR APLICAR."}
        
    set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
    update_data["eid"] = emisor_id
    
    try:
        query = text(f"UPDATE emisores SET {set_clause}, updated_at = NOW() WHERE id = :eid")
        await db.execute(query, update_data)
        await db.commit()
        return {"ok": True, "mensaje": "CONFIGURACIÓN ACTUALIZADA CORRECTAMENTE."}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL ACTUALIZAR.")