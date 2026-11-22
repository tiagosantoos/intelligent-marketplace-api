"""Estrutura relacional dos nove CSVs de origem. Importação em etapa posterior."""

import sqlalchemy as sa

metadata = sa.MetaData(
    schema="historical",
    naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    },
)

customers = sa.Table(
    "customers", metadata,
    sa.Column("customer_id", sa.String(32), primary_key=True),
    sa.Column("customer_unique_id", sa.String(32), nullable=False, index=True),
    sa.Column("customer_zip_code_prefix", sa.String(5), nullable=False, index=True),
    sa.Column("customer_city", sa.Text, nullable=False),
    sa.Column("customer_state", sa.String(2), nullable=False, index=True),
)

sellers = sa.Table(
    "sellers", metadata,
    sa.Column("seller_id", sa.String(32), primary_key=True),
    sa.Column("seller_zip_code_prefix", sa.String(5), nullable=False, index=True),
    sa.Column("seller_city", sa.Text, nullable=False),
    sa.Column("seller_state", sa.String(2), nullable=False, index=True),
)

product_category_name_translation = sa.Table(
    "product_category_name_translation", metadata,
    sa.Column("product_category_name", sa.Text, primary_key=True),
    sa.Column("product_category_name_english", sa.Text, nullable=False),
)

products = sa.Table(
    "products", metadata,
    sa.Column("product_id", sa.String(32), primary_key=True),
    sa.Column("product_category_name", sa.Text, nullable=True, index=True),
    # Original source spelling is intentional.
    sa.Column("product_name_lenght", sa.Integer, nullable=True),
    sa.Column("product_description_lenght", sa.Integer, nullable=True),
    sa.Column("product_photos_qty", sa.Integer, nullable=True),
    sa.Column("product_weight_g", sa.Integer, nullable=True),
    sa.Column("product_length_cm", sa.Integer, nullable=True),
    sa.Column("product_height_cm", sa.Integer, nullable=True),
    sa.Column("product_width_cm", sa.Integer, nullable=True),
)

orders = sa.Table(
    "orders", metadata,
    sa.Column("order_id", sa.String(32), primary_key=True),
    sa.Column("customer_id", sa.String(32), sa.ForeignKey("historical.customers.customer_id"), nullable=False, index=True),
    sa.Column("order_status", sa.Text, nullable=False, index=True),
    sa.Column("order_purchase_timestamp", sa.DateTime(timezone=False), nullable=False, index=True),
    sa.Column("order_approved_at", sa.DateTime(timezone=False), nullable=True),
    sa.Column("order_delivered_carrier_date", sa.DateTime(timezone=False), nullable=True),
    sa.Column("order_delivered_customer_date", sa.DateTime(timezone=False), nullable=True),
    sa.Column("order_estimated_delivery_date", sa.DateTime(timezone=False), nullable=False, index=True),
)

order_items = sa.Table(
    "order_items", metadata,
    sa.Column("order_id", sa.String(32), sa.ForeignKey("historical.orders.order_id"), primary_key=True),
    sa.Column("order_item_id", sa.Integer, primary_key=True),
    sa.Column("product_id", sa.String(32), sa.ForeignKey("historical.products.product_id"), nullable=False, index=True),
    sa.Column("seller_id", sa.String(32), sa.ForeignKey("historical.sellers.seller_id"), nullable=False, index=True),
    sa.Column("shipping_limit_date", sa.DateTime(timezone=False), nullable=False),
    sa.Column("price", sa.Numeric(14, 2), nullable=False),
    sa.Column("freight_value", sa.Numeric(14, 2), nullable=False),
)

order_payments = sa.Table(
    "order_payments", metadata,
    sa.Column("order_id", sa.String(32), sa.ForeignKey("historical.orders.order_id"), primary_key=True),
    sa.Column("payment_sequential", sa.Integer, primary_key=True),
    sa.Column("payment_type", sa.Text, nullable=False),
    sa.Column("payment_installments", sa.Integer, nullable=False),
    sa.Column("payment_value", sa.Numeric(14, 2), nullable=False),
)

order_reviews = sa.Table(
    "order_reviews", metadata,
    sa.Column("review_id", sa.String(32), primary_key=True),
    sa.Column("order_id", sa.String(32), sa.ForeignKey("historical.orders.order_id"), primary_key=True, index=True),
    sa.Column("review_score", sa.Integer, nullable=False),
    sa.Column("review_comment_title", sa.Text, nullable=True),
    sa.Column("review_comment_message", sa.Text, nullable=True),
    sa.Column("review_creation_date", sa.DateTime(timezone=False), nullable=False),
    sa.Column("review_answer_timestamp", sa.DateTime(timezone=False), nullable=False),
)

geolocation = sa.Table(
    "geolocation", metadata,
    # CEP prefixes and even identical source rows repeat; keep every source occurrence.
    sa.Column("geolocation_id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("geolocation_zip_code_prefix", sa.String(5), nullable=False, index=True),
    sa.Column("geolocation_lat", sa.Numeric(24, 20), nullable=False),
    sa.Column("geolocation_lng", sa.Numeric(24, 20), nullable=False),
    sa.Column("geolocation_city", sa.Text, nullable=False),
    sa.Column("geolocation_state", sa.String(2), nullable=False),
)
