"""TimeTrack's PostgreSQL persistence layer."""
import os

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


PGHOST = "a712wc.h.filess.io"
PGPORT = "61008"
PGDATABASE = "time_tracking_db_fellitgift"
PGUSER = "time_tracking_db_fellitgift"
PGSCHEMA = os.getenv("PGSCHEMA") or "public"
TIME_ENTRIES = sql.Identifier(PGSCHEMA, "time_entries")


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        conn = psycopg2.connect(database_url)
    else:
        conn = psycopg2.connect(
            dbname=PGDATABASE,
            user=PGUSER,
            password=os.environ["PGPASSWORD"],
            host=PGHOST,
            port=PGPORT,
        )
    cursor = conn.cursor()
    cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {};").format(sql.Identifier(PGSCHEMA)))
    cursor.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(PGSCHEMA)))
    cursor.close()
    conn.commit()
    return conn


def _cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)


def init_db():
    conn = get_connection()
    cursor = _cursor(conn)
    cursor.execute(sql.SQL("""
        CREATE TABLE IF NOT EXISTS {} (
            id SERIAL PRIMARY KEY,
            employee_name TEXT NOT NULL,
            project TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            hours REAL NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        )
    """).format(TIME_ENTRIES))
    cursor.execute(sql.SQL("SELECT COUNT(*) AS count FROM {}").format(TIME_ENTRIES))
    count = cursor.fetchone()["count"]
    if count == 0:
        seed = [
            ("Asha Patel", "Website Redesign", "2026-09-08", 6.5, "Homepage layout"),
            ("Asha Patel", "Website Redesign", "2026-09-09", 7.0, "Mobile responsive fixes"),
            ("Asha Patel", "Client Onboarding", "2026-09-10", 3.0, "Kickoff call + notes"),
            ("Rahul Mehta", "Website Redesign", "2026-09-08", 5.5, "API integration"),
            ("Rahul Mehta", "Internal Tools", "2026-09-09", 8.0, "Dashboard bug fixes"),
        ]
        cursor.executemany(
            sql.SQL("INSERT INTO {} (employee_name, project, entry_date, hours, description) "
            "VALUES (%s, %s, %s, %s, %s)").format(TIME_ENTRIES),
            seed,
        )
        conn.commit()
    conn.close()


def _row_to_dict(row) -> dict:
    return dict(row)


def list_all_entries() -> list[dict]:
    conn = get_connection()
    cursor = _cursor(conn)
    cursor.execute(sql.SQL("SELECT * FROM {} ORDER BY entry_date DESC, id DESC").format(TIME_ENTRIES))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def log_time(employee_name: str, project: str, entry_date: str, hours: float, description: str = "") -> dict:
    if hours <= 0:
        raise ValueError("hours must be a positive number")
    conn = get_connection()
    cursor = _cursor(conn)
    cursor.execute(sql.SQL(
        "INSERT INTO {} (employee_name, project, entry_date, hours, description) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING *"
    ).format(TIME_ENTRIES),
        (employee_name, project, entry_date, hours, description),
    )
    conn.commit()
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("The new time entry could not be created")
    conn.close()
    return _row_to_dict(row)


def get_timesheet(employee_name: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    conn = get_connection()
    cursor = _cursor(conn)
    query = sql.SQL("SELECT * FROM {} WHERE employee_name = %s").format(TIME_ENTRIES)
    params: list = [employee_name]
    if start_date:
        query += sql.SQL(" AND entry_date >= %s")
        params.append(start_date)
    if end_date:
        query += sql.SQL(" AND entry_date <= %s")
        params.append(end_date)
    query += sql.SQL(" ORDER BY entry_date")
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def execute_query(query: str, params: list = []) -> list[dict]:
    conn = get_connection()
    cursor = _cursor(conn)
    cursor.execute(query.replace("?", "%s"), params)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def list_projects() -> list[str]:
    conn = get_connection()
    cursor = _cursor(conn)
    cursor.execute(sql.SQL("SELECT DISTINCT project FROM {} ORDER BY project").format(TIME_ENTRIES))
    rows = cursor.fetchall()
    conn.close()
    return [r["project"] for r in rows]


def get_project_summary(project: str) -> dict:
    conn = get_connection()
    cursor = _cursor(conn)
    cursor.execute(sql.SQL(
        "SELECT employee_name, SUM(hours) as total_hours FROM {} "
        "WHERE project = %s GROUP BY employee_name ORDER BY employee_name"
    ).format(TIME_ENTRIES),
        (project,),
    )
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        raise ValueError(f"No time logged against project '{project}'")
    by_employee = {r["employee_name"]: r["total_hours"] for r in rows}
    return {
        "project": project,
        "total_hours": sum(by_employee.values()),
        "by_employee": by_employee,
    }
