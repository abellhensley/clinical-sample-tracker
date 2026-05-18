"""
src/generate_data.py
Generates realistic synthetic clinical trial sample tracking data.
Usage: python src/generate_data.py --studies 5 --sites 20 --subjects 125
"""

import sys
from pathlib import Path
import argparse
import random
import uuid
from datetime import date, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import init_db, executemany, get_db_stats

random.seed(42)

# ── Reference data ─────────────────────────────────────────────────────────────
THERAPEUTIC_AREAS = ["Oncology", "Neurology", "Cardiovascular", "Rare Disease", "Immunology"]
PHASES = ["Phase 1", "Phase 2", "Phase 3"]
STUDY_STATUSES = ["Enrolling", "Enrolled", "Completed"]
COUNTRIES = ["United States", "United Kingdom", "Germany", "France", "Canada", "Japan", "Australia"]
VISIT_NAMES = ["Screening", "Baseline", "Week 4", "Week 8", "Week 12", "Week 24", "Week 52", "End of Study"]
LAB_NAMES = ["Covance Central Lab", "Q2 Solutions", "ICON Central Labs", "Pacific Biomarker Labs"]
LAB_TYPES = ["Central", "Specialty", "Biomarker"]
ISSUE_CATEGORIES = [
    "Sample Quality", "Shipment Delay", "Temperature Excursion",
    "Missing Data", "Kit Issue", "Collection Deviation", "Lab Query", "Documentation"
]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
SEVERITY_WEIGHTS = [0.4, 0.35, 0.18, 0.07]

SAMPLE_TYPES = [
    ("ST001", "K2-EDTA Whole Blood", "K2-EDTA tube", 6.0, -80, 365),
    ("ST002", "Serum", "SST tube", 3.0, -80, 730),
    ("ST003", "PAXgene RNA", "PAXgene tube", 2.5, -80, 365),
    ("ST004", "PBMC", "CPT tube", 8.0, -80, 730),
    ("ST005", "Urine", "Urine cup", 10.0, -20, 180),
    ("ST006", "Plasma", "K2-EDTA tube", 3.0, -80, 365),
]

def rand_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))

def uid() -> str:
    return str(uuid.uuid4())[:8].upper()


def generate_all(n_studies: int, n_sites_per_study: int, n_subjects: int):
    print("Initializing database...")
    init_db()

    # Sample types
    executemany(
        "INSERT OR IGNORE INTO sample_types VALUES (?,?,?,?,?,?)",
        SAMPLE_TYPES
    )

    study_start = date(2022, 1, 1)
    study_end = date(2025, 12, 31)

    study_ids, site_ids, subject_ids = [], [], []

    # Studies
    studies = []
    for i in range(n_studies):
        sid = f"STUDY-{i+1:03d}"
        study_ids.append(sid)
        start = rand_date(study_start, date(2024, 1, 1))
        studies.append((
            sid,
            f"PROT-{1000+i}",
            f"{random.choice(THERAPEUTIC_AREAS)} Study {i+1}",
            random.choice(PHASES),
            random.choice(THERAPEUTIC_AREAS),
            random.choice(STUDY_STATUSES),
            random.randint(50, 500),
            start.isoformat(),
            (start + timedelta(days=random.randint(365, 1095))).isoformat(),
        ))
    executemany(
        "INSERT OR IGNORE INTO studies VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        studies
    )
    print(f"  Inserted {len(studies)} studies")

    # Sites
    sites = []
    for sid in study_ids:
        n_sites = random.randint(3, max(3, n_sites_per_study))
        for j in range(n_sites):
            site_id = f"{sid}-SITE-{j+1:02d}"
            site_ids.append((sid, site_id))
            enroll_target = random.randint(5, 30)
            country = random.choice(COUNTRIES)
            sites.append((
                site_id, sid,
                f"Site {j+1} - {country}",
                f"Dr. {random.choice(['Smith','Jones','Chen','Patel','Kim','Mueller'])}",
                country,
                random.choice(["Active", "Active", "Active", "On Hold", "Closed"]),
                enroll_target,
                random.randint(0, enroll_target),
                rand_date(date(2022, 1, 1), date(2023, 6, 1)).isoformat(),
            ))
    executemany(
        "INSERT OR IGNORE INTO sites VALUES (?,?,?,?,?,?,?,?,?)",
        sites
    )
    print(f"  Inserted {len(sites)} sites")

    # Subjects
    subjects = []
    for study_id, site_id in site_ids:
        n_subjects = random.randint(1, 10)
        for _ in range(n_subjects):
            subj_id = f"SUBJ-{uid()}"
            subject_ids.append((study_id, site_id, subj_id))
            subjects.append((
                subj_id, site_id, study_id,
                rand_date(date(2022, 6, 1), date(2024, 12, 1)).isoformat(),
                random.choice(["Enrolled", "Enrolled", "Enrolled", "Completed", "Withdrawn"]),
            ))
    executemany(
        "INSERT OR IGNORE INTO subjects VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
        subjects
    )
    print(f"  Inserted {len(subjects)} subjects")

    # Kits and Samples (one kit per sample)
    kits = []
    samples = []
    kit_status_map = {
        "Collected": "Used",
        "Missed":    "Received at Site",
        "Planned":   "In Use",
        "Deviated":  "Used",
    }
    # Guarantee at least one subject per study, then fill remaining slots randomly
    from collections import defaultdict
    study_subject_map = defaultdict(list)
    for entry in subject_ids:
        study_subject_map[entry[0]].append(entry)
    guaranteed = [random.choice(subjs) for subjs in study_subject_map.values()]
    guaranteed_set = set(guaranteed)
    remaining = [s for s in subject_ids if s not in guaranteed_set]
    extra = random.sample(remaining, min(len(remaining), max(0, n_subjects - len(guaranteed))))
    selected_subjects = guaranteed + extra

    for study_id, site_id, subj_id in selected_subjects:
        for visit in random.sample(VISIT_NAMES, random.randint(2, 5)):
            for st_id, *_ in random.sample(SAMPLE_TYPES, random.randint(1, 3)):
                coll_date = rand_date(date(2022, 6, 1), date(2025, 6, 1))
                status_roll = random.random()
                if status_roll < 0.78:
                    status = "Collected"
                elif status_roll < 0.90:
                    status = "Missed"
                elif status_roll < 0.96:
                    status = "Planned"
                else:
                    status = "Deviated"

                quality = None
                if status == "Collected":
                    quality = random.choices(["Pass", "Fail", "Pending"], weights=[0.85, 0.08, 0.07])[0]

                kit_id = f"KIT-{uid()}"
                kit_type = next(name for sid, name, *_ in SAMPLE_TYPES if sid == st_id)
                ship_date = rand_date(date(2022, 1, 1), coll_date)
                kits.append((
                    kit_id, study_id, site_id, kit_type,
                    kit_status_map[status],
                    ship_date.isoformat(),
                    (ship_date + timedelta(days=random.randint(3, 10))).isoformat(),
                    (coll_date + timedelta(days=random.randint(180, 365))).isoformat(),
                    f"LOT-{uid()}",
                ))
                samples.append((
                    f"SMP-{uid()}", subj_id, study_id, site_id, kit_id, st_id,
                    visit, f"T{random.randint(0, 52)}",
                    coll_date.isoformat() if status == "Collected" else None,
                    status,
                    round(random.uniform(1.0, 8.0), 1) if status == "Collected" else None,
                    quality, None,
                ))
    executemany(
        "INSERT OR IGNORE INTO kits VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        kits
    )
    print(f"  Inserted {len(kits)} kits")
    executemany(
        "INSERT OR IGNORE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        samples
    )
    print(f"  Inserted {len(samples)} samples")

    # Shipments
    shipments = []
    today = date.today()
    for study_id, site_id in random.sample(site_ids, min(len(site_ids), 50)):
        for _ in range(random.randint(1, 4)):
            status_roll = random.random()
            if status_roll < 0.75:
                status = "Received"
                ship_date = rand_date(date(2022, 6, 1), date(2025, 3, 1))
                actual = (ship_date + timedelta(days=random.randint(1, 5))).isoformat()
            elif status_roll < 0.85:
                status = "In Transit"
                ship_date = today - timedelta(days=random.randint(4, 7))
                actual = None
            elif status_roll < 0.92:
                status = "Overdue"
                ship_date = today - timedelta(days=random.randint(8, 21))
                actual = None
            else:
                status = "Damaged"
                ship_date = rand_date(date(2022, 6, 1), date(2025, 3, 1))
                actual = None
            expected = ship_date + timedelta(days=random.randint(1, 4))
            shipments.append((
                f"SHIP-{uid()}", study_id, site_id,
                random.choice(LAB_NAMES), random.choice(LAB_TYPES),
                ship_date.isoformat(), expected.isoformat(), actual,
                status,
                random.choices([0, 1], weights=[0.92, 0.08])[0],
                f"1Z{uid()}", random.randint(2, 20),
            ))
    executemany(
        "INSERT OR IGNORE INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        shipments
    )
    print(f"  Inserted {len(shipments)} shipments")

    # Lab results
    results = []
    collected = [s for s in samples if s[9] == "Collected"]
    for smp in collected:
        smp_id = smp[0]
        result_date = rand_date(date(2022, 7, 1), date(2025, 6, 1))
        status = random.choices(
            ["Received", "Locked", "Queryable", "Missing", "Pending"],
            weights=[0.45, 0.30, 0.12, 0.08, 0.05]
        )[0]
        is_complete = 1 if status in ("Locked", "Received") else 0
        results.append((
            f"RES-{uid()}", smp_id, None,
            random.choice(LAB_NAMES),
            random.choice(["RNA-seq", "Proteomics", "Metabolomics", "CBC", "CMP", "Biomarker Panel"]),
            status,
            result_date.isoformat() if status != "Pending" else None,
            (result_date - timedelta(days=random.randint(0, 14))).isoformat(),
            is_complete,
            random.choices([0, 1, 2, 3], weights=[0.7, 0.18, 0.08, 0.04])[0],
        ))
    executemany(
        "INSERT OR IGNORE INTO lab_results VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        results
    )
    print(f"  Inserted {len(results)} lab results")

    # Issues — draw only from sites that have samples so they appear in risk ranking
    sampled_site_ids = list({(s[2], s[3]) for s in samples})  # (study_id, site_id)
    issues = []
    for _ in range(random.randint(30, 80)):
        study_id, site_id = random.choice(sampled_site_ids)
        open_date = rand_date(date(2022, 6, 1), date(2025, 3, 1))
        status = random.choices(
            ["Open", "In Progress", "Resolved", "Closed"],
            weights=[0.25, 0.20, 0.30, 0.25]
        )[0]
        resolved = None
        if status in ("Resolved", "Closed"):
            resolved = (open_date + timedelta(days=random.randint(1, 60))).isoformat()
        issues.append((
            f"ISS-{uid()}", study_id, site_id, None, None,
            random.choice(ISSUE_CATEGORIES),
            random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0],
            "Auto-generated issue for demonstration",
            status,
            open_date.isoformat(), resolved,
            "Clinical Operations", None,
        ))
    executemany(
        "INSERT OR IGNORE INTO issues VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        issues
    )
    print(f"  Inserted {len(issues)} issues")

    stats = get_db_stats()
    print("\nFinal database counts:")
    for table, count in stats.items():
        print(f"  {table}: {count:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic clinical sample tracking data")
    parser.add_argument("--studies", type=int, default=5)
    parser.add_argument("--sites", type=int, default=4)
    parser.add_argument("--subjects", type=int, default=125)
    args = parser.parse_args()
    generate_all(args.studies, args.sites, args.subjects)
