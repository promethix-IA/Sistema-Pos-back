from sqlalchemy import select
from sqlalchemy.orm import Session

from integration.infrastructure.models.integration_model import DianSettingModel, PeripheralModel, PrinterSettingModel
from shared.exceptions import NotFoundError

DEFAULT_PERIPHERALS = [
    ("barcode", "Lector de código de barras", True, "USB-HID"),
    ("scale", "Balanza digital", False, "COM3"),
    ("printer", "Impresora de tickets", True, "192.168.1.50"),
    ("dian", "DIAN Facturación Electrónica", True, "API REST"),
]


class IntegrationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self) -> dict:
        self._ensure()
        peripherals = list(self.session.scalars(select(PeripheralModel).order_by(PeripheralModel.id.asc())).all())
        printer = self.session.scalars(select(PrinterSettingModel)).first()
        dian = self.session.scalars(select(DianSettingModel)).first()
        return {
            "peripherals": [
                {"id": item.code, "label": item.label, "connected": item.connected, "port": item.port}
                for item in peripherals
            ],
            "printer": {"host": printer.host, "tcpPort": printer.tcp_port, "paperWidth": printer.paper_width},
            "dian": {
                "nit": dian.nit,
                "softwareId": dian.software_id,
                "softwarePin": dian.software_pin,
                "environment": dian.environment,
            },
        }

    def set_connected(self, code: str, connected: bool) -> dict:
        self._ensure()
        peripheral = self.session.scalar(select(PeripheralModel).where(PeripheralModel.code == code))
        if peripheral is None:
            raise NotFoundError("Integración no encontrada")
        peripheral.connected = connected
        self.session.commit()
        return self.get()

    def save_printer(self, data: dict) -> dict:
        self._ensure()
        printer = self.session.scalars(select(PrinterSettingModel)).first()
        printer.host = data["host"].strip()
        printer.tcp_port = data["tcpPort"]
        printer.paper_width = data["paperWidth"]
        peripheral = self.session.scalar(select(PeripheralModel).where(PeripheralModel.code == "printer"))
        if peripheral is not None:
            peripheral.port = printer.host
        self.session.commit()
        return self.get()

    def save_dian(self, data: dict) -> dict:
        self._ensure()
        dian = self.session.scalars(select(DianSettingModel)).first()
        dian.nit = data["nit"].strip()
        dian.software_id = data["softwareId"].strip()
        dian.software_pin = data["softwarePin"]
        dian.environment = data["environment"]
        self.session.commit()
        return self.get()

    def _ensure(self) -> None:
        if self.session.scalar(select(PeripheralModel.id)) is None:
            for code, label, connected, port in DEFAULT_PERIPHERALS:
                self.session.add(PeripheralModel(code=code, label=label, connected=connected, port=port))
        if self.session.scalar(select(PrinterSettingModel.id)) is None:
            self.session.add(PrinterSettingModel(host="192.168.1.50", tcp_port=9100, paper_width="80mm"))
        if self.session.scalar(select(DianSettingModel.id)) is None:
            self.session.add(
                DianSettingModel(
                    nit="900.123.456-1",
                    software_id="abc123-dian-prod",
                    software_pin="",
                    environment="Producción",
                )
            )
        self.session.commit()
