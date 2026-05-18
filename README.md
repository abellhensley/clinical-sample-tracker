# Clinical Trial Sample Operations Tracker

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![SQL](https://img.shields.io/badge/SQL-SQLite-green)](https://sqlite.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

A SQL-backed data pipeline and operational dashboard simulating clinical trial sample and data tracking workflows in a Precision Medicine Operations context.

This project mirrors the kind of sample, kit, data, and logistics (SKDL) operations used by clinical operations teams at biopharmaceutical companies — tracking biomarker sample collection, shipment status, lab receipt, data completeness, and issue flags across multiple concurrent clinical studies.

---

## Project Structure

```
clinical-sample-tracker/
├── sql/
│   ├── schema.sql              # Database schema — studies, sites, samples, kits, data completeness
│   ├── seed_data.sql           # Realistic synthetic data for development/demo
│   ├── queries/
│   │   ├── sample_status.sql   # Sample collection vs expected by site
│   │   ├── data_completeness.sql # Data completeness rates by study
│   │   ├── overdue_shipments.sql # Flagged overdue sample shipments
│   │   └── issue_summary.sql   # Operational issue dashboard queries
├── src/
│   ├── db.py                   # Database connection and query utilities
│   ├── pipeline.py             # Automated data quality check pipeline
│   └── generate_data.py        # Synthetic data generator for demo
├── dashboard/
│   └── app.py                  # Streamlit operational dashboard
├── data/
│   └── sample_tracker.db       # SQLite database (auto-generated)
├── docs/
│   └── schema_diagram.md       # Entity-relationship diagram (text)
├── requirements.txt
└── README.md
```

---

## Quickstart

### 1. Clone and install
```bash
git clone https://github.com/abellhensley/clinical-sample-tracker.git
cd clinical-sample-tracker
pip install -r requirements.txt
```

### 2. Initialize the database
```bash
python src/db.py --init
```

### 3. Generate synthetic data
```bash
python src/generate_data.py --studies 5 --sites 20 --subjects 125
```

### 4. Run data quality pipeline
```bash
python src/pipeline.py
```

### 5. Launch dashboard
```bash
streamlit run dashboard/app.py
```

---

## Database Schema

### Core Tables
- **studies** — Clinical study metadata (protocol, phase, status, timeline)
- **sites** — Investigator sites per study (country, enrollment target, status)
- **subjects** — Enrolled subjects per site
- **samples** — Individual biomarker samples (type, collection date, status)
- **kits** — Sample collection kits (assignment, shipment, receipt tracking)
- **lab_results** — Lab data receipt and completeness status
- **issues** — Flagged sample/data issues and resolution tracking

### Key Relationships
- Studies → Sites (one-to-many)
- Sites → Subjects (one-to-many)
- Subjects → Samples (one-to-many)
- Samples → Lab Results (one-to-one)
- Kits → Samples (one-to-one)

---

## Author

Austin Bell-Hensley, PhD  
[LinkedIn](https://www.linkedin.com/in/austinbellhensley) · [Google Scholar]([https://scholar.google.com/citations?hl=en&user=fgtNXpgAAAAJ])
