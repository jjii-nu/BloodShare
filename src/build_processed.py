"""KOSIS 원본(data/raw) → 분석용 tidy 테이블(data/processed).

실행:  py src/build_processed.py

원본 특이사항 (2026-10-01 확인):
- 모든 파일 CP949 인코딩, 결측은 '-'.
- 03 일별 보유 추이는 '농축적혈구' 재고다. 월평균이 04의 농축적혈구와 2006~2025 전 월에서 일치한다(아래 check).
- 03의 2005년 열은 02/29~12/31(307일)이 2016년 값과 동일하다. 원표 복사 오류로 보고 2005-03-01 이후를 제외한다.
"""
import calendar
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

# 적혈구 소요량 = 적혈구 계열 3종 공급 합 (대한적십자사 공표 소요량과 일치하는 정의)
RBC_PARTS = ["농축적혈구", "세척적혈구", "백혈구여과제거적혈구"]
SHORTAGE_DAYS = 5.0


def read_raw(name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(RAW / name, encoding="cp949", na_values=["-"], **kw)


def inventory_daily_rbc() -> pd.DataFrame:
    """date, rbc_units (농축적혈구 일별 재고)."""
    d = read_raw("03_inventory_daily_2005-2025.csv")
    d = d.melt(id_vars=d.columns[0], var_name="year", value_name="rbc_units")
    md = d.iloc[:, 0].str.extract(r"(\d+)월 (\d+)일")
    d["date"] = pd.to_datetime(
        d["year"] + "-" + md[0] + "-" + md[1], format="%Y-%m-%d", errors="coerce"
    )
    d = d.dropna(subset=["date"])  # 평년의 02/29 제거
    d = d[~((d["date"].dt.year == 2005) & (d["date"] >= "2005-03-01"))]
    return d[["date", "rbc_units"]].dropna().sort_values("date").reset_index(drop=True)


def inventory_monthly_by_product() -> pd.DataFrame:
    """month, product, avg_units."""
    m = read_raw("04_inventory_monthly_by_product_2005-2025.csv", header=[0, 1])
    m = m.set_index(m.columns[0])
    m.index = m.index.str.replace("월", "").astype(int)
    m.columns = pd.MultiIndex.from_tuples([(y.split(".")[0], p) for y, p in m.columns])
    long = m.stack(level=[0, 1], future_stack=True).reset_index()
    long.columns = ["mon", "year", "product", "avg_units"]
    long["month"] = long["year"] + "-" + long["mon"].astype(str).str.zfill(2)
    return long[["month", "product", "avg_units"]].dropna().sort_values(["month", "product"])


def supply_annual_by_product() -> pd.DataFrame:
    """year, product, units (전국, 수혈용량 합계). product ∈ RBC_PARTS + 농축혈소판, 성분채혈혈소판, 신선동결혈장."""
    s = read_raw("02_supply_by_product_2005-2024.csv")
    s = s[(s["수혈용량별"] == "합계") & (s["혈액원별"] == "합계") & s["항목"].str.startswith("혈액량")]
    s = s.melt(id_vars="제제별", value_vars=[c for c in s.columns if "년" in c],
               var_name="year", value_name="units")
    s["year"] = s["year"].str[:4].astype(int)
    s["product"] = s["제제별"].replace({"백혈구여과제거성분채혈 혈소판제제": "성분채혈혈소판"})
    old = s[["year", "product", "units"]]

    n = read_raw("02_supply_by_product_2025.csv", header=[0, 1, 2, 3, 4])
    row = n[(n.iloc[:, 0] == "합계") & (n.iloc[:, 1] == "합계")].iloc[0]
    vals = {c[1:4]: v for c, v in row.items() if "혈액량" in str(c[4])}
    new = {
        "농축적혈구": vals[("전혈유래제제", "적혈구", "농축적혈구")],
        "세척적혈구": vals[("전혈유래제제", "적혈구", "세척적혈구")],
        "백혈구여과제거적혈구": vals[("전혈유래제제", "적혈구", "백혈구여과제거적혈구")],
        "농축혈소판": vals[("전혈유래제제", "혈소판", "농축혈소판")],
        "신선동결혈장": vals[("전혈유래제제", "혈장", "신선동결혈장")],
        "성분채혈혈소판": vals[("성분채혈제제", "백혈구여과제거혈소판", "소계")]
        + vals[("성분채혈제제", "세척혈소판", "소계")],
    }
    new = pd.DataFrame({"year": 2025, "product": list(new), "units": list(new.values())})

    keep = RBC_PARTS + ["농축혈소판", "성분채혈혈소판", "신선동결혈장"]
    out = pd.concat([old, new])
    out = out[out["product"].isin(keep)]
    out["units"] = pd.to_numeric(out["units"]).fillna(0)
    return out.sort_values(["year", "product"]).reset_index(drop=True)


def rbc_days_of_supply(daily: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    """보유일수 = 재고 ÷ (해당 연도 적혈구 공급 ÷ 연간 일수)."""
    rbc = supply[supply["product"].isin(RBC_PARTS)].groupby("year")["units"].sum()
    days = pd.Series({y: 366 if calendar.isleap(y) else 365 for y in rbc.index})
    demand = (rbc / days).rename("daily_demand")
    out = daily.assign(year=daily["date"].dt.year).join(demand, on="year")
    out["days_of_supply"] = out["rbc_units"] / out["daily_demand"]
    out["shortage"] = out["days_of_supply"] < SHORTAGE_DAYS
    return out.drop(columns="year")


def check_daily_is_rbc(daily: pd.DataFrame, monthly: pd.DataFrame) -> float:
    """일별 재고의 월평균 ÷ 04 농축적혈구 월평균 (2006~) — 1.0이어야 한다."""
    dm = daily.groupby(daily["date"].dt.strftime("%Y-%m"))["rbc_units"].mean()
    rbc = monthly[monthly["product"] == "농축적혈구"].set_index("month")["avg_units"]
    ratio = (dm / rbc).dropna()
    return ratio[ratio.index >= "2006"].agg(["min", "max"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    daily = inventory_daily_rbc()
    monthly = inventory_monthly_by_product()
    supply = supply_annual_by_product()
    dos = rbc_days_of_supply(daily, supply)

    lo, hi = check_daily_is_rbc(daily, monthly)
    assert abs(lo - 1) < 0.01 and abs(hi - 1) < 0.01, (lo, hi)

    for name, df in [("inventory_daily_rbc", daily), ("inventory_monthly_by_product", monthly),
                     ("supply_annual_by_product", supply), ("rbc_days_of_supply", dos)]:
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"{name}: {len(df)} rows")


if __name__ == "__main__":
    main()
