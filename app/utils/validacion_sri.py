# app/utils/validacion_sri.py
#
# Validación de documentos de identificación Ecuador — SRI.
# Fuente única de verdad para cédula, RUC y pasaporte.
# Usada por cliente_service.py, emisor.py, y cualquier otro módulo que necesite validar.

def validar_documento_ecuador(documento: str) -> tuple[bool, str, str]:
    """
    Valida cédula (10 dígitos) o RUC (13 dígitos) ecuatoriano.
    Retorna: (es_valido, mensaje_error, tipo_sri_detectado)
    tipo_sri_detectado: "05" para cédula, "04" para RUC, "" si inválido.
    """
    documento = documento.replace("-", "").replace(".", "").replace(" ", "").strip()

    if not documento.isdigit():
        return False, "El documento debe contener solo números.", ""

    if len(documento) not in [10, 13]:
        return False, "Longitud no válida (debe ser 10 o 13 dígitos).", ""

    provincia = int(documento[0:2])
    if (provincia < 1 or provincia > 24) and provincia != 30:
        return False, f"Provincia '{documento[0:2]}' no existe.", ""

    tercero = int(documento[2])

    def modulo_10(s: str) -> bool:
        digitos = [int(x) for x in s[:9]]
        verificador = int(s[9])
        suma = 0
        for i, d in enumerate(digitos):
            p = d * (2 if i % 2 == 0 else 1)
            if p > 9: p -= 9
            suma += p
        calc = 0 if suma % 10 == 0 else 10 - (suma % 10)
        return calc == verificador

    # ── Cédula (10 dígitos) ───────────────────────────────────────────────────
    if len(documento) == 10:
        if tercero > 5:
            return False, "Cédula inválida (tercer dígito incorrecto).", ""
        if not modulo_10(documento):
            return False, "Número de cédula inválido.", ""
        return True, "", "05"

    # ── RUC (13 dígitos) ──────────────────────────────────────────────────────
    if not documento.endswith("001"):
        return False, "El RUC debe terminar en 001.", ""

    if tercero <= 5:
        # Persona natural — base es la cédula, validar módulo 10
        if not modulo_10(documento[:10]):
            return False, "RUC de persona natural inválido.", ""

    elif tercero == 6 or tercero == 9:
        # Jurídico público (6) o privado (9) — no se valida dígito verificador
        pass

    else:
        return False, "Tercer dígito de RUC inválido.", ""

    return True, "", "04"


def validar_ruc_ecuador(ruc: str) -> tuple[bool, str]:
    """
    Wrapper simplificado para onboarding — solo RUC de 13 dígitos.
    Retorna: (es_valido, mensaje_error)
    """
    es_valido, error, _ = validar_documento_ecuador(ruc)
    if not es_valido:
        return False, error
    if len(ruc.replace("-", "").replace(".", "").strip()) != 13:
        return False, "El RUC debe tener exactamente 13 dígitos."
    return True, ""