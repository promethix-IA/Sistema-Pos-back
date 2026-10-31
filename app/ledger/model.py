from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String

from db.database import Base


class LedgerEntryModel(Base):
    __tablename__ = "platform_ledger"

    id = Column(Integer, primary_key=True)
    kind = Column(String(10), nullable=False, index=True)
    category = Column(String(40), nullable=False, default="otro")
    concept = Column(String(200), nullable=False, default="")
    amount = Column(Numeric(14, 2), nullable=False)
    occurred_on = Column(Date, nullable=False, index=True)
    note = Column(String(400), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
