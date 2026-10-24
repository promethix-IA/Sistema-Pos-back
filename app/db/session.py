import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from db.database import Base, SessionLocal, engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


TENANT_TABLES = (
    "products",
    "categories",
    "clients",
    "suppliers",
    "sales",
    "inventory_movements",
    "cash_shifts",
    "credit_debts",
    "peripherals",
    "printer_settings",
    "ticket_settings",
    "dian_settings",
)


def _apply_tenant_columns(connection) -> None:
    connection.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
    ))
    connection.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'owner'"
    ))
    connection.execute(text(
        "UPDATE users SET role = 'admin' WHERE lower(email) LIKE 'admin@%'"
    ))
    connection.execute(text(
        """
        UPDATE users
        SET owner_id = NULL, role = 'owner'
        WHERE owner_id IS NOT NULL
          AND owner_id IN (SELECT admins.id FROM (SELECT id FROM users WHERE role = 'admin') AS admins)
        """
    ))
    connection.execute(text(
        "UPDATE users SET role = 'cajero' WHERE role = 'cashier'"
    ))
    connection.execute(text(
        "UPDATE users SET role = 'owner' WHERE owner_id IS NULL AND role <> 'admin'"
    ))
    connection.execute(text(
        """
        UPDATE users
        SET role = 'cajero'
        WHERE owner_id IS NOT NULL
          AND role NOT IN ('administrador', 'cajero', 'inventario')
        """
    ))
    for table in TENANT_TABLES:
        connection.execute(text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
        ))
    owner = connection.execute(text(
        "SELECT id FROM users WHERE role = 'owner' ORDER BY id ASC LIMIT 1"
    )).scalar()
    admin_id = connection.execute(text(
        "SELECT id FROM users WHERE role = 'admin' ORDER BY id ASC LIMIT 1"
    )).scalar()
    fallback = owner or admin_id
    if fallback is not None:
        for table in TENANT_TABLES:
            connection.execute(text(f"UPDATE {table} SET user_id = :owner WHERE user_id IS NULL"), {"owner": fallback})
            if owner is not None and admin_id is not None and owner != admin_id:
                owner_has_rows = connection.execute(
                    text(f"SELECT 1 FROM {table} WHERE user_id = :owner LIMIT 1"),
                    {"owner": owner},
                ).first()
                if owner_has_rows is None:
                    connection.execute(
                        text(f"UPDATE {table} SET user_id = :owner WHERE user_id = :admin_id"),
                        {"owner": owner, "admin_id": admin_id},
                    )
            connection.execute(text(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL"))
    connection.execute(text("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_code_key"))
    connection.execute(text("ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key"))
    connection.execute(text("ALTER TABLE sales DROP CONSTRAINT IF EXISTS sales_ticket_key"))
    connection.execute(text("ALTER TABLE peripherals DROP CONSTRAINT IF EXISTS peripherals_code_key"))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS products_user_code_key ON products (user_id, code)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS categories_user_name_key ON categories (user_id, name)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS sales_user_ticket_key ON sales (user_id, ticket)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS peripherals_user_code_key ON peripherals (user_id, code)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS printer_settings_user_id_key ON printer_settings (user_id)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS dian_settings_user_id_key ON dian_settings (user_id)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ticket_settings_user_id_key ON ticket_settings (user_id)"
    ))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_products_user_id ON products (user_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_clients_user_id ON clients (user_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_user_id ON sales (user_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_owner_id ON users (owner_id)"))
    connection.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT ''"
    ))
    connection.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ"
    ))



def init_db():
    from category.infrastructure.models.category_model import CategoryModel  # noqa: F401
    from client.infrastructure.models.client_model import ClientModel, ClientPurchaseModel  # noqa: F401
    from inventory.infrastructure.models.movement_model import InventoryMovementModel  # noqa: F401
    from integration.infrastructure.models.integration_model import (  # noqa: F401
        DianSettingModel,
        PeripheralModel,
        PrinterSettingModel,
        TicketSettingModel,
    )
    from credit.infrastructure.models.credit_model import CreditDebtModel, CreditPaymentModel  # noqa: F401
    from product.infrastructure.models.product_model import ProductModel  # noqa: F401
    from sale.infrastructure.models.sale_model import SaleItemModel, SaleModel  # noqa: F401
    from shift.infrastructure.models.shift_model import CashShiftModel  # noqa: F401
    from supplier.infrastructure.models.supplier_model import SupplierModel, SupplierOrderModel  # noqa: F401
    from user.infrastructure.models.user_model import UserModel  # noqa: F401

    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            with engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE supplier_orders ADD COLUMN IF NOT EXISTS invoice VARCHAR(80) NOT NULL DEFAULT ''"
                ))
                connection.execute(text(
                    "ALTER TABLE supplier_orders ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES products(id) ON DELETE SET NULL"
                ))
                connection.execute(text(
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS sale_mode VARCHAR(20) NOT NULL DEFAULT 'unidad'"
                ))
                connection.execute(text(
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS tracks_inventory BOOLEAN NOT NULL DEFAULT true"
                ))
                connection.execute(text(
                    "ALTER TABLE products ALTER COLUMN stock TYPE NUMERIC(14, 3) USING stock::numeric"
                ))
                connection.execute(text(
                    "ALTER TABLE inventory_movements ALTER COLUMN balance_after TYPE NUMERIC(14, 3) USING balance_after::numeric"
                ))
                connection.execute(text(
                    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'completed'"
                ))
                connection.execute(text(
                    "ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS cancelled_qty NUMERIC(12, 3) NOT NULL DEFAULT 0"
                ))
                connection.execute(text(
                    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS shift_id INTEGER REFERENCES cash_shifts(id) ON DELETE SET NULL"
                ))
                connection.execute(text(
                    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS amount_efectivo NUMERIC(14, 2) NOT NULL DEFAULT 0"
                ))
                connection.execute(text(
                    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS amount_tarjeta NUMERIC(14, 2) NOT NULL DEFAULT 0"
                ))
                connection.execute(text(
                    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS amount_transferencia NUMERIC(14, 2) NOT NULL DEFAULT 0"
                ))
                connection.execute(text(
                    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS amount_credito NUMERIC(14, 2) NOT NULL DEFAULT 0"
                ))
                # Backfill simple payment amounts for legacy rows
                connection.execute(text(
                    """
                    UPDATE sales
                    SET amount_efectivo = total
                    WHERE COALESCE(amount_efectivo, 0) = 0
                      AND COALESCE(amount_tarjeta, 0) = 0
                      AND COALESCE(amount_transferencia, 0) = 0
                      AND COALESCE(amount_credito, 0) = 0
                      AND payment = 'efectivo'
                    """
                ))
                connection.execute(text(
                    """
                    UPDATE sales
                    SET amount_tarjeta = total
                    WHERE COALESCE(amount_efectivo, 0) = 0
                      AND COALESCE(amount_tarjeta, 0) = 0
                      AND COALESCE(amount_transferencia, 0) = 0
                      AND COALESCE(amount_credito, 0) = 0
                      AND payment = 'tarjeta'
                    """
                ))
                _apply_tenant_columns(connection)
            from inventory.infrastructure.repositories.inventory_repository import seed_movements

            session = SessionLocal()
            try:
                seed_movements(session)
            finally:
                session.close()
            return
        except OperationalError:
            if attempt == 9:
                raise
            time.sleep(2)
