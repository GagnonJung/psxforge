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

커맨드라인 스크립트. **원본 폴더는 수정하지 않으며** 모든 결과물은 `output/` 폴더에 생성됩니다.  
**output 폴더는 삭제하지 않습니다.** 이미 존재하는 폴더는 건너뛰고 새 게임만 처리합니다.

### 실행

```bash
python psxforge.py                   # 현재 폴더 대상
python psxforge.py /path/to/roms     # 경로 지정
```

### 처리 순서

1. **output/ 폴더 준비** — 없으면 생성, 있으면 유지
2. **원본 스캔 및 그룹화**
   - 지역 약어 정규화 — `(K)` → `(Korea)`, `(J)` → `(Japan)` 등
   - 레거시 폴더명 수정 — `(2 Discs) Game (Japan)` → `Game (2 Discs) (Japan)`
   - 멀티 디스크 그룹화 — `(Disc 1)/`, `(Disc 2)/` → `(2 Discs)/`
3. **output/ 에 복사 및 변환**
   - 이미 output에 존재하는 폴더는 스킵
   - 멀티 트랙 cue: bin 병합 + cu2 생성
   - 싱글 트랙 cue: 그대로 복사 (파일명 약어 정규화 포함)
4. **MULTIDISC.LST 생성** — 멀티 디스크 게임 목록 파일
5. **썸네일 다운로드** — bin에서 PSX 시리얼을 읽어 커버 이미지 자동 다운로드

### 지원 지역 약어

| 약어 | 변환 |
|------|------|
| `J`, `JPN` | Japan |
| `U`, `US` | USA |
| `E`, `EU`, `EUR` | Europe |
| `K`, `KR`, `KOR` | Korea |
| `AU`, `AUS` | Australia |
| `BR` | Brazil |
| `CN`, `CHN` | China |
| 그 외 다수 | — |

---

## PSIO Game Manager

tkinter 기반 GUI. 게임 목록 확인 및 SD카드 전송에 사용합니다.

### 요구사항

```bash
pip install pillow
pip install requests   # URL 썸네일 다운로드 안정성 향상 (선택)
```

### 실행

```bash
python psio_manager.py
```

### 주요 기능

#### 게임 목록
- 국기 이모지 / 이름 / 장르 / 시리얼 / 디스크 수 / 용량 / 썸네일 유무 표시
- 멀티 디스크 게임은 디스크별로 각각 표시 (`Game — Disc 1/2`, `Game — Disc 2/2`)
- 컬럼 헤더 클릭으로 정렬
- 검색 (이름·시리얼), 장르·국가·썸네일 필터
- 스캔 완료 / 전송 완료 시 팝업 알림

#### 즐겨찾기
- `★` 컬럼 클릭으로 개별 토글
- `★ 즐겨찾기 등록` 버튼으로 선택 게임 일괄 등록
- `★ 즐겨찾기만 선택` 버튼으로 즐겨찾기 게임만 한 번에 선택
- 즐겨찾기 게임은 목록 최상단 고정, 황금색 배경 표시
- `.psio_favs.json`에 자동 저장 및 로드

#### 장르 편집
- 장르 셀 더블클릭 → 드롭다운 or 직접 입력
- 같은 게임의 모든 디스크 행에 동시 반영
- `.psio_genres.json`에 자동 저장 및 로드

#### 썸네일
- **자동 다운로드** — PSX 시리얼 기반으로 PSIO Library에서 다운로드
- **직접 생성** — 이미지 파일 또는 URL 입력 → PSIO 규격(80×84px, 24-bit BMP)으로 변환
  - 변환(미리보기) / 저장 버튼 분리
  - 폭 맞춤 스케일 + 검정 패딩

#### 대상 폴더 동기화
- 대상 폴더 선택 또는 스캔 완료 시 이미 존재하는 게임을 `📥` 아이콘 + 회색으로 표시
- 선택(☑)과 별도로 표시되므로 자유롭게 선택/해제 가능
- 이미 있는 게임을 선택하면 초록 배경으로 강조

#### SD카드 복사
- 선택 용량 / 대상 드라이브 남은 공간 실시간 표시
- `이미 있는 게임 제외` 옵션 — 대상에 이미 있는 게임은 건너뜀
- `중복 시 묻지 않고 덮어쓰기` 옵션
- 중복 시 개별 팝업 — 덮어쓰기 / 건너뜀 / 모두 덮어쓰기
- 파일 단위 진행률 실시간 표시 (타이틀바 인라인)

#### 🍀 I'm Feeling Lucky
- 대상 드라이브 남은 용량 안에서 게임 랜덤 선택
- 멀티 디스크는 게임 단위로 묶어 모든 디스크 포함

#### 설정 자동 저장
- 소스·대상 경로를 `~/.psio_manager.json`에 저장, 재시작 시 자동 복원

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
