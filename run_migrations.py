import os
from alembic.config import Config
from alembic import command

def main() -> None:
    # Керовано прапорцем, щоб в проді можна було вимкнути
    run_flag = (os.getenv("RUN_MIGRATIONS") or "").strip().lower()
    if run_flag not in {"1", "true", "yes", "on"}:
        print("ℹ️ RUN_MIGRATIONS is off, skipping alembic.")
        return

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    command.upgrade(cfg, "head")
    print("✅ alembic upgrade head done")

if __name__ == "__main__":
    main()