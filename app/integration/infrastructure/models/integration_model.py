from sqlalchemy import Boolean, Column, Integer, String

from db.database import Base


class PeripheralModel(Base):
    __tablename__ = "peripherals"

    id = Column(Integer, primary_key=True)
    code = Column(String(40), nullable=False, unique=True)
    label = Column(String(120), nullable=False)
    connected = Column(Boolean, nullable=False, default=False)
    port = Column(String(80), nullable=False)


class PrinterSettingModel(Base):
    __tablename__ = "printer_settings"

    id = Column(Integer, primary_key=True)
    host = Column(String(120), nullable=False)
    tcp_port = Column(Integer, nullable=False)
    paper_width = Column(String(20), nullable=False)


class DianSettingModel(Base):
    __tablename__ = "dian_settings"

    id = Column(Integer, primary_key=True)
    nit = Column(String(40), nullable=False)
    software_id = Column(String(120), nullable=False)
    software_pin = Column(String(255), nullable=False)
    environment = Column(String(40), nullable=False)
