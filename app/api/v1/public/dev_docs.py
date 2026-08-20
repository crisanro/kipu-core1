# app/api/v1/public/dev_docs.py
#
# Endpoint que expone la documentación pública de la API Kipu.
# Consumido por el sitio de docs en Cloudflare Pages (dev.kipufacturacion.com).
# No requiere autenticación — es público por diseño.

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# =============================================================================
# DEFINICIÓN MANUAL DE ENDPOINTS PÚBLICOS
# (más estable que parsear el schema OpenAPI dinámicamente)
# =============================================================================

PUBLIC_API_DOCS = {
    "version": "1.0",
    "base_url": "https://api.kipufacturacion.com",
    "auth": {
        "headers": [
            {
                "name": "X-Api-Key",
                "required": True,
                "description": "Tu clave de API. Formato: kp_live_... (producción) o kp_test_... (pruebas).",
            },
            {
                "name": "X-Idempotency-Key",
                "required": "solo en emisión",
                "description": "UUID v4 único por comprobante. Reusar el mismo key ante reintentos devuelve el comprobante original sin re-emitir.",
            },
            {
                "name": "Content-Type",
                "required": True,
                "description": "Debe ser application/json",
            },
        ]
    },
    "endpoints": [
        # ── Emisión ──────────────────────────────────────────────────────────
        {
            "method": "POST",
            "path": "/api/v1/public/integraciones/emit",
            "summary": "Emitir comprobante electrónico",
            "description": (
                "Emite cualquier tipo de comprobante electrónico. "
                "Firma con XAdES-BES, envía al SRI y devuelve el XML autorizado y URL del PDF. "
                "El campo tipo_doc determina el flujo."
            ),
            "auth": ["X-Api-Key", "X-Idempotency-Key"],
            "tags": ["Emisión"],
            "parameters": [
                {
                    "name": "tipo_doc",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "enum": ["FAC", "LIQ", "NCR", "NDB", "RET"],
                    "description": "Tipo de comprobante: FAC=Factura, LIQ=Liquidación de compra, NCR=Nota de crédito, NDB=Nota de débito, RET=Retención.",
                },
                {
                    "name": "estab",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Código del establecimiento. Ejemplo: '001'",
                },
                {
                    "name": "pto_emi",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Código del punto de emisión. Ejemplo: '001'",
                },
                {
                    "name": "secuencial",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Número secuencial de 9 dígitos. Ejemplo: '000000001'",
                },
                {
                    "name": "fecha_emision",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Fecha de emisión en formato DD/MM/YYYY. Ejemplo: '15/01/2024'",
                },
                {
                    "name": "cliente",
                    "in": "body",
                    "required": True,
                    "type": "object",
                    "description": "Datos del cliente / receptor del comprobante.",
                    "fields": {
                        "identificacion": "RUC, cédula o pasaporte del cliente.",
                        "tipo_identificacion": "04=RUC, 05=Cédula, 06=Pasaporte, 07=Consumidor final.",
                        "razon_social": "Nombre o razón social del cliente.",
                        "email": "(Opcional) Email para notificación del comprobante.",
                        "direccion": "(Opcional) Dirección del cliente.",
                    },
                },
                {
                    "name": "items",
                    "in": "body",
                    "required": True,
                    "type": "array",
                    "description": "Líneas de detalle del comprobante.",
                    "fields": {
                        "descripcion": "Descripción del bien o servicio.",
                        "cantidad": "Cantidad (numérico).",
                        "precio_unitario": "Precio unitario sin IVA.",
                        "descuento": "Descuento en valor (0 si no aplica).",
                        "iva": "Tarifa de IVA: 0, 5 o 15.",
                    },
                },
                {
                    "name": "pagos",
                    "in": "body",
                    "required": "solo FAC y LIQ",
                    "type": "array",
                    "description": "Formas de pago del comprobante.",
                    "fields": {
                        "medio": "Código SRI: 01=Efectivo, 16=Transferencia, 19=Tarjeta crédito.",
                        "total": "Monto pagado con este medio.",
                        "plazo": "Plazo en días (0 para pago inmediato).",
                        "unidad_tiempo": "Unidad del plazo: 'dias'",
                    },
                },
            ],
            "example_request": {
                "tipo_doc": "FAC",
                "estab": "001",
                "pto_emi": "001",
                "secuencial": "000000001",
                "fecha_emision": "15/01/2024",
                "cliente": {
                    "identificacion": "0987654321",
                    "tipo_identificacion": "05",
                    "razon_social": "Juan Pérez",
                    "email": "juan@ejemplo.com",
                },
                "items": [
                    {
                        "descripcion": "Servicio de consultoría técnica",
                        "cantidad": 2,
                        "precio_unitario": 150.00,
                        "descuento": 0,
                        "iva": 15,
                    }
                ],
                "pagos": [
                    {
                        "medio": "01",
                        "total": 345.00,
                        "plazo": 0,
                        "unidad_tiempo": "dias",
                    }
                ],
            },
            "example_response": {
                "ok": True,
                "clave_acceso": "1501202401234567890011234567890112345678",
                "numero_autorizacion": "2401201234567890001123456789",
                "fecha_autorizacion": "2024-01-15T14:32:10-05:00",
                "estado": "AUTORIZADO",
                "pdf_url": "https://api.kipufacturacion.com/api/v1/public/pdf/1501202401234567890011234567890112345678",
                "xml_url": "https://api.kipufacturacion.com/api/v1/public/xml/1501202401234567890011234567890112345678",
            },
        },

        # ── Invoice legacy ───────────────────────────────────────────────────
        {
            "method": "POST",
            "path": "/api/v1/public/integraciones/invoice",
            "summary": "[Deprecado] Emitir factura (FAC)",
            "description": (
                "Alias de /emit con tipo_doc=FAC. "
                "Se mantiene por compatibilidad con integraciones existentes. "
                "Usar /emit para nuevas integraciones."
            ),
            "auth": ["X-Api-Key", "X-Idempotency-Key"],
            "tags": ["Emisión"],
            "deprecated": True,
            "parameters": [],
            "example_request": None,
            "example_response": None,
        },

        # ── Validate ─────────────────────────────────────────────────────────
        {
            "method": "POST",
            "path": "/api/v1/public/integraciones/validate",
            "summary": "Validar establecimiento y punto de emisión",
            "description": (
                "Verifica que el código de establecimiento y punto de emisión existen "
                "y están activos para el emisor autenticado. "
                "Útil para validar la configuración antes de emitir."
            ),
            "auth": ["X-Api-Key"],
            "tags": ["Validación"],
            "parameters": [
                {
                    "name": "estab_codigo",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Código del establecimiento. Ejemplo: '001'",
                },
                {
                    "name": "punto_codigo",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Código del punto de emisión. Ejemplo: '001'",
                },
            ],
            "example_request": {
                "estab_codigo": "001",
                "punto_codigo": "001",
            },
            "example_response": {
                "ok": True,
                "estab": "001",
                "pto_emi": "001",
                "nombre_comercial": "Sucursal Principal",
                "direccion": "Av. Amazonas 123, Quito",
            },
        },

        # ── Status ───────────────────────────────────────────────────────────
        {
            "method": "GET",
            "path": "/api/v1/public/integraciones/status",
            "summary": "Estado del emisor",
            "description": (
                "Devuelve el estado actual del emisor: ambiente activo, "
                "vencimiento del certificado digital y conexión con los servidores del SRI."
            ),
            "auth": ["X-Api-Key"],
            "tags": ["Estado"],
            "parameters": [],
            "example_request": None,
            "example_response": {
                "ok": True,
                "ruc": "1234567890001",
                "razon_social": "Mi Empresa S.A.",
                "ambiente": "produccion",
                "certificado": {
                    "cn": "MI EMPRESA SA",
                    "vence": "2026-03-15",
                    "dias_restantes": 420,
                },
                "sri_conexion": "ok",
            },
        },

        # ── PDF ──────────────────────────────────────────────────────────────
        {
            "method": "GET",
            "path": "/api/v1/public/pdf/{clave_acceso}",
            "summary": "Descargar RIDE (PDF)",
            "description": (
                "Descarga el RIDE (Representación Impresa del Documento Electrónico) "
                "en formato PDF. No requiere autenticación — solo la clave de acceso válida."
            ),
            "auth": [],
            "tags": ["Documentos"],
            "parameters": [
                {
                    "name": "clave_acceso",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "Clave de acceso de 49 dígitos del comprobante autorizado.",
                },
                {
                    "name": "formato",
                    "in": "query",
                    "required": False,
                    "type": "string",
                    "enum": ["a4", "ticket"],
                    "description": "Formato del PDF. Por defecto: 'a4'.",
                },
            ],
            "example_request": None,
            "example_response": "application/pdf (binario)",
        },

        # ── XML ──────────────────────────────────────────────────────────────
        {
            "method": "GET",
            "path": "/api/v1/public/xml/{clave_acceso}",
            "summary": "Descargar XML autorizado",
            "description": (
                "Descarga el XML autorizado y firmado digitalmente por el SRI. "
                "No requiere autenticación — solo la clave de acceso válida."
            ),
            "auth": [],
            "tags": ["Documentos"],
            "parameters": [
                {
                    "name": "clave_acceso",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "Clave de acceso de 49 dígitos del comprobante autorizado.",
                },
            ],
            "example_request": None,
            "example_response": "application/xml (binario)",
        },

        # ── Clientes ─────────────────────────────────────────────────────────
        {
            "method": "POST",
            "path": "/api/v1/public/clientes/",
            "summary": "Crear cliente",
            "description": (
                "Registra un nuevo cliente en la base de datos del emisor. "
                "Solo acepta RUC (04) y cédula (05) vía API. "
                "Para pasaportes o extranjeros usa la app web."
            ),
            "auth": ["X-Api-Key"],
            "tags": ["Clientes"],
            "parameters": [
                {
                    "name": "identificacion",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "RUC o cédula del cliente.",
                },
                {
                    "name": "tipo_identificacion_sri",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "enum": ["04", "05"],
                    "description": "04=RUC, 05=Cédula.",
                },
                {
                    "name": "razon_social",
                    "in": "body",
                    "required": True,
                    "type": "string",
                    "description": "Nombre o razón social del cliente.",
                },
                {
                    "name": "email",
                    "in": "body",
                    "required": False,
                    "type": "string",
                    "description": "Email para notificación de comprobantes.",
                },
                {
                    "name": "telefono",
                    "in": "body",
                    "required": False,
                    "type": "string",
                    "description": "Teléfono de contacto.",
                },
                {
                    "name": "direccion",
                    "in": "body",
                    "required": False,
                    "type": "string",
                    "description": "Dirección del cliente.",
                },
            ],
            "example_request": {
                "identificacion": "0987654321",
                "tipo_identificacion_sri": "05",
                "razon_social": "Juan Pérez",
                "email": "juan@ejemplo.com",
                "telefono": "0991234567",
                "direccion": "Av. Amazonas 123, Quito",
            },
            "example_response": {
                "ok": True,
                "cliente_id": "cli_01hx7...",
                "identificacion": "0987654321",
                "razon_social": "Juan Pérez",
            },
        },

        {
            "method": "GET",
            "path": "/api/v1/public/clientes/{identificacion}",
            "summary": "Consultar cliente por identificación",
            "description": "Busca un cliente registrado por su RUC o cédula.",
            "auth": ["X-Api-Key"],
            "tags": ["Clientes"],
            "parameters": [
                {
                    "name": "identificacion",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "RUC o cédula a consultar.",
                }
            ],
            "example_request": None,
            "example_response": {
                "ok": True,
                "identificacion": "0987654321",
                "tipo_identificacion_sri": "05",
                "razon_social": "Juan Pérez",
                "email": "juan@ejemplo.com",
            },
        },

        {
            "method": "POST",
            "path": "/api/v1/public/clientes/buscar",
            "summary": "Búsqueda masiva de clientes",
            "description": "Busca múltiples clientes por sus identificaciones en una sola petición. Máximo 50 identificaciones por llamada.",
            "auth": ["X-Api-Key"],
            "tags": ["Clientes"],
            "parameters": [
                {
                    "name": "terminos",
                    "in": "body",
                    "required": True,
                    "type": "array",
                    "description": "Lista de RUCs o cédulas a buscar. Máximo 50.",
                }
            ],
            "example_request": {
                "terminos": ["0987654321", "1234567890001"],
            },
            "example_response": {
                "ok": True,
                "resultados": [
                    {"identificacion": "0987654321", "razon_social": "Juan Pérez", "encontrado": True},
                    {"identificacion": "1234567890001", "razon_social": None, "encontrado": False},
                ],
            },
        },
    ],

    # ── Tablas de referencia SRI ─────────────────────────────────────────────
    "reference_tables": {
        "tipos_identificacion": [
            {"codigo": "04", "nombre": "RUC",             "ejemplo": "1234567890001"},
            {"codigo": "05", "nombre": "Cédula",          "ejemplo": "0987654321"},
            {"codigo": "06", "nombre": "Pasaporte",       "ejemplo": "AB123456"},
            {"codigo": "07", "nombre": "Consumidor final","ejemplo": "9999999999999"},
            {"codigo": "08", "nombre": "Identificación exterior", "ejemplo": "EXT-001"},
        ],
        "formas_pago": [
            {"codigo": "01", "nombre": "Efectivo"},
            {"codigo": "15", "nombre": "Compensación de deudas"},
            {"codigo": "16", "nombre": "Tarjeta débito"},
            {"codigo": "17", "nombre": "Dinero electrónico"},
            {"codigo": "18", "nombre": "Tarjeta pre-pago"},
            {"codigo": "19", "nombre": "Tarjeta crédito"},
            {"codigo": "20", "nombre": "Otros con utilización del sistema financiero"},
            {"codigo": "21", "nombre": "Endoso de títulos"},
        ],
        "tarifas_iva": [
            {"codigo": 0,  "nombre": "Tarifa 0%"},
            {"codigo": 5,  "nombre": "Tarifa 5%"},
            {"codigo": 15, "nombre": "Tarifa 15% (general)"},
        ],
        "tipos_comprobante": [
            {"tipo_doc": "FAC", "nombre": "Factura",                    "cod_sri": "01"},
            {"tipo_doc": "LIQ", "nombre": "Liquidación de compra",      "cod_sri": "03"},
            {"tipo_doc": "NCR", "nombre": "Nota de crédito",            "cod_sri": "04"},
            {"tipo_doc": "NDB", "nombre": "Nota de débito",             "cod_sri": "05"},
            {"tipo_doc": "RET", "nombre": "Comprobante de retención",   "cod_sri": "07"},
        ],
    },

    # ── Errores ──────────────────────────────────────────────────────────────
    "errors": [
        {"code": "INVALID_API_KEY",         "http": 401, "description": "API Key inválida o inactiva."},
        {"code": "MISSING_API_KEY",         "http": 401, "description": "Header X-Api-Key ausente."},
        {"code": "MISSING_IDEMPOTENCY_KEY", "http": 400, "description": "Header X-Idempotency-Key requerido en emisión."},
        {"code": "VALIDATION_ERROR",        "http": 422, "description": "Campos del body inválidos. Ver array 'errors' en la respuesta."},
        {"code": "SRI_REJECTED",            "http": 422, "description": "Comprobante rechazado por el SRI. Ver campo 'detail' para mensajes SRI."},
        {"code": "DUPLICATE_COMPROBANTE",   "http": 409, "description": "Ya existe un comprobante con ese número para el emisor."},
        {"code": "EMISOR_NOT_CONFIGURED",   "http": 412, "description": "El emisor no tiene certificado digital activo."},
        {"code": "SRI_UNAVAILABLE",         "http": 503, "description": "Servidores SRI no disponibles. Reintentar con mismo X-Idempotency-Key."},
        {"code": "RATE_LIMIT_EXCEEDED",     "http": 429, "description": "Demasiadas peticiones. Ver header Retry-After."},
    ],
}


# =============================================================================
# GET /api/v1/public/openapi-public
# =============================================================================

@router.get(
    "/openapi-public",
    summary     = "Documentación pública de la API",
    description = "Devuelve los endpoints públicos con parámetros y ejemplos. Consumido por dev.kipufacturacion.com.",
    tags        = ["📖 Dev Docs"],
    include_in_schema = True,
)
async def get_public_api_docs():
    return JSONResponse(
        content = PUBLIC_API_DOCS,
        headers = {
            # Cachear 1 hora en CDN — las docs no cambian con frecuencia
            "Cache-Control": "public, max-age=3600, s-maxage=3600",
            # CORS abierto — Cloudflare Pages necesita leer esto
            "Access-Control-Allow-Origin": "*",
        }
    )