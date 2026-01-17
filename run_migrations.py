from alembic.config import Config
from alembic import command

def run():
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    command.upgrade(cfg, "head")
    print("✅ alembic upgrade head done")

if __name__ == "__main__":
    run()