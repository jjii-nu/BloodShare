# 데이터 목록

- `raw/` — 원본 다운로드 파일 그대로 (수정 금지). 파일명: `<출처>_<표이름>_<시작연도>-<끝연도>.<확장자>`
- `processed/` — 스크립트로 생성한 가공 테이블 (직접 편집 금지, `src/`로 재생성)
- `reference/` — 공식 발표 스냅샷 (검증용). 캡처 날짜를 파일명에 포함

## 확보 현황 (2026-10-01)

KOSIS 원본은 모두 CP949 인코딩이며, 결측은 `-`로 표시된다. 가공은 `py src/build_processed.py`로 한다.

| 파일 (raw/) | 내용 | 비고 |
|---|---|---|
| 01_supply_by_center_2005-2018 / 2019-2025 | 혈액원별 공급실적 | 두 표의 제제 분류 체계가 다름 |
| 02_supply_by_product_2005-2024 / 2025 | 제제별 공급실적 (혈액원×용량) | 2025 표만 다단 헤더 |
| 03_inventory_daily_2005-2025 | **농축적혈구** 일별 재고 | 2005-03-01 이후는 2016 값 복사 → 제외 |
| 04_inventory_monthly_by_product_2005-2025 | 4개 제제 월평균 재고 | |
| 05_donation_by_age | 연령별 헌혈 (혈액원×성별) | |
| 06_deferral_by_reason_2008-2025 | 헌혈 전 부적격 사유 | |
| 07_test_deferral | 헌혈 후 검사 부적격 (간기능=ALT 포함) | |
| 08_donation_by_job / 10_donation_monthly | 직업별 / 월별 헌혈 | |
| 09_donors | 헌혈 실인원, 헌혈가능인구 | |
| 11_donation_vs_supply | 월별 헌혈 대비 공급 | |

미확보: 장래인구추계(통계청), 수혈 진료통계(심평원), 기상(ASOS), 공휴일·학사일정

## 가공 결과 (processed/)

| 파일 | 열 |
|---|---|
| inventory_daily_rbc.csv | date, rbc_units |
| inventory_monthly_by_product.csv | month, product, avg_units |
| supply_annual_by_product.csv | year, product, units (전국) |
| rbc_days_of_supply.csv | date, rbc_units, daily_demand, days_of_supply, shortage(<5일) |
