from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text

from db.database import Base


class SupplierModel(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(40), nullable=False, default="")
    products = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class SupplierOrderModel(Base):
    __tablename__ = "supplier_orders"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    ordered_on = Column(Date, nullable=False)
    product = Column(String(200), nullable=False)
    qty = Column(Numeric(12, 3), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    price = Column(Numeric(14, 2), nullable=False)
