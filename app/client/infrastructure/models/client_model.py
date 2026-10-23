from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text

from db.database import Base


class ClientModel(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(40), nullable=False, default="")
    email = Column(String(255), nullable=False, default="")
    address = Column(String(255), nullable=False, default="")
    id_number = Column(String(40), nullable=False, default="")
    birth_date = Column(Date, nullable=True)
    total_bought = Column(Numeric(14, 2), nullable=False, default=0)
    last_purchase = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ClientPurchaseModel(Base):
    __tablename__ = "client_purchases"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    purchased_on = Column(Date, nullable=False)
    items = Column(Text, nullable=False)
    total = Column(Numeric(14, 2), nullable=False)
