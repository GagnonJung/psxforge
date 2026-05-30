# PSXForge + PSIO Game Manager

PSX 롬 폴더를 정리하고 PSIO SD카드로 전송하는 도구 세트입니다.

---

## 구성

| 파일 | 설명 |
|------|------|
| `psxforge.py` | 롬 폴더 일괄 정리 스크립트 |
| `psio_manager.py` | GUI 파일 매니저 |

---

## PSXForge

커맨드라인 스크립트. 소스 폴더는 수정하지 않으며 모든 결과물은 `output/` 폴더에 생성됩니다.

### 실행

```bash
python psxforge.py                   # 현재 폴더 대상
python psxforge.py /path/to/roms     # 경로 지정
```

### 처리 순서

1. **지역 약어 정규화** — `(K)` → `(Korea)`, `(J)` → `(Japan)` 등
2. **레거시 폴더명 수정** — `(2 Discs) Game (Japan)` → `Game (2 Discs) (Japan)`
3. **MULTIDISC.LST 생성** — 멀티 디스크 게임 목록 파일
4. **멀티 디스크 폴더 병합** — `(Disc 1)/`, `(Disc 2)/` → `(2 Discs)/`
5. **CUE → CU2 변환** — 멀티 트랙: bin 병합 + cu2 생성 / 싱글 트랙: 그대로 복사
6. **썸네일 다운로드** — bin에서 PSX 시리얼을 읽어 커버 이미지 자동 다운로드

### 지원 약어

`J/JPN` → Japan, `U/US` → USA, `E/EU/EUR` → Europe, `K/KR/KOR` → Korea 외 다수

---

## PSIO Game Manager

tkinter 기반 GUI. 게임 목록 확인 및 SD카드 전송에 사용합니다.

### 요구사항

```bash
pip install pillow
```

### 실행

```bash
python psio_manager.py
```

### 주요 기능

- **게임 목록** — 이름 / 장르 / 시리얼 / 디스크 수 / 용량 / 썸네일 유무 표시
- **검색 및 필터** — 이름·시리얼 검색, 장르·썸네일 필터, 컬럼 정렬
- **즐겨찾기** — ★ 클릭으로 즐겨찾기 등록, 목록 최상단 고정
- **장르 편집** — 장르 셀 더블클릭으로 직접 편집 및 로컬 저장
- **썸네일**
  - 자동 다운로드 (PSX 시리얼 기반)
  - 직접 생성 — 이미지 파일 또는 URL → PSIO 규격(80×84px, 24-bit BMP) 변환
- **🍀 I'm Feeling Lucky** — 대상 드라이브 용량 안에서 게임 랜덤 선택
- **SD카드 복사** — 선택 게임을 대상 폴더로 복사, 중복 시 개별/일괄 덮어쓰기 선택
- **설정 자동 저장** — 소스·대상 경로를 `~/.psio_manager.json`에 저장

### 로컬 데이터 파일

| 파일 | 위치 | 내용 |
|------|------|------|
| `.psio_genres.json` | 소스 폴더 | 게임별 장르 |
| `.psio_favs.json` | 소스 폴더 | 즐겨찾기 목록 |
| `~/.psio_manager.json` | 홈 디렉토리 | 소스·대상 경로 |

---

## 참고

- CUE→CU2 변환 로직: [ncirocco/cue-to-cu2](https://github.com/ncirocco/cue-to-cu2)
- PSX 시리얼 추출: [ncirocco/psx-serial-number](https://github.com/ncirocco/psx-serial-number)
- 썸네일 이미지: [ncirocco/PSIO-Library](https://github.com/ncirocco/PSIO-Library)
