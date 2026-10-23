from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text

from db.database import Base


class InventoryMovementModel(Base):
    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(200), nullable=False)
    product_code = Column(String(80), nullable=False)
    movement_type = Column(String(30), nullable=False)
    qty = Column(Numeric(12, 3), nullable=False)
    balance_after = Column(Numeric(14, 3), nullable=False)
    note = Column(Text, nullable=False, default="")
    ref = Column(String(80), nullable=False, default="")
    moved_on = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
