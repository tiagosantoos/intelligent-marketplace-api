"""Cria as nove tabelas históricas. Não importa os CSVs."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None
SCHEMA = "historical"


def upgrade():
    op.execute(sa.schema.CreateSchema(SCHEMA))
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("customer_unique_id", sa.String(32), nullable=False),
        sa.Column("customer_zip_code_prefix", sa.String(5), nullable=False),
        sa.Column("customer_city", sa.Text(), nullable=False),
        sa.Column("customer_state", sa.String(2), nullable=False),
        sa.PrimaryKeyConstraint("customer_id", name="pk_customers"), schema=SCHEMA,
    )
    op.create_table(
        "sellers",
        sa.Column("seller_id", sa.String(32), nullable=False),
        sa.Column("seller_zip_code_prefix", sa.String(5), nullable=False),
        sa.Column("seller_city", sa.Text(), nullable=False),
        sa.Column("seller_state", sa.String(2), nullable=False),
        sa.PrimaryKeyConstraint("seller_id", name="pk_sellers"), schema=SCHEMA,
    )
    op.create_table(
        "product_category_name_translation",
        sa.Column("product_category_name", sa.Text(), nullable=False),
        sa.Column("product_category_name_english", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("product_category_name", name="pk_product_category_name_translation"), schema=SCHEMA,
    )
    op.create_table(
        "products",
        sa.Column("product_id", sa.String(32), nullable=False),
        sa.Column("product_category_name", sa.Text(), nullable=True),
        sa.Column("product_name_lenght", sa.Integer(), nullable=True),
        sa.Column("product_description_lenght", sa.Integer(), nullable=True),
        sa.Column("product_photos_qty", sa.Integer(), nullable=True),
        sa.Column("product_weight_g", sa.Integer(), nullable=True),
        sa.Column("product_length_cm", sa.Integer(), nullable=True),
        sa.Column("product_height_cm", sa.Integer(), nullable=True),
        sa.Column("product_width_cm", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("product_id", name="pk_products"), schema=SCHEMA,
    )
    op.create_table(
        "geolocation",
        sa.Column("geolocation_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("geolocation_zip_code_prefix", sa.String(5), nullable=False),
        sa.Column("geolocation_lat", sa.Numeric(24, 20), nullable=False),
        sa.Column("geolocation_lng", sa.Numeric(24, 20), nullable=False),
        sa.Column("geolocation_city", sa.Text(), nullable=False),
        sa.Column("geolocation_state", sa.String(2), nullable=False),
        sa.PrimaryKeyConstraint("geolocation_id", name="pk_geolocation"), schema=SCHEMA,
    )
    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("order_status", sa.Text(), nullable=False),
        sa.Column("order_purchase_timestamp", sa.DateTime(timezone=False), nullable=False),
        sa.Column("order_approved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("order_delivered_carrier_date", sa.DateTime(timezone=False), nullable=True),
        sa.Column("order_delivered_customer_date", sa.DateTime(timezone=False), nullable=True),
        sa.Column("order_estimated_delivery_date", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("order_id", name="pk_orders"),
        sa.ForeignKeyConstraint(["customer_id"], ["historical.customers.customer_id"], name="fk_orders_customer_id_customers"), schema=SCHEMA,
    )
    op.create_table(
        "order_items",
        sa.Column("order_id", sa.String(32), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(32), nullable=False),
        sa.Column("seller_id", sa.String(32), nullable=False),
        sa.Column("shipping_limit_date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("freight_value", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("order_id", "order_item_id", name="pk_order_items"),
        sa.ForeignKeyConstraint(["order_id"], ["historical.orders.order_id"], name="fk_order_items_order_id_orders"),
        sa.ForeignKeyConstraint(["product_id"], ["historical.products.product_id"], name="fk_order_items_product_id_products"),
        sa.ForeignKeyConstraint(["seller_id"], ["historical.sellers.seller_id"], name="fk_order_items_seller_id_sellers"), schema=SCHEMA,
    )
    op.create_table(
        "order_payments",
        sa.Column("order_id", sa.String(32), nullable=False),
        sa.Column("payment_sequential", sa.Integer(), nullable=False),
        sa.Column("payment_type", sa.Text(), nullable=False),
        sa.Column("payment_installments", sa.Integer(), nullable=False),
        sa.Column("payment_value", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("order_id", "payment_sequential", name="pk_order_payments"),
        sa.ForeignKeyConstraint(["order_id"], ["historical.orders.order_id"], name="fk_order_payments_order_id_orders"), schema=SCHEMA,
    )
    op.create_table(
        "order_reviews",
        sa.Column("review_id", sa.String(32), nullable=False),
        sa.Column("order_id", sa.String(32), nullable=False),
        sa.Column("review_score", sa.Integer(), nullable=False),
        sa.Column("review_comment_title", sa.Text(), nullable=True),
        sa.Column("review_comment_message", sa.Text(), nullable=True),
        sa.Column("review_creation_date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("review_answer_timestamp", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("review_id", "order_id", name="pk_order_reviews"),
        sa.ForeignKeyConstraint(["order_id"], ["historical.orders.order_id"], name="fk_order_reviews_order_id_orders"), schema=SCHEMA,
    )
    for table, columns in {
        "customers": ["customer_unique_id", "customer_zip_code_prefix", "customer_state"],
        "sellers": ["seller_zip_code_prefix", "seller_state"],
        "products": ["product_category_name"],
        "geolocation": ["geolocation_zip_code_prefix"],
        "orders": ["customer_id", "order_status", "order_purchase_timestamp", "order_estimated_delivery_date"],
        "order_items": ["product_id", "seller_id"],
        "order_reviews": ["order_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column], schema=SCHEMA)


def downgrade():
    for table in (
        "order_reviews", "order_payments", "order_items", "orders", "geolocation",
        "products", "product_category_name_translation", "sellers", "customers",
    ):
        op.drop_table(table, schema=SCHEMA)
    # No CASCADE: unexpected objects must not be removed silently.
    op.execute(sa.schema.DropSchema(SCHEMA))
