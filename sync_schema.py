"""Fixes the "column X does not exist" error without wiping your database.

Compares each model's expected columns against what's actually in Postgres/
SQLite, and runs ALTER TABLE ADD COLUMN for anything missing. Existing rows
and data are left untouched — new columns just come back NULL until you
fill them in (e.g. via Settings).

Run this instead of dropping tables whenever a model gains a new column:
    python sync_schema.py

Safe to re-run — it only adds columns that don't exist yet.
"""

from sqlalchemy import inspect, text

from app import create_app, db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    added_any = False

    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            # Whole table is missing — create_all handles new tables fine,
            # it's only new COLUMNS on existing tables that need this script.
            table.create(bind=db.engine)
            print(f"Created missing table: {table.name}")
            added_any = True
            continue

        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}

        for column in table.columns:
            if column.name in existing_columns:
                continue

            col_type = column.type.compile(dialect=db.engine.dialect)
            nullable = "" if column.nullable else " NOT NULL"
            default_clause = ""
            # Adding a NOT NULL column to a table with existing rows needs a
            # default, or Postgres will refuse. Our models don't currently
            # define server defaults, so fall back to nullable if needed.
            if not column.nullable and column.default is None:
                nullable = ""  # allow NULL instead of failing the ALTER

            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{nullable}{default_clause}'
            with db.engine.begin() as conn:
                conn.execute(text(ddl))
            print(f"Added column: {table.name}.{column.name} ({col_type})")
            added_any = True

    if not added_any:
        print("Schema already matches the models — nothing to do.")
    else:
        print("\nDone. Existing data was preserved.")
