class NotFoundError(Exception):
    def __init__(self, message: str = "Recurso no encontrado"):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    def __init__(self, message: str = "El recurso ya existe"):
        self.message = message
        super().__init__(message)


class UnauthorizedError(Exception):
    def __init__(self, message: str = "No autorizado"):
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str = "Datos inválidos"):
        self.message = message
        super().__init__(message)


class RateLimitError(Exception):
    def __init__(self, message: str = "Demasiados intentos. Espera unos minutos e intenta de nuevo."):
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    def __init__(self, message: str = "No tienes permiso para esta acción"):
        self.message = message
        super().__init__(message)
