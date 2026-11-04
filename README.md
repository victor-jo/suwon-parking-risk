# 수원 주정차 단속 지도

수원시가 공개한 주정차 단속 기록으로 **어디서 단속이 자주 일어나는지** 보여 주는 지도예요.

👉 **[지도 보기](https://victor-jo.github.io/suwon-parking-risk/)**

- 실시간 정보가 아니에요. 2022-01 ~ 2023-10 단속 기록 약 79만 건을 바탕으로 만들었어요.
- 점을 누르면 "단속 있던 날 10일 중 N일", 요일·시간표(참고용), 2025년 9월에도 근처에서 신고가 있었는지가 보여요.
- 고정 CCTV 지점에는 "신고가 없어도 카메라가 자동으로 단속해요"라는 경고가 떠요.

## 왜 만들었나

빈 주차 자리를 알려 주는 서비스는 이미 많아요. 그런데 "여기 잠깐 세우면 단속될까?"를 미리 알려 주는 수원 지도는 찾지 못했어요.
수원시 단속 기록에는 좌표가 없고 장소가 `인계동 ○○ 앞`처럼 글자로만 적혀 있어요. 이 프로젝트는 그 글자를 좌표로 바꾸고, 지점별로 단속이 얼마나 자주 있었는지 계산해요.

## 지도 읽는 법

| 표시 | 뜻 |
|---|---|
| 🔵 파란 원 | 고정 CCTV가 주로 단속한 곳 |
| 🟠 주황 원 | 순찰차·신고로 자주 걸린 곳 |
| 원 크기 | 단속이 있던 날의 비율 (클수록 자주) |
| 점선 원 | 위치가 대략인 곳 (도로·동 단위). 기본으로 꺼져 있어요 |

**알아 둘 점**

- "어디"는 오래가지만 "몇 시"는 해마다 바뀌어요. 다른 해 기록으로 확인해 보니, 옛 단속 지점은 2025년에도 500m 옆 자리보다 약 4배 자주 신고됐어요. 반면 정확한 요일·시간 칸은 많이 바뀌었어요. 그래서 요일·시간표는 참고용으로만 보여 줘요.
- 지도에 없다고 안전한 곳은 아니에요. 단속 기록의 약 89%(자주 나온 장소 3,000곳)만 좌표로 바꿨어요.
- 위치 정확도는 장소마다 달라요. CCTV 좌표나 주소로 찾은 곳은 정확하고, 장소 이름으로 찾은 곳은 실제와 보통 74m(중간값) 정도 차이 나요.

## 사용한 데이터

모두 [공공데이터포털](https://www.data.go.kr)의 경기도 수원시 파일 데이터예요. 실시간 API는 없고, 일회성 파일로만 제공돼요.

| 데이터 | 기간 | 쓰는 곳 |
|---|---|---|
| [주정차위반단속위치현황 (15125266)](https://www.data.go.kr/data/15125266/fileData.do) | 2022-01 ~ 2023-10, 약 79만 건 | 지도의 기본 데이터 |
| [고정형 CCTV 위치 (15157315)](https://www.data.go.kr/data/15157315/fileData.do) | 카메라 534대 | CCTV 지점 좌표, 지오코딩 채점 |
| [주정차위반 특정구간 단속현황 (15159231)](https://www.data.go.kr/data/15159231/fileData.do) | 2021 ~ 2025, 고색동 한 구역 | 패턴이 해마다 유지되는지 확인 |
| [불법주정차 과태료 (15155622)](https://www.data.go.kr/data/15155622/fileData.do) | 2025-09 한 달, 안전신문고 | 지점마다 "2025년에도 신고됐나" 표시 |

장소 글자를 좌표로 바꿀 때는 [카카오 로컬 API](https://developers.kakao.com/docs/latest/ko/local/dev-guide)를 써요. 지도 배경은 [OpenStreetMap](https://www.openstreetmap.org/copyright)이에요.

## 직접 실행하기

**준비물**

- Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)
- 카카오 REST API 키 (좌표 변환할 때만 필요해요)

```bash
uv sync
echo "KAKAO_REST_API_KEY=발급받은_키" > .env   # .env는 git에 올라가지 않아요
```

**지도 만들기**

```bash
uv run suwon-parking fetch            # 데이터 4종을 data/raw/에 내려받기
uv run suwon-parking geocode          # 자주 나온 장소 3,000곳을 좌표로 (카카오 API, 캐시됨)
uv run suwon-parking geocode --fines  # 2025-09 신고 장소를 좌표로
uv run suwon-parking map              # data/map.html 만들기
open data/map.html                    # 서버 없이 바로 열려요
```

좌표 변환 결과는 `data/geocode_cache.jsonl`에 쌓여서, 다시 실행해도 API를 또 부르지 않아요.

**그 밖의 명령**

| 명령 | 하는 일 |
|---|---|
| `profile` | 건수, 기간, 장소 분포, 시간대별 건수 출력 |
| `validate` | 카카오 좌표를 CCTV 실제 좌표와 비교해 채점 |
| `aggregate` | 지점 × 요일 × 시간별 단속 비율을 `data/cells.csv`로 저장 |
| `freshness` | 고색동 구역에서 2022~23년 패턴이 2021년, 2024~25년에도 맞는지 확인 |
| `recent` | 수원 전체에서 옛 단속 지점이 2025-09에도 신고됐는지 확인 |

**테스트**

```bash
uv run pytest
```

## 폴더 구조

```text
src/suwon_parking/
  fetch.py             공공데이터포털에서 파일 내려받기
  records.py           CSV 읽기 (깨진 시각 표기 처리 포함)
  geocode.py           장소 글자 → 좌표 (카카오 API + 캐시)
  cctv.py              CCTV 목록과 장소 이름 맞추기
  aggregate.py         지점 × 요일 × 시간 집계
  points.py            지도 점 요약, 2025 신고 붙이기
  freshness.py         다른 기간에도 패턴이 맞는지 비교
  mapview.py           지도 HTML 만들기
  map_template.html    지도 페이지 틀 (Leaflet)
  cli.py               suwon-parking 명령
tests/                 pytest 테스트
data/                  내려받은 원본, 캐시, 결과물 (git에 안 올림)
context-notes.md       작업하며 내린 결정과 그 이유
```

## 지도 다시 배포하기

지도는 `gh-pages` 브랜치의 `index.html` 한 파일이에요.

```bash
uv run suwon-parking map
git worktree add /tmp/pages gh-pages
cp data/map.html /tmp/pages/index.html
(cd /tmp/pages && git commit -am "지도 갱신" && git push)
git worktree remove /tmp/pages
```
