"""
dashboard/app.py
Streamlit operational dashboard for Clinical Sample Tracker.
Run with: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Clinical Sample Ops Tracker",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size:1.9rem; font-weight:bold; color:#1F3864; margin-bottom:0; }
    .sub-header  { color:#595959; font-size:0.9rem; margin-bottom:1.2rem; }
    .kpi-card    { background:#f8f9fc; border-radius:8px; padding:14px 18px;
                   border-left:4px solid #1F3864; }
    .kpi-value   { font-size:2rem; font-weight:bold; color:#1F3864; }
    .kpi-label   { color:#595959; font-size:0.82rem; }
    .warn        { border-left-color:#E07B00 !important; }
    .warn .kpi-value { color:#E07B00 !important; }
    .crit        { border-left-color:#C0392B !important; }
    .crit .kpi-value { color:#C0392B !important; }
</style>
""", unsafe_allow_html=True)


# ── Try to load real DB; fall back to demo data ────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    try:
        from src.db import (
            get_portfolio_summary, get_flagged_sites, get_overdue_shipments,
            get_data_completeness, get_open_issues, get_site_risk_ranking,
            get_recent_samples
        )
        return {
            "portfolio":    get_portfolio_summary(),
            "flagged":      get_flagged_sites(),
            "overdue":      get_overdue_shipments(),
            "completeness": get_data_completeness(),
            "issues":       get_open_issues(),
            "risk":         get_site_risk_ranking(),
            "recent":       get_recent_samples(),
            "source":       "live"
        }
    except Exception as e:
        import traceback
        st.sidebar.error(f"DB Error: {e}")
        st.sidebar.code(traceback.format_exc())
        return _demo_data()


def _demo_data() -> dict:
    """Demo data shown before database is initialized."""
    import numpy as np
    rng = np.random.default_rng(42)

    studies = [f"STUDY-{i:03d}" for i in range(1, 6)]
    protos  = [f"PROT-{1000+i}" for i in range(5)]

    portfolio = pd.DataFrame({
        "study_id": studies, "protocol_number": protos,
        "total_planned": rng.integers(100, 400, 5),
        "collected":     rng.integers(60, 350, 5),
        "missed":        rng.integers(0, 30, 5),
        "collection_rate_pct": rng.uniform(62, 98, 5).round(1)
    })

    flagged = portfolio[portfolio["collection_rate_pct"] < 80].copy()

    overdue = pd.DataFrame({
        "shipment_id":    [f"SHIP-{i:04d}" for i in range(8)],
        "protocol_number": rng.choice(protos, 8),
        "site_name":      [f"Site {i}" for i in range(8)],
        "lab_name":       rng.choice(["Covance", "Q2 Solutions", "ICON Labs"], 8),
        "days_in_transit": rng.integers(4, 21, 8),
        "sample_count":   rng.integers(2, 15, 8),
    })

    completeness = pd.DataFrame({
        "study_id": studies, "protocol_number": protos,
        "lab_name": rng.choice(["Covance", "Q2 Solutions", "Pacific Biomarker"], 5),
        "total_results_expected": rng.integers(80, 300, 5),
        "results_complete":       rng.integers(50, 280, 5),
        "results_missing":        rng.integers(0, 40, 5),
        "completeness_pct":       rng.uniform(68, 98, 5).round(1),
        "total_queries":          rng.integers(0, 20, 5),
    })

    issues = pd.DataFrame({
        "study_id": rng.choice(studies, 12),
        "protocol_number": rng.choice(protos, 12),
        "category": rng.choice(["Sample Quality","Shipment Delay","Missing Data","Lab Query"], 12),
        "severity": rng.choice(["Low","Medium","High","Critical"], 12, p=[0.4,0.35,0.18,0.07]),
        "issue_count": rng.integers(1, 5, 12),
        "avg_age_days": rng.uniform(1, 45, 12).round(1),
        "max_age_days": rng.uniform(5, 90, 12).round(0),
    })

    risk = pd.DataFrame({
        "protocol_number": rng.choice(protos, 15),
        "site_id": [f"SITE-{i:02d}" for i in range(15)],
        "site_name": [f"Site {i}" for i in range(15)],
        "country": rng.choice(["USA","UK","Germany","France","Canada"], 15),
        "collection_rate_pct": rng.uniform(55, 99, 15).round(1),
        "critical_issues": rng.integers(0, 3, 15),
        "high_issues": rng.integers(0, 5, 15),
        "risk_score": rng.uniform(1, 65, 15).round(1),
    })

    return {
        "portfolio": portfolio, "flagged": flagged, "overdue": overdue,
        "completeness": completeness, "issues": issues, "risk": risk,
        "recent": pd.DataFrame(), "source": "demo"
    }


data = load_data()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Sample Ops Tracker")
    if data["source"] == "demo":
        st.warning("Demo data — run `python src/generate_data.py` to load real data")
    else:
        st.success("Live database connected")
    st.divider()

    page = st.radio("Navigate", [
        "Portfolio Overview",
        "Sample Collection",
        "Shipment Tracking",
        "Data Completeness",
        "Issues & Risk",
    ])

    st.divider()
    collection_threshold = st.slider("Collection rate alert threshold (%)", 50, 95, 80)
    transit_threshold = st.slider("Shipment critical threshold (days)", 3, 21, 7)
    completeness_threshold = st.slider("Data completeness target (%)", 50, 100, 85)


# ── Pages ──────────────────────────────────────────────────────────────────────

if page == "Portfolio Overview":
    st.markdown('<div class="main-header">Clinical Sample Operations</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Precision Medicine Operations — Portfolio Dashboard</div>', unsafe_allow_html=True)

    port = data["portfolio"]
    n_studies   = len(port)
    total_smp   = int(port["total_planned"].sum()) if len(port) > 0 else 0
    total_coll  = int(port["collected"].sum())     if len(port) > 0 else 0
    avg_rate    = port["collection_rate_pct"].mean() if len(port) > 0 else 0
    n_overdue   = len(data["overdue"])
    n_flagged   = len(data["flagged"])

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, str(n_studies), "Active Studies", ""),
        (c2, f"{total_coll:,}", "Samples Collected", ""),
        (c3, f"{avg_rate:.1f}%", "Avg Collection Rate", "warn" if avg_rate < 85 else ""),
        (c4, str(n_overdue), "Overdue Shipments", "crit" if n_overdue > 0 else ""),
        (c5, str(n_flagged), "Sites Below Threshold", "warn" if n_flagged > 0 else ""),
    ]
    for col, value, label, cls in kpis:
        with col:
            st.markdown(f"""<div class="kpi-card {cls}">
                <div class="kpi-value">{value}</div>
                <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()
    if len(port) > 0:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(port, x="protocol_number", y="collection_rate_pct",
                         color="collection_rate_pct",
                         color_continuous_scale=["#C0392B","#E07B00","#27AE60"],
                         range_color=[50, 100],
                         category_orders={"protocol_number": sorted(port["protocol_number"].unique())},
                         title="Collection Rate by Study",
                         labels={"collection_rate_pct": "Collection Rate (%)",
                                 "protocol_number": "Study"})
            fig.add_hline(y=collection_threshold, line_dash="dash",
                          line_color="gray", annotation_text=f"Threshold ({collection_threshold}%)")
            fig.update_layout(template="plotly_white", height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.pie(port, values="collected", names="protocol_number",
                         title="Sample Distribution by Study",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(template="plotly_white", height=350)
            st.plotly_chart(fig, use_container_width=True)


elif page == "Sample Collection":
    st.header("Sample Collection Status")
    port = data["portfolio"]
    flagged = port[port["collection_rate_pct"] < collection_threshold]

    if len(port) > 0:
        port_sorted = port.sort_values("protocol_number")
        planned = (port_sorted["total_planned"] - port_sorted["collected"]
                   - port_sorted["missed"] - port_sorted["deviated"]).clip(lower=0)
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Collected", x=port_sorted["protocol_number"],
                             y=port_sorted["collected"], marker_color="#27AE60"))
        fig.add_trace(go.Bar(name="Missed", x=port_sorted["protocol_number"],
                             y=port_sorted["missed"], marker_color="#C0392B"))
        fig.add_trace(go.Bar(name="Deviated", x=port_sorted["protocol_number"],
                             y=port_sorted["deviated"], marker_color="#E07B00"))
        fig.add_trace(go.Bar(name="Planned", x=port_sorted["protocol_number"],
                             y=planned, marker_color="#BDC3C7"))
        fig.update_layout(barmode="stack", title="Sample Status by Study",
                          template="plotly_white", height=400,
                          xaxis_title="Study", yaxis_title="Sample Count")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Sites Below {collection_threshold}% Collection Rate")
    if len(flagged) > 0:
        st.dataframe(flagged.style.background_gradient(
            subset=["collection_rate_pct"], cmap="RdYlGn").format(
            {"collection_rate_pct": "{:.1f}"}), use_container_width=True)
        csv = flagged.to_csv(index=False).encode()
        st.download_button("Download Flagged Sites", csv, "flagged_sites.csv", "text/csv")
    else:
        st.success("All sites meeting collection threshold.")


elif page == "Shipment Tracking":
    st.header("Shipment Tracking")
    overdue = data["overdue"]

    col1, col2 = st.columns(2)
    with col1:
        n_critical = len(overdue[overdue["days_in_transit"] > transit_threshold]) if len(overdue) > 0 else 0
        st.metric("Overdue Shipments", len(overdue),
                  delta=f"{n_critical} critical (>{transit_threshold} days)" if len(overdue) > 0 else None,
                  delta_color="inverse")
    with col2:
        avg_days = overdue["days_in_transit"].mean() if len(overdue) > 0 else 0
        st.metric("Avg Days in Transit", f"{avg_days:.1f}")

    if len(overdue) > 0:
        fig = px.bar(overdue.sort_values("days_in_transit", ascending=False),
                     x="shipment_id", y="days_in_transit",
                     color="days_in_transit",
                     color_continuous_scale=["#F4D03F","#E07B00","#C0392B"],
                     hover_data={"site_name": True},
                     title="Overdue Shipments by Shipment",
                     labels={"days_in_transit": "Days in Transit", "shipment_id": "Shipment ID"})
        fig.add_hline(y=transit_threshold, line_dash="dash", line_color="red",
                      annotation_text=f"Critical threshold ({transit_threshold} days)")
        fig.update_layout(template="plotly_white", height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(overdue, use_container_width=True)
    else:
        st.success("No overdue shipments.")


elif page == "Data Completeness":
    st.header("Data Completeness")
    comp = data["completeness"]

    if len(comp) > 0:
        fig = px.bar(comp, x="protocol_number", y="completeness_pct",
                     category_orders={"protocol_number": sorted(comp["protocol_number"].unique()),
                                      "lab_name": sorted(comp["lab_name"].unique())},
                     color="lab_name",
                     barmode="group",
                     title="Data Completeness by Study and Lab",
                     labels={"completeness_pct": "Completeness (%)",
                             "protocol_number": "Study",
                             "lab_name": "Lab"})
        fig.add_hline(y=completeness_threshold, line_dash="dash", line_color="gray",
                      annotation_text=f"Target ({completeness_threshold}%)")
        fig.update_layout(template="plotly_white", height=380)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Below {completeness_threshold}% Completeness Target")
        display = comp[comp["completeness_pct"] < completeness_threshold][
            ["protocol_number","lab_name","total_results_expected",
             "results_complete","results_missing","completeness_pct","total_queries"]
        ]
        if len(display) > 0:
            st.dataframe(display.style.background_gradient(
                subset=["completeness_pct"], cmap="RdYlGn", vmin=0, vmax=completeness_threshold).format(
                {"completeness_pct": "{:.1f}"}), use_container_width=True)
            st.download_button("Download Completeness Report",
                               display.to_csv(index=False).encode(),
                               "data_completeness.csv", "text/csv")
        else:
            st.success("All studies meeting completeness target.")
    else:
        st.info("No data completeness records found.")


elif page == "Issues & Risk":
    st.header("Issues & Site Risk")
    issues = data["issues"]
    risk   = data["risk"]

    if len(issues) > 0:
        col1, col2 = st.columns(2)
        with col1:
            sev_counts = issues.groupby("severity")["issue_count"].sum().reset_index()
            sev_order = ["Critical","High","Medium","Low"]
            sev_counts["severity"] = pd.Categorical(sev_counts["severity"],
                                                     categories=sev_order, ordered=True)
            sev_counts = sev_counts.sort_values("severity")
            fig = px.bar(sev_counts, x="severity", y="issue_count",
                         color="severity",
                         color_discrete_map={"Critical":"#C0392B","High":"#E07B00",
                                             "Medium":"#F4D03F","Low":"#27AE60"},
                         title="Open Issues by Severity")
            fig.update_layout(template="plotly_white", height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            cat_counts = issues.groupby("category")["issue_count"].sum().reset_index()
            fig = px.pie(cat_counts, values="issue_count", names="category",
                         title="Issues by Category",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(template="plotly_white", height=350)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Site Risk Ranking")
    if len(risk) > 0:
        risk_plot = risk.copy()
        risk_plot["Collection Rate"] = (100 - risk_plot["collection_rate_pct"]).clip(lower=0).round(1)
        risk_plot["Critical Issues"] = risk_plot["critical_issues"] * 10
        risk_plot["High Issues"]     = risk_plot["high_issues"] * 5
        risk_plot["site_label"] = risk_plot["site_name"].str.extract(r"^(Site \d+)")
        risk_plot["site_num"] = risk_plot["site_label"].str.extract(r"(\d+)").astype(int)
        risk_plot = risk_plot.sort_values(["protocol_number", "site_num"])
        site_order = risk_plot.drop_duplicates("site_label") \
                              .sort_values("site_num")["site_label"].tolist()

        plot_data = risk_plot.melt(
            id_vars=["protocol_number", "site_label"],
            value_vars=["Collection Rate", "Critical Issues", "High Issues"],
            var_name="Component",
            value_name="Points"
        )

        n_studies = risk_plot["protocol_number"].nunique()
        fig = px.bar(
            plot_data,
            x="site_label",
            y="Points",
            color="Component",
            facet_col="protocol_number",
            facet_col_wrap=1,
            facet_row_spacing=min(0.05, 1 / n_studies) if n_studies > 1 else 0.05,
            color_discrete_map={
                "Critical Issues": "#C0392B",
                "High Issues":     "#E07B00",
                "Collection Rate": "#7D3C98",
            },
            category_orders={
                "Component":       ["High Issues", "Critical Issues", "Collection Rate"],
                "protocol_number": sorted(risk_plot["protocol_number"].unique()),
                "site_label":      site_order,
            },
            labels={"site_label": "Site", "Points": "Risk Score (higher = more risk)"},
        )
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(
            template="plotly_white", height=max(600, n_studies * 300),
            barmode="stack", legend_title="Risk Component",
            legend=dict(traceorder="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

        risk_table = risk[risk["risk_score"] > 0].sort_values("risk_score", ascending=False)
        st.dataframe(
            risk_table.style.background_gradient(
                subset=["risk_score"], cmap="RdYlGn_r",
                vmin=0, vmax=risk_table["risk_score"].max()
            ).format({"risk_score": "{:.1f}", "collection_rate_pct": "{:.1f}"}),
            use_container_width=True
        )
