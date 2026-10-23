# app/api/v1/public/integraciones.py
from typing import Optional
from fastapi import APIRouter, Depends, Body, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_api_key
from app.core.config import settings
from app.schemas.integracion import ValidatePuntoRequest
from app.schemas.factura import (
    DocumentoCreate,
    FacturaCreate,
    NotaCreditoCreate,
    NotaDebitoCreate,
    LiquidacionCompraCreate,
    RetencionCreate,
    EmisionResponse,
    ErrorResponse,
)
from app.services.integracion_service import validar_estructura_core, obtener_status_core
from app.services.documento_service import emitir_documento_core
from app.core.idempotency import verificar_idempotency, guardar_idempotency
from app.core.rate_limit import RateLimit, RateLimitScope

router = APIRouter()

# ─── Respuestas de error reutilizables para OpenAPI ───────────────────────────
_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "**Datos inválidos.** El cuerpo no cumple las reglas SRI (consumidor final > $50, forma de pago inválida, tipo de identificación no permitido, etc.)."},
    401: {"model": ErrorResponse, "description": "**No autenticado.** Falta `X-Api-Key` o la clave es inválida/expirada."},
    402: {"model": ErrorResponse, "description": "**Sin créditos.** La suscripción del emisor está vencida y no tiene créditos API disponibles."},
    404: {"model": ErrorResponse, "description": "**No encontrado.** El cliente, documento origen o punto de emisión referenciado no existe."},
    409: {"model": ErrorResponse, "description": "**Idempotencia duplicada.** Ya existe un comprobante emitido con la misma `X-Idempotency-Key`. Se devuelve el resultado original."},
    429: {"model": ErrorResponse, "description": "**Rate limit excedido.** Se superó el límite de emisiones por minuto. Reintenta después del tiempo indicado en `Retry-After`."},
    500: {"model": ErrorResponse, "description": "**Error interno.** Fallo inesperado al generar el comprobante. Contacta soporte con la `X-Idempotency-Key` usada."},
}


# ─── HELPER DE EMISIÓN COMÚN ──────────────────────────────────────────────────
async def _procesar_emision_base(
    tipo_doc: str,
    data_dict: dict,
    x_idempotency_key: Optional[str],
    x_api_key: Optional[str],
    x_internal_key: Optional[str],
    db: AsyncSession,
):
    if not x_idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el header X-Idempotency-Key. Usa un UUID v4 único por comprobante."
        )

    es_interno = False
    if x_internal_key and x_internal_key == settings.INTERNAL_API_KEY:
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Servicios internos requieren X-Api-Key para identificar el emisor."
            )
        auth       = await verify_api_key(x_api_key, db)
        es_interno = True
    elif x_api_key:
        auth = await verify_api_key(x_api_key, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Usa X-Api-Key o X-Internal-Key + X-Api-Key."
        )

    emisor_id  = auth["emisor_id"]
    api_key_id = auth.get("api_key_id") if not es_interno else None
    es_sandbox = auth.get("es_sandbox", False)

    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    result = await emitir_documento_core(
        tipo_doc   = tipo_doc,
        data       = data_dict,
        emisor_id  = emisor_id,
        db         = db,
        api_key_id = api_key_id,
        es_sandbox = es_sandbox,
    )

    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)

    return result


# =============================================================================
# ENDPOINTS DE DIAGNÓSTICO
# =============================================================================

@router.post(
    "/validate",
    summary="Validar establecimiento y punto de emisión",
    tags=["🔧 Utilidades", "public_export"],
    description=(
        "Verifica que el **establecimiento** y **punto de emisión** estén configurados "
        "correctamente para el emisor autenticado.\n\n"
        "Úsalo antes de la primera emisión para confirmar que los datos fiscales "
        "están completos (RUC, certificado de firma, secuenciales activos)."
    ),
    responses={
        200: {"description": "Estructura válida. Devuelve detalle del establecimiento y punto de emisión."},
        401: {"model": ErrorResponse, "description": "API Key inválida o no proporcionada."},
        404: {"model": ErrorResponse, "description": "Establecimiento o punto de emisión no encontrado."},
    },
)
async def api_validate_structure(
    request: ValidatePuntoRequest,
    auth:    dict         = Depends(verify_api_key),
    db:      AsyncSession = Depends(get_db),
):
    return await validar_estructura_core(auth["emisor_id"], request.estab_codigo, request.punto_codigo, db)


@router.get(
    "/status",
    summary="Resumen completo del estado del emisor",
    tags=["🔧 Utilidades", "public_export"],
    description=(
        "Devuelve el estado general del emisor autenticado:\n\n"
        "- **Datos fiscales:** RUC, razón social, ambiente (pruebas/producción).\n"
        "- **Suscripción:** plan activo, créditos API restantes, fecha de vencimiento.\n"
        "- **Certificado de firma:** vigencia, días restantes.\n"
        "- **Establecimientos y puntos de emisión** configurados.\n\n"
        "Ideal para dashboards de monitoreo o validación pre-integración."
    ),
    responses={
        200: {"description": "Estado completo del emisor."},
        401: {"model": ErrorResponse, "description": "API Key inválida o no proporcionada."},
    },
)
async def api_get_status(
    auth: dict         = Depends(verify_api_key),
    db:   AsyncSession = Depends(get_db),
):
    return await obtener_status_core(auth["emisor_id"], db)


# =============================================================================
# RUTA LEGACY UNIFICADA (MANTENIDA POR COMPATIBILIDAD)
# =============================================================================

@router.post(
    "/emit",
    summary="Emitir comprobante (Legacy / Multi-tipo)",
    tags=["📦 Legacy", "public_export"],
    description=(
        "⚠️ **Ruta legacy.** Usa las rutas específicas (`/emitir/factura`, `/emitir/nota-credito`, etc.) "
        "para mejor validación y documentación.\n\n"
        "Acepta cualquier tipo de documento en un solo endpoint. El campo `tipo_doc` determina "
        "el tipo: `FAC`, `NCR`, `NDB`, `LIQ`, `RET`.\n\n"
        "**Headers requeridos:**\n"
        "- `X-Api-Key` — clave de API del emisor.\n"
        "- `X-Idempotency-Key` — UUID v4 único por comprobante (evita duplicados)."
    ),
    response_model=EmisionResponse,
    responses=_ERROR_RESPONSES,
)
async def api_emit(
    request:           Request,
    data:              dict          = Body(
        ...,
        openapi_examples={
            "factura_simple": {
                "summary": "Factura simple con IVA 15%",
                "value": {
                    "tipo_doc": "FAC",
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "cliente": {
                        "tipo_id": "05",
                        "nombre": "Juan Pérez",
                        "identificacion": "1722334455",
                        "email": "juan@example.com"
                    },
                    "items": [{"descripcion": "Servicio de consultoría", "cantidad": 1, "precio_unitario": 100.00, "tipo_iva": "15"}],
                    "pagos": [{"forma_pago": "20", "total": 115.00}],
                    "estado_cobro": "PAGADO",
                    "forma_pago_cobro": "TRANSFERENCIA"
                }
            },
            "retencion": {
                "summary": "Retención sobre documento recibido",
                "value": {
                    "tipo_doc": "RET",
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "doc_origen_recibido_id": "uuid-del-documento-recibido",
                    "periodo_fiscal": "10/2026",
                    "impuestos_ret": [
                        {"codigo": "1", "codigoRetencion": "303", "baseImponible": 500.00, "porcentajeRetener": 10.0, "valorRetenido": 50.00}
                    ]
                }
            }
        }
    ),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key", description="UUID v4 único por comprobante. Garantiza idempotencia: si reenvías la misma clave, recibes el resultado original sin emitir de nuevo."),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key", description="Clave de API del emisor. Se obtiene en el panel de Kipu → Configuración → API Keys."),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key", description="Clave interna de Kipu (solo servicios propios). Requiere `X-Api-Key` adicional."),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    tipo_doc = data.pop("tipo_doc", "FAC").upper()
    return await _procesar_emision_base(tipo_doc, data, x_idempotency_key, x_api_key, x_internal_key, db)


# =============================================================================
# RUTAS ESPECÍFICAS POR TIPO DE DOCUMENTO
# =============================================================================

@router.post(
    "/emitir/factura",
    summary="Emitir Factura Electrónica",
    tags=["🧾 Facturación", "public_export"],
    description=(
        "Emite una **Factura Electrónica** (código SRI 01) para ventas de bienes o servicios.\n\n"
        "**Flujo:**\n"
        "1. Kipu valida los datos, calcula impuestos (IVA 0%, 5%, 15%) y genera el XML.\n"
        "2. El XML se firma con el certificado digital del emisor.\n"
        "3. Se persiste en base de datos y se encola para autorización del SRI.\n"
        "4. La respuesta incluye la **clave de acceso** de 49 dígitos para consulta posterior.\n\n"
        "**Reglas SRI:**\n"
        "- Consumidor Final (`tipo_id=07`): máximo $50.00 por factura.\n"
        "- Transacciones ≥ $500: no aceptan efectivo (`forma_pago=01`).\n"
        "- La suma de `pagos[].total` debe coincidir con el total calculado.\n\n"
        "**Estado de cobro:** opcional. Si no se envía, se registra como `PAGADO`. "
        "Valores válidos: `PAGADO`, `PENDIENTE`, `PARCIAL`.\n\n"
        "**Identificación del comprador:** envía `cliente_id` (UUID de cliente existente en Kipu) "
        "o el objeto `cliente` para crear uno al vuelo."
    ),
    response_model=EmisionResponse,
    responses=_ERROR_RESPONSES,
)
async def api_emit_invoice(
    data:              FacturaCreate = Body(
        ...,
        openapi_examples={
            "factura_pagada": {
                "summary": "Factura pagada con transferencia",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "cliente": {
                        "tipo_id": "05",
                        "nombre": "Juan Pérez",
                        "identificacion": "1722334455",
                        "email": "juan@example.com",
                        "direccion": "Av. Amazonas, Quito"
                    },
                    "items": [
                        {
                            "descripcion": "Servicio de consultoría IT",
                            "cantidad": 1,
                            "precio_unitario": 200.00,
                            "tipo_iva": "15"
                        },
                        {
                            "codigo": "LIC-001",
                            "descripcion": "Licencia de software anual",
                            "cantidad": 2,
                            "precio_unitario": 50.00,
                            "descuento": 10.00,
                            "tipo_iva": "15"
                        }
                    ],
                    "pagos": [{"forma_pago": "20", "total": 333.50}],
                    "campos_adicionales": [
                        {"nombre": "Proyecto", "valor": "Migración a la nube"}
                    ],
                    "estado_cobro": "PAGADO",
                    "forma_pago_cobro": "TRANSFERENCIA",
                    "numero_comprobante_pago": "TRF-2026-001",
                    "fecha_pago": "2026-10-22"
                }
            },
            "factura_pendiente": {
                "summary": "Factura a crédito (pendiente de cobro)",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "cliente": {
                        "tipo_id": "04",
                        "nombre": "Empresa ABC S.A.",
                        "identificacion": "1790012345001",
                        "email": "pagos@empresaabc.com"
                    },
                    "items": [
                        {"descripcion": "Hosting anual", "cantidad": 1, "precio_unitario": 500.00, "tipo_iva": "15"}
                    ],
                    "pagos": [{"forma_pago": "20", "total": 575.00, "plazo": "30", "unidad_tiempo": "dias"}],
                    "estado_cobro": "PENDIENTE"
                }
            },
            "factura_sin_cobro": {
                "summary": "Factura sin estado de cobro (default: PAGADO)",
                "value": {
                    "cliente_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
                    "items": [
                        {"descripcion": "Hosting mensual", "cantidad": 1, "precio_unitario": 29.99, "tipo_iva": "15"}
                    ],
                    "pagos": [{"forma_pago": "20", "total": 34.49}]
                }
            }
        }
    ),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key", description="UUID v4 único por comprobante. Garantiza idempotencia."),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key", description="Clave de API del emisor."),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key", description="Clave interna (solo servicios Kipu)."),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    payload = data.model_dump(exclude_unset=True)
    return await _procesar_emision_base("FAC", payload, x_idempotency_key, x_api_key, x_internal_key, db)


@router.post(
    "/emitir/nota-credito",
    summary="Emitir Nota de Crédito",
    tags=["📄 Notas de Crédito / Débito", "public_export"],
    description=(
        "Emite una **Nota de Crédito Electrónica** (código SRI 04) que modifica una factura autorizada.\n\n"
        "**Casos de uso:** devolución de mercadería, descuento posterior, anulación parcial o total.\n\n"
        "**Origen del documento:**\n"
        "- `doc_origen_id` — UUID de una factura emitida en Kipu (los datos del comprador se heredan).\n"
        "- `doc_origen_numero` + `doc_origen_fecha` + `cliente_origen` — documento externo (no está en Kipu).\n\n"
        "**Restricciones SRI:**\n"
        "- No se puede emitir sobre Consumidor Final (`tipo_id=07`).\n"
        "- Los ítems deben corresponder a líneas de la factura original.\n"
        "- Motivos válidos: `DEVOLUCION DE MERCADERIA`, `ANULACION DE COMPROBANTE`, "
        "`DESCUENTO COMERCIAL`, `CORRECION EN FACTURACION`."
    ),
    response_model=EmisionResponse,
    responses=_ERROR_RESPONSES,
)
async def api_emit_credit_note(
    data:              NotaCreditoCreate = Body(
        ...,
        openapi_examples={
            "ncr_documento_kipu": {
                "summary": "Nota de crédito sobre factura emitida en Kipu",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "doc_origen_id": "a3b8c9d0-1234-5678-9abc-def012345678",
                    "motivo": "DEVOLUCION DE MERCADERIA",
                    "items": [
                        {"descripcion": "Licencia de software anual", "cantidad": 1, "precio_unitario": 50.00, "tipo_iva": "15"}
                    ]
                }
            },
            "ncr_documento_externo": {
                "summary": "Nota de crédito sobre documento externo",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "doc_origen_numero": "001-001-000000123",
                    "doc_origen_fecha": "15/10/2026",
                    "doc_origen_cod_doc": "01",
                    "cliente_origen": {
                        "tipo_id": "04",
                        "identificacion": "1790012345001",
                        "razon_social": "Empresa ABC S.A."
                    },
                    "motivo": "ANULACION DE COMPROBANTE",
                    "items": [
                        {"descripcion": "Producto devuelto", "cantidad": 2, "precio_unitario": 25.00, "tipo_iva": "15"}
                    ]
                }
            }
        }
    ),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key", description="UUID v4 único por comprobante."),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key", description="Clave de API del emisor."),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key", description="Clave interna (solo servicios Kipu)."),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    payload = data.model_dump(exclude_unset=True)
    return await _procesar_emision_base("NCR", payload, x_idempotency_key, x_api_key, x_internal_key, db)


@router.post(
    "/emitir/nota-debito",
    summary="Emitir Nota de Débito",
    tags=["📄 Notas de Crédito / Débito", "public_export"],
    description=(
        "Emite una **Nota de Débito Electrónica** (código SRI 05) que carga valores adicionales "
        "sobre una factura autorizada.\n\n"
        "**Casos de uso:** intereses por mora, gastos administrativos, diferencias de precio, penalizaciones.\n\n"
        "**Origen del documento:** igual que la Nota de Crédito (`doc_origen_id` o datos manuales).\n\n"
        "**Estado de cobro:** opcional. Si no se envía, se registra como `PAGADO`.\n\n"
        "**Restricciones SRI:**\n"
        "- No se puede emitir sobre Consumidor Final (`tipo_id=07`).\n"
        "- Cada motivo lleva `razon` (texto) y `valor` (monto del cargo)."
    ),
    response_model=EmisionResponse,
    responses=_ERROR_RESPONSES,
)
async def api_emit_debit_note(
    data:              NotaDebitoCreate = Body(
        ...,
        openapi_examples={
            "ndb_mora_pagada": {
                "summary": "Nota de débito por mora (cobrada)",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "doc_origen_id": "a3b8c9d0-1234-5678-9abc-def012345678",
                    "motivos": [
                        {"razon": "Intereses por mora — 30 días", "valor": 15.00},
                        {"razon": "Gastos administrativos de cobranza", "valor": 5.00}
                    ],
                    "estado_cobro": "PAGADO",
                    "forma_pago_cobro": "TRANSFERENCIA"
                }
            },
            "ndb_pendiente": {
                "summary": "Nota de débito pendiente de cobro",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "doc_origen_id": "a3b8c9d0-1234-5678-9abc-def012345678",
                    "motivos": [
                        {"razon": "Diferencia de precio por ajuste contractual", "valor": 50.00}
                    ],
                    "estado_cobro": "PENDIENTE"
                }
            }
        }
    ),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key", description="UUID v4 único por comprobante."),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key", description="Clave de API del emisor."),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key", description="Clave interna (solo servicios Kipu)."),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    payload = data.model_dump(exclude_unset=True)
    return await _procesar_emision_base("NDB", payload, x_idempotency_key, x_api_key, x_internal_key, db)


@router.post(
    "/emitir/liquidacion-compra",
    summary="Emitir Liquidación de Compra",
    tags=["🛒 Liquidaciones de Compra", "public_export"],
    description=(
        "Emite una **Liquidación de Compra de Bienes o Prestación de Servicios** (código SRI 03).\n\n"
        "Se usa cuando el proveedor no emite factura: personas naturales no obligadas a llevar "
        "contabilidad, servicios ocasionales, sector agrícola, artesanos, etc.\n\n"
        "**Importante:** el stock de los ítems se **suma** al inventario (es una compra).\n\n"
        "**Estado de cobro:** opcional. Si no se envía, se registra como `PAGADO`.\n\n"
        "**Restricciones SRI:**\n"
        "- Solo acepta cédula (`05`), pasaporte (`06`) o identificación del exterior (`08`).\n"
        "- **No** acepta RUC (`04`) ni Consumidor Final (`07`).\n"
        "- Transacciones ≥ $500: no aceptan efectivo."
    ),
    response_model=EmisionResponse,
    responses=_ERROR_RESPONSES,
)
async def api_emit_liquidation(
    data:              LiquidacionCompraCreate = Body(
        ...,
        openapi_examples={
            "liquidacion_efectivo": {
                "summary": "Compra a proveedor informal (pagada en efectivo)",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "cliente": {
                        "tipo_id": "05",
                        "nombre": "María López",
                        "identificacion": "1311223344",
                        "direccion": "Portoviejo, Manabí"
                    },
                    "items": [
                        {
                            "descripcion": "Naranjas orgánicas",
                            "cantidad": 100,
                            "precio_unitario": 0.25,
                            "tipo_iva": "0",
                            "unidad_medida": "KG"
                        }
                    ],
                    "pagos": [{"forma_pago": "01", "total": 25.00}],
                    "estado_cobro": "PAGADO",
                    "forma_pago_cobro": "EFECTIVO",
                    "fecha_pago": "2026-10-22"
                }
            },
            "liquidacion_sin_cobro": {
                "summary": "Liquidación sin estado de cobro (default: PAGADO)",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "cliente": {
                        "tipo_id": "05",
                        "nombre": "Pedro Gómez",
                        "identificacion": "1305667788",
                        "direccion": "Manta, Manabí"
                    },
                    "items": [
                        {"descripcion": "Servicio de limpieza", "cantidad": 1, "precio_unitario": 80.00, "tipo_iva": "15"}
                    ],
                    "pagos": [{"forma_pago": "01", "total": 92.00}]
                }
            }
        }
    ),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key", description="UUID v4 único por comprobante."),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key", description="Clave de API del emisor."),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key", description="Clave interna (solo servicios Kipu)."),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    payload = data.model_dump(exclude_unset=True)
    return await _procesar_emision_base("LIQ", payload, x_idempotency_key, x_api_key, x_internal_key, db)


@router.post(
    "/emitir/retencion",
    summary="Emitir Comprobante de Retención",
    tags=["🛡️ Retenciones", "public_export"],
    description=(
        "Emite un **Comprobante de Retención Electrónico** (código SRI 07, versión 2.0).\n\n"
        "Se emite sobre un documento recibido de un proveedor (factura, nota de venta) o sobre "
        "una Liquidación de Compra emitida por el propio emisor.\n\n"
        "**Orígenes soportados:**\n"
        "- `doc_origen_recibido_id` — documento recibido registrado en Kipu.\n"
        "- `doc_origen_emitido_id` — liquidación de compra emitida en Kipu.\n"
        "- `doc_origen_numero` + `doc_origen_fecha` + `proveedor_origen` — documento externo.\n\n"
        "**Códigos de retención comunes:**\n"
        "- Renta (`codigo=1`): 303 (Honorarios 10%), 312 (Transferencia bienes 1%), 340 (Otras compras 1%)\n"
        "- IVA (`codigo=2`): 725 (IVA presuntivo 100%), 731 (IVA 30%), 732 (IVA 70%)\n\n"
        "**Restricción:** solo se permite una retención por documento recibido."
    ),
    response_model=EmisionResponse,
    responses=_ERROR_RESPONSES,
)
async def api_emit_retention(
    data:              RetencionCreate = Body(
        ...,
        openapi_examples={
            "retencion_renta_iva": {
                "summary": "Retención de Renta + IVA sobre documento recibido",
                "value": {
                    "establecimiento": "001",
                    "punto_emision": "001",
                    "doc_origen_recibido_id": "c1d2e3f4-5678-90ab-cdef-1234567890ab",
                    "periodo_fiscal": "10/2026",
                    "impuestos_ret": [
                        {
                            "codigo": "1",
                            "codigoRetencion": "303",
                            "baseImponible": 500.00,
                            "porcentajeRetener": 10.0,
                            "valorRetenido": 50.00,
                            "codDocSustento": "01"
                        },
                        {
                            "codigo": "2",
                            "codigoRetencion": "725",
                            "baseImponible": 75.00,
                            "porcentajeRetener": 100.0,
                            "valorRetenido": 75.00,
                            "codDocSustento": "01"
                        }
                    ]
                }
            }
        }
    ),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key", description="UUID v4 único por comprobante."),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key", description="Clave de API del emisor."),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key", description="Clave interna (solo servicios Kipu)."),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    payload = data.model_dump(exclude_unset=True)
    return await _procesar_emision_base("RET", payload, x_idempotency_key, x_api_key, x_internal_key, db)