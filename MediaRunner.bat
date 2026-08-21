@echo off
chcp 65001 >nul
echo Checking for updates...

REM เติม ?v=%RANDOM% ท้าย URL เพื่อป้องกันการติด Cache ของ GitHub
curl -f -s -o temp_code.py -L "https://raw.githubusercontent.com/phakin558/Media-Downloader-V1/main/Media_yt_downloader.py?v=%RANDOM%"

if exist temp_code.py (
    move /y temp_code.py Media_yt_downloader.py >nul
    echo Update completed!
) else (
    echo [Warning] Using local code.
)

.\python-3.14.3-embed-amd64\python.exe Media_yt_downloader.py
pause