# Media YouTube Downloader สำหรับ macOS

โฟลเดอร์นี้เป็นชุดแยกสำหรับ macOS สามารถดาวน์โหลดทั้งโฟลเดอร์แล้วใช้งานได้จากที่เดียว

## ติดตั้งและใช้งาน

```bash
cd macOS
python3 -m pip install -r requirements.txt
chmod +x tools/ffmpeg/ffmpeg
python3 Media_yt_downloader.py
```

ชุดนี้มี FFmpeg สำหรับ macOS Intel (`x86_64`) ซึ่งใช้ได้กับ Intel Mac และ Apple Silicon ที่ติดตั้ง Rosetta 2 แล้ว

ถ้าใช้ Mac Apple Silicon แท้และต้องการ native performance ให้ติดตั้ง FFmpeg arm64 แทน:

```bash
brew install ffmpeg
```

จากนั้นสามารถลบ `tools/ffmpeg/ffmpeg` ได้ เพราะโปรแกรมจะค้นหา FFmpeg จาก PATH ให้อัตโนมัติ

## โครงสร้าง

```text
macOS/
├─ Media_yt_downloader.py
├─ requirements.txt
├─ README.md
└─ tools/
   └─ ffmpeg/
      └─ ffmpeg
```

ไฟล์ FFmpeg นี้มีขนาดประมาณ 77 MB จึงยังอยู่ภายใต้ข้อจำกัด 100 MB ต่อไฟล์ของ GitHub และใส่ไฟล์จริงไว้ให้แล้ว
