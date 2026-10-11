import pandas as pd

STANDARD_DAILY_MINUTES = 8 * 60

GENERAL_WORK_CODE = "GENERAL"
LEAVE_CODE = "LEAVE"


def load_timesheet_data():
    timesheets = pd.read_csv("data/timesheets_sample.csv")
    users = pd.read_csv("data/users_sample.csv")

    timesheets["date"] = pd.to_datetime(timesheets["date"])

    return timesheets, users


def calculate_daily_metrics(timesheets):
    df = timesheets.copy()

    # 시간 단위 변환
    df["hours"] = df["minutes"] / 60

    # 일반업무 / 연차 구분
    df["general_minutes"] = df["minutes"].where(
        df["project_code"] == GENERAL_WORK_CODE, 0
    )

    df["leave_minutes"] = df["minutes"].where(
        df["project_code"] == LEAVE_CODE, 0
    )

    df["project_minutes"] = df["minutes"].where(
        ~df["project_code"].isin([GENERAL_WORK_CODE, LEAVE_CODE]), 0
    )

    # 사용자별 일일 집계
    daily = (
        df.groupby(["user_id", "date"], as_index=False)
        .agg(
            total_minutes=("minutes", "sum"),
            project_minutes=("project_minutes", "sum"),
            general_minutes=("general_minutes", "sum"),
            leave_minutes=("leave_minutes", "sum"),
        )
    )

    # 기본 가용시간: 8시간
    daily["available_minutes"] = STANDARD_DAILY_MINUTES

    # 연차 사용 시간만큼 가용시간 차감
    daily["available_minutes"] = (
        daily["available_minutes"] - daily["leave_minutes"]
    ).clip(lower=0)

    # OT: 일일 총 근무시간이 8시간을 초과한 경우
    daily["overtime_minutes"] = (
        daily["total_minutes"] - STANDARD_DAILY_MINUTES
    ).clip(lower=0)

    # 가동률:
    # 일반업무·연차를 제외한 프로젝트 투입시간 / 가용시간
    daily["utilization"] = daily.apply(
        lambda row: (
            row["project_minutes"] / row["available_minutes"]
            if row["available_minutes"] > 0
            else 0
        ),
        axis=1,
    )

    daily["utilization_pct"] = (daily["utilization"] * 100).round(1)

    # 보기 편한 시간 단위 컬럼
    daily["project_hours"] = (daily["project_minutes"] / 60).round(2)
    daily["general_hours"] = (daily["general_minutes"] / 60).round(2)
    daily["leave_hours"] = (daily["leave_minutes"] / 60).round(2)
    daily["available_hours"] = (daily["available_minutes"] / 60).round(2)
    daily["overtime_hours"] = (daily["overtime_minutes"] / 60).round(2)

    return daily


def add_organization_info(daily, users):
    result = daily.merge(
        users[["user_id", "name", "team", "part", "tft"]],
        on="user_id",
        how="left",
    )

    return result


def summarize_by_team(result):
    team_summary = (
        result.groupby("team", as_index=False)
        .agg(
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


if __name__ == "__main__":
    timesheets, users = load_timesheet_data()

    daily = calculate_daily_metrics(timesheets)
    result = add_organization_info(daily, users)
    team_summary = summarize_by_team(result)

    print("\nDaily Utilization")
    print(
        result[
            [
                "date",
                "name",
                "team",
                "project_hours",
                "general_hours",
                "leave_hours",
                "available_hours",
                "overtime_hours",
                "utilization_pct",
            ]
        ].head(20)
    )

    print("\nTeam Summary")
    print(team_summary)
