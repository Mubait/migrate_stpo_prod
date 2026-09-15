from connect import check_connections
from reset_db import reset_dbs


def main():
    print("=" * 60)
    print("STPO DATABASE MIGRATION")
    print("=" * 60)

    # 1. Проверяем подключения
    print("\n[1] Проверка подключений")

    if not check_connections():
        print("\n✗ Подключение к базам не установлено")
        return

    print("\n✓ Подключение к обеим базам успешно")

    # 2. Сбрасываем целевую БД
    print("\n[2] Сброс целевой базы")

    reset_dbs()

    # 3. Здесь дальше будут миграции
    print("\n[3] Перенос данных")

    # migrate_divisions()
    # migrate_users()
    # migrate_services()
    # ...


if __name__ == "__main__":
    main()
