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


def init_db():
    from category.infrastructure.models.category_model import CategoryModel  # noqa: F401
    from client.infrastructure.models.client_model import ClientModel, ClientPurchaseModel  # noqa: F401
    from inventory.infrastructure.models.movement_model import InventoryMovementModel  # noqa: F401
    from integration.infrastructure.models.integration_model import (  # noqa: F401
        DianSettingModel,
        PeripheralModel,
        PrinterSettingModel,
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
