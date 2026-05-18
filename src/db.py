"""
src/db.py
Database connection, initialization, and query utilities.
Usage: python src/db.py --init
"""

import sqlite3
import pandas as pd
import argparse
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sample_tracker.db"
SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory for dict-like access."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database from schema.sql."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")
    schema = SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.executescript(schema)
    print(f"Database initialized at: {DB_PATH}")


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a SQL query and return results as a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute(sql: str, params: tuple = ()):
    """Execute a non-SELECT statement."""
    with get_connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def executemany(sql: str, data: list):
    """Execute a statement for multiple rows."""
    with get_connection() as conn:
        conn.executemany(sql, data)
        conn.commit()


# ── Operational query functions ───────────────────────────────────────────────

def get_portfolio_summary() -> pd.DataFrame:
    """High-level sample collection summary across all studies."""
    return query_df("""
        SELECT
            study_id,
            protocol_number,
            SUM(total_planned)  AS total_planned,
            SUM(collected)      AS collected,
            SUM(missed)         AS missed,
            SUM(deviated)       AS deviated,
            ROUND(100.0 * SUM(collected) / NULLIF(SUM(total_planned), 0), 1) AS collection_rate_pct
        FROM vw_sample_collection_rate
        GROUP BY study_id, protocol_number
        ORDER BY collection_rate_pct ASC
    """)


def get_flagged_sites(threshold: float = 80.0) -> pd.DataFrame:
    """Sites below collection rate threshold."""
    return query_df("""
        SELECT *
        FROM vw_sample_collection_rate
        WHERE collection_rate_pct < ?
        ORDER BY collection_rate_pct ASC
    """, (threshold,))


def get_overdue_shipments() -> pd.DataFrame:
    """All currently overdue shipments."""
    return query_df("SELECT * FROM vw_overdue_shipments")


def get_data_completeness() -> pd.DataFrame:
    """Data completeness rates by study and lab."""
    return query_df("SELECT * FROM vw_data_completeness ORDER BY completeness_pct ASC")


def get_open_issues() -> pd.DataFrame:
    """Open issues grouped by study, category, and severity."""
    return query_df("SELECT * FROM vw_open_issues")


def get_site_risk_ranking() -> pd.DataFrame:
    """Composite site risk score combining collection rate and open issues."""
    return query_df("""
        SELECT
            cr.study_id,
            cr.protocol_number,
            cr.site_id,
            cr.site_name,
            cr.country,
            cr.collection_rate_pct,
            COALESCE(oi.critical_issues, 0) AS critical_issues,
            COALESCE(oi.high_issues, 0) AS high_issues,
            ROUND(
                (100 - cr.collection_rate_pct) +
                (COALESCE(oi.critical_issues, 0) * 10) +
                (COALESCE(oi.high_issues, 0) * 5), 1
            ) AS risk_score
        FROM vw_sample_collection_rate cr
        LEFT JOIN (
            SELECT
                site_id,
                SUM(CASE WHEN severity = 'Critical' THEN issue_count ELSE 0 END) AS critical_issues,
                SUM(CASE WHEN severity = 'High' THEN issue_count ELSE 0 END) AS high_issues
            FROM vw_open_issues
            GROUP BY site_id
        ) oi ON cr.site_id = oi.site_id
        ORDER BY risk_score DESC
    """)


def get_recent_samples(days: int = 7) -> pd.DataFrame:
    """Samples collected in the last N days."""
    return query_df("""
        SELECT s.sample_id, s.study_id, s.site_id, si.site_name,
               s.visit, s.collection_date, s.quality_flag
        FROM samples s
        JOIN sites si ON s.site_id = si.site_id
        WHERE s.collection_status = 'Collected'
        AND s.collection_date >= date('now', ?)
        ORDER BY s.collection_date DESC
    """, (f"-{days} days",))


def get_db_stats() -> dict:
    """Quick count of all major tables."""
    tables = ["studies", "sites", "subjects", "samples", "kits", "shipments", "lab_results", "issues"]
    stats = {}
    with get_connection() as conn:
        for table in tables:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            stats[table] = result[0]
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database utilities")
    parser.add_argument("--init", action="store_true", help="Initialize database from schema")
    parser.add_argument("--stats", action="store_true", help="Print table counts")
    args = parser.parse_args()

    if args.init:
        init_db()
    if args.stats:
        stats = get_db_stats()
        print("\nDatabase row counts:")
        for table, count in stats.items():
            print(f"  {table}: {count:,}")
