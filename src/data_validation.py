import pandas as pd


def load_data():
    users = pd.read_csv("data/users_sample.csv")
    projects = pd.read_csv("data/projects_sample.csv")
    timesheets = pd.read_csv("data/timesheets_sample.csv")

    return users, projects, timesheets


def validate_timesheets(timesheets):
    df = timesheets.copy()

    # 날짜 형식 확인
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 음수 또는 비정상적인 투입시간 확인
    df["invalid_minutes"] = (df["minutes"] < 0) | (df["minutes"] > 1440)

    # 동일 사용자·일자·프로젝트 중복 입력 확인
    df["duplicate_entry"] = df.duplicated(
        subset=["user_id", "date", "project_code"],
        keep=False
    )

    # 사용자별 일일 총 투입시간 계산
    daily_total = (
        df.groupby(["user_id", "date"], as_index=False)["minutes"]
        .sum()
        .rename(columns={"minutes": "daily_minutes"})
    )

    df = df.merge(daily_total, on=["user_id", "date"], how="left")

    # 하루 24시간을 초과하는 비정상 입력 확인
    df["invalid_daily_total"] = df["daily_minutes"] > 1440

    return df


if __name__ == "__main__":
    users, projects, timesheets = load_data()
    validated = validate_timesheets(timesheets)

    print(validated.head())
    print("\nValidation Summary")
    print("Invalid minutes:", validated["invalid_minutes"].sum())
    print("Duplicate entries:", validated["duplicate_entry"].sum())
    print("Invalid daily totals:", validated["invalid_daily_total"].sum())
