from sqlalchemy import text

from ..connect import source, target


def migrate_table(table):
    print(f"\nПеренос: {table}")

    with source.connect() as src:
        with target.begin() as dst:

            # Получаем колонки источника
            source_columns = [
                row[0]
                for row in src.execute(
                    text("""
                        SELECT COLUMN_NAME
                        FROM information_schema.columns
                        WHERE table_schema = 'STPO_prod'
                          AND table_name = :table
                        ORDER BY ORDINAL_POSITION
                    """),
                    {"table": table},
                )
            ]

            # Получаем колонки назначения
            target_columns = [
                row[0]
                for row in dst.execute(
                    text("""
                        SELECT COLUMN_NAME
                        FROM information_schema.columns
                        WHERE table_schema = 'stpo'
                          AND table_name = :table
                        ORDER BY ORDINAL_POSITION
                    """),
                    {"table": table},
                )
            ]

            # Берём только общие колонки
            columns = [
                column
                for column in source_columns
                if column in target_columns
            ]

            if not columns:
                raise RuntimeError(
                    f"Нет общих колонок у таблицы {table}"
                )

            column_sql = ", ".join(
                f"`{column}`"
                for column in columns
            )

            print(f"Колонки: {len(columns)}")
            print(", ".join(columns))

            # Очищаем таблицу назначения
            dst.execute(
                text(f"TRUNCATE TABLE `stpo`.`{table}`")
            )

            # Переносим данные
            result = dst.execute(
                text(f"""
                    INSERT INTO `stpo`.`{table}` ({column_sql})
                    SELECT {column_sql}
                    FROM `STPO_prod`.`{table}`
                """)
            )

            print(f"✓ Перенесено строк: {result.rowcount}")
