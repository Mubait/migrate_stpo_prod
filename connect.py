# migrate_db/connect.py

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


USER = "root"
PASSWORD = "Wtynh2023$"
HOST = "localhost"

SOURCE_DB = "STPO_prod"
TARGET_DB = "stpo"


source = create_engine(
    f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{SOURCE_DB}",
    pool_pre_ping=True,
    future=True,
)

target = create_engine(
    f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{TARGET_DB}",
    pool_pre_ping=True,
    future=True,
)


SourceSession = sessionmaker(bind=source, future=True)
TargetSession = sessionmaker(bind=target, future=True)


@contextmanager
def src_conn():
    with source.begin() as conn:
        yield conn


@contextmanager
def dst_conn():
    with target.begin() as conn:
        yield conn


def check_connection(engine, database):
    """Проверяет подключение к MySQL и конкретной базе."""

    try:
        with engine.connect() as connection:
            # Проверяем соединение
            connection.execute(text("SELECT 1"))

            # Получаем текущую БД
            current_database = connection.execute(
                text("SELECT DATABASE()")
            ).scalar()

            # Получаем версию MySQL
            version = connection.execute(
                text("SELECT VERSION()")
            ).scalar()

            # Количество таблиц
            tables_count = connection.execute(
                text("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                """)
            ).scalar()

            print(f"✓ MySQL: {HOST}")
            print(f"✓ База: {current_database}")
            print(f"✓ Версия MySQL: {version}")
            print(f"✓ Таблиц: {tables_count}")

            return True

    except Exception as e:
        print(f"✗ Ошибка подключения к базе {database}")
        print(f"  {e}")

        return False


def check_connections():
    print("=" * 60)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЙ К БАЗАМ ДАННЫХ")
    print("=" * 60)

    print("\n[1] STPO_prod")

    source_ok = check_connection(
        source,
        SOURCE_DB,
    )

    print("\n[2] stpo")

    target_ok = check_connection(
        target,
        TARGET_DB,
    )

    print("\n" + "=" * 60)

    if source_ok and target_ok:
        print("✓ Оба подключения успешно установлены")
    else:
        print("✗ Не удалось подключиться ко всем базам")

    print("=" * 60)

    return source_ok and target_ok


if __name__ == "__main__":
    check_connections()
