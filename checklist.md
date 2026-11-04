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
- [ ] 6b. (선택) 특정구간 단속 2021~2025(15159231) 결합
- [ ] 7. 결과 보여주는 방식 결정 (지도 웹 페이지 / API / CLI)
