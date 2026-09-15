#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Перенос уведомлений:

STPO_prod.main__alerts
        ->
stpo.base__notifications

Маппинг:

    id
        -> id

    message
        -> message

    context
        -> {}

    visible
        -> is_readed

    to
        -> recipient_id

    sender_id
        -> 2, если указан recipient_id
        -> NULL, если recipient_id отсутствует

    type_id
        -> 2

    created_at
        -> created_at

    updated_at
        -> updated_at

Не переносятся:

    header
    link
"""

from pathlib import Path
from datetime import datetime
import sys

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)

from connect import (
    get_source_connection,
    get_target_connection,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

TRUNCATE_TARGET = True

BATCH_SIZE = 5000

DEFAULT_SENDER_ID = 2

DEFAULT_TYPE_ID = 2

# ============================================================
# ЦВЕТА
# ============================================================

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"


# ============================================================
# ЛОГ
# ============================================================

def log(message):
    print(
        f"[{datetime.now():%H:%M:%S}] {message}"
    )


# ============================================================
# ПОДГОТОВКА ЗНАЧЕНИЯ MESSAGE
# ============================================================

def convert_message(value):
    if value is None:
        return ""

    return str(value)


# ============================================================
# МИГРАЦИЯ
# ============================================================

def migrate_notifications():

    src = None
    dst = None

    try:

        # ====================================================
        # CONNECTION
        # ====================================================

        src = get_source_connection()
        dst = get_target_connection()

        print(f"{CYAN}\nMIGRATE NOTIFICATIONS{RESET}")

        # ====================================================
        # Получаем уведомления
        # ====================================================

        with src.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    `to`,
                    visible,
                    message,
                    created_at,
                    updated_at
                FROM main__alerts
                ORDER BY id
            """)

            alerts = cur.fetchall()

        log(
            f"Записей в источнике: "
            f"{len(alerts)}"
        )

        # ====================================================
        # Очищаем target
        # ====================================================

        if TRUNCATE_TARGET:

            with dst.cursor() as cur:

                cur.execute(
                    "SET FOREIGN_KEY_CHECKS = 0"
                )

                cur.execute("""
                    DELETE FROM base__notifications
                """)

                cur.execute(
                    "SET FOREIGN_KEY_CHECKS = 1"
                )

            log(
                "Очищена таблица "
                "base__notifications"
            )

        # ====================================================
        # Подготавливаем данные
        # ====================================================

        rows = []

        for alert in alerts:

            recipient_id = alert["to"]

            # ------------------------------------------------
            # sender_id
            #
            # Если есть получатель -> sender_id = 2
            # Если получателя нет -> NULL
            # ------------------------------------------------

            sender_id = (
                DEFAULT_SENDER_ID
                if recipient_id is not None
                else None
            )

            rows.append((
                alert["id"],

                # message
                convert_message(
                    alert["message"]
                ),

                # context
                "{}",

                # is_readed
                alert["visible"],

                # recipient_id
                recipient_id,

                # sender_id
                sender_id,

                # type_id
                DEFAULT_TYPE_ID,

                # created_at
                alert["created_at"],

                # updated_at
                alert["updated_at"],
            ))

        # ====================================================
        # SQL
        # ====================================================

        sql = """
            INSERT INTO base__notifications
            (
                id,
                message,
                context,
                is_readed,
                recipient_id,
                sender_id,
                type_id,
                created_at,
                updated_at
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """

        # ====================================================
        # Вставка батчами
        # ====================================================

        total = len(rows)

        for start in range(
            0,
            total,
            BATCH_SIZE
        ):

            batch = rows[
                start:start + BATCH_SIZE
            ]

            with dst.cursor() as cur:

                cur.executemany(
                    sql,
                    batch,
                )

            log(
                f"Перенесено: "
                f"{min(start + len(batch), total)}"
                f"/{total}"
            )

        # ====================================================
        # AUTO_INCREMENT
        # ====================================================

        with dst.cursor() as cur:

            cur.execute("""
                SELECT MAX(id) AS max_id
                FROM base__notifications
            """)

            max_id = (
                cur.fetchone()["max_id"]
                or 0
            )

            cur.execute(
                f"""
                ALTER TABLE base__notifications
                AUTO_INCREMENT = {max_id + 1}
                """
            )

        # ====================================================
        # COMMIT
        # ====================================================

        dst.commit()

        log(
            f"Вставлено уведомлений: "
            f"{len(rows)} шт."
        )

        log(
            "✅ Миграция уведомлений завершена"
        )

    except Exception as exc:

        if dst is not None:
            dst.rollback()

        log(
            f"❌ Ошибка: {exc}"
        )

        raise

    finally:

        if src is not None:
            src.close()

        if dst is not None:
            dst.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        migrate_notifications()

    except Exception:

        sys.exit(1)