from sqlalchemy import select
from sqlalchemy.orm import Session

from license.infrastructure.models.license_model import DesktopLicenseModel
from shared.clock import now_bogota
from shared.exceptions import NotFoundError


class LicenseRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[dict]:
        rows = self.session.scalars(
            select(DesktopLicenseModel).order_by(DesktopLicenseModel.created_at.desc(), DesktopLicenseModel.id.desc())
        ).all()
        return [self._public(row) for row in rows]

    def create(
        self,
        *,
        cliente: str,
        equipo: str | None,
        actualizaciones_hasta: str,
        emitida: str,
        filename: str,
        archivo: str,
        created_by: int | None,
    ) -> dict:
        model = DesktopLicenseModel(
            cliente=cliente,
            equipo=equipo,
            actualizaciones_hasta=actualizaciones_hasta,
            emitida=emitida,
            filename=filename,
            archivo=archivo,
            created_by=created_by,
            created_at=now_bogota(),
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._public(model)

    def file_of(self, license_id: int) -> tuple[str, str]:
        model = self.session.get(DesktopLicenseModel, license_id)
        if model is None:
            raise NotFoundError("Licencia no encontrada")
        return model.filename, model.archivo

    @staticmethod
    def _public(model: DesktopLicenseModel) -> dict:
        return {
            "id": model.id,
            "cliente": model.cliente,
            "equipo": model.equipo,
            "actualizaciones_hasta": model.actualizaciones_hasta,
            "emitida": model.emitida,
            "filename": model.filename,
            "created_at": model.created_at.isoformat(),
        }
