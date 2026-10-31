import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from integration.infrastructure.models.integration_model import (
    DianSettingModel,
    PeripheralModel,
    PrinterSettingModel,
    TicketSettingModel,
)
from shared.exceptions import NotFoundError

DEFAULT_PERIPHERALS = [
    ("barcode", "Lector de código de barras", True, "USB-HID"),
    ("scale", "Balanza digital", False, "COM3"),
    ("printer", "Impresora de tickets", True, "192.168.1.50"),
    ("dian", "DIAN Facturación Electrónica", True, "API REST"),
]

def _split_extra_header(extra: str) -> tuple[str, str, str, str]:
    phone = address = city = ""
    rest: list[str] = []
    for raw in (extra or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.casefold()
        if not phone and re.match(r"^(celular|tel[eé]fono|tel\.?|whats?app)\b", low):
            phone = re.sub(r"^(celular|tel[eé]fono|tel\.?|whats?app)\s*", "", line, flags=re.I).strip(" :.-")
            continue
        if not address and re.match(r"^(direcci[oó]n|dir\.?)\b", low):
            address = re.sub(r"^(direcci[oó]n|dir\.?)\s*", "", line, flags=re.I).strip(" :.-") or line
            continue
        if not city:
            city = line
            continue
        rest.append(line)
    return phone, address, city, "\n".join(rest)


DEFAULT_TICKET = {
    "storeName": "Mi negocio",
    "nitLine": "",
    "phone": "",
    "address": "",
    "city": "",
    "footer": "¡Gracias por su compra!",
    "showDate": True,
    "showClient": True,
    "showPayment": True,
    "showChange": True,
    "showReprint": True,
    "extraHeader": "",
}


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
        ticket = self.session.scalars(
            select(TicketSettingModel).where(TicketSettingModel.user_id == self.user_id)
        ).first()
        return {
            "peripherals": [
                {"id": item.code, "label": item.label, "connected": item.connected, "port": item.port}
                for item in peripherals
            ],
            "printer": {"host": printer.host, "tcpPort": printer.tcp_port, "paperWidth": printer.paper_width},
            "ticket": self._to_ticket(ticket),
            "dian": {
                "nit": dian.nit,
                "softwareId": dian.software_id,
                "softwarePin": "",
                "softwarePinSet": bool((dian.software_pin or "").strip()),
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

    def save_ticket(self, data: dict) -> dict:
        self._ensure()
        ticket = self.session.scalars(
            select(TicketSettingModel).where(TicketSettingModel.user_id == self.user_id)
        ).first()
        ticket.store_name = (data.get("storeName") or DEFAULT_TICKET["storeName"]).strip() or DEFAULT_TICKET["storeName"]
        ticket.nit_line = (data.get("nitLine") or "").strip()
        ticket.phone = (data.get("phone") or "").strip()
        ticket.address = (data.get("address") or "").strip()
        ticket.city = (data.get("city") or "").strip()
        ticket.footer = (data.get("footer") or "").strip()
        ticket.show_date = bool(data.get("showDate", True))
        ticket.show_client = bool(data.get("showClient", True))
        ticket.show_payment = bool(data.get("showPayment", True))
        ticket.show_change = bool(data.get("showChange", True))
        ticket.show_reprint = bool(data.get("showReprint", True))
        ticket.extra_header = (data.get("extraHeader") or "").strip()
        self.session.commit()
        return self.get()

    def save_dian(self, data: dict) -> dict:
        self._ensure()
        dian = self.session.scalars(
            select(DianSettingModel).where(DianSettingModel.user_id == self.user_id)
        ).first()
        dian.nit = data["nit"].strip()
        dian.software_id = data["softwareId"].strip()
        pin = (data.get("softwarePin") or "").strip()
        if pin:
            dian.software_pin = pin
        dian.environment = data["environment"]
        self.session.commit()
        return self.get()

    def _to_ticket(self, ticket: TicketSettingModel | None) -> dict:
        if ticket is None:
            return dict(DEFAULT_TICKET)
        phone = getattr(ticket, "phone", "") or ""
        address = getattr(ticket, "address", "") or ""
        city = getattr(ticket, "city", "") or ""
        extra = ticket.extra_header or ""
        if not (phone or address or city):
            parsed_phone, parsed_address, parsed_city, extra = _split_extra_header(extra)
            phone, address, city = parsed_phone, parsed_address, parsed_city
        return {
            "storeName": ticket.store_name or DEFAULT_TICKET["storeName"],
            "nitLine": ticket.nit_line or "",
            "phone": phone,
            "address": address,
            "city": city,
            "footer": ticket.footer or "",
            "showDate": bool(ticket.show_date),
            "showClient": bool(ticket.show_client),
            "showPayment": bool(ticket.show_payment),
            "showChange": bool(ticket.show_change),
            "showReprint": bool(ticket.show_reprint),
            "extraHeader": extra,
        }

    def ensure_defaults(self) -> None:
        self._ensure()

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
        if self.session.scalar(select(TicketSettingModel.id).where(TicketSettingModel.user_id == self.user_id)) is None:
            self.session.add(
                TicketSettingModel(
                    user_id=self.user_id,
                    store_name=DEFAULT_TICKET["storeName"],
                    nit_line=DEFAULT_TICKET["nitLine"],
                    phone="",
                    address="",
                    city="",
                    footer=DEFAULT_TICKET["footer"],
                    show_date=True,
                    show_client=True,
                    show_payment=True,
                    show_change=True,
                    show_reprint=True,
                    extra_header="",
                )
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
