from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text

from db.database import Base


class CashShiftModel(Base):
    __tablename__ = "cash_shifts"

    id = Column(Integer, primary_key=True)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    opening_cash = Column(Numeric(14, 2), nullable=False, default=0)
    counted_cash = Column(Numeric(14, 2), nullable=True)
    status = Column(String(20), nullable=False, default="open")
    opened_by = Column(String(200), nullable=False, default="")
    closed_by = Column(String(200), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
