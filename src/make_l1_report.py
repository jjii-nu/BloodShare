"""L1 수급 전망 보고서 — reports/l1_report.html + reports/figures/L1M_*.png

실행:  py src/make_l1_report.py            (끝나면 브라우저로 연다)
       py src/make_l1_report.py --no-open
"""
import sys
import webbrowser

import numpy as np
import matplotlib.pyplot as plt

import l1_model as M
from make_report import BLUE, DARK, FIG, GREY, REPORT, img, save  # 같은 그래프 스타일·저장 함수 사용

SC_COLORS = {"중위": BLUE, "빠른 고령화": "#c0504d", "느린 고령화": "#7a9a3a"}


def med(a, axis=0):
    return np.median(a, axis=axis)


def band(ax, x, arr, color, label, lw=2.5):
    lo, mid, hi = np.quantile(arr, [0.05, 0.5, 0.95], axis=0)
    ax.fill_between(x, lo, hi, color=color, alpha=0.15, lw=0)
    ax.plot(x, mid, color=color, lw=lw, label=label)
    return mid


# ---------- 그래프 ----------

def fig_rates(rates):
    r = rates[rates["year"] == M.BASE_YEAR].pivot(index="group", columns="sex", values="rate").loc[list(M.DONOR_GROUPS)]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = np.arange(len(r))
    ax.bar(x - 0.2, r["남자"] * 100, 0.38, color=BLUE, label="남자")
    ax.bar(x + 0.2, r["여자"] * 100, 0.38, color=GREY, label="여자")
    for i, (m, f) in enumerate(zip(r["남자"], r["여자"])):
        ax.text(i - 0.2, m * 100 + 0.6, f"{m * 100:.1f}", ha="center", fontsize=9)
        ax.text(i + 0.2, f * 100 + 0.6, f"{f * 100:.1f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([g.replace("세이상", "~69세") for g in r.index])
    ax.set_ylabel("인구 100명당 연간 헌혈 건수")
    top = r["남자"].idxmax()
    ax.set_title(f"{M.BASE_YEAR}년 헌혈률: {top.replace('세', '')}세 남자가 100명당 {r.loc[top, '남자'] * 100:.0f}건으로 가장 높다")
    ax.legend(frameon=False)
    return save(fig, "L1M_1_rates"), r


def fig_rate_trend(rates):
    t = rates.groupby(["year", "group"])[["n", "pop"]].sum()
    t = (t["n"] / t["pop"] * 100).unstack()[list(M.DONOR_GROUPS)]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    colors = {"16~19세": BLUE, "20~29세": "#8db6ea", "30~39세": GREY, "40~49세": DARK, "50~59세": "#888888", "60세이상": "#bbbbbb"}
    for g in t.columns:
        ax.plot(t.index, t[g], color=colors[g], lw=3 if g in ("16~19세", "40~49세") else 2, marker="o", ms=3)
    # 끝 라벨이 겹치지 않게 아래에서부터 최소 간격(1.6)을 두고 쌓는다
    last = t.iloc[-1].sort_values()
    pos, prev = {}, -np.inf
    for g, v in last.items():
        prev = max(v, prev + 1.6)
        pos[g] = prev
    for g, v in last.items():
        ax.text(t.index[-1] + 0.3, pos[g], f"{g} {v:.1f}", va="center", fontweight="bold")
    ax.set_xlim(t.index.min() - 0.5, t.index.max() + 3.5)
    ax.set_ylabel("인구 100명당 연간 헌혈 건수")
    ax.set_title("10대 헌혈률은 떨어지고, 40대 이상은 꾸준히 오르고 있다")
    return save(fig, "L1M_2_rate_trend"), t


def fig_population(proj):
    p = proj[proj["scenario"] == "중위"]
    dp = M.donor_pop(p).groupby(["year", "group"])["pop"].sum().unstack()[list(M.DONOR_GROUPS)]
    a, b = dp.loc[M.YEARS[0]], dp.loc[M.YEARS[-1]]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = np.arange(len(a))
    ax.bar(x - 0.2, a / 1e4, 0.38, color=GREY, label=str(M.YEARS[0]))
    ax.bar(x + 0.2, b / 1e4, 0.38, color=BLUE, label=str(M.YEARS[-1]))
    for i in range(len(a)):
        chg = (b.iloc[i] / a.iloc[i] - 1) * 100
        ax.text(i + 0.2, b.iloc[i] / 1e4 + 15, f"{chg:+.0f}%", ha="center", fontweight="bold",
                color=BLUE if chg < 0 else DARK)
    ax.set_xticks(x)
    ax.set_xticklabels([g.replace("세이상", "~69세") for g in a.index])
    ax.set_ylabel("인구 (만 명)")
    young = (b.iloc[:2].sum() / a.iloc[:2].sum() - 1) * 100
    ax.set_title(f"{M.YEARS[-1]}년까지 헌혈 주력층(16~29세)이 {abs(young):.0f}% 줄어든다 (중위 추계)")
    ax.legend(frameon=False)
    return save(fig, "L1M_3_population"), young


def fig_supply_demand(sim):
    fig, ax = plt.subplots(figsize=(11, 4.8))
    base = sim["rbc25"]
    s = band(ax, M.YEARS, sim["supply"] / base * 100, BLUE, "공급 (헌혈 → 적혈구)")
    d = band(ax, M.YEARS, sim["demand"] / base * 100, "#c0504d", "수요 (수혈)")
    ax.axhline(100, color="#999999", lw=1)
    ax.text(M.YEARS[-1] + 0.3, s[-1], f"공급 {s[-1]:.0f}", va="center", fontweight="bold", color=BLUE)
    ax.text(M.YEARS[-1] + 0.3, d[-1], f"수요 {d[-1]:.0f}", va="center", fontweight="bold", color="#c0504d")
    ax.set_xlim(M.YEARS[0] - 0.5, M.YEARS[-1] + 2.5)
    ax.set_xticks(range(M.YEARS[0], M.YEARS[-1] + 1, 2))
    ax.set_ylabel(f"{M.YEARS[0]}년 = 100")
    ax.set_title(f"공급은 {100 - s[-1]:.0f}% 줄고 수요는 {d[-1] - 100:.0f}% 늘어 {M.YEARS[-1]}년에 격차가 벌어진다 (중위)")
    ax.text(0.01, 0.03, "선 = 중앙값, 음영 = 90% 범위 (몬테카를로 2,000회)", transform=ax.transAxes, color="#666666")
    ax.legend(frameon=False, loc="upper left")
    return save(fig, "L1M_4_supply_demand"), s, d


def fig_ratio(sims):
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ends = {}
    for sc, sim in sims.items():
        m = band(ax, M.YEARS, sim["ratio"] * 100, SC_COLORS[sc], sc)
        ends[sc] = m[-1]
    pos, prev = {}, -np.inf
    for sc, v in sorted(ends.items(), key=lambda kv: kv[1]):
        prev = max(v, prev + 2.2)
        pos[sc] = prev
    for sc, v in ends.items():
        ax.text(M.YEARS[-1] + 0.3, pos[sc], f"{sc} {v:.0f}%", va="center", fontweight="bold", color=SC_COLORS[sc])
    ax.axhline(100, color="#999999", lw=1)
    ax.set_xlim(M.YEARS[0] - 0.5, M.YEARS[-1] + 3.5)
    ax.set_xticks(range(M.YEARS[0], M.YEARS[-1] + 1, 2))
    ax.set_ylabel("수요 대비 공급 (%)")
    ax.set_title(f"{M.YEARS[-1]}년 공급은 수요의 {min(ends.values()):.0f}~{max(ends.values()):.0f}% — 인구 시나리오가 달라도 결과는 비슷하다")
    ax.legend(frameon=False, loc="lower left")
    return save(fig, "L1M_5_ratio"), ends


def fig_policy(policy):
    labels = list(policy)
    gaps = [(1 - med(policy[k]["ratio"][:, -1])) * 100 for k in labels]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    y = np.arange(len(labels))[::-1]
    ax.barh(y, gaps, color=[GREY] + [BLUE] * (len(labels) - 1), height=0.55)
    for yi, g in zip(y, gaps):
        diff = g - gaps[0]
        ax.text(g + 0.6, yi, f"{g:.1f}%" + (f"  ({diff:+.1f}%p)" if diff else ""), va="center", fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel(f"{M.YEARS[-1]}년 적혈구 부족률 (수요 대비, %)")
    ax.set_xlim(0, max(gaps) + 12)
    ax.grid(axis="x", color="#e6e6e6")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"검토 중인 정책을 모두 써도 {M.YEARS[-1]}년 부족률은 {gaps[0]:.0f}% → {min(gaps):.0f}%로 조금 줄 뿐이다")
    return save(fig, "L1M_6_policy"), dict(zip(labels, gaps))


# ---------- 보고서 ----------

def build():
    res = M.run_all()
    rates, proj, sims, policy = res["rates"], res["proj"], res["sims"], res["policy"]
    mid = sims["중위"]

    p1, r25 = fig_rates(rates)
    p2, trend = fig_rate_trend(rates)
    p3, young = fig_population(proj)
    p4, s, d = fig_supply_demand(mid)
    p5, ends = fig_ratio(sims)
    p6, gaps = fig_policy(policy)

    y1 = M.YEARS[-1]
    ratio_mid = med(mid["ratio"][:, -1])
    gap_units = med(mid["demand"][:, -1] - mid["supply"][:, -1])
    extra_don = gap_units / mid["rbc_per_donation"]
    need_up = (1 / ratio_mid - 1) * 100
    first_10 = next((y for y, v in zip(M.YEARS, med(mid["ratio"])) if v < 0.9), None)
    # 수요가 고령화와 무관하게 인구에만 비례한다고 해도(k=1) 남는 부족
    p_mid = proj[proj["scenario"] == "중위"]
    pop_ratio = p_mid[p_mid["year"] == y1]["pop"].sum() / p_mid[p_mid["year"] == M.YEARS[0]]["pop"].sum()
    ratio_k1 = med(mid["supply"][:, -1]) / (mid["rbc25"] * pop_ratio)

    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>L1 수급 전망</title>
<style>
 body {{ font-family: 'Malgun Gothic', sans-serif; max-width: 980px; margin: 0 auto; padding: 24px 16px 64px; color: #222; background: #fff; line-height: 1.65; }}
 h1 {{ font-size: 26px; margin-bottom: 4px; }} h2 {{ margin-top: 44px; border-bottom: 2px solid #eee; padding-bottom: 6px; }}
 .muted {{ color: #777; }} .easy {{ background: #f3f7fd; border-left: 4px solid {BLUE}; padding: 12px 16px; border-radius: 4px; }}
 .warn {{ background: #fff6e8; border-left: 4px solid #e0a040; padding: 12px 16px; border-radius: 4px; }}
 img {{ width: 100%; height: auto; margin: 12px 0; }}
 table {{ border-collapse: collapse; margin: 12px 0; }} td, th {{ border: 1px solid #ddd; padding: 6px 12px; text-align: left; }} th {{ background: #f6f6f6; }}
 code {{ background: #f3f3f3; padding: 1px 4px; border-radius: 3px; }}
</style></head><body>
<h1>L1 수급 전망: 인구가 바뀌면 적혈구는 얼마나 모자랄까</h1>
<p class="muted">src/make_l1_report.py로 자동 생성 · 코호트 회계모형 + 몬테카를로 {M.N_SIM:,}회 · 전망 {M.YEARS[0]}–{y1}</p>

<p class="easy"><b>한 줄 요약:</b> 지금처럼 헌혈하면 {y1}년 적혈구 공급은 수요의 <b>{ratio_mid * 100:.0f}%</b>(중위 추계)에 그친다.
1년에 약 <b>{gap_units / 1e4:.0f}만 unit</b>이 모자라고, 이를 메우려면 헌혈이 연 <b>{extra_don / 1e4:.0f}만 건</b>
(지금보다 {need_up:.0f}%) 더 필요하다. 검토 중인 정책(ALT 검사 폐지, 헌혈 상한연령 74세)을 다 써도 부족률은
{gaps['현행']:.0f}%에서 {min(gaps.values()):.0f}%로 조금 줄어들 뿐이다.</p>

<h2>모형은 이렇게 생겼다</h2>
<table>
<tr><th>단계</th><th>계산</th><th>쓴 데이터</th></tr>
<tr><td>① 헌혈률</td><td>연령·성별 헌혈 건수 ÷ 연령·성별 인구 ({M.BASE_YEAR}년)</td><td>05 연령별 헌혈, 13 주민등록인구</td></tr>
<tr><td>② 미래 헌혈</td><td>헌혈률 × 미래 인구 (중위·빠른 고령화·느린 고령화)</td><td>12 장래인구추계</td></tr>
<tr><td>③ 공급</td><td>헌혈 건수 × 적혈구 전환비 ({mid['rbc_per_donation']:.3f} unit/건)</td><td>02 제제별 공급, 05</td></tr>
<tr><td>④ 수요</td><td>{M.BASE_YEAR}년 적혈구 공급 {mid['rbc25'] / 1e4:.0f}만 unit × 인구 변화 (65세 이상은 1인당 k배 사용)</td><td>12, 02</td></tr>
<tr><td>⑤ 불확실성</td><td>헌혈률(최근 연간 변동폭만큼)과 k를 무작위로 {M.N_SIM:,}번 뽑아 범위로 표시</td><td>05, 13</td></tr>
</table>
<p class="warn"><b>가정 하나 주의:</b> 연령별 수혈량 데이터(17번, 심평원)가 아직 없어서, 65세 이상이 65세 미만보다 1인당
<b>{M.K_RANGE[0]:.0f}~{M.K_RANGE[1]:.0f}배</b> 수혈받는다고 가정하고 그 범위에서 무작위로 뽑았다. 17번을 받으면 이 가정을 실제 값으로 바꾼다.
다만 이 가정을 빼고 <b>수요가 인구에만 비례한다고 해도</b>(k=1) {y1}년 공급은 수요의 {ratio_k1 * 100:.0f}%다. 공급 감소만으로도 부족은 생긴다.</p>

<h2>① 누가 얼마나 헌혈하나</h2>
{img(p1)}
<p class="easy"><b>쉽게 말하면:</b> 16~19세 남자는 100명당 1년에 {r25.loc['16~19세', '남자'] * 100:.0f}건, 60대 여자는 {r25.loc['60세이상', '여자'] * 100:.1f}건이다.
헌혈은 젊은 남자에게 크게 쏠려 있다. 그래서 젊은 인구가 줄면 헌혈이 바로 줄어든다.</p>

{img(p2)}
<p class="easy"><b>쉽게 말하면:</b> 다만 헌혈률 자체도 바뀌고 있다. 40대 헌혈률은 {trend.index.min()}년 {trend['40~49세'].iloc[0]:.1f}건에서
{trend.index.max()}년 {trend['40~49세'].iloc[-1]:.1f}건으로 올랐다(100명당). 이 모형은 {M.BASE_YEAR}년 헌혈률이 앞으로 유지된다고 본다.
40대 이상의 상승 추세가 계속된다면 공급 감소는 이보다 작을 수 있다.</p>

<h2>② 헌혈할 사람이 줄어든다</h2>
{img(p3)}
<p class="easy"><b>쉽게 말하면:</b> 저출산 세대가 헌혈 나이에 들어오면서, 헌혈을 가장 많이 하는 16~29세 인구가
{M.YEARS[0]}년부터 {y1}년까지 {abs(young):.0f}% 줄어든다. 반면 헌혈률이 낮은 50~60대는 늘어난다.</p>

<h2>③ 공급은 줄고 수요는 는다</h2>
{img(p4)}
<p class="easy"><b>쉽게 말하면:</b> {M.YEARS[0]}년을 100으로 놓으면 {y1}년 공급은 {s[-1]:.0f}, 수요는 {d[-1]:.0f}이다.
공급이 줄어드는 건 젊은 헌혈자가 줄기 때문이고, 수요가 느는 건 수혈을 많이 받는 노인이 늘기 때문이다.</p>

<h2>④ 인구 시나리오별 수급 비율</h2>
{img(p5)}
<p class="easy"><b>쉽게 말하면:</b> 빠른 고령화든 느린 고령화든 {y1}년 공급은 수요의
{min(ends.values()):.0f}~{max(ends.values()):.0f}%로 비슷하다. {y1}년까지 헌혈 나이에 들어올 사람은 이미 태어나 있어서,
출산율 가정이 달라도 결과가 크게 바뀌지 않는다. 중위 추계에서는 <b>{first_10}년</b>에 처음으로 공급이 수요의 90% 아래로 떨어진다.</p>

<h2>⑤ 정책을 쓰면 얼마나 나아지나</h2>
{img(p6)}
<table>
<tr><th>정책</th><th>어떻게 넣었나</th><th>{y1}년 부족률</th></tr>
<tr><td>현행</td><td>16~69세, ALT 검사 유지</td><td>{gaps['현행']:.1f}%</td></tr>
<tr><td>ALT 검사 폐지</td><td>{M.BASE_YEAR}년 간기능(ALT) 탈락 비율 {M.alt_deferral_share() * 100:.2f}%만큼 공급 증가 (07번)</td><td>{gaps['ALT 검사 폐지']:.1f}%</td></tr>
<tr><td>상한연령 74세 (보수)</td><td>70~74세 헌혈률 = 60대 × (60대 ÷ 50대)</td><td>{gaps['상한연령 74세 (보수)']:.1f}%</td></tr>
<tr><td>상한연령 74세 (낙관)</td><td>70~74세 헌혈률 = 60대와 같음</td><td>{gaps['상한연령 74세 (낙관)']:.1f}%</td></tr>
<tr><td>ALT 폐지 + 74세 (낙관)</td><td>둘 다</td><td>{gaps['ALT 폐지 + 74세 (낙관)']:.1f}%</td></tr>
</table>
<p class="easy"><b>쉽게 말하면:</b> 두 정책 모두 방향은 맞지만 효과가 작다. 60대 헌혈률이 이미 낮아서 70대까지 열어도
더해지는 헌혈이 적고, ALT 탈락은 헌혈의 1%도 안 된다. 부족을 메우려면 헌혈률 자체를 {need_up:.0f}% 끌어올려야 한다.
40~60대 헌혈 참여를 늘리는 정책(직장 단체헌혈 등)이나, 수요 쪽 관리(환자혈액관리, PBM)가 함께 필요하다.</p>

<h2>한계와 다음 단계</h2>
<ul>
<li><b>수요 연령 가중치(k)가 가정이다.</b> 심평원 연령별 수혈 통계(17번)를 받으면 실제 연령별 수혈률로 바꾼다.</li>
<li><b>헌혈률이 {M.BASE_YEAR}년 수준으로 유지된다고 본다.</b> 40대 이상 상승 추세를 이어가는 시나리오를 추가할 수 있다.</li>
<li><b>16~19세 인구는 15~19세 인구의 4/5로 근사했다.</b> 60세 이상 헌혈은 60~69세 인구로 나눴다(현행 상한 69세).</li>
<li><b>{M.BASE_YEAR}년에 공급 = 수요라고 가정했다.</b> 실제로는 재고가 부족한 날이 많았으므로(L2 분석), 출발점부터 수요가 더 클 수 있다.</li>
<li>신규·재헌혈자 구분(14번)과 채혈 전 적합률(06번)은 확장 모형에서 쓸 예정이다.</li>
</ul>
</body></html>"""
    out = REPORT / "l1_report.html"
    out.write_text(html, encoding="utf-8")
    print(f"보고서: {out}")
    return out


if __name__ == "__main__":
    report = build()
    if "--no-open" not in sys.argv:
        webbrowser.open(report.as_uri())
