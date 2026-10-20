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
from shift.presentation.router import router as shift_router
from supplier.presentation.router import router as supplier_router
from user.presentation.deps import get_current_user
from user.presentation.router import router as user_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Sistema POS",
    version="0.1.0",
    description="API del POS: usuarios, productos, inventario, clientes, proveedores, ventas e integraciones.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://promethixiafront.netlify.app",
        "http://localhost:8443",
        "http://127.0.0.1:8443",
    ],
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_methods=["*"],
    allow_headers=["*"],
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
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
