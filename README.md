# Sistema POS — backend

API FastAPI del POS. Cada módulo sigue arquitectura hexagonal: el caso de uso habla con un puerto y el adaptador de Postgres implementa ese puerto.

## Módulo actual

El inicio de sesión sale de la pantalla del front: correo, contraseña y “mantener sesión iniciada”.

| Módulo | Qué representa en el front |
| --- | --- |
| `user` | Cuenta que entra con correo y contraseña y recibe un JWT |

CORS no está habilitado.

## Estructura

```text
app/
  main.py
  db/
  shared/
  user/
    domain/
      entities/
      ports/
    application/
    infrastructure/
      models/
      repositories/
    presentation/
      router.py
      schemas/
```

El flujo es `HTTP → caso de uso → puerto → repositorio`.

## Arranque

La API usa el proyecto de Supabase definido en `.env`. Postgres entra por el shared pooler (`aws-0-us-east-2`, puerto 5432) y pide `SUPABASE_DB_PASSWORD`.

```bash
docker compose up --build
```

- API: http://localhost:8000
- Salud: http://localhost:8000/health
- Swagger: http://localhost:8000/docs

`POST /users/login` inicia sesión y devuelve el JWT. `GET /users/me` y `POST /users` exigen `Authorization: Bearer`. La pantalla de login no crea cuentas.
