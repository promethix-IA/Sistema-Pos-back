from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from db.database import Base


class DesktopLicenseModel(Base):
    __tablename__ = "desktop_licenses"

    id = Column(Integer, primary_key=True)
    cliente = Column(String(200), nullable=False)
    equipo = Column(String(19), nullable=True)
    actualizaciones_hasta = Column(String(10), nullable=False)
    emitida = Column(String(10), nullable=False)
    filename = Column(String(220), nullable=False)
    archivo = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
