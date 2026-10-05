"""L1 수급 전망 — 코호트 회계모형 + 몬테카를로.

공급(t) = Σ_a,s 헌혈률(a,s) × 인구(a,s,t) × 적혈구 전환비 × (1 + 정책효과)
수요(t) = 2025년 적혈구 공급 × Σ_a,s 수혈가중치(a) × 인구(a,s,t) / (같은 식의 기준연도 값)

- 헌혈률(a,s)    = 연령·성별 헌혈 건수(05) ÷ 주민등록인구(13)
- 인구(a,s,t)    = 장래인구추계(12) 중위 / 빠른 고령화 / 느린 고령화
- 적혈구 전환비 = 2025년 적혈구 공급(02) ÷ 2025년 전국 헌혈 건수(05)
- 수혈가중치(a)  = 65세 미만 1, 65세 이상 k (심평원 17번 확보 전까지 가정, MC에서 k를 범위로 뽑음)

기준점: 2026년 중위 추계 인구에서 공급 = 수요 = 2025년 실제 적혈구 공급으로 놓고(그해 공급된 만큼 쓰였다고 가정),
이후의 상대 변화를 본다. 장래인구추계(외국인 포함)와 주민등록인구는 정의가 달라(15~39세 3.7% 차이)
두 인구를 섞어 비교하면 가짜 변화가 생기므로, 전망은 추계 인구끼리만 비교한다.
헌혈률은 연령·성별 사이의 상대 가중치로만 쓰인다.
"""
import re

import numpy as np
import pandas as pd

from build_processed import RBC_PARTS, read_raw, supply_annual_by_product

BASE_YEAR = 2025
YEARS = list(range(2026, 2041))
RATE_YEARS = [2022, 2023, 2024, 2025]  # MC에서 헌혈률을 뽑는 범위 (코로나 급감기 2020~2021 제외)
K_RANGE = (3.0, 6.0)  # 65세 이상 1인당 수혈량 / 65세 미만 (가정 — 17번 데이터로 대체 예정)
N_SIM = 2000
SEED = 42

# 헌혈 통계(05)의 연령 구간 → 인구 5세 구간 하한값 (16~19세는 15~19세 인구의 4/5로 근사)
DONOR_GROUPS = {
    "16~19세": {15: 0.8},
    "20~29세": {20: 1, 25: 1},
    "30~39세": {30: 1, 35: 1},
    "40~49세": {40: 1, 45: 1},
    "50~59세": {50: 1, 55: 1},
    "60세이상": {60: 1, 65: 1},  # 현행 상한 69세
}
SCENARIOS = {
    "중위": None,
    "빠른 고령화": "빠른 고령화",
    "느린 고령화": "느린 고령화",
}
SEXES = ["남자", "여자"]
POLICIES = {
    "현행": {},
    "ALT 검사 폐지": {"alt_abolish": True},
    "상한연령 74세 (보수)": {"upper_age": 74, "upper_mode": "decay"},
    "상한연령 74세 (낙관)": {"upper_age": 74, "upper_mode": "same"},
    "ALT 폐지 + 74세 (낙관)": {"alt_abolish": True, "upper_age": 74, "upper_mode": "same"},
}


# ---------- 데이터 읽기 ----------

def _age_lo(label: str):
    """'0 - 4세', '0-4세', '100+', '100세 이상' → 하한값. '계', '80세이상'(겹치는 합계 구간)은 None."""
    s = str(label).replace(" ", "")
    if s in ("계", "80세이상"):
        return None
    m = re.match(r"(\d+)", s)
    return int(m.group(1)) if m else None


def donations_by_age_sex() -> pd.DataFrame:
    """year, sex, group, n — 전국 연령·성별 헌혈 건수 (05)."""
    a = read_raw("05_donation_by_age_2005-2025.csv", header=[0, 1, 2])
    rows = a[(a.iloc[:, 0] == "합계") & (a.iloc[:, 1] == "소계") & a.iloc[:, 2].isin(SEXES)]
    recs = []
    for _, row in rows.iterrows():
        sex = row.iloc[2]
        for c, v in row.items():
            if c[2].startswith("실적") and c[1] in DONOR_GROUPS:
                recs.append((int(c[0].split(".")[0]), sex, c[1], float(v)))
    return pd.DataFrame(recs, columns=["year", "sex", "group", "n"])


def resident_pop() -> pd.DataFrame:
    """year, sex, age(5세 하한), pop — 주민등록인구 전국 (13)."""
    old = read_raw("13_resident_pop_2005-2010.csv")
    old = old[old.iloc[:, 1] == "전국"]
    old = old[old["항목"].isin(["남", "여"])]
    o = old.melt(id_vars=["시점", "항목"], value_vars=[c for c in old.columns[3:] if _age_lo(c) is not None],
                 var_name="label", value_name="pop")
    o = o.rename(columns={"시점": "year"})
    o["sex"] = o["항목"].map({"남": "남자", "여": "여자"})

    new = read_raw("13_resident_pop_2011-2025.csv")
    new = new[(new.iloc[:, 0] == "전국") & new["항목"].str.startswith(("남자", "여자"))]
    ycols = [c for c in new.columns if str(c).endswith(" 년")]
    n = new.melt(id_vars=["5세별", "항목"], value_vars=ycols, var_name="year", value_name="pop")
    n["year"] = n["year"].str[:4].astype(int)
    n["sex"] = n["항목"].str[:2]
    n = n.rename(columns={"5세별": "label"})

    out = pd.concat([o[["year", "sex", "label", "pop"]], n[["year", "sex", "label", "pop"]]])
    out["age"] = out["label"].map(_age_lo)
    out = out.dropna(subset=["age"])
    out["age"] = out["age"].astype(int)
    out["pop"] = pd.to_numeric(out["pop"])
    return out[["year", "sex", "age", "pop"]].reset_index(drop=True)


def projected_pop() -> pd.DataFrame:
    """scenario, year, sex, age, pop — 장래인구추계 (12)."""
    mid = read_raw("12_population_projection_2026-2040_mid.csv")
    mid = mid[mid["성별"].isin(SEXES)]
    m = mid.melt(id_vars=["성별", "연령별"], value_vars=[str(y) for y in YEARS], var_name="year", value_name="pop")
    m["scenario"] = "중위"

    sc = read_raw("12_population_projection_scenarios_2026-2040.csv")
    frames = [m]
    for name, key in SCENARIOS.items():
        if key is None:
            continue
        s = sc[sc["시나리오별"].str.startswith(key) & sc["성별"].isin(SEXES)]
        s = s.melt(id_vars=["성별", "연령별"], value_vars=[f"{y} 년" for y in YEARS], var_name="year", value_name="pop")
        s["scenario"] = name
        frames.append(s)
    out = pd.concat(frames)
    out["year"] = out["year"].astype(str).str[:4].astype(int)
    out["age"] = out["연령별"].map(_age_lo)
    out = out.dropna(subset=["age"])
    out["age"] = out["age"].astype(int)
    out = out.rename(columns={"성별": "sex"})
    out["pop"] = pd.to_numeric(out["pop"])
    return out[["scenario", "year", "sex", "age", "pop"]].reset_index(drop=True)


def alt_deferral_share(year: int = BASE_YEAR) -> float:
    """검사 부적격 중 간기능(ALT) 탈락 건수 ÷ 헌혈 건수 (07, 적십자사 기준 비율)."""
    t = read_raw("07_test_deferral_2005-2025.csv", header=[0, 1, 2])
    row = t.iloc[0]
    cols = {c[1]: row[c] for c in t.columns if str(c[0]).startswith(str(year))}
    return float(cols["간기능검사"]) / float(cols["총 검사수(헌혈실적)"])


# ---------- 헌혈률 ----------

def donor_pop(pop: pd.DataFrame, upper_age: int = 69) -> pd.DataFrame:
    """인구를 헌혈 연령 구간으로 묶는다. upper_age=74면 70~74세를 '70~74세' 구간으로 추가."""
    rows = []
    groups = dict(DONOR_GROUPS)
    if upper_age >= 74:
        groups["70~74세"] = {70: 1}
    for g, parts in groups.items():
        sub = pop[pop["age"].isin(parts)].copy()
        sub["pop"] = sub["pop"] * sub["age"].map(parts)
        keys = [c for c in pop.columns if c not in ("age", "pop")]
        agg = sub.groupby(keys, as_index=False)["pop"].sum()
        agg["group"] = g
        rows.append(agg)
    return pd.concat(rows, ignore_index=True)


def donation_rates() -> pd.DataFrame:
    """year, sex, group, n, pop, rate (1인당 연간 헌혈 건수)."""
    don = donations_by_age_sex()
    pop = donor_pop(resident_pop())
    out = don.merge(pop, on=["year", "sex", "group"])
    out["rate"] = out["n"] / out["pop"]
    return out


# ---------- 시뮬레이션 ----------

def simulate(scenario: str, rates: pd.DataFrame, proj: pd.DataFrame, base_pop: pd.DataFrame,
             upper_age: int = 69, alt_abolish: bool = False, upper_mode: str = "decay",
             n_sim: int = N_SIM, seed: int = SEED) -> dict:
    """한 인구 시나리오에 대해 공급·수요·수급비율의 MC 분포(연도 × 시뮬레이션)를 돌려준다."""
    rng = np.random.default_rng(seed)
    p = proj[proj["scenario"] == scenario]
    p_base = proj[(proj["scenario"] == "중위") & (proj["year"] == YEARS[0])]  # 모든 시나리오 공통 기준점

    # --- 공급: 2025년 헌혈률 × exp(오차), 오차 표준편차 = 2022~2025 연간 변화율(log)의 표준편차 ---
    piv = rates[rates["year"].isin(RATE_YEARS)].pivot_table(index=["sex", "group"], columns="year", values="rate")
    center = piv[BASE_YEAR].copy()
    sigma = np.log(piv).diff(axis=1).std(axis=1)
    if upper_age >= 74:
        # 70~74세 헌혈률 가정 — "decay"(보수): 50대→60대 감소 비율이 한 번 더 이어짐 / "same"(낙관): 60대와 같음
        for s in SEXES:
            r60 = center[(s, "60세이상")]
            center[(s, "70~74세")] = r60 ** 2 / center[(s, "50~59세")] if upper_mode == "decay" else r60
            sigma[(s, "70~74세")] = sigma[(s, "60세이상")]
    keys = list(center.index)
    draws = center.values * np.exp(rng.normal(0, sigma[keys].values, size=(n_sim, len(keys))))

    def donations_for(popdf, upper):
        dp = donor_pop(popdf, upper_age=upper).set_index(["year", "sex", "group"])["pop"]
        years = sorted(popdf["year"].unique())
        mat = np.array([[dp.get((y, s, g), 0.0) for (s, g) in keys] for y in years])
        return draws @ mat.T

    donations = donations_for(p, upper_age)                    # n_sim × 연도
    base_don = donations_for(p_base, 69)[:, 0]                 # 현행 기준 2026년 (정책 없음)

    don25_actual = rates[rates["year"] == BASE_YEAR]["n"].sum()
    rbc25 = supply_annual_by_product().query("year == @BASE_YEAR and product in @RBC_PARTS")["units"].sum()
    rbc_per_donation = rbc25 / don25_actual
    policy = 1 + (alt_deferral_share() if alt_abolish else 0)
    # 기준점(2026, 현행)의 공급을 2025년 실제 적혈구 공급에 맞춘다 → 인구 정의 차이(추계 vs 주민등록)를 지운다
    supply = rbc25 * donations / base_don[:, None] * policy
    donations_scaled = don25_actual * donations / base_don[:, None]

    # --- 수요: 65세 이상 가중치 k, 같은 기준점에서 2025년 공급량으로 맞춘다 ---
    k = rng.uniform(*K_RANGE, size=n_sim)
    def weighted(popdf):
        return popdf[popdf["age"] < 65]["pop"].sum(), popdf[popdf["age"] >= 65]["pop"].sum()
    yb, ob = weighted(p_base)
    w_base = yb + k * ob
    demand = np.empty((n_sim, len(YEARS)))
    for j, y in enumerate(YEARS):
        yg, od = weighted(p[p["year"] == y])
        demand[:, j] = rbc25 * (yg + k * od) / w_base
    donations = donations_scaled
    rate25 = center

    return {"supply": supply, "demand": demand, "ratio": supply / demand,
            "donations": donations, "rbc_per_donation": rbc_per_donation,
            "rbc25": rbc25, "don25": don25_actual, "rate25": rate25}


def summarize(sim: dict, qs=(0.05, 0.5, 0.95)) -> pd.DataFrame:
    rows = []
    for name in ("supply", "demand", "ratio", "donations"):
        q = np.quantile(sim[name], qs, axis=0)
        for j, y in enumerate(YEARS):
            rows.append({"var": name, "year": y, **{f"q{int(x * 100)}": q[i, j] for i, x in enumerate(qs)}})
    return pd.DataFrame(rows)


def run_all() -> dict:
    rates = donation_rates()
    proj = projected_pop()
    base = None
    out = {"rates": rates, "proj": proj, "sims": {}, "policy": {}}
    for sc in SCENARIOS:
        out["sims"][sc] = simulate(sc, rates, proj, base)
    for label, kw in POLICIES.items():
        out["policy"][label] = simulate("중위", rates, proj, base, **kw)
    return out


if __name__ == "__main__":
    res = run_all()
    for sc, sim in res["sims"].items():
        r = summarize(sim).query("var == 'ratio'").set_index("year")
        print(sc, r.loc[[2026, 2030, 2035, 2040], ["q5", "q50", "q95"]].round(3).to_dict("index"))
