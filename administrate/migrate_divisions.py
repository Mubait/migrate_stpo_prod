#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Перенос справочника подразделений
из STPO_prod.main__divisions в stpo.administrate__divisions.
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

def migrate_divisions():

    src = None
    dst = None

    try:
        src = get_source_connection()
        dst = get_target_connection()

        print(f'{CYAN}\n-MIGRATE_DIVISIONS{RESET}')

        # 1. Читаем подразделения и определяем название города
        with src.cursor() as cur:
            cur.execute("""
                SELECT
                    d.id,
                    d.name,
                    d.city_code,
                    c.name AS city_name
                FROM main__divisions d
                LEFT JOIN main__cityes c
                    ON c.code = d.city_code
                ORDER BY d.id
            """)

            divisions = cur.fetchall()

        log(f"Записей: {len(divisions)}")

        # 2. Получаем города из новой БД
        with dst.cursor() as cur:
            cur.execute("""
                SELECT id, name
                FROM administrate__cities
            """)

            cities = {
                city["name"]: city["id"]
                for city in cur.fetchall()
            }

        log(f"Городов в новой БД: {len(cities)}")

        # 3. Очищаем целевую таблицу
        if TRUNCATE_TARGET:
            with dst.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                cur.execute("""
                    TRUNCATE TABLE administrate__divisions
                """)
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 4. Подготавливаем данные
        now = datetime.now()
        rows = []
        skipped = 0

        for division in divisions:

            city_name = division["city_name"]

            if city_name is None:
                log(
                    f"⚠ Город не найден в источнике: "
                    f"division_id={division['id']} | "
                    f"name={division['name']} | "
                    f"city_code={division['city_code']}"
                )

                skipped += 1
                continue

            city_id = cities.get(city_name)

            if city_id is None:
                log(
                    f"⚠ Город не найден в новой БД: "
                    f"{city_name} "
                    f"(code={division['city_code']}, "
                    f"division_id={division['id']})"
                )

                skipped += 1
                continue

            rows.append((
                division["name"],
                city_id,
                now,
                now,
            ))

        # 5. Вставляем подразделения
        sql = """
            INSERT INTO administrate__divisions
                (name, city_id, created_at, updated_at)
            VALUES
                (%s, %s, %s, %s)
        """

        with dst.cursor() as cur:
            cur.executemany(sql, rows)

        log(f"Вставлено: {len(rows)}")

        if skipped:
            log(f"Пропущено: {skipped}")

        # 6. Сбрасываем AUTO_INCREMENT
        with dst.cursor() as cur:
            cur.execute("""
                SELECT MAX(id) AS m
                FROM administrate__divisions
            """)

            next_id = (cur.fetchone()["m"] or 0) + 1

            cur.execute(
                f"""
                ALTER TABLE administrate__divisions
                AUTO_INCREMENT = {next_id}
                """
            )

        # 7. Сохраняем изменения
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
        migrate_divisions()
    except Exception:
        sys.exit(1)