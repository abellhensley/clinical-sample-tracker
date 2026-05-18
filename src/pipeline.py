"""
src/pipeline.py
Automated daily data quality check pipeline.
Runs checks, flags issues, and outputs a summary report.
Usage: python src/pipeline.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from datetime import date
from src.db import (
    get_portfolio_summary, get_flagged_sites, get_overdue_shipments,
    get_data_completeness, get_open_issues, get_db_stats, query_df
)

REPORT_DIR = Path(__file__).parent.parent / "results"
REPORT_DIR.mkdir(exist_ok=True)


def check_collection_rates(threshold: float = 80.0) -> dict:
    """Flag sites below collection rate threshold."""
    flagged = get_flagged_sites(threshold)
    return {
        "check": "Collection Rate",
        "status": "WARNING" if len(flagged) > 0 else "PASS",
        "flagged_count": len(flagged),
        "detail": flagged[["protocol_number", "site_name", "country", "collection_rate_pct"]].to_dict("records")
    }


def check_overdue_shipments() -> dict:
    """Flag shipments overdue for receipt."""
    overdue = get_overdue_shipments()
    critical = overdue[overdue["days_in_transit"] > 7] if len(overdue) > 0 else overdue
    return {
        "check": "Overdue Shipments",
        "status": "CRITICAL" if len(critical) > 0 else ("WARNING" if len(overdue) > 0 else "PASS"),
        "flagged_count": len(overdue),
        "critical_count": len(critical),
        "detail": overdue[["protocol_number", "site_name", "lab_name", "days_in_transit"]].head(10).to_dict("records") if len(overdue) > 0 else []
    }


def check_data_completeness(threshold: float = 85.0) -> dict:
    """Flag studies with low data completeness."""
    completeness = get_data_completeness()
    flagged = completeness[completeness["completeness_pct"] < threshold] if len(completeness) > 0 else completeness
    return {
        "check": "Data Completeness",
        "status": "WARNING" if len(flagged) > 0 else "PASS",
        "flagged_count": len(flagged),
        "detail": flagged[["protocol_number", "lab_name", "completeness_pct", "results_missing"]].to_dict("records") if len(flagged) > 0 else []
    }


def check_open_issues() -> dict:
    """Flag critical and high severity open issues."""
    issues = get_open_issues()
    if len(issues) == 0:
        return {"check": "Open Issues", "status": "PASS", "flagged_count": 0, "detail": []}

    critical = issues[issues["severity"] == "Critical"]
    high = issues[issues["severity"] == "High"]
    return {
        "check": "Open Issues",
        "status": "CRITICAL" if len(critical) > 0 else ("WARNING" if len(high) > 0 else "PASS"),
        "critical_count": len(critical),
        "high_count": len(high),
        "flagged_count": len(critical) + len(high),
        "detail": issues[issues["severity"].isin(["Critical", "High"])].head(10).to_dict("records")
    }


def check_quality_failures() -> dict:
    """Flag elevated sample quality failure rates."""
    df = query_df("""
        SELECT
            study_id,
            COUNT(*) AS collected,
            SUM(CASE WHEN quality_flag = 'Fail' THEN 1 ELSE 0 END) AS fails,
            ROUND(100.0 * SUM(CASE WHEN quality_flag = 'Fail' THEN 1 ELSE 0 END) / COUNT(*), 1) AS fail_rate_pct
        FROM samples
        WHERE collection_status = 'Collected'
        GROUP BY study_id
        HAVING fail_rate_pct > 10
        ORDER BY fail_rate_pct DESC
    """)
    return {
        "check": "Sample Quality Failures",
        "status": "WARNING" if len(df) > 0 else "PASS",
        "flagged_count": len(df),
        "detail": df.to_dict("records")
    }


def run_pipeline() -> list:
    """Run all data quality checks and return results."""
    print(f"\n{'='*60}")
    print(f"Clinical Sample Tracker — Data Quality Pipeline")
    print(f"Run date: {date.today().isoformat()}")
    print(f"{'='*60}\n")

    checks = [
        check_collection_rates(),
        check_overdue_shipments(),
        check_data_completeness(),
        check_open_issues(),
        check_quality_failures(),
    ]

    status_icons = {"PASS": "✓", "WARNING": "⚠", "CRITICAL": "✗"}

    for check in checks:
        icon = status_icons.get(check["status"], "?")
        print(f"  {icon} {check['check']}: {check['status']} ({check['flagged_count']} flagged)")

    n_critical = sum(1 for c in checks if c["status"] == "CRITICAL")
    n_warning = sum(1 for c in checks if c["status"] == "WARNING")
    n_pass = sum(1 for c in checks if c["status"] == "PASS")

    print(f"\nSummary: {n_pass} PASS | {n_warning} WARNING | {n_critical} CRITICAL")

    # Write report
    report_path = REPORT_DIR / f"pipeline_report_{date.today().isoformat()}.txt"
    with open(report_path, "w") as f:
        f.write(f"Clinical Sample Tracker Pipeline Report\n")
        f.write(f"Date: {date.today().isoformat()}\n\n")
        for check in checks:
            f.write(f"{check['check']}: {check['status']}\n")
            if check.get("detail"):
                for item in check["detail"][:5]:
                    f.write(f"  {item}\n")
            f.write("\n")
    print(f"\nReport saved: {report_path}")
    return checks


if __name__ == "__main__":
    run_pipeline()
