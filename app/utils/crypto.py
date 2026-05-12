# app/utils/crypto.py

import os
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from app.core.config import settings
import re
from datetime import datetime
import pytz

# =============================================================================
# ALGORITMOS SRI (CLAVE DE ACCESO)
# =============================================================================

def modulo11(cadena: str) -> int:
    """Algoritmo Módulo 11 (Requisito estricto del SRI - Ficha Técnica)"""
    suma = 0
    factor = 2
    
    # Recorremos la cadena de atrás hacia adelante
    for i in range(len(cadena) - 1, -1, -1):
        suma += int(cadena[i]) * factor
        factor = 2 if factor == 7 else factor + 1
        
    residuo = suma % 11
    verificador = 11 - residuo
    
    if verificador == 11:
        return 0
    if verificador == 10:
        return 1
        
    return verificador

def generar_clave_acceso(fecha: str, tipo_comprobante: str, ruc: str, ambiente: str, serie: str, secuencial: str, codigo_numerico: str = None) -> str:
    """
    Genera la clave de acceso de 49 dígitos requerida por el SRI.
    Estructura: Fecha(8) + Tipo(2) + RUC(13) + Amb(1) + Serie(6) + Sec(9) + Cod(8) + Emi(1) + Verificador(1)
    """
    tz = pytz.timezone('America/Guayaquil')
    ahora = datetime.now(tz)

    # 1. Fecha (ddmmyyyy)
    if fecha and fecha != 'now':
        try:
            # Intentamos detectar si viene yyyy-mm-dd o ya viene formateada
            if "-" in fecha:
                fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
            else:
                fecha_dt = datetime.strptime(fecha, "%d%m%Y")
            final_fecha = fecha_dt.strftime('%d%m%Y')
        except ValueError:
            final_fecha = ahora.strftime('%d%m%Y')
    else:
        final_fecha = ahora.strftime('%d%m%Y')

    # 2. Código Numérico (8 dígitos) - AJUSTE: Más aleatoriedad si no se provee
    if not codigo_numerico:
        # Usamos microsegundos invertidos para evitar colisiones en facturación masiva
        codigo_numerico = ahora.strftime('%S%M%H') + str(ahora.microsecond)[:2].zfill(2)

    # 3. Limpieza estricta
    def limpiar(val) -> str:
        return re.sub(r'\D', '', str(val))

    p1_fecha = limpiar(final_fecha).zfill(8)[:8]
    p2_tipo  = limpiar(tipo_comprobante).zfill(2)[:2]
    p3_ruc   = limpiar(ruc).zfill(13)[:13]
    p4_amb   = limpiar(ambiente).zfill(1)[:1]
    p5_serie = limpiar(serie).zfill(6)[:6]
    p6_sec   = limpiar(secuencial).zfill(9)[:9]
    p7_cod   = limpiar(codigo_numerico).zfill(8)[:8]
    p8_emi   = "1" # Tipo de emisión: Normal

    clave48 = p1_fecha + p2_tipo + p3_ruc + p4_amb + p5_serie + p6_sec + p7_cod + p8_emi

    if len(clave48) != 48:
        raise ValueError(f"Error estructural: Clave base mide {len(clave48)} (deben ser 48)")

    # 4. Dígito verificador
    digito_verificador = modulo11(clave48)
    clave_final = clave48 + str(digito_verificador)

    return clave_final

# =============================================================================
# ENCRIPTACIÓN (PARA P12 PASSWORDS)
# =============================================================================

def encrypt_password(text: str) -> str:
    """Encripta texto (passwords de firmas) usando AES-256-CBC"""
    if not settings.ENCRYPTION_KEY or not text:
        return text
    
    try:
        # Derivamos la llave de 32 bytes (AES-256) usando SHA256
        key = hashlib.sha256(str(settings.ENCRYPTION_KEY).strip().encode('utf-8')).digest()
        iv = os.urandom(16)
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # PKCS7 Padding manual
        pad_len = 16 - (len(text.encode('utf-8')) % 16)
        padded_text = text + chr(pad_len) * pad_len
        
        ct = encryptor.update(padded_text.encode('utf-8')) + encryptor.finalize()
        return f"{iv.hex()}:{ct.hex()}"
    except Exception as e:
        print(f"❌ Error encriptando: {e}")
        return text

def decrypt_password(encrypted_text: str) -> str:
    """Descifra texto cifrado en formato iv_hex:ct_hex"""
    if not settings.ENCRYPTION_KEY or ":" not in str(encrypted_text):
        return encrypted_text
    
    try:
        iv_hex, ct_hex = encrypted_text.split(":")
        iv = bytes.fromhex(iv_hex)
        ct = bytes.fromhex(ct_hex)
        
        key = hashlib.sha256(str(settings.ENCRYPTION_KEY).strip().encode('utf-8')).digest()
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # Descifrar
        padded_data = decryptor.update(ct) + decryptor.finalize()
        padded_text = padded_data.decode('utf-8')
        
        # Quitar PKCS7 Padding
        pad_len = ord(padded_text[-1])
        # Validación de seguridad del padding
        if pad_len < 1 or pad_len > 16:
            return padded_text
            
        return padded_text[:-pad_len]
        
    except Exception as e:
        print(f"❌ Error desencriptando: {str(e)}")
        return encrypted_text