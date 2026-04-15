import os
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from app.core.config import settings
import re
from datetime import datetime
import pytz

def modulo11(cadena: str) -> int:
    """Algoritmo Módulo 11 (Requisito estricto del SRI)"""
    suma = 0
    factor = 2
    
    # Recorremos la cadena de atrás hacia adelante
    for i in range(len(cadena) - 1, -1, -1):
        suma += int(cadena[i]) * factor
        factor = 2 if factor == 7 else factor + 1
        
    verificador = 11 - (suma % 11)
    
    if verificador == 11:
        return 0
    if verificador == 10:
        return 1
        
    return verificador

def generar_clave_acceso(fecha: str, tipo_comprobante: str, ruc: str, ambiente: str, serie: str, secuencial: str, codigo_numerico: str = None) -> str:
    tz = pytz.timezone('America/Guayaquil')
    ahora = datetime.now(tz)

    # 1. Fecha (8 dígitos - ddmmyyyy)
    if fecha and fecha != 'now':
        try:
            # Asumimos formato yyyy-mm-dd
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
            final_fecha = fecha_dt.strftime('%d%m%Y')
        except ValueError:
            final_fecha = ahora.strftime('%d%m%Y')
    else:
        final_fecha = ahora.strftime('%d%m%Y')

    # 2. Código Numérico (8 dígitos)
    if not codigo_numerico:
        # Generamos: Hora(2) + Min(2) + Seg(2) + Miliseg(2)
        ms = str(ahora.microsecond)[:2].zfill(2)
        codigo_numerico = ahora.strftime('%H%M%S') + ms

    # 3. Limpieza estricta: Eliminar cualquier cosa que no sea número
    def limpiar(val) -> str:
        return re.sub(r'\D', '', str(val))

    p1_fecha = limpiar(final_fecha)[:8].zfill(8)
    p2_tipo  = limpiar(tipo_comprobante).zfill(2)[:2]
    p3_ruc   = limpiar(ruc)[:13].zfill(13)
    p4_amb   = limpiar(ambiente)[:1].zfill(1)
    p5_serie = limpiar(serie).zfill(6)[:6]
    p6_sec   = limpiar(secuencial).zfill(9)[:9]
    p7_cod   = limpiar(codigo_numerico).zfill(8)[:8]
    p8_emi   = "1"

    clave48 = p1_fecha + p2_tipo + p3_ruc + p4_amb + p5_serie + p6_sec + p7_cod + p8_emi

    if len(clave48) != 48:
        raise ValueError(f"Clave base inválida: mide {len(clave48)} y debe medir 48. Valor: {clave48}")

    # 4. Calcular dígito verificador
    digito_verificador = modulo11(clave48)
    clave_final = clave48 + str(digito_verificador)

    print(f"[Crypto] ✅ Clave Generada: {clave_final}")
    return clave_final

def encrypt_password(text: str) -> str:
    if not settings.ENCRYPTION_KEY or not text:
        return text
    
    # Replicamos el hash SHA256 de Node.js para la llave
    key = hashlib.sha256(str(settings.ENCRYPTION_KEY).strip().encode('utf-8')).digest()
    iv = os.urandom(16)
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # PKCS7 Padding
    pad_len = 16 - (len(text.encode('utf-8')) % 16)
    padded_text = text + chr(pad_len) * pad_len
    
    ct = encryptor.update(padded_text.encode('utf-8')) + encryptor.finalize()
    return f"{iv.hex()}:{ct.hex()}"

def decrypt_password(encrypted_text: str) -> str:
    if not settings.ENCRYPTION_KEY or ":" not in str(encrypted_text):
        return encrypted_text
    
    try:
        # 1. Separar el IV y el contenido cifrado (hexadecimal)
        iv_hex, ct_hex = encrypted_text.split(":")
        iv = bytes.fromhex(iv_hex)
        ct = bytes.fromhex(ct_hex)
        
        # 2. Replicar la misma llave SHA256
        key = hashlib.sha256(str(settings.ENCRYPTION_KEY).strip().encode('utf-8')).digest()
        
        # 3. Configurar el descifrador AES-CBC
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # 4. Descifrar y quitar el PKCS7 Padding
        padded_text = (decryptor.update(ct) + decryptor.finalize()).decode('utf-8')
        
        # El último carácter nos dice cuántos bytes de padding hay que quitar
        pad_len = ord(padded_text[-1])
        return padded_text[:-pad_len]
        
    except Exception as e:
        print(f"❌ Error al desencriptar: {str(e)}")
        return encrypted_text # Retornamos el original si algo falla