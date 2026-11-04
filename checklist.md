# Checklist

## Plan
수원시 주정차 위반 단속 기록(data.go.kr 15125266, 2022-01~2023-10, 약 79만 건)으로
"이 장소, 이 시간에 세우면 단속될 가능성" 지도를 만든다. 실시간이 아니라 과거 패턴 기반.

## Tasks
- [x] 1. 프로젝트 골격(uv, pytest, git) + checklist / context-notes
- [x] 2. 원본 다운로드(`suwon-parking fetch`) + 파싱 + 기본 프로파일(`suwon-parking profile`)
- [x] 3. 지오코딩 방식 결정 → 카카오 로컬 API (키는 .env)
- [x] 4. 상위 장소 문자열(상위 3,000개 ≈ 89%) 정규화 + 좌표 변환, 캐시(`data/geocode_cache.jsonl`)
- [x] 5. 장소 × 요일 × 시간대 단속 빈도 집계 (`suwon-parking aggregate` → `data/cells.csv`)
- [x] 6. 고정형 CCTV 위치(15157315) 결합 + 지오코딩 검증(`suwon-parking validate`)
- [x] 6b. 특정구간 단속 2021~2025(15159231): cells.csv엔 안 합침(기간 다름), 신선도 검증(`suwon-parking freshness`)으로 사용
- [x] 7. 정적 지도 웹 페이지(`suwon-parking map` → `data/map.html`)
- [x] 8. 2025-09 신고·과태료(15155622)를 지도 점의 최근 신호로 붙이기 + 수원 전체 신선도(`suwon-parking recent`)
- [x] 9. GitHub Pages 배포 (gh-pages 브랜치, https://victor-jo.github.io/suwon-parking-risk/)

## 10. 성남 합치기 (15037104, 2025년 기록)
수원 지도 한 장에 성남 점을 같이 올린다. 성남 기록에는 시각이 없어서 요일·시간표와 2025-09 신고 줄은 수원 점에만 보인다.
- [x] 10a. 성남 파일 받기(`fetch seongnam`) + 읽기(UTF-8 BOM, 날짜만 있는 시각) — 테스트 먼저
- [ ] 10b. 좌표 변환기를 도시별로(검색어 '성남', 구 이름, 중심점) + 도로명으로 시작하는 장소 처리 — 테스트 먼저
- [ ] 10c. 성남 상위 3,000곳 좌표 변환(`geocode --city seongnam`, 캐시 파일 따로) + 정확도 분포 확인
- [ ] 10d. 지도에 두 도시 넣기(도시별 기간·건수, 시간표·신고 줄은 있는 도시만) — 테스트 먼저
- [ ] 10e. 화면 확인(스크린샷) → README·context-notes 갱신 → gh-pages 재배포
