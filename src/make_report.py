"""원본 데이터 → 가공 테이블 → 그래프 → 보고서(HTML)까지 한 번에 만든다.

실행:  py src/make_report.py            (끝나면 브라우저로 보고서를 연다)
       py src/make_report.py --no-open  (열지 않음)

결과:
  reports/report.html      그래프와 설명이 들어간 보고서 (파일 하나로 완결, 공유 가능)
  reports/figures/*.png    그래프 그림 (발표 자료에 붙여 넣기용)
"""
import base64
import sys
import webbrowser
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import analysis as A  # noqa: E402
import build_processed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports"
FIG = REPORT / "figures"

BLUE = "#2a78d6"
GREY = "#c4c3b9"
DARK = "#555555"
GREEN = "#59b86a"
RED = "#dc7070"

plt.rcParams.update({
    "font.family": "Malgun Gothic",  # 윈도우 기본 한글 글꼴
    "axes.unicode_minus": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#e6e6e6", "axes.axisbelow": True,
    "axes.titlesize": 14, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "figure.dpi": 110,
})


def save(fig, name: str) -> Path:
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def fmt_man(n: float) -> str:
    return f"{round(n / 10000):,}만"


# ---------- 그래프 ----------

def fig_age(age):
    share = age.div(age.sum(axis=1), axis=0) * 100
    young = share["16~19세"] + share["20~29세"]
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = [BLUE, "#8db6ea", "#a9a89f", "#c4c3b9", "#dcdbd4", "#eeede8"]
    bottom = 0
    for col, c in zip(A.AGE_ORDER, colors):
        ax.bar(share.index, share[col], bottom=bottom, color=c, width=0.75,
               label=col.replace("이상", " 이상"))
        bottom = bottom + share[col]
    for yr in (share.index.min(), 2014, share.index.max()):
        ax.text(yr, young[yr] + 1.5, f"{young[yr]:.0f}%", ha="center", fontweight="bold")
    first, last = share.index.min(), share.index.max()
    ax.set_title(f"헌혈의 주력인 10·20대 비중이 {young[first]:.0f}%에서 {young[last]:.0f}%로 줄었다")
    ax.set_ylabel("그해 전체 헌혈 중 비중 (%)")
    ax.set_ylim(0, 100)
    ax.set_xticks(share.index)
    ax.set_xticklabels([f"'{str(y)[2:]}" for y in share.index])
    ax.legend(ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False)
    return save(fig, "L1_1_age_share"), young


def fig_job(job):
    fig, ax = plt.subplots(figsize=(11, 5))
    style = {"고등학생": (BLUE, 1, 3), "군인": (BLUE, 0.45, 2),
             "대학생": (GREY, 1, 2), "회사원": (DARK, 1, 3)}
    nudge = {"군인": 1.5, "고등학생": -1.5}
    for j in A.JOBS:
        c, a, w = style[j]
        ax.plot(job.index, job[j] / 1e4, color=c, alpha=a, lw=w, marker="o", ms=3)
        last = job[j].iloc[-1]
        ax.text(job.index[-1] + 0.4, last / 1e4 + nudge.get(j, 0), f"{j} {fmt_man(last)}",
                va="center", fontweight="bold")
    hs = job["고등학생"]
    ax.annotate(f"{fmt_man(hs.max())} ({hs.idxmax()})", (hs.idxmax(), hs.max() / 1e4),
                xytext=(0, 10), textcoords="offset points", ha="center", color=BLUE, fontweight="bold")
    ax.set_title("고등학생 헌혈은 절반 아래로, 회사원 헌혈은 크게 늘었다")
    ax.set_ylabel("연간 헌혈 건수 (만 건)")
    ax.set_ylim(0, 110)
    ax.set_xlim(job.index.min() - 0.5, job.index.max() + 4)
    return save(fig, "L1_2_job")


def fig_donors(dn):
    idx = dn / dn.iloc[0] * 100
    fig, ax = plt.subplots(figsize=(11, 5))
    last = dn.iloc[-1]
    lines = [
        ("per_donor", DARK, 2.5, f"1인당 {last.per_donor:.2f}회"),
        ("donations", GREY, 2.5, f"총 헌혈 {fmt_man(last.donations)} 건"),
        ("donors", BLUE, 3, f"헌혈자 {fmt_man(last.donors)} 명"),
    ]
    for col, c, w, label in lines:
        ax.plot(idx.index, idx[col], color=c, lw=w, marker="o", ms=3)
        chg = idx[col].iloc[-1] - 100
        ax.text(idx.index[-1] + 0.4, idx[col].iloc[-1], f"{label} ({chg:+.0f}%)", va="center", fontweight="bold")
    ax.axhline(100, color="#999999", lw=1)
    peak = dn["donors"].idxmax()
    ax.annotate(f"최고 {fmt_man(dn.donors[peak])} 명 ({peak})", (peak, idx.donors[peak]),
                xytext=(0, -45), textcoords="offset points", ha="center", color=BLUE, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    d_don = idx["donors"].iloc[-1] - 100
    d_per = idx["per_donor"].iloc[-1] - 100
    ax.set_title(f"헌혈하는 사람은 {abs(d_don):.0f}% 줄었지만, 한 사람이 {d_per:.0f}% 더 자주 헌혈한다")
    ax.set_ylabel(f"{dn.index[0]}년 = 100")
    ax.set_xlim(dn.index.min() - 0.5, dn.index.max() + 6)
    ax.set_xticks(range(dn.index.min(), dn.index.max() + 1, 5))
    return save(fig, "L1_3_donors"), d_don, d_per


def fig_yearly_dos(yd):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.vlines(yd.index, yd["min"], yd["max"], color=GREY, lw=3)
    ax.scatter(yd.index, yd["mean"], color=BLUE, s=45, zorder=3)
    ax.axhline(5, color="#888888", ls="--", lw=1.2)
    ax.axhline(3, color="#888888", ls=":", lw=1.5)
    ax.text(yd.index.max() + 0.7, 5, "5일 · 관심", va="center", color="#666666")
    ax.text(yd.index.max() + 0.7, 3, "3일 · 주의", va="center", color="#666666")
    under = int((yd["mean"] < 5).sum())
    ax.set_title(f"적혈구 보유일수: {len(yd)}년 중 {under}년은 연평균이 5일 미만")
    ax.set_ylabel("보유일수 (일)  · 점 = 연평균, 세로선 = 최저~최고")
    ax.set_ylim(0, 13)
    ax.set_xlim(yd.index.min() - 0.7, yd.index.max() + 2)
    ax.set_xticks(yd.index)
    ax.set_xticklabels([f"'{str(y)[2:]}" for y in yd.index])
    return save(fig, "L2_0_yearly_dos"), under


def fig_month(pm):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    top3 = pm.nlargest(3).index
    ax.bar(pm.index, pm.values, color=[BLUE if m in top3 else GREY for m in pm.index], width=0.6)
    for m, v in pm.items():
        ax.text(m, v + 0.6, f"{v:.1f}%", ha="center", fontweight="bold" if m in top3 else "normal")
    names = "·".join(f"{m}월" for m in top3)
    ax.set_title(f"{names}에 가장 자주 부족하고, {pm.idxmin()}월은 거의 없다")
    ax.set_ylabel("3일 미만이었던 날의 비율 (%)")
    ax.set_xticks(pm.index)
    ax.set_xticklabels([f"{m}월" for m in pm.index])
    return save(fig, "L2_1_month"), top3


def fig_weekday(wd):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.bar(wd.index, wd.values, color=[GREEN if v > 0 else RED for v in wd.values], width=0.55, alpha=0.8)
    for k, v in wd.items():
        ax.text(k, v + (60 if v > 0 else -60), f"{v:+,.0f}", ha="center",
                va="bottom" if v > 0 else "top", fontweight="bold")
    ax.axhline(0, color="#999999", lw=1)
    ax.set_title("평일에는 매일 재고가 줄고, 토·일에 다시 채워진다")
    ax.set_ylabel("전날 대비 평균 재고 변화 (unit)")
    ax.set_ylim(wd.min() - 350, wd.max() + 300)
    ax.text(0.99, 0.97, "초록 = 증가, 빨강 = 감소", transform=ax.transAxes, ha="right", va="top", color="#666666")
    return save(fig, "L2_2_weekday")


def fig_threshold(yd):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    w = 0.38
    ax.bar(yd.index - w / 2, yd["below5"], w, color=GREY, label="5일 미만")
    ax.bar(yd.index + w / 2, yd["below3"], w, color=BLUE, label="3일 미만")
    ax.axhline(365, color="#888888", ls="--", lw=1)
    ax.text(yd.index.max() + 0.8, 365, "365일", va="center", color="#666666")
    ax.set_title(f"5일 기준이면 거의 매일 결핍, 3일 기준은 연 {yd.below3.min()}~{yd.below3.max()}일")
    ax.set_ylabel("기준 미만이었던 날 수 (일/년)")
    ax.set_xticks(yd.index)
    ax.set_xticklabels([f"'{str(y)[2:]}" for y in yd.index])
    ax.legend(frameon=False, loc="upper left")
    return save(fig, "L2_4_threshold")


# ---------- 보고서 ----------

def img(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{path.stem}">'


def build():
    build_processed.main()

    age, job, dn = A.donations_by_age(), A.donations_by_job(), A.donors()
    d = A.rbc_dos()
    yd = A.yearly_dos(d)
    pm = A.shortage_by_month(d)
    wd = A.change_by_weekday(d)
    ps = A.persistence(d)
    spells = A.shortage_spells(d)

    p_age, young = fig_age(age)
    p_job = fig_job(job)
    p_don, d_don, d_per = fig_donors(dn)
    p_year, under = fig_yearly_dos(yd)
    p_month, top3 = fig_month(pm)
    p_wd = fig_weekday(wd)
    p_thr = fig_threshold(yd)

    y0, y1 = age.index.min(), age.index.max()
    teen = age["16~19세"]
    hs = job["고등학생"]
    old_share = lambda y: age.loc[y, ["40~49세", "50~59세", "60세이상"]].sum() / age.loc[y].sum() * 100  # noqa: E731

    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>헌혈 수급 쉽게 보기</title>
<style>
 body {{ font-family: 'Malgun Gothic', sans-serif; max-width: 980px; margin: 0 auto; padding: 24px 16px 64px;
        color: #222; background: #fff; line-height: 1.65; }}
 h1 {{ font-size: 26px; margin-bottom: 4px; }} h2 {{ margin-top: 48px; border-bottom: 2px solid #eee; padding-bottom: 6px; }}
 .muted {{ color: #777; }} .easy {{ background: #f3f7fd; border-left: 4px solid {BLUE}; padding: 12px 16px; border-radius: 4px; }}
 img {{ width: 100%; height: auto; margin: 12px 0; }}
 table {{ border-collapse: collapse; margin: 12px 0; }} td, th {{ border: 1px solid #ddd; padding: 6px 12px; text-align: left; }}
 th {{ background: #f6f6f6; }}
</style></head><body>
<h1>L1·L2 데이터로 본 헌혈 수급, 쉽게 보기</h1>
<p class="muted">src/make_report.py로 자동 생성 · 원본: KOSIS 대한적십자사 혈액정보통계 (data/raw)</p>

<p><b>한 줄 요약:</b> 헌혈은 줄어드는 젊은 층과 소수의 단골에 기대고 있고(L1),
피는 가을·겨울에, 그리고 평일에 부족해진다(L2).</p>

<table>
<tr><th></th><th>묻는 것</th><th>쓴 데이터</th></tr>
<tr><td><b>L1</b></td><td>인구가 늙고 줄면, 헌혈하는 사람도 줄어서 피가 모자라게 될까?</td><td>연령별·직업별 헌혈통계, 헌혈자 수 ({y0}–{y1})</td></tr>
<tr><td><b>L2</b></td><td>1년 중 언제 피가 가장 모자랄까? 미리 알 수 있을까?</td><td>적혈구 일별 재고 ({d.date.dt.year.min()}–{d.date.dt.year.max()}, {len(d):,}일)</td></tr>
</table>
<p><b>보유일수</b> = "지금 창고에 있는 피로 며칠 버틸 수 있나". 5일 이상이면 적정, 3일 미만이면 주의 단계.
이 보고서에서 "부족"은 3일 미만을 뜻한다.</p>

<h2>L1-① 누가 헌혈하나 — 젊은 층의 비중이 빠르게 줄고 있다</h2>
{img(p_age)}
<p class="easy"><b>쉽게 말하면:</b> {y0}년에는 헌혈 10건 중 {young[y0] / 10:.0f}건을 10·20대가 했다.
{y1}년에는 {young[y1] / 10:.0f}건뿐이다. 10대(16~19세) 헌혈 건수는 {teen.idxmax()}년 {fmt_man(teen.max())} 건에서
{y1}년 {fmt_man(teen[y1])} 건으로 줄었다. 빈자리는 40대 이상이 채웠다({old_share(y0):.0f}% → {old_share(y1):.0f}%).
2020년에 급격히 꺾인 건 코로나로 학교 단체헌혈이 멈춘 영향으로 보인다.</p>

<h2>L1-② 단체헌혈이 줄고, 직장인이 빈자리를 채운다</h2>
{img(p_job)}
<p class="easy"><b>쉽게 말하면:</b> 고등학생 헌혈은 {hs.idxmax()}년 {fmt_man(hs.max())} 건에서 {y1}년 {fmt_man(hs[y1])} 건으로
{(1 - hs[y1] / hs.max()) * 100:.0f}% 줄었다. 군인도 {y0}년 {fmt_man(job['군인'][y0])} 건에서 {fmt_man(job['군인'][y1])} 건이 됐다.
학교·부대 단체헌혈에 기대는 집단이라, 학령인구와 병력이 줄면 바로 타격을 받는다.
반대로 회사원 헌혈은 {fmt_man(job['회사원'][y0])} 건에서 {fmt_man(job['회사원'][y1])} 건으로 늘었다.</p>

<h2>L1-③ 사람은 줄고, 한 사람이 더 자주 한다</h2>
{img(p_don)}
<p class="easy"><b>쉽게 말하면:</b> 실제로 헌혈한 사람 수는 {dn.donors.idxmax()}년 {fmt_man(dn.donors.max())} 명에서
{y1}년 {fmt_man(dn.donors[y1])} 명으로 줄었다. 그래도 총 헌혈 건수가 버틴 건 한 사람이 1년에
{dn.per_donor[y0]:.2f}회에서 {dn.per_donor[y1]:.2f}회로 더 자주 헌혈했기 때문이다.
지금의 헌혈량은 "단골 헌혈자"에게 기대고 있다.</p>

<h2>L1 정리</h2>
<ol>
<li>헌혈의 주력은 10·20대인데, 이 연령대 인구는 저출산으로 계속 줄어든다.</li>
<li>고등학생·군인처럼 단체로 헌혈하던 집단이 가장 크게 줄었다.</li>
<li>적은 사람이 더 자주 헌혈해서 버티고 있지만, 전혈은 연 5회까지라 1인당 횟수를 계속 늘릴 수는 없다.</li>
</ol>
<p><b>L1 모형에서 할 일:</b> 연령별 헌혈 건수 ÷ 연령별 인구 = 연령별 헌혈률. 여기에 통계청 장래인구추계를 곱해
2030·2040년 헌혈량을 예측한다.</p>

<h2>L2-⓪ 20년 동안의 적혈구 보유일수</h2>
{img(p_year)}
<p class="easy"><b>쉽게 말하면:</b> {len(yd)}년 중 {under}년은 연평균이 5일 미만이었다.
같은 해 안에서도 최저와 최고가 크게 벌어져, 연 단위보다 일 단위 예측이 필요하다.</p>

<h2>L2-① 언제 부족한가 — 가을과 겨울이 위험하다</h2>
{img(p_month)}
<p class="easy"><b>쉽게 말하면:</b> {top3[0]}월에는 전체 날의 {pm[top3[0]]:.0f}%가 부족했다.
반대로 {pm.idxmin()}월은 {pm.min():.1f}%로 거의 없다. 9~10월은 추석, 1~2월은 겨울방학·설과 겹치는 시기라
명절·방학 효과로 추정된다(공휴일 달력을 붙여 확인할 예정).</p>

<h2>L2-② 일주일 리듬 — 평일에 줄고 주말에 채워진다</h2>
{img(p_wd)}
<p class="easy"><b>쉽게 말하면:</b> 월~금에는 재고가 매일 줄고, 토·일에 다시 쌓인다.
평일에 병원 수술이 많아 피가 많이 나가기 때문으로 보인다(추정). 그래서 금요일이 한 주 중 가장 빠듯하다.
요일은 L2 예측 모델에 꼭 넣어야 하는 입력이다.</p>

<h2>L2-③ 오늘 부족하면, 일주일 뒤에도 부족할 가능성이 크다</h2>
<table>
<tr><th>오늘 상태</th>{''.join(f'<th>{c}에도 부족할 확률</th>' for c in ps.columns)}</tr>
{''.join(f"<tr><td>{i}</td>{''.join(f'<td>{v:.0f}%</td>' for v in r)}</tr>" for i, r in ps.iterrows())}
</table>
<p class="easy"><b>쉽게 말하면:</b> 부족 상태는 한번 시작되면 이어진다. 20년 동안 부족 구간이 {len(spells)}번 있었고,
보통 {spells.median():.0f}일, 가장 길게는 {spells.max()}일 이어졌다. 그래서 "오늘 재고"만 봐도 일주일 뒤를 꽤 맞힐 수 있다.
L2 모델은 이 단순 예측보다 얼마나 더 잘 맞히는지로 평가해야 한다.</p>

<h2>L2-④ 팀 결정 필요 — 부족 기준을 5일로 할까, 3일로 할까</h2>
{img(p_thr)}
<p>5일 미만을 기준으로 하면 최근 연도는 대부분의 날이 "결핍"이 된다. 모델이 항상 "결핍"이라고만 답해도
정확도가 높게 나와서 예측의 의미가 없어진다. <b>추천:</b> 주 타깃은 3일 미만, 5일 미만은 보조 지표.</p>

<h2>부록 — 데이터 확인에서 알게 된 것</h2>
<ul>
<li>KOSIS "수혈용 혈액 보유 추이(일별)"는 총량이 아니라 <b>농축적혈구 재고</b>다 (월평균이 240개월 모두 일치).</li>
<li>적혈구 소요량 = (농축 + 세척 + 백혈구여과제거 적혈구 공급) ÷ 365. 2025년 5,030/일, 공식 발표 5,052/일과 0.4% 차이.</li>
<li>일별 표의 2005년 3~12월 값은 2016년 값의 복사본(원자료 오류)이라 제외했다.</li>
</ul>
</body></html>"""
    REPORT.mkdir(parents=True, exist_ok=True)
    out = REPORT / "report.html"
    out.write_text(html, encoding="utf-8")
    print(f"보고서: {out}")
    print(f"그림:   {FIG} ({len(list(FIG.glob('*.png')))}개)")
    return out


if __name__ == "__main__":
    report = build()
    if "--no-open" not in sys.argv:
        webbrowser.open(report.as_uri())
