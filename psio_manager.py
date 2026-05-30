"""
PSIO Game Manager
사용법: python psio_manager.py
"""

import os, re, sys, shutil, threading, urllib.request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk   # pillow — 없으면 아래서 안내

# ── PSX 유틸 ────────────────────────────────────────────────

SERIAL_REGEX = re.compile(
    r'((SLPS|SLES|SLUS|SCPS|SCUS|SCES|SIPS|SLPM|SLEH|SLED|SCED|ESPM|PBPX|LSP)[_P\-])|(LSP9|907127)'
)
SERIAL_EX = {'SLUSP':'SLUS_','LSP9':'LSP_9','907127':'LSP_907127'}
COVER_URL   = "https://ncirocco.github.io/PSIO-Library/images/covers_by_id/{}.bmp"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".psio_manager.json")

# 국가 → 국기 이모지
FLAG_MAP = {
    'Japan':           '🇯🇵',
    'USA':             '🇺🇸',
    'Europe':          '🇪🇺',
    'Korea':           '🇰🇷',
    'Australia':       '🇦🇺',
    'Brazil':          '🇧🇷',
    'Canada':          '🇨🇦',
    'China':           '🇨🇳',
    'France':          '🇫🇷',
    'Germany':         '🇩🇪',
    'Italy':           '🇮🇹',
    'Netherlands':     '🇳🇱',
    'Russia':          '🇷🇺',
    'Spain':           '🇪🇸',
    'Sweden':          '🇸🇪',
    'Taiwan':          '🇹🇼',
    'World':           '🌍',
    'Asia':            '🌏',
    'Latin America':   '🌎',
}

REGION_RE = re.compile(
    r'[(](Japan|USA|Europe|Korea|Australia|Brazil|Canada|China|France|Germany'
    r'|Italy|Netherlands|Russia|Spain|Sweden|Taiwan|World|Asia|Latin America)[^)]*[)]',
    re.IGNORECASE
)

def get_flag(name: str) -> str:
    try:
        m = REGION_RE.search(name)
        if m:
            region = m.group(1)
            for k in FLAG_MAP:
                if k.lower() == region.lower():
                    return FLAG_MAP[k]
    except Exception:
        pass
    return '🌐'

GENRE_MAP = {
    'final fantasy':'RPG','dragon quest':'RPG','chrono':'RPG','xenogears':'RPG',
    'vagrant':'RPG','legend of dragoon':'RPG','wild arms':'RPG','breath of fire':'RPG',
    'suikoden':'RPG','persona':'RPG','tales of':'RPG','star ocean':'RPG',
    'parasite eve':'RPG','castlevania':'Action','metal gear':'Action',
    'crash':'Action','spyro':'Action','tomb raider':'Action','ape escape':'Action',
    'resident evil':'Horror','biohazard':'Horror','silent hill':'Horror',
    'tekken':'Fighting','street fighter':'Fighting','king of fighters':'Fighting',
    'marvel vs':'Fighting','soul blade':'Fighting','soul edge':'Fighting',
    'gran turismo':'Racing','ridge racer':'Racing','wipeout':'Racing',
    'need for speed':'Racing','colin mcrae':'Racing','aconcagua':'Adventure',
}

def guess_genre(name):
    low = name.lower()
    for k, v in GENRE_MAP.items():
        if k in low: return v
    return 'Other'

def get_serial(bin_path):
    try:
        with open(bin_path,'rb') as f:
            while True:
                chunk = f.read(1024*1024)
                if not chunk: break
                t = chunk.decode('latin-1', errors='replace')
                m = SERIAL_REGEX.search(t)
                if m:
                    raw = t[m.start():m.start()+11]
                    s = raw.replace('.','').replace('-','_',1).replace('-','')
                    for k,v in SERIAL_EX.items():
                        if k in s: s=s.replace(k,v)
                    return s[:8]+'.'+s[8:10]
    except: pass
    return None

def folder_size(path):
    total = 0
    for dp,_,files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(dp,f))
            except: pass
    return total

def fmt(b):
    for u in ['B','KB','MB','GB']:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

def count_discs(path):
    cues = [f for f in os.listdir(path) if f.lower().endswith('.cue')]
    return max(1, len(cues))

def has_thumb(path):
    return any(f.lower().endswith('.bmp') for f in os.listdir(path))

def thumb_path(path):
    for f in os.listdir(path):
        if f.lower().endswith('.bmp'):
            return os.path.join(path, f)
    return None

def scan_games(folder):
    entries = sorted(e for e in os.listdir(folder)
                     if os.path.isdir(os.path.join(folder, e)))
    total = len(entries)
    for i, entry in enumerate(entries):
        path = os.path.join(folder, entry)
        # 각 cue 파일 → 디스크 하나로 처리
        cues = sorted(f for f in os.listdir(path) if f.lower().endswith('.cue'))
        bins = sorted(f for f in os.listdir(path) if f.lower().endswith('.bin'))

        if len(cues) >= 2:
            # 멀티 디스크: cue마다 별도 항목
            for disc_idx, cue in enumerate(cues, 1):
                cue_stem = os.path.splitext(cue)[0]
                bin_name = cue_stem + '.bin'
                bin_path = os.path.join(path, bin_name)
                if not os.path.exists(bin_path) and bins:
                    bin_path = os.path.join(path, bins[0])
                serial = get_serial(bin_path) if os.path.exists(bin_path) else None
                size   = folder_size(path) // len(cues)
                yield i, total, {
                    'name':       entry,
                    'path':       path,
                    'genre':      guess_genre(entry),
                    'serial':     serial or '—',
                    'discs':      len(cues),
                    'disc_index': disc_idx,
                    'cue':        cue,
                    'size':       size,
                    'size_str':   fmt(size),
                    'thumb':      has_thumb(path),
                    'row_id':     f"{entry}__disc{disc_idx}",
                    'fav':        False,
                'flag':       get_flag(entry),
                    'flag':       get_flag(entry),
                }
        else:
            # 싱글 디스크
            serial = get_serial(os.path.join(path, bins[0])) if bins else None
            size   = folder_size(path)
            yield i, total, {
                'name':       entry,
                'path':       path,
                'genre':      guess_genre(entry),
                'serial':     serial or '—',
                'discs':      1,
                'disc_index': 1,
                'cue':        cues[0] if cues else '',
                'size':       size,
                'size_str':   fmt(size),
                'thumb':      has_thumb(path),
                'row_id':     entry,
                'fav':        False,
            }

# ── GUI ─────────────────────────────────────────────────────

ACCENT  = "#2E86DE"
BG      = "#F5F4F0"
PANEL   = "#FFFFFF"
BORDER  = "#DDDCD7"
SUCCESS = "#1D9E75"
DANGER  = "#C0392B"
MUTED   = "#888"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PSIO Game Manager")
        self.geometry("1100x760")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.src_folder  = tk.StringVar()
        self.dst_folder  = tk.StringVar()
        self.search_var  = tk.StringVar()
        self.genre_var   = tk.StringVar(value="전체")
        self.thumb_var   = tk.StringVar(value="전체")
        self.ow_all        = tk.BooleanVar(value=False)
        self.skip_existing = tk.BooleanVar(value=False)
        self.region_var    = tk.StringVar(value="전체")

        self.all_games:      list[dict] = []
        self.filtered:       list[dict] = []
        self.selected:       set[str]   = set()
        self._sort_col = "name"
        self._sort_rev = False
        self._thumb_photo = None   # GC 방지

        self._build()
        self._bind()
        self._load_config()

    # ── 빌드 ────────────────────────────────────────────────

    def _build(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".",             font=("Segoe UI", 10))
        s.configure("Treeview",      font=("Segoe UI", 10), rowheight=24,
                    background=PANEL, fieldbackground=PANEL)
        s.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                    background="#EBEBEB", relief="flat")
        s.map("Treeview", background=[("selected", "#E3F0FC")],
                          foreground=[("selected", "#1A1A1A")])
        s.configure("Accent.TButton", font=("Segoe UI", 11, "bold"),
                    background=ACCENT, foreground="white")
        s.map("Accent.TButton", background=[("active","#1A6FBB")])

        # ── 타이틀바 ──
        top = tk.Frame(self, bg=PANEL, height=46)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="PSIO Game Manager", font=("Segoe UI",14,"bold"),
                 bg=PANEL, fg="#1A1A1A").pack(side="left", padx=16, pady=10)
        tk.Button(top, text="📂  소스 폴더 열기", command=self._open_src,
                  font=("Segoe UI",10), bg=PANEL, relief="flat",
                  cursor="hand2", fg="#444").pack(side="right", padx=14, pady=10)
        # 타이틀 인라인 진행바 영역 (평소 숨김)
        self.inline_bar_frame = tk.Frame(top, bg=PANEL)
        self.inline_bar_frame.pack(side="right", padx=8, pady=10)
        self.inline_bar_label = tk.Label(self.inline_bar_frame, text="",
                                         bg=PANEL, fg="#555", font=("Segoe UI",9))
        self.inline_bar_label.pack(side="left", padx=(0,6))
        self.inline_bar_pv = tk.DoubleVar(value=0)
        self.inline_bar_prog = ttk.Progressbar(self.inline_bar_frame,
                                               variable=self.inline_bar_pv,
                                               maximum=100, length=220)
        self.inline_bar_prog.pack(side="left")
        tk.Frame(top, bg=BORDER, height=1).pack(side="bottom", fill="x")

        # ── 메인 (PanedWindow — 드래그 가능 분할) ──
        pane = tk.PanedWindow(self, orient="horizontal",
                              bg=BG, sashwidth=5, sashrelief="flat",
                              handlesize=0)
        pane.pack(fill="both", expand=True, padx=8, pady=(8,0))

        # ── 왼쪽: 검색바 + [버튼사이드바 | 목록+스크롤] ──
        left = tk.Frame(pane, bg=BG)
        pane.add(left, minsize=500, stretch="always")

        # 검색바 (상단 고정)
        bar = tk.Frame(left, bg=BG)
        bar.pack(side="top", fill="x", pady=(0, 4))

        sf = tk.Frame(bar, bg=PANEL, highlightbackground=BORDER,
                      highlightthickness=1, bd=0)
        sf.pack(side="left", fill="x", expand=True, ipady=1)
        tk.Label(sf, text="🔍", bg=PANEL, font=("Segoe UI",11)).pack(side="left", padx=6)
        tk.Entry(sf, textvariable=self.search_var, relief="flat",
                 bg=PANEL, font=("Segoe UI",11), fg="#333").pack(
                 side="left", fill="x", expand=True, pady=5)

        for lbl, var, opts in [
            ("장르",   self.genre_var, ["전체","RPG","Action","Horror","Fighting","Racing","Adventure","Other"]),
            ("국가",   self.region_var, ["전체","🇯🇵 Japan","🇺🇸 USA","🇪🇺 Europe","🇰🇷 Korea",
                                        "🌍 World","🌐 기타"]),
            ("썸네일", self.thumb_var, ["전체","있음","없음"]),
        ]:
            f = tk.Frame(bar, bg=BG)
            f.pack(side="left", padx=(6,0))
            tk.Label(f, text=lbl, bg=BG, fg=MUTED, font=("Segoe UI",9)).pack(anchor="w")
            cb = ttk.Combobox(f, textvariable=var, values=opts,
                              width=7, state="readonly", font=("Segoe UI",10))
            cb.pack()
            cb.bind("<<ComboboxSelected>>", lambda e: self._filter())

        # 중단: 버튼 사이드바(왼쪽 고정) + 목록(나머지)
        mid = tk.Frame(left, bg=BG)
        mid.pack(side="top", fill="both", expand=True)

        # 버튼 사이드바 (세로, 고정 너비)
        sidebar = tk.Frame(mid, bg=BG, width=110)
        sidebar.pack(side="left", fill="y", padx=(0, 4))
        sidebar.pack_propagate(False)

        self.lbl_count = tk.Label(sidebar, text="0개", bg=BG, fg=MUTED,
                                  font=("Segoe UI",9))
        self.lbl_count.pack(anchor="w", pady=(2,6), padx=4)

        for txt, cmd, color in [
            ("전체 선택",          self._sel_all,        PANEL),
            ("선택 해제",          self._desel_all,      PANEL),
            ("⬇ 썸네일 다운로드",  self._dl_thumbs,      PANEL),
            ("🖼 썸네일 직접 생성", self._make_thumb,     PANEL),
            ("★ 즐겨찾기 등록",    self._fav_selected,   "#FFFBEA"),
            ("🍀 Feeling Lucky",   self._feeling_lucky,  "#E8F8EF"),
        ]:
            tk.Button(sidebar, text=txt, command=cmd,
                      font=("Segoe UI",9), bg=color, relief="solid",
                      bd=1, cursor="hand2", wraplength=90).pack(
                      fill="x", pady=2, padx=2)

        # 목록 테이블 + 스크롤바
        tree_frame = tk.Frame(mid, bg=BG)
        tree_frame.pack(side="left", fill="both", expand=True)

        cols = ("fav","flag","chk","name","genre","serial","discs","size","thumb")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 selectmode="none")
        hdrs = [("fav","★",28),("flag","",32),("chk","",28),("name","게임명",0),
                ("genre","장르",70),("serial","시리얼",90),("discs","💿",38),
                ("size","용량",72),("thumb","🖼",30)]
        for cid, text, w in hdrs:
            self.tree.heading(cid, text=text,
                              command=lambda c=cid: self._sort(c))
            anchor = "w" if cid == "name" else "center"
            if w:
                self.tree.column(cid, width=w, minwidth=w, stretch=(cid=="name"), anchor=anchor)
            else:
                self.tree.column(cid, stretch=True, anchor=anchor)

        self.tree.tag_configure("sel",     background="#E3F0FC")
        self.tree.tag_configure("fav",     background="#FFFBEA", foreground="#7A5800")
        self.tree.tag_configure("fav_sel", background="#FFF3C4", foreground="#7A5800")
        self.tree.tag_configure("odd",     background="#FAFAF8")
        self.tree.tag_configure("even",    background=PANEL)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # ── 오른쪽: 썸네일 + 전송 패널 ──
        right = tk.Frame(pane, bg=PANEL,
                         highlightbackground=BORDER, highlightthickness=1)
        pane.add(right, minsize=220, width=260, stretch="never")

        # 썸네일 영역
        self.thumb_frame = tk.Frame(right, bg="#EAEAE8", height=160)
        self.thumb_frame.pack(fill="x")
        self.thumb_frame.pack_propagate(False)
        self.thumb_lbl = tk.Label(self.thumb_frame, text="썸네일 없음",
                                  bg="#EAEAE8", fg=MUTED,
                                  font=("Segoe UI",10))
        self.thumb_lbl.pack(expand=True)

        inner = tk.Frame(right, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=12)

        def sec(t):
            tk.Label(inner, text=t, bg=PANEL, fg=MUTED,
                     font=("Segoe UI",9)).pack(anchor="w", pady=(10,2))

        # 대상 폴더
        sec("대상 폴더")
        df = tk.Frame(inner, bg=PANEL)
        df.pack(fill="x")
        tk.Entry(df, textvariable=self.dst_folder, font=("Segoe UI",10),
                 relief="solid", bd=1, fg="#333").pack(side="left", fill="x",
                                                        expand=True, ipady=3)
        tk.Button(df, text="···", command=self._open_dst,
                  font=("Segoe UI",10), bg="#F0EFEB", relief="flat",
                  cursor="hand2", padx=6).pack(side="left", padx=(3,0))

        # 용량 카드
        sec("용량")
        cards = tk.Frame(inner, bg=PANEL)
        cards.pack(fill="x")
        self.lbl_sel  = self._card(cards, "선택 용량", "0 B",    "#1A1A1A", True)
        self.lbl_free = self._card(cards, "남은 공간", "—",       SUCCESS,  False)

        sec("드라이브 사용량")
        pf = tk.Frame(inner, bg=PANEL)
        pf.pack(fill="x")
        self.pv = tk.DoubleVar(value=0)
        ttk.Progressbar(pf, variable=self.pv, maximum=100).pack(
            side="left", fill="x", expand=True)
        self.lbl_pct = tk.Label(pf, text="0%", bg=PANEL, fg=MUTED,
                                font=("Segoe UI",9), width=5)
        self.lbl_pct.pack(side="left")

        # 선택 목록
        sec("선택된 게임")
        self.sel_box = tk.Listbox(inner, font=("Segoe UI",9), relief="flat",
                                  bg="#F5F4F0", fg="#333", selectmode="none",
                                  height=5, highlightthickness=0)
        self.sel_box.pack(fill="both", expand=True)

        # 전송 옵션
        tk.Checkbutton(inner, text="이미 있는 게임 제외",
                       variable=self.skip_existing, bg=PANEL, fg="#555",
                       font=("Segoe UI",9), anchor="w").pack(
                       fill="x", pady=(8,0))
        tk.Checkbutton(inner, text="중복 시 묻지 않고 덮어쓰기",
                       variable=self.ow_all, bg=PANEL, fg="#555",
                       font=("Segoe UI",9), anchor="w").pack(
                       fill="x", pady=(2,0))

        # 복사 버튼
        self.btn_copy = tk.Button(inner, text="SD카드로 복사 →",
                                  command=self._copy,
                                  font=("Segoe UI",12,"bold"),
                                  bg=ACCENT, fg="white", relief="flat",
                                  cursor="hand2", pady=9, state="disabled")
        self.btn_copy.pack(fill="x", pady=10)

        # 진행바는 타이틀바 인라인으로 통합 (scan_bar/copy_bar는 dict로 유지)
        self.scan_bar = {"pv": self.inline_bar_pv, "lbl": self.inline_bar_label,
                         "frame": self.inline_bar_frame, "color": "#3B6D11", "prefix": "📂 스캔"}
        self.copy_bar = {"pv": self.inline_bar_pv, "lbl": self.inline_bar_label,
                         "frame": self.inline_bar_frame, "color": "#185FA5", "prefix": "📋 복사"}

        # ── 상태바 ──
        self.status = tk.Label(self, text="소스 폴더를 선택하세요.",
                               bg="#E8E7E2", fg="#555", font=("Segoe UI",10),
                               anchor="w", padx=12, pady=3)
        self.status.pack(side="bottom", fill="x")

    def _make_bar(self, parent, bg, fg, label):
        f = tk.Frame(parent, bg=bg, pady=5)
        tk.Label(f, text=label, bg=bg, fg=fg,
                 font=("Segoe UI",10,"bold"), padx=12).pack(side="left")
        pv = tk.DoubleVar(value=0)
        ttk.Progressbar(f, variable=pv, maximum=100, length=300).pack(
            side="left", padx=8)
        lbl = tk.Label(f, text="", bg=bg, fg=fg, font=("Segoe UI",9))
        lbl.pack(side="left")
        return {"frame": f, "pv": pv, "lbl": lbl}

    def _card(self, parent, title, init, color, left):
        f = tk.Frame(parent, bg="#F5F4F0", width=96, height=58)
        f.pack(side="left" if left else "right",
               padx=(0,4) if left else (4,0), pady=2, fill="x", expand=True)
        f.pack_propagate(False)
        tk.Label(f, text=title, bg="#F5F4F0", fg=MUTED,
                 font=("Segoe UI",8)).pack(pady=(6,0))
        lbl = tk.Label(f, text=init, bg="#F5F4F0", fg=color,
                       font=("Segoe UI",12,"bold"))
        lbl.pack()
        return lbl

    # ── 이벤트 ──────────────────────────────────────────────

    def _bind(self):
        self.tree.bind("<Button-1>",         self._click)
        self.tree.bind("<Double-Button-1>",  self._dbl_click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: None)
        self.search_var.trace_add("write",   lambda *_: self._filter())
        self.dst_folder.trace_add("write",   lambda *_: self._dst_info())

    # ── 소스 열기 ────────────────────────────────────────────

    def _open_src(self):
        folder = filedialog.askdirectory(title="소스 폴더 선택")
        if not folder: return
        self.src_folder.set(folder)
        self._save_config()
        self.all_games = []
        self.selected.clear()
        self._refresh()
        self._bar_show(self.scan_bar, True)
        self._st("스캔 중...")

        def worker():
            games = []
            for i, total, g in scan_games(folder):
                games.append(g)
                pct = (i+1)/total*100 if total else 100
                self.after(0, lambda p=pct, n=g['name']: (
                    self.scan_bar["pv"].set(p),
                    self.scan_bar["lbl"].config(text=f"{n[:40]}")
                ))
            self.after(0, lambda: self._scan_done(games))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_done(self, games):
        self.all_games = games
        # flag 필드 누락 방어
        for g in self.all_games:
            if 'flag' not in g:
                g['flag'] = get_flag(g.get('name', ''))
            if 'fav' not in g:
                g['fav'] = False
        self._bar_show(self.scan_bar, False)
        self._load_genres()
        self._load_favs()
        self._filter()
        # 스캔 완료 후 대상 폴더 이미 설정돼 있으면 동기화
        dst = self.dst_folder.get()
        if dst and os.path.isdir(dst):
            self._sync_existing(dst)
        self._st(f"{len(games)}개 게임 로드됨.")

    def _open_dst(self):
        f = filedialog.askdirectory(title="대상 폴더 선택")
        if f:
            self.dst_folder.set(f)
            self._save_config()

    # ── 필터 / 정렬 ──────────────────────────────────────────

    def _filter(self):
        q   = self.search_var.get().lower()
        gn  = self.genre_var.get()
        th  = self.thumb_var.get()
        rgn = self.region_var.get()
        def match_region(g):
            if rgn == "전체": return True
            flag = g['flag']
            if "🌐 기타" == rgn: return flag == '🌐'
            return rgn.split(" ", 1)[1] in g['name'] if " " in rgn else True
        self.filtered = [
            g for g in self.all_games
            if (q in g['name'].lower() or q in g['serial'].lower())
            and (gn == "전체" or g['genre'] == gn)
            and match_region(g)
            and (th == "전체"
                 or (th == "있음" and g['thumb'])
                 or (th == "없음" and not g['thumb']))
        ]
        self._sort(self._sort_col, toggle=False)

    def _sort(self, col, toggle=True):
        if toggle:
            self._sort_rev = (not self._sort_rev) if self._sort_col == col else False
            self._sort_col = col
        key = {"name":  lambda g: g['name'].lower(),
               "genre": lambda g: g['genre'],
               "serial":lambda g: g['serial'],
               "discs": lambda g: g['discs'],
               "size":  lambda g: g['size'],
               "thumb": lambda g: g['thumb']}.get(col)
        if key:
            self.filtered.sort(key=key, reverse=self._sort_rev)
        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        # 즐겨찾기 우선, 그 안에서 알파벳 순
        ordered = sorted(self.filtered,
                         key=lambda g: (0 if g['fav'] else 1, g['name'].lower()))
        for i, g in enumerate(ordered):
            rid   = g['row_id']
            chk   = "☑" if rid in self.selected else "☐"
            fav   = "★" if g['fav'] else "☆"
            thumb = "✓" if g['thumb'] else "✗"
            if g['discs'] >= 2:
                display = f"{g['name']}  —  Disc {g['disc_index']}/{g['discs']}"
            else:
                display = g['name']
            if g['fav'] and rid in self.selected:
                tag = "fav_sel"
            elif g['fav']:
                tag = "fav"
            elif rid in self.selected:
                tag = "sel"
            else:
                tag = "odd" if i % 2 else "even"
            self.tree.insert("", "end", iid=rid, tags=(tag,),
                             values=(fav, g.get('flag','🌐'), chk, display, g['genre'],
                                     g['serial'], g['disc_index'], g['size_str'], thumb))
        self.lbl_count.config(text=f"게임 {len(self.filtered)}개")

    # ── 선택 ────────────────────────────────────────────────

    def _click(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        col = self.tree.identify_column(event.x)
        g = next((x for x in self.filtered if x['row_id'] == item), None)
        if not g: return
        # ★ 컬럼(#1) → 즐겨찾기 토글
        if col == "#1":
            g['fav'] = not g['fav']
            for game in self.all_games:
                if game['name'] == g['name']:
                    game['fav'] = g['fav']
            self._save_favs()
            self._refresh()
            return
        # 장르 컬럼(#4) 더블클릭 → 직접 편집 (_dbl_click에서 처리)
        if item in self.selected:
            self.selected.discard(item)
        else:
            self.selected.add(item)
        self._refresh()
        self._update_sel()
        self._show_thumb(item)

    def _show_thumb(self, name):
        g = next((x for x in self.all_games if x['row_id'] == name), None)
        if not g:
            return
        tp = thumb_path(g['path'])
        if tp:
            try:
                img = Image.open(tp)
                # 썸네일 영역 크기에 맞춰 비율 유지
                img.thumbnail((240, 176), Image.LANCZOS)
                self._thumb_photo = ImageTk.PhotoImage(img)
                self.thumb_lbl.config(image=self._thumb_photo, text="",
                                      bg="#EAEAE8")
                return
            except Exception:
                pass
        self._thumb_photo = None
        self.thumb_lbl.config(image="", text="썸네일 없음", bg="#EAEAE8")

    def _sel_all(self):
        self.selected = {g['row_id'] for g in self.filtered}
        self._refresh(); self._update_sel()

    def _desel_all(self):
        self.selected.clear()
        self._refresh(); self._update_sel()

    def _update_sel(self):
        sel = [g for g in self.all_games if g['row_id'] in self.selected]
        total = sum(g['size'] for g in sel)
        self.lbl_sel.config(text=fmt(total))
        self.sel_box.delete(0, "end")
        for g in sorted(sel, key=lambda x: x['name']):
            self.sel_box.insert("end", f"{g['name'][:30]}  {g['size_str']}")
        has = bool(sel) and bool(self.dst_folder.get())
        self.btn_copy.config(state="normal" if has else "disabled")
        self._dst_info()

    def _dst_info(self):
        dst = self.dst_folder.get()
        if not dst or not os.path.isdir(dst):
            self.lbl_free.config(text="—")
            self.pv.set(0); self.lbl_pct.config(text="0%")
            return
        u = shutil.disk_usage(dst)
        pct = u.used / u.total * 100 if u.total else 0
        self.lbl_free.config(text=fmt(u.free))
        self.pv.set(pct)
        self.lbl_pct.config(text=f"{pct:.0f}%")
        # 대상 폴더에 이미 있는 게임 자동 체크
        self._sync_existing(dst)
        has = bool(self.selected) and bool(self.dst_folder.get())
        self.btn_copy.config(state="normal" if has else "disabled")

    def _sync_existing(self, dst: str):
        """대상 폴더에 이미 존재하는 게임을 자동으로 선택 표시."""
        if not self.all_games:
            return
        try:
            existing = set(os.listdir(dst))
        except Exception:
            return
        changed = False
        for g in self.all_games:
            if g['name'] in existing:
                if g['row_id'] not in self.selected:
                    self.selected.add(g['row_id'])
                    changed = True
        if changed:
            self._refresh()
            self._update_sel()

    # ── 썸네일 다운로드 ──────────────────────────────────────

    def _dl_thumbs(self):
        targets = [g for g in self.all_games
                   if g['row_id'] in self.selected
                   and not g['thumb'] and g['serial'] != '—']
        if not targets:
            messagebox.showinfo("썸네일", "다운로드할 대상이 없습니다.")
            return

        def worker():
            ok = fail = 0
            for g in targets:
                dst = os.path.join(g['path'], f"{g['serial']}.bmp")
                try:
                    urllib.request.urlretrieve(COVER_URL.format(g['serial']), dst)
                    g['thumb'] = True; ok += 1
                    self.after(0, lambda n=g['name']: self._st(f"다운로드: {n}"))
                except Exception:
                    if os.path.exists(dst): os.remove(dst)
                    fail += 1
            self.after(0, lambda: (
                self._refresh(),
                self._st(f"썸네일: 성공 {ok} / 실패 {fail}"),
                messagebox.showinfo("썸네일 다운로드", f"성공 {ok}개 / 실패 {fail}개")
            ))
        threading.Thread(target=worker, daemon=True).start()

    # ── 복사 ────────────────────────────────────────────────

    def _copy(self):
        dst = self.dst_folder.get()
        if not dst or not os.path.isdir(dst):
            messagebox.showerror("오류", "대상 폴더가 올바르지 않습니다."); return

        sel = [g for g in self.all_games if g['row_id'] in self.selected]
        if not sel: return

        # 이미 있는 게임 제외 옵션
        if self.skip_existing.get():
            try:
                existing = set(os.listdir(dst))
            except Exception:
                existing = set()
            skipped_names = {g['name'] for g in sel if g['name'] in existing}
            sel = [g for g in sel if g['name'] not in skipped_names]
            if skipped_names:
                self._st(f"이미 있는 게임 {len(skipped_names)}개 제외됨")
            if not sel:
                messagebox.showinfo("전송", "전송할 게임이 없습니다.\n(모두 대상 폴더에 이미 존재)")
                return

        total_b = sum(g['size'] for g in sel)
        free    = shutil.disk_usage(dst).free
        if total_b > free:
            if not messagebox.askyesno("용량 부족",
                f"선택 {fmt(total_b)} > 남은 공간 {fmt(free)}\n계속하시겠습니까?"):
                return

        ow = [self.ow_all.get()]
        done_b = [0]

        def copy_tree(src_dir, dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
            for item in os.listdir(src_dir):
                s = os.path.join(src_dir, item)
                d = os.path.join(dst_dir, item)
                if os.path.isdir(s):
                    copy_tree(s, d)
                else:
                    fsize = os.path.getsize(s)
                    shutil.copy2(s, d)
                    done_b[0] += fsize
                    pct = done_b[0] / total_b * 100 if total_b else 100
                    self.after(0, lambda p=pct: (
                        self.copy_bar["pv"].set(p),
                        self.copy_bar["lbl"].config(
                            text=f"{fmt(done_b[0])} / {fmt(total_b)}  ({p:.0f}%)")
                    ))

        def worker():
            ok = fail = skip = 0
            self.after(0, lambda: (
                self._bar_show(self.copy_bar, True),
                self.btn_copy.config(state="disabled")
            ))
            for g in sel:
                dp = os.path.join(dst, g['name'])
                self.after(0, lambda n=g['name']: self._st(f"복사 중: {n}"))
                if os.path.exists(dp):
                    if not ow[0]:
                        ans = self._ask_ow(g['name'])
                        if ans == "skip":
                            done_b[0] += g['size']; skip += 1; continue
                        elif ans == "all": ow[0] = True
                    try: shutil.rmtree(dp)
                    except: fail += 1; continue
                try:
                    copy_tree(g['path'], dp); ok += 1
                except: fail += 1
            self.after(0, lambda: (
                self._bar_show(self.copy_bar, False),
                self.btn_copy.config(state="normal"),
                self._dst_info(),
                self._st(f"완료: 성공 {ok} / 건너뜀 {skip} / 실패 {fail}"),
                messagebox.showinfo("복사 완료",
                    f"성공 {ok}개\n건너뜀 {skip}개\n실패 {fail}개")
            ))
        threading.Thread(target=worker, daemon=True).start()

    def _ask_ow(self, name):
        res = {"v": "skip"}
        ev  = threading.Event()
        def show():
            w = tk.Toplevel(self)
            w.title("중복 폴더"); w.grab_set(); w.resizable(False,False)
            tk.Label(w, text=f"이미 존재합니다:\n{name}",
                     font=("Segoe UI",11), pady=12, padx=20).pack()
            bf = tk.Frame(w); bf.pack(pady=(0,12), padx=20, fill="x")
            def ch(v): res["v"]=v; w.destroy(); ev.set()
            tk.Button(bf,text="덮어쓰기",    command=lambda:ch("yes"),
                      bg=ACCENT,fg="white",relief="flat",
                      padx=10,pady=6).pack(side="left",expand=True,fill="x",padx=3)
            tk.Button(bf,text="건너뜀",      command=lambda:ch("skip"),
                      relief="solid",bd=1,
                      padx=10,pady=6).pack(side="left",expand=True,fill="x",padx=3)
            tk.Button(bf,text="모두 덮어쓰기",command=lambda:ch("all"),
                      bg="#C0392B",fg="white",relief="flat",
                      padx=10,pady=6).pack(side="left",expand=True,fill="x",padx=3)
            w.protocol("WM_DELETE_WINDOW", lambda:ch("skip"))
        self.after(0, show); ev.wait(); return res["v"]

    # ── 진행바 토글 ──────────────────────────────────────────

    def _bar_show(self, bar, show):
        if show:
            self.inline_bar_label.config(fg=bar["color"])
            self.inline_bar_prog.config(style="TProgressbar")
            bar["pv"].set(0)
            bar["lbl"].config(text=bar["prefix"])
        else:
            bar["pv"].set(0)
            bar["lbl"].config(text="")


    # ── 장르 직접 편집 ───────────────────────────────────────


    def _dbl_click(self, event):
        item = self.tree.identify_row(event.y)
        col  = self.tree.identify_column(event.x)
        if not item: return
        g = next((x for x in self.filtered if x['row_id'] == item), None)
        if not g: return
        if col == "#5":  # 장르 컬럼
            self._edit_genre(item, g)

    def _edit_genre(self, row_id: str, g: dict):
        """장르 셀 더블클릭 → 인라인 편집 팝업."""
        # 셀 위치 계산
        bbox = self.tree.bbox(row_id, "#3")
        if not bbox: return
        x, y, w, h = bbox

        genres = ["RPG","Action","Horror","Fighting","Racing",
                  "Adventure","Sports","Simulation","Puzzle","Shooter","Other"]

        var = tk.StringVar(value=g['genre'])
        cb = ttk.Combobox(self.tree, textvariable=var,
                          values=genres, font=("Segoe UI", 10),
                          width=12, state="normal")
        cb.place(x=x, y=y, width=max(w, 110), height=h)
        cb.focus_set()
        cb.event_generate('<Button-1>')

        def commit(event=None):
            new_genre = var.get().strip()
            if new_genre:
                g['genre'] = new_genre
                # 같은 게임(name 동일)의 모든 디스크 행도 업데이트
                for game in self.all_games:
                    if game['name'] == g['name']:
                        game['genre'] = new_genre
                self._save_genres()
            cb.destroy()
            self._refresh()

        cb.bind("<Return>",    commit)
        cb.bind("<FocusOut>",  commit)
        cb.bind("<<ComboboxSelected>>", commit)

    def _genre_db_path(self):
        """장르 DB 저장 경로 (소스 폴더 기준)."""
        src = self.src_folder.get()
        if src:
            return os.path.join(src, '.psio_genres.json')
        return None

    def _save_genres(self):
        """현재 모든 게임의 장르를 JSON으로 저장."""
        path = self._genre_db_path()
        if not path: return
        import json
        db = {g['name']: g['genre'] for g in self.all_games}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
        except Exception: pass

    def _load_genres(self):
        """저장된 장르 DB를 불러와 all_games에 반영."""
        path = self._genre_db_path()
        if not path or not os.path.exists(path): return
        import json
        try:
            with open(path, 'r', encoding='utf-8') as f:
                db = json.load(f)
            for g in self.all_games:
                if g['name'] in db:
                    g['genre'] = db[g['name']]
        except Exception: pass

    # ── 썸네일 커스텀 생성 ───────────────────────────────────

    def _make_thumb(self):
        """선택된 게임에 커스텀 썸네일 생성."""
        sel = [g for g in self.all_games if g['row_id'] in self.selected]
        if not sel:
            messagebox.showinfo("썸네일 생성", "먼저 게임을 선택하세요."); return
        if len(sel) > 1:
            messagebox.showinfo("썸네일 생성",
                "썸네일 생성은 한 번에 하나씩 선택해주세요."); return

        g = sel[0]
        win = tk.Toplevel(self)
        win.title(f"썸네일 생성 — {g['name'][:40]}")
        win.geometry("440x520")
        win.resizable(False, False)
        win.grab_set()
        win.configure(bg=PANEL)

        tk.Label(win, text="이미지 파일 또는 URL을 입력하세요.",
                 bg=PANEL, fg="#555", font=("Segoe UI", 10)).pack(pady=(16,4))
        tk.Label(win, text="변환 후 PSIO 썸네일 규격(BMP, 정사각형)으로 저장됩니다.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0,10))

        # URL / 파일 경로 입력
        row = tk.Frame(win, bg=PANEL)
        row.pack(fill="x", padx=20)
        src_var = tk.StringVar()
        entry = tk.Entry(row, textvariable=src_var, font=("Segoe UI", 10),
                 relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True, ipady=4)

        def browse():
            p = filedialog.askopenfilename(
                title="이미지 선택",
                filetypes=[("이미지", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
                           ("모든 파일", "*.*")],
                parent=win)
            if p: src_var.set(p)

        tk.Button(row, text="파일", command=browse,
                  font=("Segoe UI", 10), bg="#F0EFEB",
                  relief="flat", padx=8, takefocus=0).pack(side="left", padx=(4,0))

        # 크기 고정 안내
        tk.Label(win, text="출력 크기: 80x84 px  /  24-bit BMP  (PSIO 규격 고정)",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(4, 0))

        THUMB_W, THUMB_H = 80, 84

        def _load_img(src):
            import io as _io, ssl
            src = src.strip().strip('"').strip("'")
            if src.startswith("http"):
                req = urllib.request.Request(src, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                })
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                    data = r.read()
                return Image.open(_io.BytesIO(data)).copy()
            return Image.open(src)

        def _fit_to_canvas(img, W, H):
            """폭 맞춤: W 기준 비율 유지 스케일, 높이 부족 시 검정 패딩."""
            img = img.convert("RGB")
            w_i, h_i = img.size
            scale = W / w_i
            new_h = round(h_i * scale)
            img = img.resize((W, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (W, H), (0, 0, 0))
            if new_h <= H:
                canvas.paste(img, (0, (H - new_h) // 2))
            else:
                top = (new_h - H) // 2
                canvas.paste(img.crop((0, top, W, top + H)), (0, 0))
            return canvas

        # 미리보기 (2배 확대 표시)
        preview_lbl = tk.Label(win, bg="#000000", width=THUMB_W*2, height=THUMB_H*2,
                               text="미리보기", fg="#888", font=("Segoe UI", 9))
        preview_lbl.pack(pady=8)

        def preview(event=None):
            src = src_var.get().strip()
            if not src: return
            try:
                img = _load_img(src)
                img = _fit_to_canvas(img, THUMB_W, THUMB_H)
                disp = img.resize((THUMB_W*2, THUMB_H*2), Image.NEAREST)
                ph = ImageTk.PhotoImage(disp)
                preview_lbl.config(image=ph, text="")
                preview_lbl._ph = ph
            except Exception as e:
                preview_lbl.config(text=f"오류: {e}", image="")
        src_var.trace_add("write", lambda *_: self.after(400, preview))

        # 변환된 이미지 보관 (저장 버튼에서 사용)
        converted = {"img": None}

        def convert_preview():
            src = src_var.get().strip()
            if not src:
                messagebox.showwarning("입력 없음", "파일 또는 URL을 입력하세요.",
                                       parent=win); return
            try:
                img = _load_img(src)
                img = _fit_to_canvas(img, THUMB_W, THUMB_H)
                converted["img"] = img
                # 미리보기 갱신
                disp = img.resize((THUMB_W*2, THUMB_H*2), Image.NEAREST)
                ph = ImageTk.PhotoImage(disp)
                preview_lbl.config(image=ph, text="")
                preview_lbl._ph = ph
                btn_save.config(state="normal")
                status_lbl.config(text="✓ 변환 완료. 저장 버튼을 눌러주세요.",
                                   fg="#1D9E75")
            except Exception as e:
                status_lbl.config(text=f"오류: {e}", fg=DANGER)
                converted["img"] = None
                btn_save.config(state="disabled")

        def save():
            if not converted["img"]:
                return
            out_path = os.path.join(g['path'], "custom_thumb.bmp")
            try:
                converted["img"].save(out_path, "BMP")
                g['thumb'] = True
                for game in self.all_games:
                    if game['name'] == g['name']:
                        game['thumb'] = True
                self._refresh()
                self._show_thumb(g['row_id'])
                win.destroy()
                messagebox.showinfo("완료", f"썸네일 저장:\n{out_path}")
            except Exception as e:
                messagebox.showerror("저장 실패", str(e), parent=win)

        # Enter 키 → 변환
        entry.bind("<Return>", lambda e: convert_preview())
        entry.focus_set()

        # 상태 메시지
        status_lbl = tk.Label(win, text="", bg=PANEL, fg=MUTED,
                              font=("Segoe UI", 9))
        status_lbl.pack(pady=(4, 0))

        # 버튼 영역
        btn_frame = tk.Frame(win, bg=PANEL)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="변환 (미리보기)",
                  command=convert_preview, font=("Segoe UI", 11),
                  bg="#F0EFEB", relief="solid", bd=1,
                  padx=12, pady=6, cursor="hand2").pack(side="left", padx=4)

        btn_save = tk.Button(btn_frame, text="저장",
                             command=save, font=("Segoe UI", 11, "bold"),
                             bg=ACCENT, fg="white", relief="flat",
                             padx=16, pady=6, cursor="hand2", state="disabled")
        btn_save.pack(side="left", padx=4)

        tk.Button(btn_frame, text="취소",
                  command=win.destroy, font=("Segoe UI", 11),
                  relief="solid", bd=1,
                  padx=12, pady=6).pack(side="left", padx=4)


    # ── 즐겨찾기 저장/로드 ──────────────────────────────────

    def _fav_selected(self):
        """선택된 게임을 모두 즐겨찾기 등록."""
        if not self.selected:
            messagebox.showinfo("즐겨찾기", "먼저 게임을 선택하세요.")
            return
        count = 0
        for g in self.all_games:
            if g['row_id'] in self.selected and not g['fav']:
                g['fav'] = True
                count += 1
        self._save_favs()
        self._refresh()
        self._st(f"즐겨찾기 {count}개 등록됨.")

    def _fav_db_path(self):
        src = self.src_folder.get()
        return os.path.join(src, '.psio_favs.json') if src else None

    def _save_favs(self):
        import json
        path = self._fav_db_path()
        if not path: return
        favs = [g['name'] for g in self.all_games if g['fav']]
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(favs, f, ensure_ascii=False, indent=2)
        except Exception: pass

    def _load_favs(self):
        import json
        path = self._fav_db_path()
        if not path or not os.path.exists(path): return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                favs = set(json.load(f))
            for g in self.all_games:
                g['fav'] = g['name'] in favs
        except Exception: pass

    # ── 🍀 I'm Feeling Lucky ────────────────────────────────

    def _feeling_lucky(self):
        """대상 폴더 용량 안에서 게임을 랜덤 셔플 선택."""
        import random
        dst = self.dst_folder.get()
        if not dst or not os.path.isdir(dst):
            messagebox.showwarning("Lucky", "먼저 대상 폴더를 선택하세요."); return

        free = shutil.disk_usage(dst).free

        # 게임 단위로 묶기 (멀티 디스크는 name 기준으로 하나로)
        game_groups: dict[str, list[dict]] = {}
        for g in self.all_games:
            game_groups.setdefault(g['name'], []).append(g)

        # 전체 용량 = 폴더 용량 (각 그룹의 첫 번째 row size * discs로 중복 방지)
        games_list = []
        seen = set()
        for g in self.all_games:
            if g['name'] not in seen:
                seen.add(g['name'])
                total_size = sum(x['size'] for x in game_groups[g['name']])
                games_list.append({'name': g['name'], 'size': total_size,
                                   'rows': game_groups[g['name']]})

        random.shuffle(games_list)

        picked = []
        used = 0
        for gp in games_list:
            if used + gp['size'] <= free:
                picked.append(gp)
                used += gp['size']

        if not picked:
            messagebox.showinfo("🍀 Lucky", "용량에 맞는 게임을 찾지 못했습니다."); return

        # 선택 반영 (모든 디스크 행 포함)
        self.selected.clear()
        for gp in picked:
            for row in gp['rows']:
                self.selected.add(row['row_id'])

        self._refresh()
        self._update_sel()

        names = "\n".join(f"  • {gp['name']}" for gp in sorted(picked, key=lambda x: x['name']))
        messagebox.showinfo(
            "🍀 I'm Feeling Lucky",
            f"{len(picked)}개 게임 선택됨 ({fmt(used)})\n\n{names}"
        )

    # ── 설정 저장/로드 ──────────────────────────────────────

    def _save_config(self):
        import json
        cfg = {
            "src_folder": self.src_folder.get(),
            "dst_folder": self.dst_folder.get(),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_config(self):
        import json
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            src = cfg.get("src_folder", "")
            dst = cfg.get("dst_folder", "")
            if src and os.path.isdir(src):
                self.src_folder.set(src)
            if dst and os.path.isdir(dst):
                self.dst_folder.set(dst)
                self._dst_info()
        except Exception:
            pass

    def _st(self, msg):
        self.status.config(text=msg)


# ── 진입점 ──────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        import subprocess, sys
        print("Pillow 설치 중...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
        from PIL import Image, ImageTk

    app = App()
    app.mainloop()
