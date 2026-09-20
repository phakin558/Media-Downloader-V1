import os
import shutil
import subprocess
import sys
import platform
from pathlib import Path
from time import time
from urllib.request import Request, urlopen

# --- [CHECK] ต้องใช้ Python 3.12 ขึ้นไป ---
if sys.version_info < (3, 12):
    print(f"❌ This program requires Python 3.12+ (You are using {platform.python_version()})")
    print("📥 Download: https://www.python.org/downloads/")
    sys.exit(1)

try:
    from pathvalidate import sanitize_filename
except ImportError:
    print("❌ Missing libraries! Please run:")
    print('   pip install -U "yt-dlp[default]" pathvalidate')
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent

CYAN     = "\033[96m"
GREEN    = "\033[92m"
YELLOW   = "\033[93m"
RED      = "\033[91m"
MAGENTA  = "\033[95m"
BOLD     = "\033[1m"
DIM      = "\033[2m"
RESET    = "\033[0m"
DARK_RED = "\033[31m"


# ============================================================
# [FFMPEG] ค้นหา FFmpeg แบบข้ามระบบปฏิบัติการ
# ============================================================
def resolve_ffmpeg() -> str | None:
    system = platform.system()
    if system == "Windows":
        candidates = [
            BASE_DIR / "tools" / "windows" / "ffmpeg" / "bin" / "ffmpeg.exe",
            BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
    elif system == "Darwin":
        machine = platform.machine().lower()
        preferred = "arm64" if machine in ("arm64", "aarch64") else "x86_64"
        other = "x86_64" if preferred == "arm64" else "arm64"
        candidates = [
            BASE_DIR / "tools" / "ffmpeg" / "ffmpeg",
            BASE_DIR / "macOS" / "tools" / "ffmpeg" / "ffmpeg",
            BASE_DIR / "tools" / "macos" / preferred / "ffmpeg",
            BASE_DIR / "tools" / "macos" / other / "ffmpeg",
            BASE_DIR / "ffmpeg" / "bin" / "ffmpeg",
        ]
    else:
        candidates = [BASE_DIR / "tools" / "linux" / "ffmpeg"]

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        candidates.append(Path(system_ffmpeg))

    for c in candidates:
        if c.is_file():
            return str(c)
    return None


FFMPEG_PATH = resolve_ffmpeg()


# ============================================================
# [JS RUNTIME] yt-dlp ต้องใช้ Deno/Node/Bun แก้ n-challenge ของ YouTube
#  - ถ้าไม่มี → format หาย / โหลดไม่ได้ / error แปลก ๆ
#  - เรียงลำดับ: Deno (แนะนำโดย yt-dlp) > Node > Bun
# ============================================================
def resolve_js_runtime() -> tuple[str, str] | None:
    system = platform.system()
    exe = ".exe" if system == "Windows" else ""
    home = Path.home()

    candidates = [
        ("deno", BASE_DIR / "tools" / "deno" / f"deno{exe}"),
        ("node", BASE_DIR / "tools" / "node" / f"node{exe}"),
        ("bun",  BASE_DIR / "tools" / "bun" / f"bun{exe}"),
        ("deno", home / ".deno" / "bin" / f"deno{exe}"),   # deno install script
        ("bun",  home / ".bun" / "bin" / f"bun{exe}"),
    ]
    for name, p in candidates:
        if p.is_file():
            return name, str(p)

    for name in ("deno", "node", "bun"):
        found = shutil.which(name)
        if found:
            return name, found
    return None


JS_RUNTIME = resolve_js_runtime()


def print_js_runtime_help():
    print(f"{YELLOW}⚠️  JavaScript runtime not found (Deno / Node.js / Bun){RESET}")
    print(f"{DIM}   YouTube downloads will fail or miss formats without it.{RESET}")
    print(f"{YELLOW}📥 Install Deno (recommended):{RESET}")
    if platform.system() == "Windows":
        print("      winget install DenoLand.Deno")
        print("      (or)  irm https://deno.land/install.ps1 | iex")
    elif platform.system() == "Darwin":
        print("      brew install deno")
    else:
        print("      curl -fsSL https://deno.land/install.sh | sh")
    print(f"{DIM}   Then RESTART the terminal and run this program again.{RESET}")
    print()


# ---- [SPEED] ----
MAX_WORKERS = 8
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en",
}

# ---- [MODE] ----
MODE_M4A      = 'M4A'
MODE_MP4_1080 = 'MP4_1080'
MODE_MP4_MAX  = 'MP4_MAX'
MODE_THUMB    = 'THUMB'

MODE_INFO = {
    MODE_M4A:      {"label": "🎵 M4A Audio",          "color": CYAN},
    MODE_MP4_1080: {"label": "🎬 MP4 1080p",          "color": GREEN},
    MODE_MP4_MAX:  {"label": "🎬 MP4 Max Resolution", "color": RED},
    MODE_THUMB:    {"label": "🖼️ Thumbnail PNG",      "color": MAGENTA},
}

# ---- [COOKIES] browser ที่ใช้ดึง cookies (สลับด้วยคำสั่ง C) ----
COOKIE_BROWSERS = [None, "chrome", "edge", "firefox", "brave"]


def open_folder(path: Path):
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(path)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        print(f"❌ Cannot open folder: {exc}")


def get_download_path() -> Path:
    p = Path.home() / "Downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_unique_output(download_path: Path, base_name: str, ext: str = ".m4a") -> Path:
    candidate = download_path / f"{base_name}{ext}"
    if not candidate.exists():
        return candidate
    counter = 1
    while True:
        candidate = download_path / f"{base_name}_({counter}){ext}"
        if not candidate.exists():
            return candidate
        counter += 1


# ============================================================
# [SHORTS] แปลงลิงก์ Shorts / youtu.be ให้เป็นรูปแบบมาตรฐาน
# ============================================================
def normalize_url(url: str) -> str:
    if "/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0].split("&")[0].split("/")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[1].split("?")[0].split("&")[0].split("/")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    return url


def is_short(url: str) -> bool:
    return "/shorts/" in url


# ============================================================
# [ENGINE] yt-dlp backend
# ============================================================
def make_progress_hook(label_holder):
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            done = d.get('downloaded_bytes', 0)
            speed = (d.get('speed') or 0) / 1048576
            if total:
                pct = done / total * 100
                bar_len = 25
                filled = int(bar_len * done / total)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r{label_holder[0]} |{bar}| {pct:5.1f}% "
                      f"({done/1048576:6.1f}/{total/1048576:.1f} MB) "
                      f"{GREEN}{speed:5.1f} MB/s{RESET}  ", end="", flush=True)
        elif d['status'] == 'finished':
            print()
    return hook


def common_opts(cookie_browser: str | None) -> dict:
    """ค่าที่ต้องใช้ทั้งตอนดึงข้อมูลและตอนดาวน์โหลด"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'retries': 5,
        'fragment_retries': 5,
        'noplaylist': True,
        # ให้ yt-dlp โหลดสคริปต์แก้ challenge (EJS) เวอร์ชันล่าสุดจาก GitHub เอง
        'remote_components': {'ejs:github'},
    }
    if JS_RUNTIME:
        name, path = JS_RUNTIME
        # ต้องระบุเอง เพราะ yt-dlp เปิดใช้แค่ deno เป็นค่าเริ่มต้น (node/bun ต้อง enable)
        opts['js_runtimes'] = {name: {'path': path}}
    if cookie_browser:
        opts['cookiesfrombrowser'] = (cookie_browser,)
    return opts


def base_opts(final_path: Path, label_holder, cookie_browser: str | None) -> dict:
    opts = common_opts(cookie_browser)
    opts.update({
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': str(final_path.with_suffix('')) + '.%(ext)s',
        'progress_hooks': [make_progress_hook(label_holder)],
        'concurrent_fragment_downloads': MAX_WORKERS,
    })
    return opts


def get_video_info(url: str, cookie_browser: str | None) -> dict:
    from yt_dlp import YoutubeDL
    opts = common_opts(cookie_browser)
    opts['skip_download'] = True
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def download_mp4(info, url, mode: str, include_audio: bool,
                 download_path: Path, short: bool, cookie_browser) -> Path:
    from yt_dlp import YoutubeDL

    cap = "" if mode == MODE_MP4_MAX else "[height<=1080]"
    if include_audio:
        fmt = (f"bestvideo{cap}[ext=mp4]+bestaudio[ext=m4a]/"
               f"bestvideo{cap}+bestaudio/best{cap}/best")
    else:
        fmt = f"bestvideo{cap}[ext=mp4]/bestvideo{cap}/best{cap}"

    height = info.get('height') or '?'
    fps = info.get('fps') or '?'
    tag = " [Short]" if short else ""
    audio_txt = (f"{GREEN}🔊 Audio included{RESET}" if include_audio
                 else f"{RED}🔇 No audio{RESET}")
    print(f"📺 Target: {BOLD}up to {'MAX' if mode == MODE_MP4_MAX else '1080p'}"
          f"{RESET} (source {height}p@{fps}fps){tag} | {audio_txt}")

    clean_name = sanitize_filename(info['title']).replace(" ", "_")
    suffix = "" if include_audio else "_no_audio"
    final_output = get_unique_output(download_path, f"{clean_name}{suffix}", ext=".mp4")

    label = ["⏬ Video"]
    opts = base_opts(final_output, label, cookie_browser)
    opts.update({
        'format': fmt,
        'merge_output_format': 'mp4',
        'postprocessor_args': {'ffmpeg': ['-movflags', '+faststart']},
    })
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    return final_output


def download_m4a(info, url, download_path: Path, cookie_browser) -> Path:
    from yt_dlp import YoutubeDL

    clean_name = sanitize_filename(info['title']).replace(" ", "_")
    final_output = get_unique_output(download_path, clean_name, ext=".m4a")

    label = ["⏬ Audio"]
    opts = base_opts(final_output, label, cookie_browser)
    opts.update({
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
    })
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    return final_output


# ============================================================
# [THUMB] ดาวน์โหลด Thumbnail ความละเอียดสูงสุด → แปลงเป็น PNG
# ============================================================
THUMB_QUALITY = ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]


def fetch_best_thumbnail(video_id: str) -> bytes:
    for name in THUMB_QUALITY:
        url = f"https://i.ytimg.com/vi/{video_id}/{name}.jpg"
        try:
            req = Request(url, headers=HTTP_HEADERS)
            with urlopen(req, timeout=15) as resp:
                data = resp.read()
            if len(data) > 2000:
                print(f"🖼️ Found quality thumbnail: {BOLD}{name}{RESET}")
                return data
        except Exception:
            continue
    raise RuntimeError("Failed to download thumbnail")
def download_thumbnail(info, download_path: Path, temp_files: list) -> Path:
    data = fetch_best_thumbnail(info['id'])

    temp_path = download_path / "_temp_thumb.jpg"
    temp_files.append(temp_path)
    with open(temp_path, 'wb') as f:
        f.write(data)

    clean_name = sanitize_filename(info['title']).replace(" ", "_")
    final_output = get_unique_output(download_path, f"{clean_name}_thumbnail", ext=".png")

    print(f"⚡ Converting -> {final_output.name}")
    result = subprocess.run([
        FFMPEG_PATH, '-i', str(temp_path),
        '-loglevel', 'error', '-y', str(final_output)
    ], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode(errors='replace').strip()}")
    return final_output


# ============================================================
# [ERROR] แปล error ของ yt-dlp ให้เป็นคำแนะนำที่ทำตามได้จริง
# ============================================================
def explain_error(e: Exception, cookie_browser: str | None):
    msg = str(e)
    low = msg.lower()
    print(f"❌ {RED}Error: {RESET}{msg}")
    print()

    if "sign in" in low or "not a bot" in low or "login" in low:
        print(f"{YELLOW}💡 YouTube asked for login (bot check){RESET}")
        print("   → Press (C) to switch cookies to a browser where you're logged into YouTube")
        print("     then paste the link again.")
        if cookie_browser:
            print(f"   → Make sure {cookie_browser} is CLOSED before downloading (cookie DB is locked).")
    elif "challenge" in low or "javascript" in low or "js runtime" in low or "ejs" in low:
        print_js_runtime_help()
    elif "requested format is not available" in low:
        print(f"{YELLOW}💡 Formats missing → usually caused by missing JS runtime{RESET}")
        if not JS_RUNTIME:
            print_js_runtime_help()
        else:
            print("   → Try updating yt-dlp: pip install -U \"yt-dlp[default]\"")
    elif "is not a valid url" in low or "unsupported url" in low:
        print(f"{YELLOW}💡 The link doesn't look like a YouTube URL. Please check it again.{RESET}")
    elif "getaddrinfo" in low or "timed out" in low or "connection" in low:
        print(f"{YELLOW}💡 Network problem → check your internet / VPN / firewall.{RESET}")
    elif "private video" in low or "unavailable" in low or "removed" in low:
        print(f"{YELLOW}💡 This video is private / removed / region-locked.{RESET}")
    else:
        print(f"{YELLOW}💡 Tip: YouTube changes often → update yt-dlp first:{RESET}")
        print('   pip install -U "yt-dlp[default]"')
        if not JS_RUNTIME:
            print()
            print_js_runtime_help()


# ============================================================
# [ASCII ART]
# ============================================================
def larp():
    text = [
    "   $$$$$$$$$$$$$$$$$$$$$$$$            $$$$$$$$$$$$$$$$$$$$     $$$$$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$$$$$$$$$$$$            $$$$$$$$$$$$$$$$$$$$     $$$$$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$$$$$$$$$$$$$$$$        $$$$$$$$$$$$$$$$$$$$     $$$$$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$$$$$$$$$$$$$$$$        $$$$$$$$$$$$$$$$$$$$     $$$$$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$$$$$$$$$$$$$$$$        $$$$$$$$$$$$$$$$$$$$     $$$$$$$$$$$$           $$$$$$$$$  ",
    "                       $$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "                       $$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "       $$$$$$$$$$$$$$$$$$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "       $$$$$$$$$$$$$$$$$$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$$$$$$$$$$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$$$$$$$$$$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$           $$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$           $$$$$$$$                    $$$$$$$$        $$$$$$$$$           $$$$$$$$$  ",
    "   $$$$$$$$$$$$$       $$$$$$$$                    $$$$$$$$        $$$$$$$$$$$$$$$$$$$$$$$$$$$$$  ",
    "   $$$$$$$$$$$$$       $$$$$$$$                    $$$$$$$$        $$$$$$$$$$$$$$$$$$$$$$$$$$$$$  ",
    "   $$$$$$$$$$$$$       $$$$$$$$                    $$$$$$$$        $$$$$$$$$$$$$$$$$$$$$$$$$$$$$  ",
    "   $$$$$$$$$$$$$       $$$$$$$$                    $$$$$$$$            $$$$$$$$$$$$$$$$$$$$$      ",
    "   $$$$$$$$$$$$$       $$$$$$$$                    $$$$$$$$            $$$$$$$$$$$$$$$$$$$$$      ",
    ]
    print("\n\n")
    for i in text:
        print(i)
    print("\n\n")


def sixseven():
    text = [
    "               ?$$$$$$$@'    d$$$$$$$$$$$$$$$           ",
    "             B$$$%qjrp%$m    k$$$$$$$$$$$$$$$           ",
    "           ^$$$l                         $$$1           ",
    "           $$$.                         $$$#            ",
    "          q$$(                         d$$@             ",
    "          $$$   `}v/>.                {$$$              ",
    "          $$$$$$$$$$$$$$             `$$$l              ",
    "         ,$$$@       k$$$            $$$z               ",
    "         `$$$         *$$d          &$$B                ",
    "          $$$.        f$$W         L$$$                 ",
    "          #$$Y        a$$0        i$$$.                 ",
    "          `$$$       f$$$         $$$-                  ",
    "           :$$$@pxz#$$$@         @$$w                   ",
    "             }$$$$$$$v          *$$&                    ",
    ]
    print("\n\n")
    for i in text:
        print(i)
    print("\n\n")


def goatf():
    _goat_ = [
        "                                                   ",
        "  ;$$$$$$@   U@$$$$$q      $$$$$     p$$$& $$$$p   ",
        "  $$$hpw%$| 8$$@bd@$$$     $$$$@    $$$$$$$$$$$$J  ",
        " `$$;       $$@    %$$    c$${$$u   $  l$$$$$  $   ",
        " I$$> &#W&& $$@    %$$    $$% @$$       $$$$8      ",
        " I$$l  $$$$ $$@    %$$   $$$@$@$$$      [$$$       ",
        " ,$$?   @$@ $$$    @$$  @$$8%&BB$$a      $$p       ",
        "  $$$$$$$$u 8$$$$$$$$$ C$$@     @$$z    iBQ$       ",
        "    $$$$$     $$$$$$  $$$$$$   &&&&&&  $$$$$$      ",
        "                                                   ",
        "                                                   ",
    ]
    print("\n\n")
    for i in _goat_:
        print(i)
    print("\n\n")


def print_link(url, label=None):
    if label is None:
        label = url
    escape_code = f"\033]8;;{url}\033\\{label}\033]8;;\033\\"
    print(f"{YELLOW}{escape_code}{RESET}", end="")


# ============================================================
# [UI]
# ============================================================
def mode_bar(current_mode: str, include_audio: bool, cookie_browser: str | None):
    def row(num, key):
        info = MODE_INFO[key]
        if key == current_mode:
            return f"  {info['color']}{BOLD} ▶ ({num}) {info['label']}{RESET}"
        return f"  {DIM}   ({num}) {info['label']}{RESET}"

    audio_txt = (f"{GREEN}🔊 ON{RESET}" if include_audio
                 else f"{RED}🔇 OFF (Video without audio.){RESET}")
    cookie_txt = (f"{GREEN}🍪 {cookie_browser}{RESET}" if cookie_browser
                  else f"{DIM}🍪 OFF{RESET}")
    if JS_RUNTIME:
        js_txt = f"{GREEN}⚙️  {JS_RUNTIME[0]}{RESET}"
    else:
        js_txt = f"{RED}⚙️  NOT FOUND (downloads may fail){RESET}"

    print(f"  {BOLD}────────────── Select Mode (Then press Enter) ──────────────{RESET}")
    print(row('1', MODE_M4A))
    print(row('2', MODE_MP4_1080))
    print(row('3', MODE_MP4_MAX))
    print(row('4', MODE_THUMB))
    print(f"  {BOLD}─────────────────────────────────────────────────────────────{RESET}")
    print(f"     (A) sound in Video MP4: {audio_txt}")

    print(f"  {BOLD}─────────────────────────────────────────────────────────────{RESET}")
    print(f"  {DIM}  Support Video & Shorts in All mode{RESET}")
    print()


def at_start(current_mode: str, include_audio: bool, cookie_browser: str | None):
    _yt_media = [
        "  ██╗   ██╗  ██████╗  ██╗   ██╗ ████████╗ ██╗   ██╗ ██████╗   ███████╗      ███╗   ███╗ ███████╗ ██████╗  ██╗  █████╗ ",
        "  ╚██╗██╔╝  ██╔═══██╗ ██║   ██║ ╚══██╔══╝ ██║   ██║ ██╔══██╗  ██╔════╝      ████╗ ████║ ██╔════╝ ██╔══██╗ ██║ ██╔══██╗",
        "   ╚███╔╝   ██║   ██║ ██║   ██║    ██║    ██║   ██║ ██████╔╝  █████╗        ██╔████╔██║ █████╗   ██║  ██║ ██║ ███████║",
        "    ██║     ██║   ██║ ██║   ██║    ██║    ██║   ██║ ██╔══██╗  ██╔══╝        ██║╚██╔╝██║ ██╔══╝   ██║  ██║ ██║ ██╔══██║",
        "    ██║     ╚██████╔╝ ╚██████╔╝    ██║    ╚██████╔╝ ██████╔╝  ███████╗      ██║ ╚═╝ ██║ ███████╗ ██████╔╝ ██║ ██║  ██║",
        "    ╚═╝      ╚═════╝   ╚═════╝     ╚═╝     ╚═════╝  ╚═════╝   ╚══════╝      ╚═╝     ╚═╝ ╚══════╝ ╚═════╝  ╚═╝ ╚═╝  ╚═╝",
    ]
    _downloader = [
        "  ██████╗  ██████╗ ██╗    ██╗███╗   ██╗██╗      ██████╗  █████╗ ██████╗ ███████╗██████╗ ",
        "  ██╔══██╗██╔═══██╗██║    ██║████╗  ██║██║     ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗",
        "  ██║  ██║██║   ██║██║ █╗ ██║██╔██╗ ██║██║     ██║   ██║███████║██║  ██║█████╗  ██████╔╝",
        "  ██║  ██║██║   ██║██║███╗██║██║╚██╗██║██║     ██║   ██║██╔══██║██║  ██║██╔══╝  ██╔══██╗",
        "  ██████╔╝╚██████╔╝╚███╔███╔╝██║ ╚████║███████╗╚██████╔╝██║  ██║██████╔╝███████╗██║  ██║",
        "  ╚═════╝  ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝",
    ]

    print("\n\n\n")
    for line in _yt_media:
        print(f"{RED}{BOLD}{line}{RESET}")
    print()
    for line in _downloader:
        print(f"{YELLOW}{line}{RESET}")
    print()
    print(f"  {DIM}Developed by Phakin Charatsri (GOAT FILM & CS32 KMITL) | PATCH (20/09/2026){RESET}")
    print()
    print(f"  {DIM}Commands: (Q) Quit | (R) Reset | (F) Open Folder | (Ctrl+V) Paste Link | (67) | (G) GOAT{RESET}")
    print()
    mode_bar(current_mode, include_audio, cookie_browser)


# ============================================================
# [MAIN]
# ============================================================
def super_fast_downloader():
    os.system('cls' if os.name == 'nt' else 'clear')

    if not FFMPEG_PATH:
        print("❌ FFmpeg not found in the project folder or system PATH")
        print()
        print(f"{YELLOW}📥 How to install FFmpeg:{RESET}")
        print("   1. Download 'ffmpeg-release-essentials.zip' from:")
        print("      https://www.gyan.dev/ffmpeg/builds/")
        print("   2. Extract the zip, rename the folder to 'ffmpeg'")
        print("   3. Place it next to Media_yt_downloader.py")
        print()
        if platform.system() == "Darwin":
            print("   macOS: install with 'brew install ffmpeg' or place 'ffmpeg'")
            print("           at <project>/ffmpeg/bin/ffmpeg (and make it executable)")
        else:
            print(f"   Required structure: {BOLD}<project>/tools/windows/ffmpeg/bin/ffmpeg.exe{RESET}")
        return

    download_path = get_download_path()
    current_mode = MODE_MP4_1080
    include_audio = True
    cookie_idx = 0
    cookie_browser = COOKIE_BROWSERS[cookie_idx]

    at_start(current_mode, include_audio, cookie_browser)
    print(f"{DIM}  Loading modules...{RESET}", end="\r")
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print("❌ yt-dlp not installed! Please run:")
        print('   pip install -U "yt-dlp[default]"')
        return
    print("                      ", end="\r")

    if not JS_RUNTIME:
        print_js_runtime_help()

    def refresh_ui():
        os.system('cls' if os.name == 'nt' else 'clear')
        at_start(current_mode, include_audio, cookie_browser)

    while True:
        info = MODE_INFO[current_mode]
        audio_icon = ""
        if current_mode in (MODE_MP4_1080, MODE_MP4_MAX):
            audio_icon = " 🔊" if include_audio else " 🔇"
        prompt = f"\n{info['color']}{BOLD}[{info['label']}{audio_icon}]{RESET} Paste YouTube/Shorts: "
        try:
            url = input(prompt).strip()
        except EOFError:
            break
        cmd = url.lower()

        if not cmd:
            continue
        if cmd in ('q', 'ๆ', '๐', 'out', 'close', 'exit'):
            break
        elif cmd in ('r', 'พ', 'ฑ', 'reset', 'cls'):
            refresh_ui()
            continue
        elif cmd in ('f', 'ด', 'โ'):
            open_folder(download_path)
            continue
        elif cmd in ('67', '11'):
            larp()
            continue
        elif cmd == '6767':
            sixseven()
            continue
        elif cmd == 'g':
            goatf()
            continue

        # ---- [MODE] ----
        elif cmd == '1':
            current_mode = MODE_M4A
            refresh_ui()
            continue
        elif cmd == '2':
            current_mode = MODE_MP4_1080
            refresh_ui()
            continue
        elif cmd == '3':
            current_mode = MODE_MP4_MAX
            refresh_ui()
            continue
        elif cmd == '4':
            current_mode = MODE_THUMB
            refresh_ui()
            continue
        elif cmd in ('a', 'ฟ'):
            include_audio = not include_audio
            refresh_ui()
            continue
        elif cmd in ('c', 'แ'):
            # cookie_idx = (cookie_idx + 1) % len(COOKIE_BROWSERS)
            # cookie_browser = COOKIE_BROWSERS[cookie_idx]
            # refresh_ui()
            # if cookie_browser:
            #     print(f"  {YELLOW}⚠️  Close {cookie_browser} before downloading, "
            #           f"otherwise the cookie database is locked.{RESET}")
            continue

        if "youtube.com" not in cmd and "youtu.be" not in cmd:
            print(f"{YELLOW}⚠️  That doesn't look like a YouTube link.{RESET}")
            continue

        temp_files = []
        try:
            start = time()
            short = is_short(url)
            norm_url = normalize_url(url)

            print(f"{DIM}🔎 Fetching video info...{RESET}", end="\r")
            vinfo = get_video_info(norm_url, cookie_browser)
            print("                              ", end="\r")

            tag = f" {MAGENTA}[Short]{RESET}" if short else ""
            print(f"🎬 กำลังจัดการ: {vinfo['title']}{tag}")

            if current_mode == MODE_M4A:
                final_output = download_m4a(vinfo, norm_url, download_path, cookie_browser)
            elif current_mode == MODE_THUMB:
                final_output = download_thumbnail(vinfo, download_path, temp_files)
            else:
                final_output = download_mp4(vinfo, norm_url, current_mode, include_audio,
                                            download_path, short, cookie_browser)

            if not final_output.exists():
                # yt-dlp อาจเปลี่ยนนามสกุลไฟล์ปลายทาง → หาไฟล์ที่ชื่อเดียวกัน
                matches = list(download_path.glob(final_output.stem + ".*"))
                if matches:
                    final_output = matches[0]
                else:
                    raise RuntimeError("Download finished but output file was not found.")

            end = time()
            print(f"for  {GREEN}{round(end - start, 2)}s.{RESET}")
            print("✅ Success! -> |", end="")
            print_link(str(final_output))
            print("| (Ctrl + Click) -> Open File Now.")
            print()

        except KeyboardInterrupt:
            print(f"\n{YELLOW}⏹ Cancelled.{RESET}")
        except Exception as e:
            explain_error(e, cookie_browser)
        finally:
            for tf in temp_files:
                if tf and tf.exists():
                    try:
                        os.remove(tf)
                    except OSError:
                        pass


if __name__ == "__main__":
    try:
        super_fast_downloader()
    except KeyboardInterrupt:
        print("\nClosed...")