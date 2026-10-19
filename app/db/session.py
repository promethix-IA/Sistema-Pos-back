import time

from sqlalchemy.exc import OperationalError

from db.database import Base, SessionLocal, engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from client.infrastructure.models.client_model import ClientModel, ClientPurchaseModel  # noqa: F401
    from integration.infrastructure.models.integration_model import (  # noqa: F401
        DianSettingModel,
        PeripheralModel,
        PrinterSettingModel,
    )
    from product.infrastructure.models.product_model import ProductModel  # noqa: F401
    from sale.infrastructure.models.sale_model import SaleItemModel, SaleModel  # noqa: F401
    from supplier.infrastructure.models.supplier_model import SupplierModel, SupplierOrderModel  # noqa: F401
    from user.infrastructure.models.user_model import UserModel  # noqa: F401

    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError:
            if attempt == 9:
                raise
            time.sleep(2)
