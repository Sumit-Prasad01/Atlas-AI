# Database migrations

Run Alembic from the repository root after installing
`backend/requirements.txt`:

```powershell
alembic -c backend/alembic.ini revision --autogenerate -m "describe change"
alembic -c backend/alembic.ini upgrade head
```

`DATABASE_URL` must use an async SQLAlchemy driver, for example
`postgresql+asyncpg://...`.
