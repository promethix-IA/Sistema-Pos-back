# Promethixia POS — backend

API del punto de venta **Promethixia**. Recibe el login, aísla los datos de cada negocio y expone productos, inventario, clientes, ventas, caja, créditos e integraciones.

El front que consume esta API está en `Sistema-Pos-Front`. La web comercial está en `Landing-Page`.

## Qué hace

- Autentica con correo y contraseña y entrega un JWT (HS256) con `iss`, `aud`, `iat`, `nbf`, `jti` y `typ`.
- Separa negocios: el admin de plataforma crea usuarios padre (`owner`); el padre crea a su equipo y les asigna rol.
- Filtra catálogo, ventas, caja y créditos por el `user_id` del negocio (el padre o su `owner_id`).
- Cubre el POS: productos (unidad o granel), categorías, inventario, clientes, proveedores, ventas, dashboard, turnos de caja, créditos y periféricos/DIAN.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2 y Postgres (pooler de Supabase)
- Pydantic Settings
- PyJWT
- Docker (opcional)

Arquitectura hexagonal por módulo: `HTTP → caso de uso → puerto → repositorio Postgres`.

```text
app/
  main.py
  db/
  shared/          # auth JWT, CORS, tenancy, cabeceras, rate limit
  user/
  product/
  category/
  inventory/
  client/
  supplier/
  sale/
  shift/
  credit/
  integration/
    domain/
    application/
    infrastructure/
    presentation/
```

## Roles

| Rol | Quién lo crea | Qué ve |
| --- | --- | --- |
| `admin` | cuenta de plataforma (`admin@…`) | solo usuarios/negocios; no comparte datos del POS |
| `owner` | el admin | POS completo + equipo de su negocio |
| `administrador` | el padre | POS completo + usuarios del negocio |
| `cajero` | el padre | dashboard, ventas, caja, créditos, clientes |
| `inventario` | el padre | dashboard, productos, inventario, proveedores |

## Endpoints

Públicos:

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/health` | salud |
| `POST` | `/users/login` | inicia sesión y devuelve JWT |

El resto exige `Authorization: Bearer`.

| Prefijo | Módulo |
| --- | --- |
| `/users` | cuentas, `/me`, cambio de rol |
| `/products` | catálogo |
| `/categories` | categorías |
| `/inventory` | movimientos y ajustes |
| `/clients` | clientes |
| `/suppliers` | proveedores y órdenes |
| `/sales` | ventas, cancelaciones y devoluciones |
| `/dashboard` | KPIs del día/semana/año |
| `/shifts` | apertura y cierre de caja |
| `/credits` | deudas y abonos |
| `/integrations` | periféricos, impresora y DIAN |

En producción (`APP_ENV` distinto de `development`) Swagger y OpenAPI se apagan.

## Seguridad

- CORS solo con orígenes de `CORS_ORIGINS` (POS en `pos.promethixia.com`, Netlify y localhost).
- Cabeceras HTTP (`X-Frame-Options`, `nosniff`, `Referrer-Policy`, etc.).
- Tope de intentos de login (`LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS`).
- `JWT_SECRET` de al menos 32 caracteres. No uses el valor de ejemplo.

## Arranque

Copia `.env.example` a `.env` y completa `SUPABASE_DB_PASSWORD` y `JWT_SECRET`. No subas `.env`.

```bash
docker compose up --build
```

O en local, desde `app/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Salud: http://localhost:8000/health
- Swagger (solo development): http://localhost:8000/docs

Producción actual: [https://sistema-pos-back.onrender.com](https://sistema-pos-back.onrender.com).
