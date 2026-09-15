#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Перенос обращений
из STPO_prod.csvi__appeal__appeals
в stpo.appeal__appeals.

Также создаются чаты в stpo.base__chat.

Маппинг:

    them_id
        -> по названию темы;
        -> если тема не найдена, используется
           "Моей темы нет в списке".

    status_code
        created  -> new
        accepted -> in_work
        closed   -> closed
        restored -> reaccepted

    chat_id
        -> appeal.id

    sender_id
        -> sender_id из старого обращения.

    worker_id
        -> accepted_by из старого обращения.

    base__chat.id
        -> appeal.id

    base__chat.created_at
        -> appeal.created_at

    base__chat.updated_at
        -> appeal.updated_at
"""

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

from pathlib import Path
import sys
from datetime import datetime

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

FALLBACK_THEM_NAME = "Моей темы нет в списке"


# ============================================================
# Соответствие source.status_code -> target.code
# ============================================================

STATUS_CODE_MAP = {
    "created": "new",
    "accepted": "in_work",
    "closed": "closed",
    "restored": "reaccepted",
}


# ============================================================
# Ручные переопределения названий тем
# ============================================================

THEM_NAME_OVERRIDES = {
    "Проблема с IP-телефоном":
        "Неполадки с IP-телефоном",
}


# ============================================================
# Лог
# ============================================================

def log(msg):
    print(
        f"[{datetime.now():%H:%M:%S}] {msg}"
    )


# ============================================================
# Даты
# ============================================================

def convert_datetime(value):
    """
    Приводит дату к datetime для MySQL.
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
                date_format,
            )

        except ValueError:
            continue

    raise ValueError(
        f"Не удалось преобразовать дату: {value}"
    )


# ============================================================
# Статусы
# ============================================================

def build_status_map(dst_cur):
    """
    source.status_code -> target.status_id
    """

    dst_cur.execute("""
        SELECT
            id,
            code
        FROM appeal__statuses
    """)

    dst_by_code = {
        row["code"]: row["id"]
        for row in dst_cur.fetchall()
    }

    result = {}

    for src_code, dst_code in STATUS_CODE_MAP.items():

        if dst_code not in dst_by_code:

            raise RuntimeError(
                f"В stpo.appeal__statuses "
                f"нет кода '{dst_code}'"
            )

        result[src_code] = dst_by_code[dst_code]

    return result


# ============================================================
# Темы
# ============================================================

def build_them_map(src_cur, dst_cur):
    """
    source.them_id -> target.them_id
    """

    # --------------------------------------------------------
    # Fallback-тема
    # --------------------------------------------------------

    dst_cur.execute(
        """
        SELECT id
        FROM appeal__thems
        WHERE name = %s
        """,
        (FALLBACK_THEM_NAME,),
    )

    fallback_row = dst_cur.fetchone()

    if not fallback_row:

        raise RuntimeError(
            f"В stpo.appeal__thems нет fallback-темы "
            f"'{FALLBACK_THEM_NAME}'"
        )

    fallback_id = fallback_row["id"]

    log(
        f"Fallback тема: "
        f"'{FALLBACK_THEM_NAME}' "
        f"(id={fallback_id})"
    )

    # --------------------------------------------------------
    # Темы новой БД
    # --------------------------------------------------------

    dst_cur.execute("""
        SELECT
            id,
            name
        FROM appeal__thems
    """)

    dst_by_name = {}

    for row in dst_cur.fetchall():

        name = (
            row["name"] or ""
        ).strip().lower()

        dst_by_name.setdefault(
            name,
            row["id"],
        )

    # --------------------------------------------------------
    # Темы старой БД
    # --------------------------------------------------------

    src_cur.execute("""
        SELECT
            id,
            name
        FROM csvi__appeal__them
    """)

    source_thems = src_cur.fetchall()

    result = {}

    for row in source_thems:

        src_id = row["id"]

        src_name = (
            row["name"] or ""
        ).strip()

        dst_name = THEM_NAME_OVERRIDES.get(
            src_name,
            src_name,
        )

        dst_id = dst_by_name.get(
            dst_name.strip().lower()
        )

        if dst_id is None:

            log(
                f"⚠ Тема '{src_name}' "
                f"(id={src_id}) не найдена "
                f"в stpo — "
                f"используется fallback "
                f"id={fallback_id}"
            )

            dst_id = fallback_id

        result[src_id] = dst_id

    return result


# ============================================================
# Миграция
# ============================================================

def migrate_appeals():

    src = None
    dst = None

    try:

        # ====================================================
        # CONNECTION
        # ====================================================

        src = get_source_connection()
        dst = get_target_connection()

        print(
            f"{CYAN}\n-MIGRATE_APPEALS{RESET}"
        )

        # ====================================================
        # Маппинг статусов
        # ====================================================

        with dst.cursor() as dst_cur:

            status_map = build_status_map(
                dst_cur
            )

        log(
            f"Маппинг статусов: "
            f"{status_map}"
        )

        # ====================================================
        # Маппинг тем
        # ====================================================

        with src.cursor() as src_cur, \
             dst.cursor() as dst_cur:

            them_map = build_them_map(
                src_cur,
                dst_cur,
            )

        log(
            "Маппинг тем "
            "(source_them_id -> target_them_id): "
            f"{them_map}"
        )

        # ====================================================
        # Получаем обращения
        # ====================================================

        with src.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    comment,
                    sender_id,
                    them_id,
                    status_code,
                    accepted_by,
                    created_at,
                    updated_at
                FROM csvi__appeal__appeals
                ORDER BY id
            """)

            appeals = cur.fetchall()

        log(
            f"Записей в источнике: "
            f"{len(appeals)}"
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
                    DELETE FROM appeal__appeals
                """)

                cur.execute("""
                    DELETE FROM base__chat
                """)

                cur.execute(
                    "SET FOREIGN_KEY_CHECKS = 1"
                )

            log(
                "Очищены "
                "appeal__appeals и base__chat"
            )

        # ====================================================
        # Создаём чаты
        #
        # base__chat.id = appeal.id
        # base__chat.created_at = appeal.created_at
        # base__chat.updated_at = appeal.updated_at
        # ====================================================

        chat_rows = [
            (
                appeal["id"],
                convert_datetime(
                    appeal["created_at"]
                ),
                convert_datetime(
                    appeal["updated_at"]
                ),
            )
            for appeal in appeals
        ]

        if chat_rows:

            with dst.cursor() as cur:

                cur.executemany(
                    """
                    INSERT INTO base__chat
                        (
                            id,
                            created_at,
                            updated_at
                        )
                    VALUES
                        (
                            %s,
                            %s,
                            %s
                        )
                    """,
                    chat_rows,
                )

        log(
            f"Создано чатов: "
            f"{len(chat_rows)} шт."
        )

        # ====================================================
        # Подготавливаем обращения
        # ====================================================

        rows = []

        skipped = 0

        for appeal in appeals:

            appeal_id = appeal["id"]

            # ------------------------------------------------
            # Статус
            # ------------------------------------------------

            status_id = status_map.get(
                appeal["status_code"]
            )

            if status_id is None:

                log(
                    f"⚠ Неизвестный статус "
                    f"'{appeal['status_code']}' "
                    f"у обращения "
                    f"id={appeal_id} — пропуск"
                )

                skipped += 1

                continue

            # ------------------------------------------------
            # Тема
            # ------------------------------------------------

            them_id = them_map.get(
                appeal["them_id"]
            )

            if them_id is None:

                log(
                    f"⚠ Тема не найдена "
                    f"для обращения "
                    f"id={appeal_id} "
                    f"| them_id={appeal['them_id']} "
                    f"— используется fallback"
                )

                # fallback id уже определён
                # через build_them_map.
                #
                # Получаем его напрямую.

                with dst.cursor() as cur:

                    cur.execute(
                        """
                        SELECT id
                        FROM appeal__thems
                        WHERE name = %s
                        """,
                        (FALLBACK_THEM_NAME,),
                    )

                    fallback_row = cur.fetchone()

                if not fallback_row:
                    raise RuntimeError(
                        f"Не найдена fallback-тема "
                        f"'{FALLBACK_THEM_NAME}'"
                    )

                them_id = fallback_row["id"]

            # ------------------------------------------------
            # Worker
            #
            # worker_id = accepted_by
            # ------------------------------------------------

            worker_id = appeal["accepted_by"]

            # ------------------------------------------------
            # Даты
            # ------------------------------------------------

            created_at = convert_datetime(
                appeal["created_at"]
            )

            updated_at = convert_datetime(
                appeal["updated_at"]
            )

            # ------------------------------------------------
            # Формируем строку
            # ------------------------------------------------

            rows.append((
                appeal_id,
                appeal["comment"] or "",
                appeal_id,
                appeal["sender_id"],
                worker_id,
                them_id,
                status_id,
                created_at,
                updated_at,
            ))

        # ====================================================
        # Статистика
        # ====================================================

        log(
            f"Пропущено обращений: "
            f"{skipped}"
        )

        # ====================================================
        # Вставка обращений
        # ====================================================

        sql = """
            INSERT INTO appeal__appeals
                (
                    id,
                    comment,
                    chat_id,
                    sender_id,
                    worker_id,
                    them_id,
                    status_id,
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

        if rows:

            with dst.cursor() as cur:

                cur.executemany(
                    sql,
                    rows,
                )

        log(
            f"Вставлено обращений: "
            f"{len(rows)} шт."
        )

        # ====================================================
        # AUTO_INCREMENT base__chat
        # ====================================================

        with dst.cursor() as cur:

            cur.execute("""
                SELECT MAX(id) AS m
                FROM base__chat
            """)

            max_chat_id = (
                cur.fetchone()["m"] or 0
            )

            cur.execute(
                f"""
                ALTER TABLE base__chat
                AUTO_INCREMENT = {max_chat_id + 1}
                """
            )

        # ====================================================
        # AUTO_INCREMENT appeal__appeals
        # ====================================================

        with dst.cursor() as cur:

            cur.execute("""
                SELECT MAX(id) AS m
                FROM appeal__appeals
            """)

            max_appeal_id = (
                cur.fetchone()["m"] or 0
            )

            cur.execute(
                f"""
                ALTER TABLE appeal__appeals
                AUTO_INCREMENT = {max_appeal_id + 1}
                """
            )

        # ====================================================
        # COMMIT
        # ====================================================

        dst.commit()

        log(
            "Чаты созданы: OK"
        )

        log(
            "Обращения перенесены: OK"
        )

        log(
            "✅ Успех"
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

        migrate_appeals()

    except Exception:

        sys.exit(1)