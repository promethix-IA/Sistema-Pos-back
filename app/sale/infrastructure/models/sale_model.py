from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String

from db.database import Base


class SaleModel(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    ticket = Column(String(40), nullable=False, unique=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    payment = Column(String(20), nullable=False)
    total = Column(Numeric(14, 2), nullable=False)
    status = Column(String(30), nullable=False, default="completed")
    sold_at = Column(DateTime(timezone=True), nullable=False)


class SaleItemModel(Base):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(200), nullable=False)
    qty = Column(Numeric(12, 3), nullable=False)
    cancelled_qty = Column(Numeric(12, 3), nullable=False, default=0)
    weight = Column(Numeric(12, 3), nullable=True)
    unit_price = Column(Numeric(14, 2), nullable=False)
    line_total = Column(Numeric(14, 2), nullable=False)
