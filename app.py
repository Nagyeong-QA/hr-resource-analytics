import pandas as pd
import streamlit as st

from src.utilization import (
    load_timesheet_data,
    calculate_daily_metrics,
    add_organization_info,
)

from src.resource_analysis import (
    load_project_data,
    summarize_by_team,
    summarize_by_user,
    summarize_by_project,
    calculate_allocation_by_user,
    identify_resource_signals,
)


st.set_page_config(
    page_title="HR Resource Analytics",
    layout="wide"
)

st.title("HR Resource Analytics Dashboard")
st.caption(
    "조직·프로젝트별 투입공수, 가동률, OT 및 인력 배분 현황을 분석하는 포트폴리오 Demo"
)


@st.cache_data
def load_dashboard_data():
    timesheets, users = load_timesheet_data()
    projects = load_project_data()

    daily = calculate_daily_metrics(timesheets)
    result = add_organization_info(daily, users)

    team_summary = summarize_by_team(result)
    user_summary = summarize_by_user(result)
    project_summary = summarize_by_project(
        timesheets,
        projects,
        users
    )
    allocation = calculate_allocation_by_user(
        timesheets,
        users,
        projects
    )
    resource_signals = identify_resource_signals(
        user_summary
    )

    return (
        result,
        team_summary,
        user_summary,
        project_summary,
        allocation,
        resource_signals,
    )


(
    result,
    team_summary,
    user_summary,
    project_summary,
    allocation,
    resource_signals,
) = load_dashboard_data()


# -------------------------
# Sidebar
# -------------------------

st.sidebar.header("Filter")

team_options = ["All"] + sorted(
    result["team"].dropna().unique().tolist()
)

selected_team = st.sidebar.selectbox(
    "Team",
    team_options
)

if selected_team == "All":
    filtered_result = result.copy()
    filtered_users = user_summary.copy()
else:
    filtered_result = result[
        result["team"] == selected_team
    ].copy()

    filtered_users = user_summary[
        user_summary["team"] == selected_team
    ].copy()


# -------------------------
# KPI
# -------------------------

headcount = filtered_result["user_id"].nunique()

avg_utilization = (
    filtered_result["utilization_pct"].mean()
    if len(filtered_result) > 0
    else 0
)

total_project_hours = filtered_result[
    "project_hours"
].sum()

total_overtime = filtered_result[
    "overtime_hours"
].sum()


col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Headcount",
    f"{headcount}"
)

col2.metric(
    "Avg. Utilization",
    f"{avg_utilization:.1f}%"
)

col3.metric(
    "Project Hours",
    f"{total_project_hours:.1f} h"
)

col4.metric(
    "Overtime",
    f"{total_overtime:.1f} h"
)


st.divider()


# -------------------------
# Team Utilization
# -------------------------

st.subheader("Team Utilization")

team_chart = (
    team_summary[
        ["team", "avg_utilization_pct"]
    ]
    .set_index("team")
)

st.bar_chart(team_chart)


# -------------------------
# Project Allocation
# -------------------------

st.subheader("Project Resource Allocation")

project_chart = (
    project_summary[
        ["project_name", "total_project_hours"]
    ]
    .set_index("project_name")
)

st.bar_chart(project_chart)


# -------------------------
# User Resource Status
# -------------------------

st.subheader("Individual Resource Status")

display_users = filtered_users[
    [
        "name",
        "team",
        "part",
        "avg_utilization_pct",
        "total_project_hours",
        "total_general_hours",
        "total_leave_hours",
        "total_overtime_hours",
    ]
].copy()

display_users.columns = [
    "Name",
    "Team",
    "Part",
    "Utilization (%)",
    "Project Hours",
    "General Hours",
    "Leave Hours",
    "Overtime Hours",
]

st.dataframe(
    display_users,
    use_container_width=True,
    hide_index=True,
)


# -------------------------
# Resource Signals
# -------------------------

st.subheader("Resource Signals")

signal_data = resource_signals.copy()

if selected_team != "All":
    signal_data = signal_data[
        signal_data["team"] == selected_team
    ]

signal_data = signal_data[
    [
        "name",
        "team",
        "avg_utilization_pct",
        "total_overtime_hours",
        "resource_signal",
    ]
]

signal_data.columns = [
    "Name",
    "Team",
    "Utilization (%)",
    "Overtime Hours",
    "Signal",
]

st.dataframe(
    signal_data,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Resource Signal은 인력 의사결정을 자동으로 판단하는 기준이 아니라, "
    "추가 검토가 필요한 현황을 빠르게 확인하기 위한 참고 지표입니다."
)


# -------------------------
# Allocation Detail
# -------------------------

st.subheader("Individual Project Allocation")

allocation_display = allocation[
    [
        "name",
        "team",
        "project_name",
        "project_hours",
        "allocation_pct",
    ]
].copy()

if selected_team != "All":
    allocation_display = allocation_display[
        allocation_display["team"] == selected_team
    ]

allocation_display.columns = [
    "Name",
    "Team",
    "Project",
    "Project Hours",
    "Allocation (%)",
]

st.dataframe(
    allocation_display,
    use_container_width=True,
    hide_index=True,
)


st.divider()

st.caption(
    "All data shown in this dashboard is fictional and was created solely "
    "for portfolio demonstration purposes."
)
