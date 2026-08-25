# Media YouTube Downloader สำหรับ macOS

โฟลเดอร์นี้เป็นชุดแยกสำหรับ macOS สามารถดาวน์โหลดทั้งโฟลเดอร์แล้วใช้งานได้จากที่เดียว

## ติดตั้งและใช้งาน

ดับเบิลคลิก `run_macos.command` เพื่อให้โปรแกรมเลือก Portable Python จากโฟลเดอร์เดียวกันโดยอัตโนมัติ หรือรันด้วย Terminal:

```bash
cd macOS
chmod +x run_macos.command tools/ffmpeg/ffmpeg
./run_macos.command
```

โปรแกรมจะค้นหา Python ตามลำดับนี้:

```text
macOS/python/bin/python3
macOS/python/bin/python3.14
macOS/python/python3
```

ถ้าไม่พบ จะไม่ใช้ Python ที่ติดตั้งในระบบ และจะแจ้งให้ดาวน์โหลด Portable Python ก่อน

## ดาวน์โหลด Portable Python

ใช้ `python-build-standalone` ซึ่งเป็น distribution แบบ standalone/redistributable:

1. เปิด [หน้า Releases ของ python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases)
2. เลือกไฟล์ `install_only.tar.gz` ที่ตรงกับเครื่อง:
   - Apple Silicon: `aarch64-apple-darwin`
   - Intel Mac: `x86_64-apple-darwin`
3. แตกไฟล์ให้เนื้อหามาอยู่ใต้ `macOS/python/` จนเห็นไฟล์ `macOS/python/bin/python3`
4. รัน `./run_macos.command`

ตัวอย่างคำสั่งหลังดาวน์โหลดไฟล์มาไว้ในโฟลเดอร์ `macOS`:

```bash
mkdir -p python
tar -xzf cpython-*-apple-darwin-install_only.tar.gz -C python --strip-components=1
chmod +x python/bin/python3 run_macos.command
```

Portable Python ไม่ได้ commit ไว้ใน GitHub เพราะมีหลายสถาปัตยกรรมและเป็นไฟล์ binary ขนาดใหญ่ จึงมี `fakeMacPython.txt` เป็น placeholder ที่ `macOS/python/`

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
