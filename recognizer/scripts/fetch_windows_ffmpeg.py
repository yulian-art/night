"""Download a portable Windows FFmpeg build linked by ffmpeg.org. No installer/PATH changes."""
import argparse
import hashlib
from pathlib import Path
import shutil
import re
import time
import tempfile
import urllib.request
import zipfile

BASE = "https://www.gyan.dev/ffmpeg/builds/"
ARCHIVE = "ffmpeg-release-essentials.zip"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"tools/windows-ffmpeg")
    args=parser.parse_args()
    target=args.output.resolve()
    if (target/"ffmpeg.exe").is_file():
        print(target/"ffmpeg.exe")
        return
    with urllib.request.urlopen(BASE+ARCHIVE+".sha256",timeout=30) as response:
        expected=response.read(512).decode("ascii").split()[0].lower()
    if len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("invalid publisher SHA256")
    with tempfile.TemporaryDirectory() as directory:
        archive=Path(directory)/ARCHIVE
        size = 0
        complete = False
        for attempt in range(6):
            try:
                request = urllib.request.Request(BASE+ARCHIVE, headers={"Range": f"bytes={size}-"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    content_range = response.headers.get("Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                    if response.status == 206:
                        if not match or int(match[1]) != size:
                            raise ValueError("unexpected archive range response")
                        total = int(match[3])
                    else:
                        size = 0  # Server ignored Range: replace, never append a whole archive.
                        total = int(response.headers["Content-Length"])
                    if total > 250*1024*1024:
                        raise ValueError("unexpected archive size")
                    with archive.open("ab" if size else "wb") as out:
                        while chunk := response.read(1024*1024):
                            out.write(chunk)
                            size += len(chunk)
                    print(f"FFmpeg download: {size}/{total} bytes", flush=True)
                    if size == total:
                        complete = True
                        break
            except (OSError, TimeoutError) as exc:
                print(f"Download retry {attempt+1}: {exc}", flush=True)
            time.sleep(1)
        if not complete:
            raise ValueError("FFmpeg download remained incomplete")
        with archive.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"FFmpeg archive checksum mismatch: expected {expected}, got {actual}, bytes {size}; no executable extracted")
        with zipfile.ZipFile(archive) as source:
            exe=next(n for n in source.namelist() if n.endswith("/bin/ffmpeg.exe"))
            target.mkdir(parents=True,exist_ok=True)
            with source.open(exe) as src, (target/"ffmpeg.exe").open("wb") as dst:
                shutil.copyfileobj(src,dst)
            for name in source.namelist():
                if Path(name).name.lower() in ("license","license.txt","readme.txt"):
                    (target/Path(name).name).write_bytes(source.read(name))
        (target/"archive.sha256").write_text(expected+"\n")
    (target/"ffmpeg.exe").chmod(0o755)
    print(target/"ffmpeg.exe")

if __name__=="__main__":
    main()
