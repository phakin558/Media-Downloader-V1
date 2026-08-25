@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Checking for updates...
curl -k -f -s -o temp_code.py -L "https://raw.githubusercontent.com/phakin558/Media-Downloader-V1/main/Media_yt_downloader.py?v=%RANDOM%"

if exist temp_code.py (
    move /y temp_code.py Media_yt_downloader.py >nul
)

echo Auto-updating yt-dlp...
REM เติมบรรทัดนี้เพื่อเช็คอัปเดต yt-dlp ทุกครั้งที่เปิดใช้งาน
.\python-3.14.3-embed-amd64\python.exe -m pip install --upgrade yt-dlp certifi >nul 2>&1

echo Starting program...
.\python-3.14.3-embed-amd64\python.exe Media_yt_downloader.py
pause