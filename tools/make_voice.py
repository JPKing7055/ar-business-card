"""把錄音整理成角色的語音：自動裁掉前後空白、音量標準化，並算出嘴型用的音量曲線。

輸入：一段錄音（m4a / mp3 / wav 都可以）
輸出：
    audio/intro.m4a    網頁播放用（AAC，iPhone 與各瀏覽器都能播）
    audio/intro.json   每 40ms 一格的音量 0~1，網頁依播放時間查表決定張嘴或閉嘴

為什麼不在網頁上即時分析音量：iPhone 上把聲音接進 Web Audio 分析時，
會受靜音開關影響而沒有聲音；預先算好音量曲線，就能用一般的 <audio> 播放。

用法：
    python tools/make_voice.py 你的錄音.m4a              → audio/intro.m4a、audio/intro.json
    python tools/make_voice.py 錄音.m4a faq/skills      → audio/faq/skills.m4a、audio/faq/skills.json
    產生後把路徑填進 faq.json 對應題目的 audio、env。
需要：ffmpeg（加入 PATH）、pip install numpy
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

SR = 16000
FRAME_MS = 40
SPEECH_DB = -40      # 高於這個音量才算說話（用來裁掉前後空白、按錄音鍵的雜音）
PAD = 0.15           # 說話前後保留的秒數


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def frame_db(samples, frame_ms):
    n = int(SR * frame_ms / 1000)
    frames = samples[: len(samples) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return 20 * np.log10(rms + 1e-9)


def process(src, name="intro"):
    """處理一段錄音：輸出 audio/<name>.m4a 與 audio/<name>.json，回傳兩個相對於專案根目錄的路徑。"""
    src = Path(src)
    out_audio = ROOT / "audio" / f"{name}.m4a"
    out_env = ROOT / "audio" / f"{name}.json"

    # 1. 找出說話的範圍
    db = frame_db(decode(src), 50)
    voiced = np.nonzero(db > SPEECH_DB)[0]
    if not len(voiced):
        raise RuntimeError(f"{src} 找不到說話的聲音，請確認錄音音量")
    start = max(0.0, voiced[0] * 0.05 - PAD)
    end = (voiced[-1] + 1) * 0.05 + PAD
    dur = end - start
    print(f"說話範圍 {start:.2f}s ~ {end:.2f}s（{dur:.2f} 秒）")

    # 2. 裁切、淡入淡出、去低頻雜音、音量標準化，輸出 AAC
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    af = (f"afade=t=in:d=0.08,afade=t=out:st={max(0, dur - 0.15):.2f}:d=0.15,"
          "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
         "-af", af, "-ar", "48000", "-ac", "1", "-c:a", "aac", "-b:a", "96k",
         "-movflags", "+faststart", str(out_audio)],
        check=True,
    )

    # 3. 從輸出的音檔算嘴型用的音量曲線（0~1）
    out_db = frame_db(decode(out_audio), FRAME_MS)
    lo, hi = SPEECH_DB, np.percentile(out_db, 95)
    env = np.clip((out_db - lo) / max(1e-6, hi - lo), 0, 1)
    out_env.write_text(json.dumps({"frameMs": FRAME_MS, "env": [round(float(v), 2) for v in env]}))
    print("wrote", out_audio, "and", out_env, f"({len(env)} frames)")
    return out_audio.relative_to(ROOT).as_posix(), out_env.relative_to(ROOT).as_posix()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    process(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "intro")


if __name__ == "__main__":
    main()
