from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from category.presentation.router import router as category_router
from client.presentation.router import router as client_router
from credit.presentation.router import router as credit_router
from inventory.presentation.router import router as inventory_router
from db.session import init_db
from integration.presentation.router import router as integration_router
from product.presentation.router import router as product_router
from sale.presentation.router import router as sale_router
from shared.config.settings import settings
from shared.security.headers import SecurityHeadersMiddleware
from shift.presentation.router import router as shift_router
from supplier.presentation.router import router as supplier_router
from user.presentation.deps import get_current_user
from user.presentation.router import router as user_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


docs_enabled = not settings.is_production

app = FastAPI(
    title="Sistema POS",
    version="0.1.0",
    description="API del POS: usuarios, productos, inventario, clientes, proveedores, ventas e integraciones.",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)

app.include_router(user_router)
protected = [Depends(get_current_user)]
app.include_router(product_router, dependencies=protected)
app.include_router(category_router, dependencies=protected)
app.include_router(inventory_router, dependencies=protected)
app.include_router(client_router, dependencies=protected)
app.include_router(supplier_router, dependencies=protected)
app.include_router(sale_router, dependencies=protected)
app.include_router(shift_router, dependencies=protected)
app.include_router(credit_router, dependencies=protected)
app.include_router(integration_router, dependencies=protected)


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": "Sistema POS",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
