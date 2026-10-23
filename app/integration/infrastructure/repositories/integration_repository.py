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
    def __init__(self, session: Session, user_id: int):
        self.session = session
        self.user_id = user_id

    def get(self) -> dict:
        self._ensure()
        peripherals = list(
            self.session.scalars(
                select(PeripheralModel)
                .where(PeripheralModel.user_id == self.user_id)
                .order_by(PeripheralModel.id.asc())
            ).all()
        )
        printer = self.session.scalars(
            select(PrinterSettingModel).where(PrinterSettingModel.user_id == self.user_id)
        ).first()
        dian = self.session.scalars(
            select(DianSettingModel).where(DianSettingModel.user_id == self.user_id)
        ).first()
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
        peripheral = self.session.scalar(
            select(PeripheralModel).where(
                PeripheralModel.user_id == self.user_id,
                PeripheralModel.code == code,
            )
        )
        if peripheral is None:
            raise NotFoundError("Integración no encontrada")
        peripheral.connected = connected
        self.session.commit()
        return self.get()

    def save_printer(self, data: dict) -> dict:
        self._ensure()
        printer = self.session.scalars(
            select(PrinterSettingModel).where(PrinterSettingModel.user_id == self.user_id)
        ).first()
        printer.host = data["host"].strip()
        printer.tcp_port = data["tcpPort"]
        printer.paper_width = data["paperWidth"]
        peripheral = self.session.scalar(
            select(PeripheralModel).where(
                PeripheralModel.user_id == self.user_id,
                PeripheralModel.code == "printer",
            )
        )
        if peripheral is not None:
            peripheral.port = printer.host
        self.session.commit()
        return self.get()

    def save_dian(self, data: dict) -> dict:
        self._ensure()
        dian = self.session.scalars(
            select(DianSettingModel).where(DianSettingModel.user_id == self.user_id)
        ).first()
        dian.nit = data["nit"].strip()
        dian.software_id = data["softwareId"].strip()
        dian.software_pin = data["softwarePin"]
        dian.environment = data["environment"]
        self.session.commit()
        return self.get()

    def _ensure(self) -> None:
        if self.session.scalar(select(PeripheralModel.id).where(PeripheralModel.user_id == self.user_id)) is None:
            for code, label, connected, port in DEFAULT_PERIPHERALS:
                self.session.add(
                    PeripheralModel(
                        user_id=self.user_id,
                        code=code,
                        label=label,
                        connected=connected,
                        port=port,
                    )
                )
        if self.session.scalar(select(PrinterSettingModel.id).where(PrinterSettingModel.user_id == self.user_id)) is None:
            self.session.add(
                PrinterSettingModel(user_id=self.user_id, host="192.168.1.50", tcp_port=9100, paper_width="80mm")
            )
        if self.session.scalar(select(DianSettingModel.id).where(DianSettingModel.user_id == self.user_id)) is None:
            self.session.add(
                DianSettingModel(
                    user_id=self.user_id,
                    nit="",
                    software_id="",
                    software_pin="",
                    environment="Habilitación / Pruebas",
                )
            )
        self.session.commit()
