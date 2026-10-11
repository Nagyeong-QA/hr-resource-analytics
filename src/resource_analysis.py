import pandas as pd

from utilization import (
    load_timesheet_data,
    calculate_daily_metrics,
    add_organization_info,
)


def load_project_data():
    projects = pd.read_csv("data/projects_sample.csv")
    return projects


def summarize_by_team(result):
    team_summary = (
        result.groupby("team", as_index=False)
        .agg(
            headcount=("user_id", "nunique"),
            avg_utilization_pct=("utilization_pct", "mean"),
            total_project_hours=("project_hours", "sum"),
            total_general_hours=("general_hours", "sum"),
            total_overtime_hours=("overtime_hours", "sum"),
        )
    )

    team_summary["avg_utilization_pct"] = (
        team_summary["avg_utilization_pct"].round(1)
    )

    return team_summary


def summarize_by_user(result):
    user_summary = (
        result.groupby(
            ["user_id", "name", "team", "part"],
            as_index=False
        )
        .agg(
            avg_utilization_pct=("utilization_pct", "mean"),
            total_project_hours=("project_hours", "sum"),
            total_general_hours=("general_hours", "sum"),
            total_leave_hours=("leave_hours", "sum"),
            total_overtime_hours=("overtime_hours", "sum"),
        )
    )

    user_summary["avg_utilization_pct"] = (
        user_summary["avg_utilization_pct"].round(1)
    )

    return user_summary


def summarize_by_project(timesheets, projects, users):
    df = timesheets.copy()

    df = df[
        ~df["project_code"].isin(["GENERAL", "LEAVE"])
    ].copy()

    df["project_hours"] = df["minutes"] / 60

    project_summary = (
        df.groupby("project_code", as_index=False)
        .agg(
            total_project_hours=("project_hours", "sum"),
            assigned_people=("user_id", "nunique"),
        )
    )

    project_summary = project_summary.merge(
        projects[
            [
                "project_code",
                "project_name",
                "start_date",
                "end_date",
                "active",
            ]
        ],
        on="project_code",
        how="left",
    )

    return project_summary


def calculate_allocation_by_user(timesheets, users, projects):
    df = timesheets.copy()

    df = df[
        ~df["project_code"].isin(["GENERAL", "LEAVE"])
    ].copy()

    df["project_hours"] = df["minutes"] / 60

    allocation = (
        df.groupby(
            ["user_id", "project_code"],
            as_index=False
        )
        .agg(
            project_hours=("project_hours", "sum")
        )
    )

    total_by_user = (
        allocation.groupby("user_id", as_index=False)
        .agg(
            total_project_hours=("project_hours", "sum")
        )
    )

    allocation = allocation.merge(
        total_by_user,
        on="user_id",
        how="left",
    )

    allocation["allocation_pct"] = (
        allocation["project_hours"]
        / allocation["total_project_hours"]
        * 100
    ).round(1)

    allocation = allocation.merge(
        users[
            ["user_id", "name", "team", "part"]
        ],
        on="user_id",
        how="left",
    )

    allocation = allocation.merge(
        projects[
            ["project_code", "project_name"]
        ],
        on="project_code",
        how="left",
    )

    return allocation


def identify_resource_signals(user_summary):
    df = user_summary.copy()

    df["resource_signal"] = "Normal"

    df.loc[
        df["avg_utilization_pct"] >= 100,
        "resource_signal"
    ] = "High Utilization"

    df.loc[
        df["avg_utilization_pct"] < 70,
        "resource_signal"
    ] = "Low Utilization"

    df.loc[
        df["total_overtime_hours"] >= 5,
        "resource_signal"
    ] = "Check Overtime"

    return df


if __name__ == "__main__":
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

    print("\n=== Team Summary ===")
    print(team_summary)

    print("\n=== User Summary ===")
    print(user_summary)

    print("\n=== Project Summary ===")
    print(project_summary)

    print("\n=== User Allocation ===")
    print(allocation)

    print("\n=== Resource Signals ===")
    print(
        resource_signals[
            [
                "name",
                "team",
                "avg_utilization_pct",
                "total_overtime_hours",
                "resource_signal",
            ]
        ]
    )
