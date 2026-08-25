import os
import shutil
import subprocess
import threading
import sys
from pathlib import Path
from time import time
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

# --- [CHECK] ต้องใช้ Python 3.12 ขึ้นไป ---
if sys.version_info < (3, 12):
    print(f"❌ This program requires Python 3.12+ (You are using {platform.python_version()})")
    print("📥 Download: https://www.python.org/downloads/release/python-3120/")
    sys.exit(1)

try:
    from pathvalidate import sanitize_filename
except ImportError:
    print("❌ Missing libraries! Please run:")
    print("   pip install -r requirements.txt")
    sys.exit(1)

# --- ระบุตำแหน่ง FFmpeg แบบข้ามระบบปฏิบัติการ ---
BASE_DIR = Path(__file__).resolve().parent


def resolve_ffmpeg() -> str | None:
    """ค้นหา FFmpeg จาก tools ของระบบนั้นก่อน แล้วจึงค้นจาก PATH"""
    system = platform.system()
    if system == "Windows":
        candidates = [
            BASE_DIR / "tools" / "windows" / "ffmpeg" / "bin" / "ffmpeg.exe",
            BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe",  # โครงสร้างเก่า
        ]
    elif system == "Darwin":
        machine = platform.machine().lower()
        preferred_arch = "arm64" if machine in ("arm64", "aarch64") else "x86_64"
        other_arch = "x86_64" if preferred_arch == "arm64" else "arm64"
        candidates = [
            BASE_DIR / "tools" / "ffmpeg" / "ffmpeg",  # ชุด macOS แบบแยกโฟลเดอร์
            BASE_DIR / "macOS" / "tools" / "ffmpeg" / "ffmpeg",  # เรียกจาก root
            BASE_DIR / "tools" / "macos" / preferred_arch / "ffmpeg",
            BASE_DIR / "tools" / "macos" / other_arch / "ffmpeg",
            BASE_DIR / "ffmpeg" / "bin" / "ffmpeg",  # โครงสร้างเก่า
        ]
    else:
        candidates = [BASE_DIR / "tools" / "linux" / "ffmpeg"]

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        candidates.append(Path(system_ffmpeg))

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


FFMPEG_PATH = resolve_ffmpeg()

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA= "\033[95m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"
DARK_RED = "\033[31m"

# ---- [SPEED] ค่าคอนฟิกดาวน์โหลดขนาน ----
MAX_WORKERS  = 8
SEGMENT_SIZE = 8 * 1024 * 1024
READ_CHUNK   = 256 * 1024
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en",
}

# ---- [MODE] โหมดการดาวน์โหลด ----
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


def open_folder(path: Path):
    """เปิดโฟลเดอร์ด้วยโปรแกรมจัดการไฟล์ของแต่ละระบบอย่างปลอดภัย"""
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(path)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        print(f"❌ Cannot open folder: {exc}")


def get_download_path():
    return Path.home() / "Downloads"


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
    return url


def is_short(url: str) -> bool:
    return "/shorts/" in url


# ============================================================
# [ENGINE] yt-dlp backend (แทน pytubefix ที่โดน YouTube บล็อก)
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


def base_opts(final_path: Path, label_holder):
    return {
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': str(final_path.with_suffix('')) + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'progress_hooks': [make_progress_hook(label_holder)],
        'concurrent_fragment_downloads': MAX_WORKERS,   # โหลดขนานในตัว
        'retries': 5,
        'fragment_retries': 5,
        # ถ้ายังโดน bot detection ให้เปิดบรรทัดล่าง (ดึง cookies จาก Chrome ที่ login YouTube อยู่)
        # 'cookiesfrombrowser': ('chrome',),
    }


def get_video_info(url: str) -> dict:
    from yt_dlp import YoutubeDL
    with YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}) as ydl:
        return ydl.extract_info(url, download=False)


def download_mp4(info, url, mode: str, include_audio: bool,
                 download_path: Path, short: bool) -> Path:
    from yt_dlp import YoutubeDL

    cap = "" if mode == MODE_MP4_MAX else "[height<=1080]"
    if include_audio:
        fmt = (f"bestvideo{cap}[ext=mp4]+bestaudio[ext=m4a]/"
               f"bestvideo{cap}+bestaudio/best{cap}")
    else:
        fmt = f"bestvideo{cap}[ext=mp4]/bestvideo{cap}"

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
    opts = base_opts(final_output, label)
    opts.update({
        'format': fmt,
        'merge_output_format': 'mp4',
        'postprocessor_args': {'ffmpeg': ['-movflags', '+faststart']},
    })
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    return final_output


def download_m4a(info, url, download_path: Path) -> Path:
    from yt_dlp import YoutubeDL

    clean_name = sanitize_filename(info['title']).replace(" ", "_")
    final_output = get_unique_output(download_path, clean_name, ext=".m4a")

    label = ["⏬ Audio"]
    opts = base_opts(final_output, label)
    opts.update({
        'format': 'bestaudio[ext=m4a]/bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
    })
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    return final_output


def download_thumbnail(info, download_path: Path, temp_files: list) -> Path:
    data = fetch_best_thumbnail(info['id'])   # ฟังก์ชันเดิมใช้ได้ เปลี่ยนแค่ที่มาของ video_id

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
# [FIX] เลือก client + "ตรวจ streams จริง" ก่อนใช้งาน
#  - โค้ดเดิมเช็คแค่ yt.title → ผ่านทั้งที่ streams พัง ทำให้ fallback ไม่ทำงาน
#  - WEB client ต้องมี PoToken (ต้องมี Node.js) จึงเอาไว้ท้ายสุด
# ============================================================

# ============================================================
# [MP4] เลือก video stream ตามโหมด
# ============================================================





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
    "   $$$$$$$$$$$$$       $$$$$$$$                    $$$$$$$$            $$$$$$$$$$$$$$$$$$$$$      "
    ]
    print("\n\n")
    for i in text:
        print(i)
    print("\n\n")


def sixseven():
    text = [
    "    test test nigga test auto update in this program    ",
    "                                                        ",
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
    "             }$$$$$$$v          *$$&                    "
    ]
    print("\n\n")
    for i in text:
        print(i)
    print("\n\n")


def print_link(url, label=None):
    if label is None:
        label = url
    escape_code = f"\033]8;;{url}\033\\{label}\033]8;;\033\\"
    print(f"{YELLOW}{escape_code}{RESET}", end="")


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
        "                                                   "
    ]
    print("\n\n")
    for i in _goat_:
        print(i)
    print("\n\n")


# ============================================================
# [UI] เมนูโหมดแบบแนวตั้ง อ่านง่าย
# ============================================================
def mode_bar(current_mode: str, include_audio: bool):
    def row(num, key):
        info = MODE_INFO[key]
        if key == current_mode:
            return f"  {info['color']}{BOLD} ▶ ({num}) {info['label']}{RESET}"
        return f"  {DIM}   ({num}) {info['label']}{RESET}"

    audio_txt = (f"{GREEN}🔊 ON{RESET}" if include_audio
                 else f"{RED}🔇 OFF (Video without audio.){RESET}")

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


def at_start(current_mode: str, include_audio: bool):
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
    print(f"  {DIM}Developed by Phakin Charatsri (GOAT FILM & CS32 KMITL){RESET}")
    print()
    print(f"  {DIM}Commands: (Q) Quit | (R) Reset | (F) Open Folder | (Ctrl+V) Paste Link | (67) | (G) GOAT | {RESET}")
    print()
    mode_bar(current_mode, include_audio)


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
    current_mode = MODE_MP4_1080   # default: MP4 1080p
    include_audio = True           # default: มีเสียง

    at_start(current_mode, include_audio)
    print(f"{DIM}  Loading modules...{RESET}", end="\r")
    try:
        import yt_dlp  # noqa: F401  แค่เช็คว่าติดตั้งแล้ว
    except ImportError:
        print("❌ yt-dlp not installed! Please run:")
        print("   pip install -r requirements.txt")
        return
    print("                      ", end="\r")


    def refresh_ui():
        os.system('cls' if os.name == 'nt' else 'clear')
        at_start(current_mode, include_audio)


    while True:
        info = MODE_INFO[current_mode]
        audio_icon = ""
        if current_mode in (MODE_MP4_1080, MODE_MP4_MAX):
            audio_icon = " 🔊" if include_audio else " 🔇"
        prompt = f"\n{info['color']}{BOLD}[{info['label']}{audio_icon}]{RESET} Paste YouTube/Shorts: "
        url = input(prompt).strip()
        cmd = url.lower()

        if cmd in ('q', 'ๆ', '๐', 'out', 'close'):
            break
        elif cmd in ('r', 'พ', 'ฑ', 'reset', 'cls'):
            os.system('cls' if os.name == 'nt' else 'clear')
            at_start(current_mode, include_audio)
            continue
        elif cmd in ('f', 'ด', 'โ'):
            open_folder(get_download_path())
            continue
        elif cmd == '67':
            sixseven()
            continue
        elif cmd == '11':
            larp()
            continue
        elif cmd == 'g':
            goatf()
            continue

        # ---- [MODE] เปลี่ยนโหมด / toggle เสียง ----
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

        temp_files = []

        try:
            start = time()
            short = is_short(url)
            norm_url = normalize_url(url)
            info = get_video_info(norm_url)
            tag = f" {MAGENTA}[Short]{RESET}" if short else ""
            print(f"🎬 กำลังจัดการ: {info['title']}{tag}")

            if current_mode == MODE_M4A:
                final_output = download_m4a(info, norm_url, download_path)
            elif current_mode == MODE_THUMB:
                final_output = download_thumbnail(info, download_path, temp_files)
            else:
                final_output = download_mp4(info, norm_url, current_mode,
                                            include_audio, download_path, short)


            end = time()
            print(f"for  {GREEN}{round(end - start, 2)}s.{RESET}")
            print("✅ Success! -> |", end="")
            print_link(str(final_output))
            print("| (Ctrl + Click) -> Open File Now.")
            print()

        except Exception as e:
            if "regex_search" in str(e):
                pass
            else:
                print(f"❌ {RED}Error at: {RESET}{e}")
                print(f"{YELLOW}💡 Tip: Try updating yt-dlp (YouTube changes often):{RESET}")
                print(f"   pip install -U yt-dlp")


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
