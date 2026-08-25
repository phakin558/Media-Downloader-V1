# ใช้งานบน macOS

ไฟล์ `Media_yt_downloader.py` ใช้ร่วมกับ Windows และ macOS ได้แล้ว โดย macOS ไม่ต้องใช้ไฟล์ `.exe` ของ Windows

## สิ่งที่ต้องมี

1. Python 3.12 ขึ้นไป
2. ไลบรารีใน `requirements.txt`
3. FFmpeg สำหรับ macOS

แนะนำให้ติดตั้งด้วย Homebrew:

```bash
brew install python ffmpeg
python3 -m pip install -r requirements.txt
python3 Media_yt_downloader.py
```

ถ้าไม่ใช้ Homebrew สามารถดาวน์โหลด FFmpeg สำหรับ macOS แล้ววางไฟล์ executable ชื่อ `ffmpeg` ไว้ตามสถาปัตยกรรม:

```text
<project>/tools/macos/arm64/ffmpeg       # Apple Silicon (M1/M2/M3/M4)
<project>/tools/macos/x86_64/ffmpeg      # Intel Mac
```

จากนั้นให้สิทธิ์รันไฟล์:

```bash
chmod +x tools/macos/x86_64/ffmpeg
```

ไฟล์ `ffmpeg-9.0.1.7z` ที่เตรียมไว้เป็น build สำหรับ macOS Intel (`x86_64`) ให้ใช้กับโฟลเดอร์ `tools/macos/x86_64` เท่านั้น หากเป็น Mac Apple Silicon ควรใช้ build `arm64` หรือใช้ `brew install ffmpeg`

ไฟล์ในโปรเจกต์ถูกแยกไว้ดังนี้:

```text
tools/windows/ffmpeg/       # FFmpeg ของ Windows
tools/macos/x86_64/ffmpeg   # FFmpeg ของ macOS Intel
launchers/windows/          # .bat, .exe และ icon ของ Windows
```

ไม่จำเป็นต้องมี `ffmpeg.exe`, `MediaRunner.bat`, `MediaDownloader.exe` หรือ `ffplay.exe` บน macOS

หมายเหตุ: ถ้าดาวน์โหลดวิดีโอแบบแยกภาพและเสียง หรือแปลงเสียง/thumbnail โปรแกรมต้องใช้ FFmpeg; ถ้ามี `ffmpeg` อยู่ใน PATH ก็ไม่ต้องคัดลอกโฟลเดอร์ `ffmpeg` มาในโปรเจกต์
