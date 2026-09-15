#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Перенос справочника городов
из STPO_prod.main__cityes в stpo.administrate__cities.
"""

from pathlib import Path
import sys
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

from connect import get_source_connection, get_target_connection

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

# --------------------------------------------------------------- config

TRUNCATE_TARGET = True

# --------------------------------------------------------------- helpers

def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


# --------------------------------------------------------------- main

def migrate_cities():

    src = None
    dst = None

    try:
        src = get_source_connection()
        dst = get_target_connection()

        print(f'{CYAN}\n-MIGRATE_CITIES{RESET}')

        # 1. Читаем города из источника
        with src.cursor() as cur:
            cur.execute("""
                SELECT code, name
                FROM main__cityes
                ORDER BY code
            """)

            cities = cur.fetchall()

        log(f"Записей: {len(cities)}")

        # 2. Очищаем целевую таблицу
        if TRUNCATE_TARGET:
            with dst.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                cur.execute("TRUNCATE TABLE administrate__cities")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 3. Вставляем города
        now = datetime.now()

        sql = """
            INSERT INTO administrate__cities
                (name, created_at, updated_at)
            VALUES
                (%s, %s, %s)
        """

        with dst.cursor() as cur:
            cur.executemany(
                sql,
                [
                    (city["name"], now, now)
                    for city in cities
                ],
            )

        log(f"Вставлено: {len(cities)}")

        # 4. Сбрасываем AUTO_INCREMENT
        with dst.cursor() as cur:
            cur.execute("""
                SELECT MAX(id) AS m
                FROM administrate__cities
            """)

            next_id = (cur.fetchone()["m"] or 0) + 1

            cur.execute(
                f"""
                ALTER TABLE administrate__cities
                AUTO_INCREMENT = {next_id}
                """
            )

        # 5. Сохраняем изменения
        dst.commit()

        log("✅ Успех")

    except Exception as exc:

        if dst is not None:
            dst.rollback()

        log(f"❌ Ошибка: {exc}")

        raise

    finally:

        if src is not None:
            src.close()

        if dst is not None:
            dst.close()


if __name__ == "__main__":
    try:
        migrate_cities()
    except Exception:
        sys.exit(1)