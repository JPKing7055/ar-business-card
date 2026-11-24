"""用本機的 GPT-SoVITS 把 faq.json 的字幕合成成你的聲音，並更新 faq.json。

流程（每一題）：
    faq.json 的 text（若有 say 欄位則念 say）→ GPT-SoVITS API（api_v2.py）合成 wav
    say：只影響發音、不影響字幕，用來修正英文縮寫或數字的念法
    → make_voice.process()：裁空白、音量標準化、輸出 m4a 與嘴型音量曲線
    → 寫回 faq.json 的 audio、env

預設只處理「還沒有音檔」的題目；本人真實錄音（例如第一題）不會被覆蓋。

事前準備：
    1. GPT-SoVITS 已用你的聲音訓練好，並啟動 API：
           python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
       （tts_infer.yaml 裡的模型路徑要指向你訓練好的 GPT／SoVITS 模型）
    2. 準備一段 3～10 秒的參考錄音，和它一字不差的逐字稿。

用法：
    python tools/synth_faq.py --ref "D:/voice/ref.wav" --ref-text "參考錄音的逐字稿"
    python tools/synth_faq.py --ref ... --ref-text ... --ids skills tools     只做指定題目
    python tools/synth_faq.py --ref ... --ref-text ... --overwrite           已有 AI 合成音檔的題目也重做
    python tools/synth_faq.py --ref ... --ref-text ... --dry-run             只列出會處理哪些題目

注意：--ref 是 GPT-SoVITS 伺服器那台電腦上的路徑（本機執行時就是你自己的路徑）。
需要：ffmpeg、pip install numpy（只用 Python 內建的 urllib 呼叫 API）
"""
import argparse
import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_voice  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAQ = ROOT / "faq.json"


def synth(api, text, ref, ref_text, speed):
    payload = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref,
        "prompt_text": ref_text,
        "prompt_lang": "zh",
        "text_split_method": "cut5",    # 依標點切句
        "batch_size": 1,
        "speed_factor": speed,
        "media_type": "wav",
        "streaming_mode": False,
    }
    req = urllib.request.Request(
        api.rstrip("/") + "/tts",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GPT-SoVITS 回傳錯誤 {e.code}：{e.read().decode('utf-8', 'replace')}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"連不到 GPT-SoVITS API（{api}），請確認 api_v2.py 已啟動：{e.reason}") from None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://127.0.0.1:9880")
    ap.add_argument("--ref", required=True, help="參考錄音（3～10 秒）")
    ap.add_argument("--ref-text", required=True, help="參考錄音的逐字稿")
    ap.add_argument("--ids", nargs="*", help="只處理這些題目 id")
    ap.add_argument("--overwrite", action="store_true", help="已有 AI 合成音檔（audio/faq/）的題目也重做")
    ap.add_argument("--speed", type=float, default=1.0, help="語速，1.0 為正常")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(FAQ.read_text(encoding="utf-8"))
    todo = []
    for item in data["items"]:
        if args.ids and item["id"] not in args.ids:
            continue
        if not item.get("text"):
            print(f"略過 {item['id']}：沒有字幕")
            continue
        audio = item.get("audio")
        if audio and not audio.startswith("audio/faq/"):
            print(f"略過 {item['id']}：使用本人錄音（{audio}）")
            continue
        if audio and not args.overwrite:
            print(f"略過 {item['id']}：已有音檔（加 --overwrite 重做）")
            continue
        todo.append(item)

    print(f"要合成 {len(todo)} 題：{', '.join(i['id'] for i in todo) or '無'}")
    if args.dry_run or not todo:
        return

    with tempfile.TemporaryDirectory() as tmp:
        for item in todo:
            t0 = time.time()
            wav = synth(args.api, item.get("say") or item["text"], args.ref, args.ref_text, args.speed)
            raw = Path(tmp) / f"{item['id']}.wav"
            raw.write_bytes(wav)
            print(f"{item['id']}：合成 {time.time() - t0:.1f} 秒")
            item["audio"], item["env"] = make_voice.process(raw, f"faq/{item['id']}")
            # 每題完成就存檔，中途出錯也不會白做
            FAQ.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("完成。先在本機聽過 audio/faq/ 的音檔，滿意再 commit 與 push。")


if __name__ == "__main__":
    main()
