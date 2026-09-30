"""L1·L2 탐색 분석 — 보고서에 들어가는 모든 숫자를 원본에서 계산한다.

build_processed.py의 가공 함수를 그대로 쓰므로, raw 파일만 있으면 결과가 재현된다.
"""
import pandas as pd

from build_processed import (inventory_daily_rbc, read_raw, rbc_days_of_supply,
                             supply_annual_by_product)

SHORTAGE = 3.0  # 이 보고서에서 "부족" = 보유일수 3일 미만 (주의 단계)
AGE_ORDER = ["16~19세", "20~29세", "30~39세", "40~49세", "50~59세", "60세이상"]
JOBS = ["고등학생", "대학생", "군인", "회사원"]
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


# ---------- L1 ----------

def donations_by_age() -> pd.DataFrame:
    """행 = 연도, 열 = 연령대, 값 = 헌혈 건수 (전국 합계)."""
    a = read_raw("05_donation_by_age_2005-2025.csv", header=[0, 1, 2])
    row = a[(a.iloc[:, 0] == "합계") & (a.iloc[:, 1] == "소계") & (a.iloc[:, 2] == "계")].iloc[0]
    recs = [(int(c[0].split(".")[0]), c[1], float(v)) for c, v in row.items()
            if c[2].startswith("실적") and c[1] in AGE_ORDER]
    df = pd.DataFrame(recs, columns=["year", "age", "n"])
    return df.pivot(index="year", columns="age", values="n")[AGE_ORDER]


def donations_by_job() -> pd.DataFrame:
    """행 = 연도, 열 = 직업 (JOBS), 값 = 헌혈 건수."""
    j = read_raw("08_donation_by_job_2005-2025.csv")
    j = j[(j["성별"] == "계") & (j["혈액원별"] == "합계") & j["항목"].str.startswith("실적")]
    j = j.set_index("직업별")[[c for c in j.columns if "년" in c]]
    j.columns = [int(c[:4]) for c in j.columns]
    return j.loc[JOBS].T.astype(float)


def donors() -> pd.DataFrame:
    """year, donations(총 헌혈 건수), donors(헌혈자 실인원), per_donor."""
    d = read_raw("09_donors_2005-2025.csv")
    out = pd.DataFrame({"year": d.iloc[:, 0].astype(int),
                        "donations": d.iloc[:, 1].astype(float),
                        "donors": d.iloc[:, 6].astype(float)})
    out["per_donor"] = out["donations"] / out["donors"]
    return out.set_index("year")


# ---------- L2 ----------

def rbc_dos() -> pd.DataFrame:
    """2006~2025 적혈구 일별 보유일수 (2005는 원자료 오류로 불완전해서 제외)."""
    d = rbc_days_of_supply(inventory_daily_rbc(), supply_annual_by_product())
    return d[d["date"].dt.year >= 2006].reset_index(drop=True)


def yearly_dos(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby(d["date"].dt.year)["days_of_supply"]
    return pd.DataFrame({"mean": g.mean(), "min": g.min(), "max": g.max(),
                         "below5": g.apply(lambda s: (s < 5).sum()),
                         "below3": g.apply(lambda s: (s < 3).sum())})


def shortage_by_month(d: pd.DataFrame) -> pd.Series:
    """월별로 부족(3일 미만)이었던 날의 비율 (%)."""
    return d.groupby(d["date"].dt.month)["days_of_supply"].apply(lambda s: (s < SHORTAGE).mean() * 100)


def change_by_weekday(d: pd.DataFrame) -> pd.Series:
    """요일별 '전날 대비 재고 변화' 평균 (unit). 인덱스 = 월~일."""
    chg = d["rbc_units"].diff()
    out = chg.groupby(d["date"].dt.dayofweek).mean()
    out.index = WEEKDAYS
    return out


def persistence(d: pd.DataFrame, horizons=(7, 14)) -> pd.DataFrame:
    """오늘 부족/정상일 때 h일 뒤에도 부족할 확률 (%)."""
    now = d["days_of_supply"] < SHORTAGE
    rows = {}
    for h in horizons:
        later = now.shift(-h)
        valid = later.notna()
        rows[f"{h}일 뒤"] = {
            "오늘 부족": later[now & valid].astype(bool).mean() * 100,
            "오늘 정상": later[~now & valid].astype(bool).mean() * 100,
        }
    return pd.DataFrame(rows)


def shortage_spells(d: pd.DataFrame) -> pd.Series:
    """연속된 부족 구간의 길이(일) 목록."""
    now = d["days_of_supply"] < SHORTAGE
    spell_id = (now != now.shift()).cumsum()
    return now[now].groupby(spell_id[now]).size()
