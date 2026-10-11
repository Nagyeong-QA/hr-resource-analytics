"""HR Resource Analytics | synthetic portfolio demo.

Run from repository root: python -m streamlit run app.py
Requires: data/users_sample.csv, data/projects_sample.csv, data/timesheets_sample.csv,
          src/utilization.py, src/resource_analysis.py.
All extended demonstration records are generated in memory and are fictional.
"""
from __future__ import annotations

import calendar
import random
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.utilization import calculate_daily_metrics, add_organization_info
from src.resource_analysis import calculate_allocation_by_user

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
GENERAL = "GENERAL"
LEAVE = "LEAVE"
DAILY_MINUTES = 480
DEMO_START = "2026-03-02"
DEMO_END = "2026-09-30"

st.set_page_config(page_title="HR Resource Analytics | Demo", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.8rem; max-width: 1500px;}
[data-testid="stMetric"] {
    border: 1px solid #e8ecf3;
    border-radius: 14px;
    background: #ffffff;
    padding: 15px 18px;
    box-shadow: 0 3px 12px rgba(40, 61, 91, .045);
}
[data-testid="stMetricValue"] {font-size: 1.8rem; color: #202c46;}
[data-testid="stMetricLabel"] {font-size: .88rem; color: #53617a;}
.small-note {color: #657084; font-size: .88rem;}
</style>
""", unsafe_allow_html=True)


def week_in_month(timestamp: pd.Timestamp) -> int:
    """Calendar weeks, Monday first; partial first/last weeks included."""
    timestamp = pd.Timestamp(timestamp)
    return (timestamp.day + date(timestamp.year, timestamp.month, 1).weekday() - 1) // 7 + 1


def month_business_days(ym: str) -> int:
    year, month = map(int, ym.split("-"))
    end = calendar.monthrange(year, month)[1]
    return len(pd.bdate_range(f"{ym}-01", f"{ym}-{end:02d}"))


def safe_ratio(numer: float, denom: float) -> float:
    return float(numer / denom * 100) if denom > 0 else 0.0


def fmt_hours(minutes: float) -> float:
    return round(float(minutes) / 60, 1)


@st.cache_data(show_spinner=False)
def load_masters() -> tuple[pd.DataFrame, pd.DataFrame]:
    users = pd.read_csv(DATA / "users_sample.csv", dtype={"user_id": "string"})
    projects = pd.read_csv(DATA / "projects_sample.csv", dtype={"project_code": "string"})
    required_users = {"user_id", "name", "team", "part"}
    required_projects = {"project_code", "project_name"}
    if not required_users.issubset(users.columns):
        raise ValueError(f"users_sample.csv 필수 컬럼 누락: {required_users - set(users.columns)}")
    if not required_projects.issubset(projects.columns):
        raise ValueError(f"projects_sample.csv 필수 컬럼 누락: {required_projects - set(projects.columns)}")
    for c in ("tft", "role"):
        if c not in users.columns:
            users[c] = ""
    users["team"] = users["team"].fillna("미분류")
    users["part"] = users["part"].fillna("미분류")
    return users, projects


@st.cache_data(show_spinner=False)
def read_sample_timesheets() -> pd.DataFrame:
    return pd.read_csv(DATA / "timesheets_sample.csv", dtype={"user_id": "string", "project_code": "string"})


@st.cache_data(show_spinner=False)
def make_extended_demo(users: pd.DataFrame, projects: pd.DataFrame) -> pd.DataFrame:
    """Create repeatable synthetic weekday records, never copying employer data."""
    rng = random.Random(20261011)
    codes = [str(x) for x in projects["project_code"].dropna().unique()
             if str(x) not in {GENERAL, LEAVE}]
    if not codes:
        raise ValueError("프로젝트 목록에 GENERAL/LEAVE 외 일반 프로젝트가 필요합니다.")
    rows = []
    row_id = 1
    bdays = pd.bdate_range(DEMO_START, DEMO_END)
    for employee_i, user in users.reset_index(drop=True).iterrows():
        uid = str(user["user_id"])
        team = str(user["team"])
        team_load = {"Platform": 45, "Data": 25, "Quality": 5, "Product": 35}.get(team, 20)
        primary = codes[employee_i % len(codes)]
        secondary = codes[(employee_i + 1) % len(codes)] if len(codes) > 1 else primary
        for day in bdays:
            month_wave = {3: -25, 4: -15, 5: 10, 6: 35, 7: 55, 8: 5, 9: 25}.get(day.month, 0)
            leave_draw = rng.random()
            leave_minutes = 480 if leave_draw < .018 else (240 if leave_draw < .06 else 0)
            if leave_minutes == 480:
                project_minutes, general_minutes = 0, 0
            else:
                available = 480 - leave_minutes
                project_minutes = max(60, min(630, round(
                    (available * .87 + team_load + month_wave + rng.randint(-90, 85)) / 30
                ) * 30))
                general_minutes = rng.choice([0, 30, 30, 60, 60, 90]) if leave_minutes == 0 else rng.choice([0, 30])
            parts = []
            if project_minutes:
                if project_minutes >= 210 and primary != secondary and rng.random() < .38:
                    second_mins = int(project_minutes * rng.choice([.25, .35, .45]) // 30) * 30
                    parts.extend([(primary, project_minutes - second_mins), (secondary, second_mins)])
                else:
                    parts.append((primary, project_minutes))
            if general_minutes:
                parts.append((GENERAL, general_minutes))
            if leave_minutes:
                parts.append((LEAVE, leave_minutes))
            for code, mins in parts:
                rows.append({"timesheet_id": f"D{row_id:06d}", "user_id": uid,
                             "date": day.strftime("%Y-%m-%d"), "project_code": code,
                             "minutes": mins})
                row_id += 1
    return pd.DataFrame(rows)


def validate_records(raw: pd.DataFrame, users: pd.DataFrame,
                     projects: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exclude invalid rows once, report why; no silent correction."""
    needed = {"user_id", "date", "project_code", "minutes"}
    if not needed.issubset(raw.columns):
        raise ValueError(f"timesheets_sample.csv 필수 컬럼 누락: {needed - set(raw.columns)}")
    df = raw.copy()
    df["user_id"] = df["user_id"].astype("string")
    df["project_code"] = df["project_code"].astype("string")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df["invalid_date"] = df["date"].isna()
    df["invalid_minutes"] = df["minutes"].isna() | (df["minutes"] <= 0) | (df["minutes"] > 1440)
    df["unknown_user"] = ~df["user_id"].isin(users["user_id"].astype("string"))
    df["unknown_project"] = ~df["project_code"].isin(projects["project_code"].astype("string"))
    df["duplicate_record"] = df.duplicated(["user_id", "date", "project_code"], keep=False)
    flags = ["invalid_date", "invalid_minutes", "unknown_user", "unknown_project", "duplicate_record"]
    df["row_error"] = df[flags].any(axis=1)
    good = df.loc[~df["row_error"], ["user_id", "date", "project_code", "minutes"]].copy()
    good["minutes"] = good["minutes"].astype(int)
    daily_total = good.groupby(["user_id", "date"])["minutes"].sum()
    invalid_days = daily_total[daily_total > 1440].index
    if len(invalid_days):
        idx = pd.MultiIndex.from_frame(good[["user_id", "date"]])
        df["over_24h_day"] = pd.MultiIndex.from_frame(df[["user_id", "date"]]).isin(invalid_days)
        good = good.loc[~idx.isin(invalid_days)].copy()
    else:
        df["over_24h_day"] = False
    df["row_error"] = df["row_error"] | df["over_24h_day"]
    return good, df


def build_daily(clean: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    daily = calculate_daily_metrics(clean)
    result = add_organization_info(daily, users)
    result["year_month"] = result["date"].dt.strftime("%Y-%m")
    result["week_no"] = result["date"].apply(week_in_month)
    result["work_minutes"] = result["project_minutes"] + result["general_minutes"]
    return result


def summary_aggregate(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Ratios of sums, not simple mean of row percentages."""
    grouped = frame.groupby(keys, dropna=False, as_index=False).agg(
        project_minutes=("project_minutes", "sum"),
        general_minutes=("general_minutes", "sum"),
        overtime_minutes=("overtime_minutes", "sum"),
        leave_minutes=("leave_minutes", "sum"),
        available_minutes=("available_minutes", "sum"),
        person_days=("user_id", "size"),
        headcount=("user_id", "nunique"),
    )
    grouped["utilization_pct"] = grouped.apply(
        lambda r: safe_ratio(r.project_minutes, r.available_minutes), axis=1)
    grouped["general_pct"] = grouped.apply(
        lambda r: safe_ratio(r.general_minutes, r.project_minutes + r.general_minutes), axis=1)
    grouped["leave_pct"] = grouped.apply(
        lambda r: safe_ratio(r.leave_minutes, r.person_days * DAILY_MINUTES), axis=1)
    grouped["project_hours"] = grouped["project_minutes"] / 60
    grouped["general_hours"] = grouped["general_minutes"] / 60
    grouped["overtime_hours"] = grouped["overtime_minutes"] / 60
    return grouped


def monthly_project_view(raw: pd.DataFrame, users: pd.DataFrame,
                         projects: pd.DataFrame, ym: str, teams: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw.merge(users[["user_id", "team", "name"]], on="user_id", how="left")
    df = df[df["date"].dt.strftime("%Y-%m") == ym].copy()
    df = df[df["team"].isin(teams)]
    df = df[~df["project_code"].isin([GENERAL, LEAVE])].copy()
    df["hours"] = df["minutes"] / 60
    df["week_no"] = df["date"].apply(week_in_month)
    # Illustrative monthly capacity: weekdays * 8 hours, excluding public-holiday corrections.
    month_capacity = month_business_days(ym) * 8
    p = df.groupby("project_code", as_index=False).agg(
        hours=("hours", "sum"), headcount=("user_id", "nunique"))
    p["monthly_mm"] = p["hours"] / month_capacity if month_capacity else 0
    p = p.merge(projects[["project_code", "project_name"]], on="project_code", how="left")
    p = p.sort_values("monthly_mm", ascending=False)

    weeks = pd.bdate_range(f"{ym}-01", periods=month_business_days(ym))
    week_capacity = pd.Series([week_in_month(d) for d in weeks]).value_counts().to_dict()
    w = df.groupby(["week_no", "project_code"], as_index=False).agg(hours=("hours", "sum"))
    w["weekly_fte"] = w.apply(
        lambda r: r.hours / (week_capacity.get(r.week_no, 0) * 8)
        if week_capacity.get(r.week_no, 0) else 0, axis=1)
    w = w.merge(projects[["project_code", "project_name"]], on="project_code", how="left")
    w["week"] = w["week_no"].astype(str) + "주차"
    return p, w


def chart_layout(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=35, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend_title_text="", hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(140,150,160,.18)")
    return fig


def monthly_resource_chart(monthly: pd.DataFrame) -> go.Figure:
    """Portfolio chart: green 80–100% reference band, utilization + general-work bars, OT line.

    Left axis: project utilization (% of available minutes).
    Right axis: general work (% of actual work minutes) and overtime
                (% of available minutes). Distinct denominators are disclosed.
    """
    plot = monthly.sort_values("year_month").copy()
    plot["overtime_ratio_pct"] = plot.apply(
        lambda r: safe_ratio(r["overtime_minutes"], r["available_minutes"]), axis=1
    )
    locations = list(range(len(plot)))
    months = plot["year_month"].astype(str).tolist()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    # Use explicit x offsets to prevent Plotly from stacking dual-axis bars.
    fig.add_trace(
        go.Bar(
            x=[x - 0.15 for x in locations], y=plot["utilization_pct"],
            width=0.42, name="프로젝트 가동률", marker_color="#527EF2",
            customdata=months,
            hovertemplate="%{customdata}<br>프로젝트 가동률 %{y:.1f}%<extra></extra>",
        ),
        secondary_y=False,
    )
    # Add after the first trace: Plotly requires an initialized primary y-axis.
    # Reference shading does not establish an HR performance threshold.
    fig.add_hrect(y0=80, y1=100, fillcolor="rgba(71, 190, 111, 0.18)",
                  line_width=0, layer="below", row=1, col=1)
    fig.add_trace(
        go.Bar(
            x=[x + 0.20 for x in locations], y=plot["general_pct"],
            width=0.17, name="일반업무 비율", marker_color="#F1BF47",
            customdata=months,
            hovertemplate="%{customdata}<br>일반업무 비율 %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=locations, y=plot["overtime_ratio_pct"],
            name="초과근무 비율", mode="lines+markers",
            line=dict(color="#E9555E", width=2.7),
            marker=dict(size=8, color="#FFFFFF", line=dict(color="#E9555E", width=2.7)),
            customdata=months,
            hovertemplate="%{customdata}<br>초과근무 비율 %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    util_max = float(plot["utilization_pct"].max()) if not plot.empty else 100.0
    right_max = max(
        float(plot["general_pct"].max()) if not plot.empty else 0,
        float(plot["overtime_ratio_pct"].max()) if not plot.empty else 0,
    )
    # Keep a stable minimum scale for readable comparisons with the original dashboard.
    left_limit = max(140, int((util_max + 19) // 10) * 10)
    right_limit = max(30, int((right_max + 9) // 5) * 5)

    fig.update_xaxes(
        tickmode="array", tickvals=locations,
        ticktext=months, title_text="월", showgrid=False,
        range=[-0.65, len(locations) - 0.35],
        tickfont=dict(size=11, color="#60708A"),
    )
    fig.update_yaxes(
        title_text="프로젝트 가동률 (%)", range=[0, left_limit],
        ticksuffix="%", dtick=20, gridcolor="rgba(99, 115, 144, 0.13)",
        zeroline=False, secondary_y=False,
    )
    fig.update_yaxes(
        title_text="일반업무·초과근무 비율 (%)", range=[0, right_limit],
        ticksuffix="%", dtick=5, showgrid=False, zeroline=False,
        secondary_y=True,
    )
    fig.add_annotation(
        xref="paper", yref="y", x=0.99, y=90,
        text="80–100% 참고 구간", showarrow=False,
        font=dict(size=11, color="#28794E"),
        bgcolor="rgba(255,255,255,0.70)", borderpad=3,
    )
    fig.update_layout(
        barmode="overlay", height=475,
        margin=dict(l=14, r=15, t=55, b=20),
        plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x", bargap=0.25,
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0,
                    font=dict(size=12)),
    )
    return fig


def team_worktime_chart(team_report: pd.DataFrame, per_person_day: bool = False) -> go.Figure:
    """Team work mix (stacked) + overtime (overlay; never double counted).

    Stacked bars = project + general work (non-leave hours).
    Right-axis line = OT per recorded person-day, NOT extra time added to the bars.
    """
    plot = team_report.sort_values("team").copy()
    plot["ot_hours_per_person_day"] = (
        plot["overtime_hours"] / plot["person_days"].clip(lower=1)
    )
    if per_person_day:
        plot["project_plot"] = plot["project_hours"] / plot["person_days"].clip(lower=1)
        plot["general_plot"] = plot["general_hours"] / plot["person_days"].clip(lower=1)
        left_title = "인당 기록일 기준 평균 업무시간 (h/인일)"
    else:
        plot["project_plot"] = plot["project_hours"]
        plot["general_plot"] = plot["general_hours"]
        left_title = "팀 총 업무시간 (h)"

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=plot["team"], y=plot["project_plot"], name="프로젝트 업무",
            marker_color="#5278D9",
            hovertemplate="%{x}<br>프로젝트 업무 %{y:.2f}h<extra></extra>",
        ), secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=plot["team"], y=plot["general_plot"], name="일반업무",
            marker_color="#E2B23A",
            hovertemplate="%{x}<br>일반업무 %{y:.2f}h<extra></extra>",
        ), secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=plot["team"], y=plot["ot_hours_per_person_day"],
            name="인당 일평균 초과근무", mode="lines+markers+text",
            text=[f"{v:.2f}h" for v in plot["ot_hours_per_person_day"]],
            textposition="top center", textfont=dict(size=11, color="#D94853"),
            line=dict(color="#E9555E", width=3),
            marker=dict(size=9, color="#FFFFFF", line=dict(color="#E9555E", width=2.5)),
            customdata=plot[["overtime_hours", "headcount", "person_days"]].to_numpy(),
            hovertemplate=("%{x}<br>인당 일평균 OT %{y:.2f}h"
                           "<br>팀 총 OT %{customdata[0]:.1f}h"
                           "<br>기록 인원 %{customdata[1]:.0f}명"
                           "<br>기록 인일 %{customdata[2]:.0f}인일<extra></extra>"),
        ), secondary_y=True,
    )
    total_bar = plot["project_plot"] + plot["general_plot"]
    left_max = max(8 if per_person_day else 10, float(total_bar.max()) * 1.20)
    right_max = max(0.5, float(plot["ot_hours_per_person_day"].max()) * 1.55)
    fig.update_yaxes(title_text=left_title, range=[0, left_max],
                     gridcolor="rgba(110, 125, 150, .13)", zeroline=False,
                     secondary_y=False)
    fig.update_yaxes(title_text="인당 일평균 초과근무 (h/인일)", range=[0, right_max],
                     showgrid=False, zeroline=False, secondary_y=True)
    fig.update_layout(
        barmode="stack", height=380, margin=dict(l=5, r=15, t=55, b=20),
        plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.04,
                    xanchor="left", x=0, font=dict(size=11)),
        hovermode="x unified",
    )
    fig.update_xaxes(title_text="팀", showgrid=False)
    return fig



def weekly_utilization_distribution_chart(
    current: pd.DataFrame,
    average_mode: str = "팀별 평균선",
) -> go.Figure:
    """Show individual weekly spread alongside team/overall weighted means.

    Boxes: employee-week utilization = weekly project minutes / weekly available minutes.
    Lines: group ratio-of-sums = all project minutes / all available minutes.
    Numeric x offsets align each team's mean exactly above its corresponding box.
    """
    employee_weeks = summary_aggregate(
        current, ["week_no", "team", "user_id", "name"]
    )
    team_weeks = summary_aggregate(current, ["week_no", "team"])
    overall_weeks = summary_aggregate(current, ["week_no"])

    weeks = sorted(int(x) for x in employee_weeks["week_no"].dropna().unique())
    teams = sorted(str(x) for x in employee_weeks["team"].dropna().unique())

    color_map = {
        "Data": "#4775D1", "Platform": "#75B8F5",
        "Product": "#E76463", "Quality": "#F29A9A",
    }
    fallback = px.colors.qualitative.Safe
    colors = {
        team: color_map.get(team, fallback[index % len(fallback)])
        for index, team in enumerate(teams)
    }
    width = min(0.17, 0.73 / max(len(teams), 1))
    offsets = {
        team: (index - (len(teams) - 1) / 2) * width
        for index, team in enumerate(teams)
    }
    show_team_averages = average_mode in ("팀별 평균선", "전체+팀별 평균선")
    show_overall_average = average_mode in ("전체 평균선", "전체+팀별 평균선")

    fig = go.Figure()
    for team in teams:
        color = colors[team]
        fill = f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.27)"
        team_rows = employee_weeks[employee_weeks["team"] == team]
        for week in weeks:
            values = team_rows.loc[team_rows["week_no"] == week]
            if values.empty:
                continue
            x_pos = week + offsets[team]
            fig.add_trace(go.Box(
                x=[x_pos] * len(values),
                y=values["utilization_pct"].tolist(),
                name=f"{team} 분포", legendgroup=team,
                showlegend=(not show_team_averages and week == weeks[0]),
                width=width * 0.84,
                marker=dict(color=color, size=6),
                fillcolor=fill,
                line=dict(color=color, width=1.6),
                boxpoints="outliers",
                customdata=values[["name"]].to_numpy(),
                hovertemplate=(f"{week}주차 · {team}"
                               "<br>개인 가동률 %{y:.1f}%<extra></extra>"),
            ))

        if show_team_averages:
            means = team_weeks.loc[team_weeks["team"] == team].set_index("week_no")
            x_positions, y_values, people = [], [], []
            for week in weeks:
                x_positions.append(week + offsets[team])
                if week in means.index:
                    record = means.loc[week]
                    y_values.append(float(record["utilization_pct"]))
                    people.append(int(record["headcount"]))
                else:
                    y_values.append(None)
                    people.append(0)
            fig.add_trace(go.Scatter(
                x=x_positions, y=y_values, mode="lines+markers",
                name=f"{team} 평균", legendgroup=team,
                line=dict(color=color, width=2.6),
                marker=dict(size=9, color="#FFFFFF", line=dict(color=color, width=2.7)),
                customdata=people,
                hovertemplate=("%{x:.0f}주차 · " + team
                               + "<br>팀 평균 가동률 %{y:.1f}%"
                               + "<br>기록 인원 %{customdata}명<extra></extra>"),
                connectgaps=False,
            ))

    if show_overall_average:
        overall = overall_weeks.set_index("week_no")
        global_means = [float(overall.loc[week, "utilization_pct"])
                        if week in overall.index else None for week in weeks]
        fig.add_trace(go.Scatter(
            x=weeks, y=global_means, mode="lines+markers",
            name="전체 평균", legendgroup="overall",
            line=dict(color="#22304A", width=3.3, dash="dot"),
            marker=dict(symbol="diamond", size=9, color="#22304A"),
            hovertemplate="%{x}주차<br>전체 평균 가동률 %{y:.1f}%<extra></extra>",
            connectgaps=False,
        ))

    combined_pct = employee_weeks["utilization_pct"].tolist() + team_weeks["utilization_pct"].tolist()
    if show_overall_average:
        combined_pct += overall_weeks["utilization_pct"].tolist()
    if combined_pct:
        min_v, max_v = min(combined_pct), max(combined_pct)
        y_min = max(0, (int((min_v - 7) // 10)) * 10)
        y_max = max(110, (int((max_v + 14) // 10)) * 10)
    else:
        y_min, y_max = 0, 120

    fig.add_hrect(y0=80, y1=100, fillcolor="rgba(71, 190, 111, 0.09)",
                  line_width=0, layer="below")
    fig.update_layout(
        height=495, margin=dict(l=10, r=18, t=58, b=32),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
        boxmode="overlay", hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.04,
                    xanchor="left", x=0, font=dict(size=11)),
    )
    fig.update_xaxes(
        title_text="주차", tickmode="array", tickvals=weeks,
        ticktext=[f"{w}주차" for w in weeks],
        range=[min(weeks) - 0.63, max(weeks) + 0.63],
        showgrid=False, zeroline=False,
    )
    fig.update_yaxes(
        title_text="주간 프로젝트 가동률 (%)", ticksuffix="%",
        range=[y_min, y_max], gridcolor="rgba(120, 135, 155, .16)",
        zeroline=False,
    )
    return fig

def file_download(frame: pd.DataFrame, filename: str, label: str) -> None:
    st.download_button(label, frame.to_csv(index=False).encode("utf-8-sig"),
                       file_name=filename, mime="text/csv")


# ---- Load, verify and aggregate ----
st.title("📊 조직·인력 리소스 분석")
st.caption("HR Resource Analytics | 조직 가동률 · 경영진 월간 보고 · 프로젝트 M/M · 데이터 품질")

try:
    users, projects = load_masters()
except (FileNotFoundError, ValueError) as exc:
    st.error(f"샘플 마스터 데이터를 불러올 수 없습니다: {exc}")
    st.stop()

with st.sidebar:
    st.header("분석 기준")
    data_mode = st.radio("데이터", ["확장 가상 데이터 (추천)", "현재 CSV 샘플"], index=0)
    st.caption("확장 가상 데이터는 인물·업무시간·프로젝트 투입을 재현 가능하게 생성한 합성 데이터입니다.")

try:
    raw = make_extended_demo(users, projects) if data_mode.startswith("확장") else read_sample_timesheets()
    clean, quality = validate_records(raw, users, projects)
    if clean.empty:
        st.error("유효한 데이터가 없습니다. data/*.csv 컬럼과 값을 확인하세요.")
        st.stop()
    daily = build_daily(clean, users)
except (FileNotFoundError, KeyError, ValueError) as exc:
    st.error(f"데이터 처리 오류: {exc}")
    st.stop()

with st.sidebar:
    months = sorted(daily["year_month"].unique().tolist())
    chosen_month = st.selectbox("보고 월", months, index=len(months) - 1)
    all_teams = sorted(daily["team"].dropna().unique().tolist())
    selected_teams = st.multiselect("팀 선택", all_teams, default=all_teams)
    selected_teams = selected_teams or all_teams
    st.divider()
    st.caption("**지표 해석**")
    st.caption("가동률 = 프로젝트 투입시간 ÷ 연차 차감 가용시간")
    st.caption("M/M = 프로젝트 투입시간 ÷ 해당 월 평일 기준시간")
    st.caption("휴일·조직변경·계약상 정원(TO)은 데모 범위에 미포함")

st.info("🔒 **공개용 가상 데이터 대시보드** · 실제 회사 인사정보·프로젝트·운영 원본은 포함하지 않습니다.")
if len(months) < 3:
    st.warning("현재 CSV는 분석 기간이 짧아 월별·주차별 추이의 의미가 제한됩니다. 왼쪽에서 '확장 가상 데이터'를 선택하세요.")

scope = daily[daily["team"].isin(selected_teams)].copy()
current = scope[scope["year_month"] == chosen_month].copy()
raw_scope = clean[clean["user_id"].isin(users.loc[users["team"].isin(selected_teams), "user_id"].astype("string"))]

st.subheader(f"{chosen_month}  |  인력 운영 핵심 지표")
if current.empty:
    st.warning("선택한 기간과 팀에 집계할 데이터가 없습니다.")
    st.stop()

util = safe_ratio(current["project_minutes"].sum(), current["available_minutes"].sum())
mean_ot = fmt_hours(current["overtime_minutes"].sum()) / len(current)
general_pct = safe_ratio(current["general_minutes"].sum(), current["work_minutes"].sum())
leave_pct = safe_ratio(current["leave_minutes"].sum(), len(current) * DAILY_MINUTES)
recorded_people = current["user_id"].nunique()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("프로젝트 가동률", f"{util:.1f}%")
k2.metric("인당 일평균 OT", f"{mean_ot:.2f}시간")
k3.metric("일반업무 비율", f"{general_pct:.1f}%")
k4.metric("연차 시간 비율", f"{leave_pct:.1f}%")
k5.metric("기록 보유 인원", f"{recorded_people}명")
st.caption("전체 합계를 기준으로 계산한 지표입니다. 가동률만으로 인력 과부하·적정 TO를 단정하지 않습니다.")

org_tab, report_tab, project_tab, check_tab = st.tabs(
    ["📈 조직 가동률", "📋 월간 경영진 보고", "📊 프로젝트 리소스", "🔎 데이터 품질"])

with org_tab:
    st.subheader("월별 리소스 투입 현황")
    monthly = summary_aggregate(scope, ["year_month"])
    st.plotly_chart(monthly_resource_chart(monthly), use_container_width=True)
    st.caption(
        "초록색 80~100% 영역은 포트폴리오 시각화를 위한 **참고 구간**이며 "
        "조직의 적정 인력·과부하 여부를 자동 판정하지 않습니다. "
        "프로젝트 가동률 = 프로젝트 투입시간 ÷ 연차 차감 가용시간, "
        "일반업무 비율 = 일반업무시간 ÷ (프로젝트+일반업무 시간), "
        "초과근무 비율 = 초과근무시간 ÷ 연차 차감 가용시간입니다."
    )

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("팀별 가동률")
        team_month = summary_aggregate(current, ["team"]).sort_values("utilization_pct", ascending=False)
        fig = px.bar(team_month, x="team", y="utilization_pct", text="utilization_pct",
                     labels={"team": "팀", "utilization_pct": "가동률 (%)"})
        fig.update_traces(marker_color="#E85E59", texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(chart_layout(fig, 350), use_container_width=True)
    with right:
        st.subheader("팀별 업무시간 구성·초과근무")
        display_basis = st.radio(
            "업무시간 표시 기준",
            ["팀 총 업무시간", "인당 일평균 업무시간"],
            horizontal=True,
            key="team_worktime_basis",
        )
        team_work = summary_aggregate(current, ["team"])
        fig = team_worktime_chart(
            team_work, per_person_day=(display_basis == "인당 일평균 업무시간")
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "파란색·노란색 막대는 각각 프로젝트·일반업무 시간이며, "
            "빨간선은 인당 기록일 기준 일평균 초과근무(h)입니다. "
            "**초과근무는 막대 시간에 이미 포함되므로 추가로 합산하지 않습니다.** "
            "팀 규모가 다른 경우 '인당 일평균 업무시간'으로 비교하세요."
        )

with report_tab:
    st.subheader(f"[{chosen_month}] 주차별 인력 가동률 분포")
    avg_mode = st.radio(
        "평균선 표시",
        ["팀별 평균선", "전체 평균선", "전체+팀별 평균선"],
        horizontal=True,
        key="weekly_utilization_average_mode",
        help="팀별 평균선은 각 팀의 주차별 가동률 흐름을, 전체 평균선은 선택된 팀 전체의 흐름을 보여줍니다.",
    )
    fig = weekly_utilization_distribution_chart(current, average_mode=avg_mode)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**상자:** 구성원별 주간 프로젝트 가동률 분포(상자의 가로선은 중앙값) · "
        "**실선:** 팀별 평균 가동률 · **진한 점선:** 선택 팀 전체 평균 가동률. "
        "평균은 프로젝트 총 투입시간 ÷ 총 가용시간으로 계산합니다. "
        "초록색 80~100%는 참고 구간이며 과부하·성과를 자동 판정하지 않습니다. "
        "월 경계에 걸친 부분 주차가 포함될 수 있습니다."
    )

    st.subheader("팀별 운영 현황")
    team_month = summary_aggregate(current, ["team"]).sort_values("utilization_pct", ascending=False)
    display = team_month[["team", "headcount", "utilization_pct", "project_hours",
                          "general_hours", "overtime_hours", "leave_pct"]].copy()
    display.columns = ["팀", "기록 인원", "가동률(%)", "프로젝트 시간(h)",
                       "일반업무(h)", "OT(h)", "연차시간 비율(%)"]
    numeric_cols = display.select_dtypes("number").columns
    display[numeric_cols] = display[numeric_cols].round(1)
    st.dataframe(display, hide_index=True, use_container_width=True)

    st.subheader("자동 생성 요약 (규칙 기반)")
    top_team = team_month.iloc[0]
    low_team = team_month.iloc[-1]
    top_name = str(top_team["team"])
    month_project_hours = fmt_hours(current["project_minutes"].sum())
    st.markdown(f"""
- **전체:** 프로젝트 {month_project_hours:,.1f}시간 투입, 기록 보유 인원 {recorded_people}명, 평균 가동률 {util:.1f}%
- **조직 비교:** {top_name}의 가동률이 {top_team['utilization_pct']:.1f}%로 가장 높고, {low_team['team']}은 {low_team['utilization_pct']:.1f}%입니다.
- **추가 확인:** 높은 가동률만으로 과부하를 단정하지 않고, 프로젝트 중복 투입·일반업무·조직 이동·입력 누락 등을 함께 확인해야 합니다.
""")
    st.caption("이 요약은 AI가 작성한 평가가 아니라, 합산 데이터로 생성한 규칙 기반 문장입니다.")
    file_download(display, f"team_report_{chosen_month}.csv", "팀별 요약 CSV 저장")

with project_tab:
    st.subheader("프로젝트 투입 현황")
    ranking, weekly_projects = monthly_project_view(raw_scope, users, projects, chosen_month, selected_teams)
    if ranking.empty:
        st.info("선택 월에 프로젝트 투입 기록이 없습니다.")
    else:
        f1, f2 = st.columns([2, 1])
        with f1:
            sort = st.radio("정렬", ["상위(Top)", "하위(Bottom)"], horizontal=True)
        with f2:
            top_n = st.slider("표시 프로젝트 수", 1, len(ranking), min(6, len(ranking)))
        ordered = ranking.sort_values("monthly_mm", ascending=sort.startswith("하위")).head(top_n)
        total_mm = ranking["monthly_mm"].sum()
        p1, p2, p3 = st.columns(3)
        p1.metric("총 프로젝트 투입", f"{total_mm:.2f} M/M")
        p2.metric("투입 프로젝트", f"{len(ranking)}개")
        p3.metric("최대 투입 프로젝트", str(ranking.iloc[0]["project_name"]))
        l, r = st.columns([1, 1.2])
        with l:
            st.subheader("프로젝트별 월간 M/M")
            fig = px.bar(ordered.sort_values("monthly_mm"), x="monthly_mm", y="project_name",
                         orientation="h", text="monthly_mm",
                         labels={"monthly_mm": "투입 M/M", "project_name": "프로젝트"})
            fig.update_traces(marker_color="#E85E59", texttemplate="%{text:.2f}", textposition="outside")
            st.plotly_chart(chart_layout(fig, 390), use_container_width=True)
        with r:
            st.subheader("프로젝트 주차별 투입 추이")
            selected_codes = ordered["project_code"].tolist()
            w = weekly_projects[weekly_projects["project_code"].isin(selected_codes)].copy()
            fig = px.line(w, x="week_no", y="weekly_fte", color="project_name", markers=True,
                          labels={"week_no": "주차", "weekly_fte": "주간 환산 FTE", "project_name": "프로젝트"})
            fig.update_xaxes(tickmode="linear", dtick=1)
            st.plotly_chart(chart_layout(fig, 390), use_container_width=True)
        st.caption("1 M/M = 해당 월 평일 수 × 8시간. 주간 FTE는 해당 주의 평일 기준 환산 인원이며, 공휴일·개인별 휴가 보정은 반영하지 않았습니다.")

        st.subheader("인력별 프로젝트 배분")
        selected_raw = raw_scope[raw_scope["date"].dt.strftime("%Y-%m") == chosen_month]
        allocation = calculate_allocation_by_user(selected_raw, users, projects)
        if not allocation.empty:
            allocation_display = allocation[["name", "team", "project_name", "project_hours", "allocation_pct"]].copy()
            allocation_display.columns = ["구성원", "팀", "프로젝트", "투입시간(h)", "개인 프로젝트 내 비중(%)"]
            st.dataframe(allocation_display.round(1), hide_index=True, use_container_width=True)
            file_download(allocation_display, f"project_allocation_{chosen_month}.csv", "프로젝트 배분 CSV 저장")

with check_tab:
    st.subheader("원천 데이터 검증 현황")
    flags = {
        "날짜 오류": "invalid_date", "시간 오류(0 이하·24시간 초과 등)": "invalid_minutes",
        "미등록 사용자": "unknown_user", "미등록 프로젝트": "unknown_project",
        "사용자·일자·프로젝트 중복": "duplicate_record", "일일 총시간 24시간 초과": "over_24h_day",
    }
    checks = pd.DataFrame([{"검증 항목": label, "해당 행 수": int(quality[col].sum())}
                           for label, col in flags.items()])
    a, b, c = st.columns(3)
    a.metric("입력 행", f"{len(raw):,}")
    b.metric("분석 반영 행", f"{len(clean):,}")
    c.metric("검토 필요 행", f"{int(quality['row_error'].sum()):,}")
    st.dataframe(checks, hide_index=True, use_container_width=True)
    if quality["row_error"].any():
        st.warning("검증 오류가 있는 행은 KPI 집계에서 제외했습니다. 원본 데이터를 수정한 뒤 재확인하세요.")
        st.dataframe(quality.loc[quality["row_error"], ["user_id", "date", "project_code", "minutes"] + list(flags.values())]
                     .head(100), hide_index=True, use_container_width=True)
    else:
        st.success("기본 검증 기준에서 오류가 발견되지 않았습니다.")
    st.markdown("""
**데모 범위와 한계**
- 가동률은 **프로젝트 투입 / 연차 차감 가용시간**으로 산출하며 일반업무는 분자에서 제외합니다.
- 기본 가용시간은 1인·평일 8시간으로 가정합니다. 공휴일, 주말 OT, 조직 이동 이력 등은 재현하지 않았습니다.
- 사용자별 실제 정원(TO), 채용 필요 인원, 과부하 여부를 자동 판정하지 않습니다.
- 8명 샘플 기반의 모형이므로 **현업 운영 실적이나 실제 조직 분석 결과가 아닙니다.**
""")

st.divider()
st.caption("Portfolio demo | 개인·조직·프로젝트 명칭 및 확장 데이터는 모두 가상입니다. 실제 업무 구조를 참고해 독립적으로 재작성했습니다.")
