"""Dev helper: run an embedded user-space PostgreSQL (no root needed)."""
import time
from pathlib import Path

import embedded_postgres as ep
import psycopg

DATA_DIR = Path(__file__).resolve().parent.parent / ".pgdata"


def main() -> None:
    pg = ep.get_server(DATA_DIR, cleanup_mode="stop")
    pg.ensure_pgdata_inited()
    pg.ensure_postgres_running()
    admin_uri = pg.get_uri("postgres")
    print(f"postgres running: {admin_uri}", flush=True)
    with psycopg.connect(admin_uri, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname='arche_dev'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE arche_dev")
            print("created database arche_dev", flush=True)
    app_uri = pg.get_uri("arche_dev")
    sa_uri = app_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    env_path = Path(__file__).resolve().parent / ".env"
    env_path.write_text(
        f"DATABASE_URL={sa_uri}\nAPP_ENV=development\nAUTH_MODE=stub\n"
        "STUB_AUTH_EMAIL=demo@example.com\nSTORAGE_LOCAL_DIR=.storage\n"
        "LIBREOFFICE_BIN=/opt/data/libreoffice/bin/soffice-arche\nEXPORT_MAX_PDF_TIMEOUT_S=120\n"
        'CORS_ALLOW_ORIGINS=["http://localhost:3000", "http://187.77.157.151:3000"]\n'
    )
    print(f"wrote backend/.env: {sa_uri}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pg.cleanup()


if __name__ == "__main__":
    main()