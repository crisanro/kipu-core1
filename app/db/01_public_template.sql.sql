-- =============================================================================
-- KIPU — 01_public.sql
-- Schema PUBLIC: tablas globales, auth, control del sistema y créditos.
-- Ejecutar UNA SOLA VEZ al crear el sistema.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- LIMPIEZA (solo desarrollo — borra todo lo existente en public)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS public.invoices             CASCADE;
DROP TABLE IF EXISTS public.clientes_emisor      CASCADE;
DROP TABLE IF EXISTS public.puntos_emision       CASCADE;
DROP TABLE IF EXISTS public.establecimientos     CASCADE;
DROP TABLE IF EXISTS public.api_keys             CASCADE;
DROP TABLE IF EXISTS public.auth_challenges      CASCADE;
DROP TABLE IF EXISTS public.credit_transactions  CASCADE;
DROP TABLE IF EXISTS public.transaction_logs     CASCADE;
DROP TABLE IF EXISTS public.user_credits         CASCADE;
DROP TABLE IF EXISTS public.profiles             CASCADE;
DROP TABLE IF EXISTS public.leads_ex_usuarios    CASCADE;
DROP TABLE IF EXISTS public.sujetos_global       CASCADE;
DROP TABLE IF EXISTS public.emisor_tenant_map    CASCADE;
DROP TABLE IF EXISTS public.emisores             CASCADE;

-- -----------------------------------------------------------------------------
-- TABLAS GLOBALES
-- -----------------------------------------------------------------------------

-- Catálogo global de RUCs / cédulas / pasaportes del Ecuador.
-- Compartido entre todos los emisores — evita duplicar datos de personas/empresas.
CREATE TABLE public.sujetos_global (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_identificacion_sri VARCHAR(2)  NOT NULL,   -- 04=RUC 05=CEDULA 06=PASAPORTE
    identificacion          VARCHAR(20) NOT NULL,
    codigo_pais             VARCHAR(3)  NOT NULL DEFAULT 'EC',
    razon_social            TEXT        NOT NULL,
    ultima_sincronizacion   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tipo_identificacion_sri, identificacion, codigo_pais)
);

-- Clientes de Kipu: emprendedores o empresas con RUC que emiten facturas.
-- Entidad raíz — casi todo apunta aquí.
CREATE TABLE public.emisores (
    id                      SERIAL      PRIMARY KEY,
    ruc                     VARCHAR(13) NOT NULL UNIQUE,
    razon_social            TEXT        NOT NULL,
    nombre_comercial        TEXT,
    direccion_matriz        TEXT        NOT NULL,
    contribuyente_especial  VARCHAR(13),
    obligado_contabilidad   VARCHAR(2)  DEFAULT 'NO',
    ambiente                SMALLINT    DEFAULT 1,  -- 1: Pruebas, 2: Producción
    p12_path                TEXT,                   -- Path en R2/MinIO
    p12_pass                TEXT,                   -- Encriptado con ENCRYPTION_KEY
    p12_expiration          DATE,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);

-- Ruteo: mapea cada emisor al schema tenant que le corresponde.
-- FastAPI consulta esto en cada request para saber a qué schema apuntar.
CREATE TABLE public.emisor_tenant_map (
    emisor_id       INTEGER     PRIMARY KEY REFERENCES public.emisores(id) ON DELETE CASCADE,
    tenant_schema   VARCHAR(20) NOT NULL,   -- 'tenant_001', 'tenant_002', ...
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Usuarios del sistema (Firebase Auth vinculado a un emisor).
CREATE TABLE public.profiles (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid    TEXT        NOT NULL UNIQUE,
    emisor_id       INTEGER     REFERENCES public.emisores(id) ON DELETE SET NULL,
    email           TEXT        NOT NULL UNIQUE,
    full_name       TEXT,
    role            VARCHAR(20) DEFAULT 'admin',    -- 'admin', 'contador', 'viewer'
    whatsapp_number VARCHAR(20),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Balance de créditos separado por tipo (modelo pay-per-use).
-- balance_emision   → para emitir facturas electrónicas al SRI
-- balance_recepcion → para recibir/procesar facturas de proveedores
CREATE TABLE public.user_credits (
    emisor_id           INTEGER PRIMARY KEY REFERENCES public.emisores(id) ON DELETE CASCADE,
    balance_emision     INTEGER NOT NULL DEFAULT 0,
    balance_recepcion   INTEGER NOT NULL DEFAULT 0,
    last_updated        TIMESTAMPTZ DEFAULT now()
);

-- Historial de movimientos de créditos (compras, usos, bonos, reembolsos).
CREATE TABLE public.credit_transactions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    emisor_id       INTEGER     NOT NULL REFERENCES public.emisores(id) ON DELETE CASCADE,
    -- Tipos:
    --   COMPRA_EMISION    → compra de créditos de emisión
    --   COMPRA_RECEPCION  → compra de créditos de recepción
    --   BONUS_RECEPCION   → créditos de recepción gratis por compra de emisión
    --   USO_EMISION       → factura emitida (descuenta balance_emision)
    --   USO_RECEPCION     → factura recibida procesada (descuenta balance_recepcion)
    --   REEMBOLSO         → devolución por error
    tipo            VARCHAR(25) NOT NULL,
    cantidad        INTEGER     NOT NULL,            -- positivo: entrada, negativo: salida
    precio_total    NUMERIC(10,2) DEFAULT 0.00,      -- 0 en bonos y usos
    metodo_pago     VARCHAR(30),                     -- 'BINANCE', 'PICHINCHA', 'STRIPE'
    referencia_pago VARCHAR(100),
    notas           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Auditoría de operaciones administrativas (usada por n8n y admin panel).
CREATE TABLE public.transaction_logs (
    id                  SERIAL      PRIMARY KEY,
    target_emisor_id    INTEGER     REFERENCES public.emisores(id) ON DELETE SET NULL,
    amount              INTEGER     NOT NULL,
    action_type         VARCHAR(50) NOT NULL,
    description         TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- API Keys para integraciones externas (ERP, POS, etc.).
CREATE TABLE public.api_keys (
    id              SERIAL      PRIMARY KEY,
    emisor_id       INTEGER     NOT NULL REFERENCES public.emisores(id) ON DELETE CASCADE,
    nombre          VARCHAR(100) NOT NULL,
    key_prefix      VARCHAR(10) NOT NULL,            -- "kp_live_" — visible al usuario
    key_hash        VARCHAR(64) NOT NULL UNIQUE,     -- SHA256 del key completo
    revoked         BOOLEAN     DEFAULT false,
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Desafíos OTP/PIN para login por WhatsApp o email.
CREATE TABLE public.auth_challenges (
    id              SERIAL      PRIMARY KEY,
    emisor_id       INTEGER     REFERENCES public.emisores(id) ON DELETE CASCADE,
    email           TEXT        NOT NULL,
    whatsapp_number VARCHAR(20),
    pin             VARCHAR(10) NOT NULL,
    tipo_accion     VARCHAR(30) NOT NULL,            -- 'LOGIN', 'CAMBIO_EMAIL', 'NUKE'
    metadata        JSONB,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Ex-clientes para análisis de churn y campañas de reactivación.
CREATE TABLE public.leads_ex_usuarios (
    id                          SERIAL      PRIMARY KEY,
    ruc                         VARCHAR(13),
    razon_social                TEXT,
    email                       TEXT,
    full_name                   TEXT,
    motivo_salida               TEXT,
    ultimo_balance_emision      INTEGER,
    ultimo_balance_recepcion    INTEGER,
    total_facturas_emitidas     INTEGER,
    total_facturas_recibidas    INTEGER,
    fecha_registro_original     TIMESTAMP,
    fecha_eliminacion           TIMESTAMP   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- ÍNDICES
-- -----------------------------------------------------------------------------
CREATE INDEX idx_profiles_emisor        ON public.profiles(emisor_id);
CREATE INDEX idx_profiles_firebase      ON public.profiles(firebase_uid);
CREATE INDEX idx_api_keys_emisor        ON public.api_keys(emisor_id);
CREATE INDEX idx_api_keys_hash          ON public.api_keys(key_hash);
CREATE INDEX idx_credit_tx_emisor       ON public.credit_transactions(emisor_id);
CREATE INDEX idx_credit_tx_tipo         ON public.credit_transactions(tipo);
CREATE INDEX idx_sujetos_identificacion ON public.sujetos_global(identificacion);
CREATE INDEX idx_tenant_map_schema      ON public.emisor_tenant_map(tenant_schema);

-- -----------------------------------------------------------------------------
-- VERIFICACIÓN
-- -----------------------------------------------------------------------------
SELECT tablename, schemaname
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename NOT LIKE 'pg_%'
ORDER BY tablename;