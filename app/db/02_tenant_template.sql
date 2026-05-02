-- =============================================================================
-- KIPU — 02_tenant_template.sql
-- Crea el primer tenant (tenant_001) y la función para crear nuevos tenants.
-- app/db/02_tenant_template.sql
-- CUÁNDO EJECUTAR:
--   - Este script: una sola vez al iniciar el sistema (crea tenant_001)
--   - Para nuevos tenants: SELECT kipu_create_tenant('tenant_002');
-- =============================================================================

DROP FUNCTION IF EXISTS kipu_create_tenant(VARCHAR);

CREATE OR REPLACE FUNCTION kipu_create_tenant(p_schema VARCHAR)
RETURNS void AS $$
BEGIN

    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', p_schema);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.establecimientos (
            id                  SERIAL      PRIMARY KEY,
            emisor_id           INTEGER     NOT NULL REFERENCES public.emisores(id) ON DELETE CASCADE,
            codigo              VARCHAR(3)  NOT NULL,
            nombre_comercial    TEXT,
            direccion           TEXT        NOT NULL,
            is_active           BOOLEAN     DEFAULT true,
            UNIQUE (emisor_id, codigo)
        )
    ', p_schema);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.puntos_emision (
            id                  SERIAL      PRIMARY KEY,
            establecimiento_id  INTEGER     NOT NULL REFERENCES %I.establecimientos(id) ON DELETE CASCADE,
            emisor_id           INTEGER     NOT NULL REFERENCES public.emisores(id) ON DELETE CASCADE,
            codigo              VARCHAR(3)  NOT NULL,
            secuencial_actual   INTEGER     DEFAULT 1,
            nombre              TEXT,
            is_active           BOOLEAN     DEFAULT true,
            UNIQUE (establecimiento_id, codigo)
        )
    ', p_schema, p_schema);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.clientes_emisor (
            id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            emisor_id               INTEGER     NOT NULL REFERENCES public.emisores(id) ON DELETE CASCADE,
            sujeto_global_id        UUID        REFERENCES public.sujetos_global(id) ON DELETE SET NULL,
            email                   VARCHAR(150),
            telefono                VARCHAR(20),
            tipo_identificacion_sri VARCHAR(2),
            identificacion          VARCHAR(20),
            razon_social            TEXT,
            direccion               TEXT,
            created_at              TIMESTAMPTZ DEFAULT now(),
            UNIQUE (emisor_id, identificacion)
        )
    ', p_schema);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.invoices_emitidas (
            id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            emisor_id                   INTEGER     NOT NULL REFERENCES public.emisores(id),
            punto_emision_id            INTEGER     NOT NULL REFERENCES %I.puntos_emision(id),
            cliente_emisor_id           UUID        REFERENCES %I.clientes_emisor(id) ON DELETE SET NULL,
            clave_acceso                VARCHAR(49) UNIQUE,
            secuencial                  VARCHAR(9)  NOT NULL,
            numero_factura              VARCHAR(17),
            fecha_emision               DATE        NOT NULL DEFAULT CURRENT_DATE,
            estado                      VARCHAR(20) DEFAULT %L,
            identificacion_comprador    VARCHAR(20) NOT NULL,
            razon_social_comprador      TEXT        NOT NULL,
            email_comprador             VARCHAR(150),
            importe_total               NUMERIC(12,2) NOT NULL,
            subtotal_iva                NUMERIC(12,2) DEFAULT 0,
            subtotal_0                  NUMERIC(12,2) DEFAULT 0,
            valor_iva                   NUMERIC(12,2) DEFAULT 0,
            datos_factura               JSONB       NOT NULL,
            xml_path                    TEXT,
            pdf_path                    TEXT,
            mensajes_sri                JSONB,
            fecha_envio_sri             TIMESTAMPTZ,
            fecha_autorizacion          TIMESTAMPTZ,
            retry_count                 INTEGER     DEFAULT 0,
            last_retry                  TIMESTAMPTZ,
            created_at                  TIMESTAMPTZ DEFAULT now()
        )
    ', p_schema, p_schema, p_schema, 'PENDIENTE');

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.invoices_recibidas (
            id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            emisor_id               INTEGER     NOT NULL REFERENCES public.emisores(id),
            ruc_proveedor           VARCHAR(13) NOT NULL,
            razon_social_proveedor  TEXT        NOT NULL,
            clave_acceso            VARCHAR(49) UNIQUE,
            numero_factura          VARCHAR(17),
            fecha_emision           DATE        NOT NULL,
            subtotal_0              NUMERIC(12,2) DEFAULT 0,
            subtotal_iva            NUMERIC(12,2) DEFAULT 0,
            valor_iva               NUMERIC(12,2) DEFAULT 0,
            importe_total           NUMERIC(12,2) NOT NULL,
            categoria_gasto         VARCHAR(50),
            deducible_renta         BOOLEAN     DEFAULT true,
            notas_cliente           TEXT,
            xml_path                TEXT,
            xml_raw                 JSONB,
            fuente                  VARCHAR(10) DEFAULT %L,
            procesado               BOOLEAN     DEFAULT false,
            created_at              TIMESTAMPTZ DEFAULT now()
        )
    ', p_schema, 'MANUAL');

    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_estab_emisor ON %I.establecimientos(emisor_id)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_pe_estab ON %I.puntos_emision(establecimiento_id)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_pe_emisor ON %I.puntos_emision(emisor_id)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_cli_emisor ON %I.clientes_emisor(emisor_id)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_cli_ident ON %I.clientes_emisor(identificacion)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_inv_emisor ON %I.invoices_emitidas(emisor_id)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_inv_estado ON %I.invoices_emitidas(estado)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_inv_fecha ON %I.invoices_emitidas(fecha_emision)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_inv_clave ON %I.invoices_emitidas(clave_acceso)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_rec_emisor ON %I.invoices_recibidas(emisor_id)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_rec_fecha ON %I.invoices_recibidas(fecha_emision)
    ', p_schema, p_schema);
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%s_rec_proveedor ON %I.invoices_recibidas(ruc_proveedor)
    ', p_schema, p_schema);

    RAISE NOTICE 'Tenant schema "%" listo.', p_schema;
END;
$$ LANGUAGE plpgsql;


-- Crear el primer tenant
SELECT kipu_create_tenant('tenant_001');


-- Verificación
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname IN ('public', 'tenant_001')
  AND tablename NOT LIKE 'pg_%'
ORDER BY schemaname, tablename;