from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint

from db.database import Base


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("user_id", "code", name="products_user_code_key"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(80), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(120), nullable=False)
    buy_price = Column(Numeric(14, 2), nullable=False)
    sell_price = Column(Numeric(14, 2), nullable=False)
    stock = Column(Numeric(14, 3), nullable=False, default=0)
    sale_mode = Column(String(20), nullable=False, default="unidad")
    tracks_inventory = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
