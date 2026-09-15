#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Перенос сообщений обращений и подписчиков чатов.

Источник:

    STPO_prod.csvi__appeal__messages
    STPO_prod.csvi__appeal__appeals

Цель:

    stpo.base__chat_messages
    stpo.base__chat_subscribers


MESSAGES:

    source.message
        -> message

    source.sender_id
        -> sender_id

    source.appeal_id
        -> chat_id

    context
        -> {}

    readed
        -> 1

    file_id
        -> NULL

    source.created_at
        -> created_at

    source.updated_at
        -> updated_at

    deleted_at
        -> NULL


SUBSCRIBERS:

    appeal.id
        -> chat_id

    appeal.sender_id
        -> user_id

    appeal.accepted_by
        -> user_id

    appeal.created_at
        -> created_at

    appeal.updated_at
        -> updated_at

Если sender_id == accepted_by,
создаётся только одна запись.

Функция migrate_messages()
не принимает аргументов и самостоятельно
создаёт подключения к базам.
"""

from pathlib import Path
import sys
import json
from datetime import datetime


# ============================================================
# PATH
# ============================================================

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)


# ============================================================
# CONNECTION
# ============================================================

from connect import (
    get_source_connection,
    get_target_connection,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

TRUNCATE_TARGET = True

BATCH_SIZE = 5000


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
# LOG
# ============================================================

def log(message):
    print(
        f"[{datetime.now():%H:%M:%S}] "
        f"{message}"
    )


# ============================================================
# DATE
# ============================================================

def convert_datetime(value):
    """
    Приведение значения даты к datetime.
    """

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    value = str(value).strip()

    formats = [
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for date_format in formats:

        try:

            return datetime.strptime(
                value,
                date_format
            )

        except ValueError:
            continue

    raise ValueError(
        f"Не удалось преобразовать дату: {value}"
    )


# ============================================================
# MESSAGE
# ============================================================

def convert_message(value):
    """
    Приведение message к строке.

    Если PyMySQL вернул JSON как dict/list,
    преобразуем его обратно в JSON.
    """

    if value is None:
        return ""

    if isinstance(value, (dict, list)):

        return json.dumps(
            value,
            ensure_ascii=False
        )

    return str(value)


# ============================================================
# MIGRATE MESSAGES
# ============================================================

def migrate_messages_data(src, dst):
    """
    Перенос base__chat_messages.
    """

    print(
        f"{CYAN}\n-MIGRATE_APPEAL_MESSAGES{RESET}"
    )

    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    with src.cursor() as cur:

        cur.execute("""
            SELECT
                id,
                appeal_id,
                sender_id,
                message,
                is_system,
                is_file,
                is_image,
                created_at,
                updated_at
            FROM csvi__appeal__messages
            ORDER BY id
        """)

        messages = cur.fetchall()

    log(
        f"Записей сообщений в источнике: "
        f"{len(messages)}"
    )

    # --------------------------------------------------------
    # CLEAR TARGET
    # --------------------------------------------------------

    if TRUNCATE_TARGET:

        with dst.cursor() as cur:

            cur.execute(
                "SET FOREIGN_KEY_CHECKS = 0"
            )

            cur.execute("""
                DELETE FROM base__chat_messages
            """)

            cur.execute(
                "SET FOREIGN_KEY_CHECKS = 1"
            )

        log(
            "Очищена таблица "
            "base__chat_messages"
        )

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    sql = """
        INSERT INTO base__chat_messages
            (
                message,
                context,
                readed,
                sender_id,
                chat_id,
                file_id,
                created_at,
                updated_at,
                deleted_at
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

    # --------------------------------------------------------
    # INSERT
    # --------------------------------------------------------

    rows = []

    total = len(messages)

    with dst.cursor() as cur:

        for index, message in enumerate(
            messages,
            start=1
        ):

            rows.append((
                convert_message(
                    message["message"]
                ),

                "{}",                              # context

                1,                                  # readed

                message["sender_id"],               # sender_id

                message["appeal_id"],               # chat_id

                None,                               # file_id

                convert_datetime(
                    message["created_at"]
                ),

                convert_datetime(
                    message["updated_at"]
                ),

                None,                               # deleted_at
            ))

            # ------------------------------------------------
            # BATCH
            # ------------------------------------------------

            if len(rows) >= BATCH_SIZE:

                cur.executemany(
                    sql,
                    rows
                )

                dst.commit()

                log(
                    f"Сообщения: "
                    f"{index}/{total}"
                )

                rows.clear()

        # ----------------------------------------------------
        # LAST BATCH
        # ----------------------------------------------------

        if rows:

            cur.executemany(
                sql,
                rows
            )

            dst.commit()

            log(
                f"Сообщения: "
                f"{total}/{total}"
            )

            rows.clear()

    # --------------------------------------------------------
    # AUTO_INCREMENT
    # --------------------------------------------------------

    with dst.cursor() as cur:

        cur.execute("""
            SELECT MAX(id) AS m
            FROM base__chat_messages
        """)

        max_id = (
            cur.fetchone()["m"]
            or 0
        )

        cur.execute(
            f"""
            ALTER TABLE base__chat_messages
            AUTO_INCREMENT = {max_id + 1}
            """
        )

    dst.commit()

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    with dst.cursor() as cur:

        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM base__chat_messages
        """)

        count = cur.fetchone()["cnt"]

    log(
        f"Создано сообщений: "
        f"{count} шт."
    )


# ============================================================
# MIGRATE SUBSCRIBERS
# ============================================================

def migrate_subscribers_data(src, dst):
    """
    Перенос base__chat_subscribers.
    """

    print(
        f"{CYAN}\n-MIGRATE_CHAT_SUBSCRIBERS{RESET}"
    )

    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    with src.cursor() as cur:

        cur.execute("""
            SELECT
                id,
                sender_id,
                accepted_by,
                created_at,
                updated_at
            FROM csvi__appeal__appeals
            ORDER BY id
        """)

        appeals = cur.fetchall()

    log(
        f"Обращений для подписчиков: "
        f"{len(appeals)}"
    )

    # --------------------------------------------------------
    # CLEAR TARGET
    # --------------------------------------------------------

    if TRUNCATE_TARGET:

        with dst.cursor() as cur:

            cur.execute(
                "SET FOREIGN_KEY_CHECKS = 0"
            )

            cur.execute("""
                DELETE FROM base__chat_subscribers
            """)

            cur.execute(
                "SET FOREIGN_KEY_CHECKS = 1"
            )

        log(
            "Очищена таблица "
            "base__chat_subscribers"
        )

    # --------------------------------------------------------
    # PREPARE
    # --------------------------------------------------------

    rows = []

    for appeal in appeals:

        chat_id = appeal["id"]

        created_at = convert_datetime(
            appeal["created_at"]
        )

        updated_at = convert_datetime(
            appeal["updated_at"]
        )

        # ----------------------------------------------------
        # AUTHOR
        # ----------------------------------------------------

        sender_id = appeal["sender_id"]

        if sender_id is not None:

            rows.append((
                chat_id,
                sender_id,
                created_at,
                updated_at,
            ))

        # ----------------------------------------------------
        # WORKER
        # ----------------------------------------------------

        accepted_by = appeal["accepted_by"]

        if (
            accepted_by is not None
            and accepted_by != sender_id
        ):

            rows.append((
                chat_id,
                accepted_by,
                created_at,
                updated_at,
            ))

    log(
        f"Подготовлено подписчиков: "
        f"{len(rows)}"
    )

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    sql = """
        INSERT INTO base__chat_subscribers
            (
                chat_id,
                user_id,
                created_at,
                updated_at
            )
        VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
    """

    # --------------------------------------------------------
    # INSERT
    # --------------------------------------------------------

    total = len(rows)

    with dst.cursor() as cur:

        for offset in range(
            0,
            total,
            BATCH_SIZE
        ):

            batch = rows[
                offset:offset + BATCH_SIZE
            ]

            cur.executemany(
                sql,
                batch
            )

            dst.commit()

            processed = min(
                offset + len(batch),
                total
            )

            log(
                f"Подписчики: "
                f"{processed}/{total}"
            )

    # --------------------------------------------------------
    # AUTO_INCREMENT
    # --------------------------------------------------------

    with dst.cursor() as cur:

        cur.execute("""
            SELECT MAX(id) AS m
            FROM base__chat_subscribers
        """)

        max_id = (
            cur.fetchone()["m"]
            or 0
        )

        cur.execute(
            f"""
            ALTER TABLE base__chat_subscribers
            AUTO_INCREMENT = {max_id + 1}
            """
        )

    dst.commit()

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    with dst.cursor() as cur:

        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM base__chat_subscribers
        """)

        count = cur.fetchone()["cnt"]

    log(
        f"Создано подписчиков: "
        f"{count} шт."
    )


# ============================================================
# MAIN MIGRATION
# ============================================================

def migrate_messages():

    src = None
    dst = None

    try:

        # ----------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------

        src = get_source_connection()
        dst = get_target_connection()

        # ----------------------------------------------------
        # MESSAGES
        # ----------------------------------------------------

        migrate_messages_data(
            src,
            dst
        )

        # ----------------------------------------------------
        # SUBSCRIBERS
        # ----------------------------------------------------

        migrate_subscribers_data(
            src,
            dst
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        print()

        log(
            "========================================"
        )

        log(
            f"{GREEN}✅ МИГРАЦИЯ "
            f"СООБЩЕНИЙ И ПОДПИСЧИКОВ "
            f"ЗАВЕРШЕНА{RESET}"
        )

        log(
            "========================================"
        )

    except Exception as exc:

        if dst is not None:
            dst.rollback()

        log(
            f"{RED}❌ Ошибка: "
            f"{exc}{RESET}"
        )

        raise

    finally:

        if src is not None:
            src.close()

        if dst is not None:
            dst.close()


# ============================================================
# DIRECT RUN
# ============================================================

if __name__ == "__main__":

    try:

        migrate_messages()

    except Exception:

        sys.exit(1)