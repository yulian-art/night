"""Explicitly download the versioned Google Pose Landmarker Lite model."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request
import zipfile

URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]/"models/pose_landmarker_lite.task")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ValueError("existing model archive is corrupt")
        print(f"Using existing model: {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        digest = hashlib.sha256()
        with urllib.request.urlopen(URL, timeout=30) as response:
            with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".part", delete=False) as target:
                temp = Path(target.name)
                count = 0
                while chunk := response.read(1024*1024):
                    count += len(chunk)
                    if count > 50*1024*1024:
                        raise ValueError("unexpectedly large model")
                    target.write(chunk)
                    digest.update(chunk)
        with zipfile.ZipFile(temp) as archive:
            if archive.testzip() is not None or len([n for n in archive.namelist() if n.endswith(".tflite")]) < 2:
                raise ValueError("download is not a valid Pose Landmarker task bundle")
        temp.replace(output)
        output.with_suffix(".json").write_text(json.dumps({"url": URL, "sha256": digest.hexdigest()},indent=2)+"\n")
        print(f"Model: {output}\nSHA256 (download receipt): {digest.hexdigest()}")
    finally:
        if temp and temp.exists():
            temp.unlink()

if __name__ == "__main__":
    main()
