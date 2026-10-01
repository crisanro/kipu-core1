# app/services/declaraciones/demo.py
#
# Datos de ejemplo para usuarios sin suscripción (sin cambios respecto al router original).


def datos_demo_iva() -> dict:
    return {
        "periodo": {"desde": "2026-08-01", "hasta": "2026-08-31", "mes": "2026-08", "tipo": "MENSUAL"},
        "preguntas": {
            "requiere_informar":        True,
            "credito_tributario_renta": True,
            "comercio_exterior":        False,
            "notas_credito":            False,
            "ha_realizado_ventas":      True,
            "ventas_tarifa_0":          True,
            "ventas_tarifa_nz":         True,
            "ha_realizado_compras":     True,
            "importaciones":            False,
            "ha_realizado_retenciones": False,
            "materiales_construccion":  False,
        },
        "ventas": {
            "desglose": [
                {"tarifa": 15, "bruto": 3240.50, "ncr": 0, "neto": 3240.50, "iva_bruto": 486.08, "iva_neto": 486.08, "num_docs": 18},
                {"tarifa": 0,  "bruto": 890.00,  "ncr": 0, "neto": 890.00,  "iva_bruto": 0,      "iva_neto": 0,      "num_docs": 4 },
            ],
            "casilleros": {
                "401": 3240.50, "411": 3240.50, "421": 486.08,
                "403": 890.00,  "413": 890.00,
                "409": 4130.50, "419": 4130.50, "429": 486.08,
                "111": 22, "113": 0,
            },
        },
        "compras": {
            "desglose": [
                {"tarifa": 15, "con_credito": 1850.00, "sin_credito": 0, "ncr": 0,
                 "neto": 1850.00, "iva_credito": 277.50, "iva_sin_credito": 0, "iva_neto": 277.50},
            ],
            "casilleros": {
                "500": 1850.00, "510": 1850.00, "520": 277.50,
                "502": 0,       "512": 0,       "522": 0,
                "507": 320.00,  "517": 320.00,
                "509": 2170.00, "519": 2170.00, "529": 277.50,
                "115": 14, "119": 0,
            },
        },
        "retenciones_emitidas":  {"desglose": [], "casilleros": {"721": 0, "723": 0, "725": 0, "727": 0, "729": 0, "731": 0, "799": 0, "801": 0}},
        "retenciones_recibidas": {"casilleros": {"609": 0}},
        "resumen": {
            "casilleros": {
                "499": 486.08, "564": 277.50,
                "601": 208.58, "602": 0,
                "609": 0,      "620": 208.58,
                "699": 208.58, "799": 0,
                "801": 0,      "859": 208.58,
            },
            "campos_manuales": [
                {"casillero": "605", "descripcion": "Saldo crédito tributario mes anterior (adquisiciones)"},
                {"casillero": "606", "descripcion": "Saldo crédito tributario mes anterior (retenciones)"},
            ],
        },
        "notas": ["⚠️ Estos son datos de ejemplo — suscríbete para ver tus datos reales."],
    }


def datos_demo_renta() -> dict:
    return {
        "periodo": {"anio": 2025, "desde": "2025-01-01", "hasta": "2025-12-31"},
        "preguntas": {
            "tiene_ingresos":          True,
            "tiene_gastos_deducibles": True,
            "tiene_retenciones":       True,
            "supera_fraccion_basica":  True,
            "debe_pagar":              True,
            "tiene_saldo_favor":       False,
        },
        "ingresos":       {"brutos": 28500.00, "ncr": 0, "netos": 28500.00},
        "gastos":         {"deducibles": 12300.00},
        "base_imponible": 16200.00,
        "tabla_ir":       {"tramo": {"desde": 15159, "hasta": 19682, "base": 163, "porcentaje": 10}, "tabla_anio": 2025, "nota": "Verificar con resolución SRI vigente"},
        "resumen": {
            "casilleros": {
                "501": 28500.00, "502": 0, "503": 28500.00,
                "601": 12300.00,
                "699": 16200.00, "701": 16200.00,
                "801": 1204.10,
                "841": 890.00,
                "859": 314.10,  "869": 0,
            },
            "campos_manuales": [
                {"casillero": "504", "descripcion": "Otros ingresos (arrendamientos, intereses, etc.)"},
                {"casillero": "602", "descripcion": "Gastos personales (salud, educación, etc.)"},
            ],
            "resultado": {
                "impuesto_causado": 1204.10,
                "retenciones":      890.00,
                "a_pagar":          314.10,
                "saldo_favor":      0,
            },
        },
        "notas": ["⚠️ Estos son datos de ejemplo — suscríbete para ver tus datos reales."],
    }


def datos_demo_ats() -> dict:
    return {
        "periodo": {"desde": "2026-08-01", "hasta": "2026-08-31", "mes": "2026-08"},
        "preguntas": {
            "tiene_ventas":                True,
            "tiene_compras":               True,
            "tiene_retenciones_emitidas":  False,
            "tiene_retenciones_recibidas": False,
            "obligado_contabilidad":       True,
        },
        "ventas": {
            "detalle": [
                {"tipo_doc": "FAC", "cod_doc": "01", "numero_doc": "001-001-000000022",
                 "fecha_emision": "2026-08-15", "tipo_id": "04", "identificacion": "1307715712001",
                 "razon_social": "EMPRESA EJEMPLO S.A.", "base_iva_nz": 3240.50, "base_iva_0": 890.00, "iva": 486.08},
            ],
            "retenciones": [],
            "totales": {"num_docs": 22, "base_iva_diferente_0": 3240.50, "base_iva_0": 890.00, "iva": 486.08, "total": 4616.58},
        },
        "compras": {
            "detalle": [
                {"tipo_doc": "FAC", "cod_doc": "01", "numero_doc": "001-001-000000100",
                 "fecha_emision": "2026-08-05", "ruc_proveedor": "1391936379001",
                 "razon_proveedor": "PROVEEDOR EJEMPLO CIA. LTDA.", "base_iva_nz": 1850.00,
                 "iva_credito": 277.50, "total": 2127.50, "fuente": "🔵 XML"},
            ],
            "retenciones": [],
            "totales": {"num_docs": 14, "base_iva_diferente_0": 1850.00, "base_iva_0": 320.00, "iva_con_credito": 277.50, "iva_sin_credito": 0, "total": 2447.50},
        },
        "resumen": {
            "emisor": {"ruc": "9999999999001", "razon_social": "EMPRESA DEMO S.A.", "obligado_contabilidad": "SI"},
            "periodo": "2026-08-01",
            "totales_ventas":  {"num_docs": 22, "total": 4616.58},
            "totales_compras": {"num_docs": 14, "total": 2447.50},
            "total_ret_emitidas":  0,
            "total_ret_recibidas": 0,
        },
        "notas": ["⚠️ Estos son datos de ejemplo — suscríbete para ver tus datos reales."],
    }