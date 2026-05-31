"""
PSX 롬 폴더 정리 스크립트
--------------------------
원본 폴더는 절대 수정하지 않습니다.
모든 결과는 <루트>/output/ 폴더에 생성됩니다.

실행 순서:
  [1] output/ 초기화 (기존 output 삭제 후 재생성)
  [2] 원본 폴더 스캔 및 그룹화
        - 지역 약어 정규화  (K) -> (Korea)
        - 멀티 디스크 그룹  (Disc 1)/(Disc 2) -> (2 Discs)
        - 레거시 폴더명     (2 Discs) Game -> Game (2 Discs)
  [3] output/ 에 복사
        - 멀티 트랙 cue: bin 병합 + cu2 생성
        - 싱글 트랙 cue: 그대로 복사
  [4] MULTIDISC.LST 생성 (output/ 루트에)
  [5] 썸네일 다운로드 (output/ 각 폴더에)

사용법:
  python psxforge.py              # 현재 폴더 대상
  python psxforge.py /path/to/dir # 특정 폴더 대상
"""

import os
import re
import sys
import shutil
import urllib.request
from collections import defaultdict


# ════════════════════════════════════════════════
# 패턴 / 상수
# ════════════════════════════════════════════════

DISC_PATTERN = re.compile(
    r'[\(\[]?\s*(?:discs?|dics?|disk|cd)\s*(\d+)\s*[\)\]]?',
    flags=re.IGNORECASE
)

REGION_PATTERN = re.compile(
    r'(\((?:Japan|USA|Europe|Korea|World|Asia|Brazil|France|Germany|Italy|Spain'
    r'|Australia|China|Taiwan|Sweden|Netherlands|Russia|Canada|Latin America)[^)]*\))',
    flags=re.IGNORECASE
)

LEGACY_PREFIX_PATTERN = re.compile(
    r'^\((\d+)\s*Discs?\)\s+',
    flags=re.IGNORECASE
)

REGION_ABBR_MAP = {
    'J':   'Japan',  'JPN': 'Japan',
    'U':   'USA',    'US':  'USA',
    'E':   'Europe', 'EU':  'Europe',  'EUR': 'Europe',
    'K':   'Korea',  'KR':  'Korea',   'KOR': 'Korea',
    'W':   'World',
    'A':   'Asia',   'AS':  'Asia',
    'B':   'Brazil', 'BR':  'Brazil',
    'F':   'France', 'FR':  'France',
    'G':   'Germany','DE':  'Germany',
    'I':   'Italy',  'IT':  'Italy',
    'S':   'Spain',  'ES':  'Spain',
    'AU':  'Australia', 'AUS': 'Australia',
    'C':   'Canada', 'CA':  'Canada',
    'CN':  'China',  'CHN': 'China',
    'TW':  'Taiwan', 'TWN': 'Taiwan',
    'SW':  'Sweden', 'SWE': 'Sweden',
    'NL':  'Netherlands',
    'RU':  'Russia', 'RUS': 'Russia',
}

REGION_ABBR_PATTERN = re.compile(
    r'\((' + '|'.join(sorted(REGION_ABBR_MAP.keys(), key=len, reverse=True)) + r')\)',
    flags=re.IGNORECASE
)

# cu2 관련
SECTORS_PER_SECOND = 75
SECONDS_PER_MINUTE = 60
BLOCK_SIZES = {
    'MODE1/2048': 2048, 'MODE1/2352': 2352,
    'MODE2/2336': 2336, 'MODE2/2352': 2352,
    'AUDIO':      2352,
}

# 썸네일
SERIAL_REGEX  = re.compile(
    r'((SLPS|SLES|SLUS|SCPS|SCUS|SCES|SIPS|SLPM|SLEH|SLED|SCED|ESPM|PBPX|LSP)[_P\-])|(LSP9|907127)'
)
SERIAL_EXCEPTIONS = {'SLUSP': 'SLUS_', 'LSP9': 'LSP_9', '907127': 'LSP_907127'}
COVER_URL = "https://ncirocco.github.io/PSIO-Library/images/covers_by_id/{}.bmp"
BUFFER_SIZE = 1024 * 1024


# ════════════════════════════════════════════════
# 이름 정규화 유틸
# ════════════════════════════════════════════════

def expand_region_abbr(name: str) -> str:
    """(K) -> (Korea) 등 약어를 풀네임으로 치환."""
    def replacer(m):
        full = REGION_ABBR_MAP.get(m.group(1).upper())
        return f"({full})" if full else m.group(0)
    return REGION_ABBR_PATTERN.sub(replacer, name)


def fix_legacy_prefix(name: str) -> str:
    """(2 Discs) Game (Japan) -> Game (2 Discs) (Japan)"""
    m = LEGACY_PREFIX_PATTERN.match(name)
    if not m:
        return name
    disc_count = int(m.group(1))
    remainder  = name[m.end():]
    return make_dest_name(remainder, disc_count)


def make_dest_name(base_name: str, disc_count: int) -> str:
    """Game (Japan) + 2  ->  Game (2 Discs) (Japan)"""
    disc_tag = f"({disc_count} Discs)"
    m = REGION_PATTERN.search(base_name)
    if m:
        pos = m.start()
        return (base_name[:pos].rstrip() + ' ' + disc_tag + ' ' + base_name[pos:]).strip()
    return f"{base_name} {disc_tag}"


def normalize_folder_name(name: str) -> str:
    """약어 확장 -> 레거시 접두사 수정을 순서대로 적용."""
    name = expand_region_abbr(name)
    name = fix_legacy_prefix(name)
    return name


def strip_disc(name: str):
    """이름에서 디스크 번호 제거 -> (기본이름, 번호)."""
    m = DISC_PATTERN.search(name)
    if not m:
        return None, None
    base = DISC_PATTERN.sub('', name).strip()
    base = re.sub(r'\s{2,}', ' ', base).strip(' -_')
    return base, int(m.group(1))


# ════════════════════════════════════════════════
# [2] 원본 스캔 및 그룹화
# ════════════════════════════════════════════════

def scan_source(parent: str) -> list[tuple[str, list[str]]]:
    """
    원본 폴더를 스캔해서 (출력폴더명, [원본폴더경로, ...]) 리스트를 반환.
    - 멀티 디스크 폴더는 하나의 그룹으로 묶임
    - 단일 폴더는 그대로
    - 폴더명은 normalize_folder_name 으로 정규화
    """
    # 1단계: 모든 하위 폴더 수집
    entries = []
    for entry in os.listdir(parent):
        full_path = os.path.join(parent, entry)
        if not os.path.isdir(full_path) or entry == 'output':
            continue
        entries.append(entry)

    # 2단계: 멀티 디스크 그룹화 (정규화 이름 기준)
    disc_groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    singles = []

    for entry in entries:
        norm = normalize_folder_name(entry)
        base, disc_num = strip_disc(norm)
        if base is not None:
            disc_groups[base].append((entry, disc_num))
        else:
            singles.append(entry)

    # 3단계: 결과 조합
    result = []

    # 멀티 디스크 그룹
    for base_name, folder_list in disc_groups.items():
        if len(folder_list) == 1:
            # 디스크 번호 태그는 있지만 쌍이 없는 경우 → 단독 처리
            singles.append(folder_list[0][0])
            continue
        sorted_list = sorted(folder_list, key=lambda x: x[1])
        max_disc = max(n for _, n in sorted_list)
        dest_name = make_dest_name(expand_region_abbr(base_name), max_disc)
        src_paths = [os.path.join(parent, f) for f, _ in sorted_list]
        result.append((dest_name, src_paths))

    # 단독 폴더
    for entry in singles:
        dest_name = normalize_folder_name(entry)
        result.append((dest_name, [os.path.join(parent, entry)]))

    return sorted(result, key=lambda x: x[0])


# ════════════════════════════════════════════════
# CUE 파싱 / cu2 변환 유틸
# ════════════════════════════════════════════════

def parse_cue(cue_path: str):
    """cue 파싱 -> (bin_files, tracks)"""
    bin_files, tracks = [], []
    try:
        with open(cue_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            for line in f:
                fields = line.strip().split()
                if not fields:
                    continue
                key = fields[0].upper()
                if key == 'FILE':
                    m = re.search(r'FILE\s+"([^"]+)"', line, re.IGNORECASE)
                    if not m:
                        m = re.search(r"FILE\s+'([^']+)'", line, re.IGNORECASE)
                    fname = m.group(1) if m else ' '.join(fields[1:-1])
                    bin_files.append(fname)
                elif key == 'TRACK':
                    tracks.append({'id': int(fields[1]), 'type': fields[2], 'indexes': []})
                elif key == 'INDEX' and tracks:
                    tracks[-1]['indexes'].append({'id': int(fields[1]), 'stamp': fields[2]})
    except Exception:
        pass
    return bin_files, tracks


def stamp_to_sectors(stamp: str) -> int:
    mm, ss, ff = (int(x) for x in stamp.strip().split(':'))
    return mm * SECONDS_PER_MINUTE * SECTORS_PER_SECOND + ss * SECTORS_PER_SECOND + ff


def sectors_to_stamp(sectors: int) -> str:
    mm  = sectors // (SECTORS_PER_SECOND * SECONDS_PER_MINUTE)
    rem = sectors %  (SECTORS_PER_SECOND * SECONDS_PER_MINUTE)
    ss  = rem // SECTORS_PER_SECOND
    ff  = sectors % SECTORS_PER_SECOND
    return f"{mm:02d}:{ss:02d}:{ff:02d}"


def generate_cu2(cue_path: str, bin_path: str) -> str:
    """cu2 문자열 생성 (github.com/ncirocco/cue-to-cu2 동일 로직)."""
    _, tracks = parse_cue(cue_path)
    if not tracks:
        raise ValueError(f"TRACK 없음: {cue_path}")
    block_size    = BLOCK_SIZES.get(tracks[0]['type'].upper(), 2352)
    total_sectors = os.path.getsize(bin_path) // block_size
    size_stamp    = sectors_to_stamp(total_sectors)

    lines = [
        f"ntracks {len(tracks)}\r\n",
        f"size      {size_stamp}\r\n",
         "data1     00:02:00\r\n",
    ]
    for track in tracks:
        tid, idxs = track['id'], track['indexes']
        if tid == 1:
            continue
        if len(idxs) == 1:
            s     = stamp_to_sectors(idxs[0]['stamp'])
            stamp = sectors_to_stamp(s + 2 * SECTORS_PER_SECOND)
            lines.append(f"pregap{tid:02d}  {stamp}\r\n")
            lines.append(f"track{tid:02d}   {stamp}\r\n")
        else:
            pregap = next((i['stamp'] for i in idxs if i['id'] == 0), idxs[0]['stamp'])
            base   = next((i['stamp'] for i in idxs if i['id'] == 1), idxs[-1]['stamp'])
            s      = stamp_to_sectors(base)
            lines.append(f"pregap{tid:02d}  {pregap}\r\n")
            lines.append(f"track{tid:02d}   {sectors_to_stamp(s + 2 * SECTORS_PER_SECOND)}\r\n")

    end = stamp_to_sectors(size_stamp) + 2 * SECTORS_PER_SECOND
    lines.append(f"\r\ntrk end   {sectors_to_stamp(end)}")
    return ''.join(lines)


def merge_bins(cue_path: str, output_bin_path: str):
    """멀티 bin을 순서대로 병합."""
    cue_dir   = os.path.dirname(cue_path)
    bin_files, _ = parse_cue(cue_path)
    with open(output_bin_path, 'wb') as out:
        for bf in bin_files:
            src = os.path.join(cue_dir, bf)
            if not os.path.exists(src):
                raise FileNotFoundError(f"bin 없음: {src}")
            with open(src, 'rb') as inp:
                shutil.copyfileobj(inp, out)


def write_merged_cue(cue_path: str, output_dir: str, new_bin_name: str):
    """단일 bin 참조 cue 생성."""
    with open(cue_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        lines = f.readlines()
    new_lines, written = [], False
    for line in lines:
        if re.match(r'\s*FILE\s+', line, re.IGNORECASE):
            if not written:
                new_lines.append(f'FILE "{new_bin_name}" BINARY\r\n')
                written = True
        else:
            new_lines.append(line)
    with open(os.path.join(output_dir, os.path.basename(cue_path)), 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


# ════════════════════════════════════════════════
# [3] output/ 에 복사
# ════════════════════════════════════════════════

def copy_non_bin_cue_files(src_folder: str, dest_dir: str):
    """bin/cue 제외한 파일(bmp 등)을 dest_dir 로 복사."""
    for fname in os.listdir(src_folder):
        fpath = os.path.join(src_folder, fname)
        if not os.path.isfile(fpath):
            continue
        if os.path.splitext(fname)[1].lower() in ('.bin', '.cue'):
            continue
        dst = os.path.join(dest_dir, fname)
        if not os.path.exists(dst):
            shutil.copy2(fpath, dst)


def process_group(dest_name: str, src_paths: list[str], output_base: str):
    """
    (dest_name, src_paths) 하나를 처리해서 output_base/dest_name/ 에 저장.
    반환: 'merged' | 'copied' | 'skipped'
    """
    dest_dir = os.path.join(output_base, dest_name)

    # 모든 원본 폴더에서 cue 파일 수집
    all_cues = []
    for src in src_paths:
        for fname in sorted(os.listdir(src)):
            if fname.lower().endswith('.cue'):
                all_cues.append(os.path.join(src, fname))

    if not all_cues:
        # cue 없으면 그냥 복사
        for src in src_paths:
            shutil.copytree(src, dest_dir, dirs_exist_ok=True)
        return 'copied'

    # 전체 트랙 수 파악 (여러 cue가 있으면 합산)
    total_tracks = 0
    for cue_path in all_cues:
        _, tracks = parse_cue(cue_path)
        total_tracks += len(tracks)

    if total_tracks < 2:
        # 싱글 트랙 → 복사 (파일명 약어 정규화 포함)
        for src in src_paths:
            for fname in os.listdir(src):
                fpath = os.path.join(src, fname)
                if not os.path.isfile(fpath):
                    continue
                new_fname = expand_region_abbr(fname)
                os.makedirs(dest_dir, exist_ok=True)
                dst = os.path.join(dest_dir, new_fname)
                shutil.copy2(fpath, dst)
                # cue 내부 참조도 수정
                if new_fname.lower().endswith('.cue'):
                    with open(dst, 'r', encoding='utf-8-sig', errors='replace') as f:
                        cue_content = f.read()
                    new_cue = re.sub(
                        r'(FILE\s+["\'])([^"\']+)(["\'])',
                        lambda m: f'{m.group(1)}{expand_region_abbr(m.group(2))}{m.group(3)}',
                        cue_content, flags=re.IGNORECASE
                    )
                    if new_cue != cue_content:
                        with open(dst, 'w', encoding='utf-8') as f:
                            f.write(new_cue)
        return 'copied'

    # 멀티 트랙 → bin 병합 + cu2 생성
    os.makedirs(dest_dir, exist_ok=True)

    # 대표 cue (첫 번째)
    main_cue = all_cues[0]
    cue_stem = os.path.splitext(os.path.basename(main_cue))[0]
    # 출력 파일명은 dest_name 기준으로
    out_stem        = dest_name
    merged_bin_name = out_stem + '.bin'
    merged_bin_path = os.path.join(dest_dir, merged_bin_name)

    # bin 파일 수집 (모든 원본 폴더에서)
    all_bin_files = []
    for cue_path in all_cues:
        cue_dir   = os.path.dirname(cue_path)
        bin_files, _ = parse_cue(cue_path)
        for bf in bin_files:
            src_bin = os.path.join(cue_dir, bf)
            if os.path.exists(src_bin):
                all_bin_files.append(src_bin)

    if not all_bin_files:
        raise FileNotFoundError(f"bin 파일 없음: {dest_name}")

    # bin 병합 (하나면 복사, 여러 개면 병합)
    if len(all_bin_files) == 1:
        shutil.copy2(all_bin_files[0], merged_bin_path)
    else:
        with open(merged_bin_path, 'wb') as out:
            for src_bin in all_bin_files:
                with open(src_bin, 'rb') as inp:
                    shutil.copyfileobj(inp, out)

    # cue 생성 (dest_name 기준으로 파일명 통일)
    out_cue_path = os.path.join(dest_dir, out_stem + '.cue')
    with open(out_cue_path, 'w', encoding='utf-8') as f:
        # 첫 번째 cue의 TRACK/INDEX 구조 사용, FILE 라인만 교체
        _, tracks_0 = parse_cue(main_cue)
        # 모든 cue의 트랙 합산
        all_tracks = []
        for cue_path in all_cues:
            _, trks = parse_cue(cue_path)
            all_tracks.extend(trks)

        f.write(f'FILE "{merged_bin_name}" BINARY\r\n')
        for track in all_tracks:
            f.write(f'  TRACK {track["id"]:02d} {track["type"]}\r\n')
            for idx in track['indexes']:
                f.write(f'    INDEX {idx["id"]:02d} {idx["stamp"]}\r\n')

    # cu2 생성
    cu2_content = generate_cu2(out_cue_path, merged_bin_path)
    with open(os.path.join(dest_dir, out_stem + '.cu2'), 'w', encoding='utf-8') as f:
        f.write(cu2_content)

    # bmp 등 나머지 파일 복사
    for src in src_paths:
        copy_non_bin_cue_files(src, dest_dir)

    return 'merged'


# ════════════════════════════════════════════════
# [4] MULTIDISC.LST
# ════════════════════════════════════════════════

def write_multidisc_lst(output_base: str, groups: list):
    """멀티 디스크 그룹(disc 폴더가 여럿이었던 것)을 MULTIDISC.LST 에 기록."""
    multi_groups = {}
    for dest_name, src_paths in groups:
        if len(src_paths) >= 2:
            # 각 src의 cue 파일명 수집
            cue_names = []
            for src in src_paths:
                for fname in sorted(os.listdir(os.path.join(output_base, dest_name))
                                    if os.path.isdir(os.path.join(output_base, dest_name))
                                    else []):
                    if fname.lower().endswith('.cue'):
                        cue_names.append(fname)
            if cue_names:
                multi_groups[dest_name] = cue_names

    # output 폴더 내 .cue 파일로 MULTIDISC.LST 작성
    lines = []
    for dest_name, _ in groups:
        dest_dir = os.path.join(output_base, dest_name)
        if not os.path.isdir(dest_dir):
            continue
        cues = sorted(f for f in os.listdir(dest_dir) if f.lower().endswith('.cue'))
        if len(cues) >= 2:
            lines.extend(cues)
            lines.append('')

    if not lines:
        return None

    while lines and lines[-1] == '':
        lines.pop()

    lst_path = os.path.join(output_base, 'MULTIDISC.LST')
    with open(lst_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return lst_path


# ════════════════════════════════════════════════
# [5] 썸네일 다운로드
# ════════════════════════════════════════════════

def get_psx_serial(bin_path: str) -> str | None:
    """bin 파일에서 PSX 시리얼 추출 (github.com/ncirocco/psx-serial-number 동일 로직)."""
    SERIAL_CODE_DOT = 8
    SERIAL_CODE_LEN = 11
    try:
        with open(bin_path, 'rb') as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break
                text = chunk.decode('latin-1', errors='replace')
                m = SERIAL_REGEX.search(text)
                if m:
                    raw = text[m.start():m.start() + SERIAL_CODE_LEN]
                    s = raw.replace('.', '').replace('-', '_', 1).replace('-', '')
                    for key, val in SERIAL_EXCEPTIONS.items():
                        if key in s:
                            s = s.replace(key, val)
                    return s[:SERIAL_CODE_DOT] + '.' + s[SERIAL_CODE_DOT:SERIAL_CODE_LEN - 1]
    except Exception:
        pass
    return None


def download_thumbnails(output_base: str):
    ok, fail, skip = [], [], []
    for entry in sorted(os.listdir(output_base)):
        folder = os.path.join(output_base, entry)
        if not os.path.isdir(folder):
            continue
        if any(f.lower().endswith('.bmp') for f in os.listdir(folder)):
            skip.append(entry)
            continue
        bins = sorted(f for f in os.listdir(folder) if f.lower().endswith('.bin'))
        if not bins:
            fail.append((entry, "bin 없음"))
            continue
        serial = get_psx_serial(os.path.join(folder, bins[0]))
        if not serial:
            fail.append((entry, "시리얼 인식 불가"))
            continue
        dest_bmp = os.path.join(folder, f"{serial}.bmp")
        print(f"  다운로드: {entry} ({serial})")
        try:
            urllib.request.urlretrieve(COVER_URL.format(serial), dest_bmp)
            ok.append((entry, serial))
            print(f"    ✅ {serial}.bmp")
        except Exception:
            fail.append((entry, f"커버 없음 ({serial})"))
            print(f"    ⚠  커버 없음: {serial}")
            if os.path.exists(dest_bmp):
                os.remove(dest_bmp)

    print(f"\n  결과: 다운로드 {len(ok)}개 / 스킵(이미 있음) {len(skip)}개 / 실패 {len(fail)}개")
    for entry, reason in fail:
        print(f"  ✗ {entry}: {reason}")


# ════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    root = os.path.abspath(root)

    if not os.path.isdir(root):
        print(f"오류: 폴더를 찾을 수 없습니다 -> {root}")
        sys.exit(1)

    output_base = os.path.join(root, 'output')

    print(f"루트 폴더: {root}")
    print("=" * 60)

    # [1] output 폴더 준비 (삭제 없이 유지)
    os.makedirs(output_base, exist_ok=True)
    print(f"\n[1] output 폴더: {output_base}")

    # [2] 원본 스캔 및 그룹화
    print("\n[2] 원본 스캔 및 그룹화")
    groups = scan_source(root)
    multi  = [(d, s) for d, s in groups if len(s) >= 2]
    single = [(d, s) for d, s in groups if len(s) == 1]
    print(f"  총 {len(groups)}개 폴더 (멀티 디스크 그룹 {len(multi)}개, 단독 {len(single)}개)")
    for dest_name, src_paths in multi:
        print(f"  📀 {dest_name}")
        for src in src_paths:
            print(f"       <- {os.path.basename(src)}")

    # [3] output 에 복사 (이미 있는 폴더는 스킵)
    print("\n[3] output/ 에 복사 및 변환")
    merged_count = copied_count = skipped_count = error_count = 0
    for dest_name, src_paths in groups:
        dest_dir = os.path.join(output_base, dest_name)
        if os.path.isdir(dest_dir):
            print(f"  ⏭  이미 존재, 건너뜀: {dest_name}")
            skipped_count += 1
            continue
        print(f"  처리 중: {dest_name}")
        try:
            result = process_group(dest_name, src_paths, output_base)
        except Exception as e:
            print(f"    ⚠  오류: {e}")
            error_count += 1
            continue
        if result == 'merged':
            print(f"    ✅ 멀티 트랙 -> bin 병합 + cu2 생성")
            merged_count += 1
        else:
            print(f"    📋 그대로 복사")
            copied_count += 1
    print(f"\n  결과: cu2 생성 {merged_count}개 / 복사 {copied_count}개 "
          f"/ 기존 {skipped_count}개 / 오류 {error_count}개")

    # [4] MULTIDISC.LST
    print("\n[4] MULTIDISC.LST 생성")
    lst_path = write_multidisc_lst(output_base, groups)
    if lst_path:
        print(f"  ✅ {lst_path}")
    else:
        print("  멀티 디스크 없음, 생성 안 함.")

    # [5] 썸네일 다운로드
    print("\n[5] 썸네일 다운로드")
    download_thumbnails(output_base)

    print("\n" + "=" * 60)
    print(f"완료! 결과물: {output_base}")


if __name__ == '__main__':
    main()
