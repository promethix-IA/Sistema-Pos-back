from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from db.database import Base


class CreditDebtModel(Base):
    __tablename__ = "credit_debts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, unique=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    ticket = Column(String(40), nullable=False, default="")
    total = Column(Numeric(14, 2), nullable=False)
    paid = Column(Numeric(14, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class CreditPaymentModel(Base):
    __tablename__ = "credit_payments"

    id = Column(Integer, primary_key=True)
    debt_id = Column(Integer, ForeignKey("credit_debts.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    method = Column(String(20), nullable=False)
    note = Column(Text, nullable=False, default="")
    paid_at = Column(DateTime(timezone=True), nullable=False)
