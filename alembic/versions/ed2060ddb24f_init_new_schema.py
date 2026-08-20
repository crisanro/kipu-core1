"""init_new_schema
Revision ID: ed2060ddb24f
Revises: 
Create Date: 2026-08-17 12:57:09.460079
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'ed2060ddb24f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # =========================================================================
    # 1. CREAR TABLAS NUEVAS
    # =========================================================================

    op.create_table('documentos_recibidos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('emisor_id', sa.Integer(), nullable=False),
        sa.Column('ruc_proveedor', sa.String(length=13), nullable=False),
        sa.Column('razon_social_proveedor', sa.Text(), nullable=False),
        sa.Column('tipo_doc', sa.String(length=5), nullable=False),
        sa.Column('cod_doc', sa.String(length=2), nullable=False),
        sa.Column('clave_acceso', sa.String(length=49), nullable=True),
        sa.Column('numero_doc', sa.String(length=17), nullable=True),
        sa.Column('fecha_emision', sa.Date(), nullable=False),
        sa.Column('fecha_autorizacion', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('importe_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('deducible_renta', sa.Boolean(), nullable=True),
        sa.Column('credito_tributario_iva', sa.Boolean(), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('estado_pago', sa.String(length=20), nullable=True),
        sa.Column('forma_pago', sa.String(length=30), nullable=True),
        sa.Column('numero_comprobante_pago', sa.String(length=100), nullable=True),
        sa.Column('fecha_pago', sa.Date(), nullable=True),
        sa.Column('impuestos_detalle', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('datos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('xml_path', sa.Text(), nullable=True),
        sa.Column('fuente', sa.String(length=10), nullable=True),
        sa.Column('procesado', sa.Boolean(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['emisor_id'], ['emisores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clave_acceso')
    )

    op.create_table('subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('emisor_id', sa.Integer(), nullable=False),
        sa.Column('plan', sa.String(length=20), nullable=False),
        sa.Column('periodo', sa.String(length=10), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=50), nullable=True),
        sa.Column('stripe_price_id', sa.String(length=50), nullable=True),
        sa.Column('current_period_start', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('current_period_end', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('trial_end', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['emisor_id'], ['emisores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('emisor_id'),
        sa.UniqueConstraint('stripe_subscription_id')
    )

    op.create_table('referidos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('referidor_emisor_id', sa.Integer(), nullable=True),
        sa.Column('referido_emisor_id', sa.Integer(), nullable=True),
        sa.Column('plan_contratado', sa.String(length=10), nullable=True),
        sa.Column('comision', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=True),
        sa.Column('fecha_liberacion', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('fecha_pago', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['referido_emisor_id'], ['emisores.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['referidor_emisor_id'], ['emisores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('referido_emisor_id')
    )

    op.create_table('documentos_emitidos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('emisor_id', sa.Integer(), nullable=False),
        sa.Column('punto_emision_id', sa.Integer(), nullable=True),
        sa.Column('cliente_id', sa.UUID(), nullable=True),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('tipo_doc', sa.String(length=5), nullable=False),
        sa.Column('cod_doc', sa.String(length=2), nullable=False),
        sa.Column('clave_acceso', sa.String(length=49), nullable=True),
        sa.Column('numero_doc', sa.String(length=17), nullable=True),
        sa.Column('secuencial', sa.String(length=9), nullable=True),
        sa.Column('fecha_emision', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=True),
        sa.Column('estado_sri', sa.String(length=20), nullable=True),
        sa.Column('mensajes_sri', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fecha_envio_sri', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('fecha_autorizacion', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('last_retry', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('estado_cobro', sa.String(length=20), nullable=True),
        sa.Column('forma_pago_cobro', sa.String(length=30), nullable=True),
        sa.Column('numero_comprobante_pago', sa.String(length=100), nullable=True),
        sa.Column('fecha_pago', sa.Date(), nullable=True),
        sa.Column('importe_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('datos', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('xml_path', sa.Text(), nullable=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('origen', sa.String(length=20), nullable=True),
        sa.Column('doc_origen_emitido_id', sa.UUID(), nullable=True),
        sa.Column('doc_origen_recibido_id', sa.UUID(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes_emisor.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['doc_origen_emitido_id'], ['documentos_emitidos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['doc_origen_recibido_id'], ['documentos_recibidos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['emisor_id'], ['emisores.id']),
        sa.ForeignKeyConstraint(['punto_emision_id'], ['puntos_emision.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clave_acceso')
    )

    # =========================================================================
    # 2. MIGRAR DATOS: invoices_emitidas → documentos_emitidos
    # =========================================================================
    op.execute("""
        INSERT INTO documentos_emitidos (
            id, emisor_id, punto_emision_id, cliente_id, api_key_id,
            tipo_doc, cod_doc,
            clave_acceso, numero_doc, secuencial, fecha_emision,
            estado_sri, mensajes_sri, fecha_envio_sri, fecha_autorizacion,
            retry_count, last_retry,
            importe_total,
            datos,
            xml_path, pdf_path,
            origen,
            doc_origen_emitido_id,
            created_at
        )
        SELECT
            id, emisor_id, punto_emision_id, cliente_emisor_id, api_key_id,
            CASE cod_doc
                WHEN '01' THEN 'FAC'
                WHEN '03' THEN 'LIQ'
                WHEN '04' THEN 'NCR'
                WHEN '05' THEN 'NDB'
                WHEN '07' THEN 'RET'
                ELSE 'FAC'
            END as tipo_doc,
            COALESCE(cod_doc, '01'),
            clave_acceso,
            numero_factura,
            secuencial,
            fecha_emision,
            COALESCE(estado, 'PENDIENTE') as estado_sri,
            mensajes_sri,
            fecha_envio_sri,
            fecha_autorizacion,
            retry_count,
            last_retry,
            importe_total,
            jsonb_build_object(
                'infoTributaria', datos_factura->'infoTributaria',
                'infoFactura', datos_factura->'infoFactura',
                'detalles', datos_factura->'detalles',
                'infoAdicional', datos_factura->'infoAdicional',
                'resumenImpuestos', datos_factura->'resumenImpuestos',
                'legacy_subtotal_iva', subtotal_iva,
                'legacy_subtotal_0', subtotal_0,
                'legacy_valor_iva', valor_iva,
                'legacy_id_comprador', identificacion_comprador,
                'legacy_razon_comprador', razon_social_comprador,
                'legacy_email_comprador', email_comprador
            ) as datos,
            xml_path,
            pdf_path,
            COALESCE(origen, 'web'),
            doc_referencia_id,
            created_at
        FROM invoices_emitidas
    """)

    # =========================================================================
    # 3. MIGRAR DATOS: invoices_recibidas → documentos_recibidos
    # =========================================================================
    op.execute("""
        INSERT INTO documentos_recibidos (
            id, emisor_id,
            ruc_proveedor, razon_social_proveedor,
            tipo_doc, cod_doc,
            clave_acceso, numero_doc,
            fecha_emision, fecha_autorizacion,
            importe_total,
            deducible_renta, credito_tributario_iva,
            notas,
            impuestos_detalle,
            datos,
            xml_path,
            fuente, procesado,
            created_at
        )
        SELECT
            id, emisor_id,
            ruc_proveedor, razon_social_proveedor,
            'FAC' as tipo_doc,
            '01' as cod_doc,
            clave_acceso,
            numero_factura,
            fecha_emision, fecha_autorizacion,
            importe_total,
            COALESCE(deducible_renta, true),
            COALESCE(credito_tributario_iva, false),
            notas_cliente,
            impuestos_detalle,
            jsonb_build_object(
                'datos_originales', datos_factura,
                'legacy_subtotal_0', subtotal_0,
                'legacy_subtotal_iva', subtotal_iva,
                'legacy_valor_iva', valor_iva,
                'legacy_total_sin_impuestos', total_sin_impuestos,
                'legacy_total_descuento', total_descuento
            ) as datos,
            xml_path,
            COALESCE(fuente, 'MANUAL'),
            COALESCE(procesado, false),
            created_at
        FROM invoices_recibidas
    """)

    # =========================================================================
    # 4. RENOMBRAR TABLAS VIEJAS COMO BACKUP (no eliminar)
    # =========================================================================
    op.execute("ALTER TABLE invoices_emitidas RENAME TO _bak_invoices_emitidas")
    op.execute("ALTER TABLE invoices_recibidas RENAME TO _bak_invoices_recibidas")

    # Tablas que ya no usamos — renombrar como backup también
    op.execute("ALTER TABLE notificaciones RENAME TO _bak_notificaciones")
    op.execute("ALTER TABLE fcm_tokens RENAME TO _bak_fcm_tokens")
    op.execute("ALTER TABLE servicios RENAME TO _bak_servicios")
    op.execute("ALTER TABLE app_ads RENAME TO _bak_app_ads")

    # =========================================================================
    # 5. CAMBIOS EN TABLAS EXISTENTES
    # =========================================================================

    # emisores — agregar tipo_emisor, quitar columnas ws_*
    op.add_column('emisores', sa.Column('tipo_emisor', sa.String(length=10), nullable=True))
    op.execute("UPDATE emisores SET tipo_emisor = 'NATURAL' WHERE tipo_emisor IS NULL")
    op.alter_column('emisores', 'tipo_emisor', nullable=False)
    op.drop_column('emisores', 'ws_punto_emision')
    op.drop_column('emisores', 'ws_establecimiento')

    # user_credits — agregar balance, migrar desde balance_emision, quitar campos viejos
    op.add_column('user_credits', sa.Column('balance', sa.Integer(), nullable=True))
    op.execute("UPDATE user_credits SET balance = COALESCE(balance_emision, 0)")
    op.alter_column('user_credits', 'balance', nullable=False)
    op.drop_column('user_credits', 'balance_emision')
    op.drop_column('user_credits', 'balance_recepcion')

    # api_keys — quitar unlimited y tipo
    op.drop_column('api_keys', 'unlimited')
    op.drop_column('api_keys', 'tipo')

    # auth_challenges — quitar emisor_id (ya no necesario)
    op.drop_constraint('auth_challenges_emisor_id_fkey', 'auth_challenges', type_='foreignkey')
    op.drop_column('auth_challenges', 'emisor_id')

    # profiles — quitar emisor_id (la relación va por emisor_usuarios)
    op.drop_constraint('profiles_emisor_id_fkey', 'profiles', type_='foreignkey')
    op.drop_column('profiles', 'emisor_id')

    # declaraciones_sri — agregar vencimiento y totales, quitar notas
    op.add_column('declaraciones_sri', sa.Column('vencimiento', sa.Date(), nullable=True))
    op.add_column('declaraciones_sri', sa.Column('totales', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute("UPDATE declaraciones_sri SET vencimiento = periodo + INTERVAL '45 days' WHERE vencimiento IS NULL")
    op.alter_column('declaraciones_sri', 'vencimiento', nullable=False)
    op.drop_column('declaraciones_sri', 'notas')
    op.drop_constraint('declaraciones_sri_emisor_id_tipo_periodo_key', 'declaraciones_sri', type_='unique')
    op.create_unique_constraint('uq_declaracion_emisor_tipo_periodo', 'declaraciones_sri', ['emisor_id', 'tipo', 'periodo'])

    # leads_ex_usuarios — agregar campos nuevos, quitar viejos
    op.add_column('leads_ex_usuarios', sa.Column('tipo_emisor', sa.String(length=10), nullable=True))
    op.add_column('leads_ex_usuarios', sa.Column('plan_ultimo', sa.String(length=20), nullable=True))
    op.add_column('leads_ex_usuarios', sa.Column('total_docs_emitidos', sa.Integer(), nullable=True))
    op.add_column('leads_ex_usuarios', sa.Column('total_docs_recibidos', sa.Integer(), nullable=True))
    op.execute("""
        UPDATE leads_ex_usuarios SET
            total_docs_emitidos = total_facturas_emitidas,
            total_docs_recibidos = total_facturas_recibidas
        WHERE total_facturas_emitidas IS NOT NULL
    """)
    op.drop_column('leads_ex_usuarios', 'ultimo_balance_emision')
    op.drop_column('leads_ex_usuarios', 'ultimo_balance_recepcion')
    op.drop_column('leads_ex_usuarios', 'total_facturas_emitidas')
    op.drop_column('leads_ex_usuarios', 'total_facturas_recibidas')
    op.drop_column('leads_ex_usuarios', 'whatsapp_number')

    # planes_creditos — quitar columnas viejas
    op.drop_column('planes_creditos', 'tipo')
    op.drop_column('planes_creditos', 'popular')
    op.drop_column('planes_creditos', 'orden')

    # =========================================================================
    # 6. ÍNDICES PARA LAS TABLAS NUEVAS
    # =========================================================================
    op.create_index('idx_docs_emitidos_emisor_fecha', 'documentos_emitidos', ['emisor_id', 'fecha_emision'])
    op.create_index('idx_docs_emitidos_estado_sri', 'documentos_emitidos', ['estado_sri'])
    op.create_index('idx_docs_emitidos_tipo', 'documentos_emitidos', ['emisor_id', 'tipo_doc'])
    op.create_index('idx_docs_emitidos_clave', 'documentos_emitidos', ['clave_acceso'])
    op.create_index('idx_docs_recibidos_emisor_fecha', 'documentos_recibidos', ['emisor_id', 'fecha_emision'])
    op.create_index('idx_docs_recibidos_ruc_proveedor', 'documentos_recibidos', ['emisor_id', 'ruc_proveedor'])
    op.create_index('idx_subscriptions_estado', 'subscriptions', ['estado'])


def downgrade() -> None:
    # Restaurar tablas desde backup
    op.execute("ALTER TABLE _bak_invoices_emitidas RENAME TO invoices_emitidas")
    op.execute("ALTER TABLE _bak_invoices_recibidas RENAME TO invoices_recibidas")
    op.execute("ALTER TABLE _bak_notificaciones RENAME TO notificaciones")
    op.execute("ALTER TABLE _bak_fcm_tokens RENAME TO fcm_tokens")
    op.execute("ALTER TABLE _bak_servicios RENAME TO servicios")
    op.execute("ALTER TABLE _bak_app_ads RENAME TO app_ads")

    # Eliminar tablas nuevas
    op.drop_table('documentos_emitidos')
    op.drop_table('documentos_recibidos')
    op.drop_table('subscriptions')
    op.drop_table('referidos')

    # Revertir columnas (simplificado — restaurar las críticas)
    op.add_column('user_credits', sa.Column('balance_emision', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user_credits', sa.Column('balance_recepcion', sa.Integer(), nullable=False, server_default='0'))
    op.execute("UPDATE user_credits SET balance_emision = balance")
    op.drop_column('user_credits', 'balance')

    op.drop_column('emisores', 'tipo_emisor')
    op.add_column('emisores', sa.Column('ws_establecimiento', sa.String(3), nullable=True))
    op.add_column('emisores', sa.Column('ws_punto_emision', sa.String(3), nullable=True))

    op.drop_column('declaraciones_sri', 'vencimiento')
    op.drop_column('declaraciones_sri', 'totales')