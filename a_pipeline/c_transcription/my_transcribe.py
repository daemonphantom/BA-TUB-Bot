"""
Transcode *.mp4 videos into sentence-level transcript chunks that follow the
*unified knowledge-graph format* you described.

Each output JSON lives next to the originating video, inside a new directory
called **transcribed_videos**.  One JSON file is produced *per video* and
contains a list of chunks like

Run the script once at the top level of your *b_data* tree:

python -m a_pipeline.c_transcription.my_transcribe

You may point `--model-size` at any Whisper size you have on disk ("small" by
default).  Files that have already been processed are skipped via a
*transformation_log.json* written to the course root, so you can safely resume
or re-run.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timezone
from ..a_crawling.utils.utils import get_logger
from whisper_timestamped import transcribe_timestamped, load_model  # pip install whisper_timestamped

# ---------------------------------------------------------------------------
# CONFIGURATION ----------------------------------------------------------------
# ---------------------------------------------------------------------------
MODEL_SIZE = "small"  # change at runtime with --model-size
AUDIO_CODEC = "libmp3lame"
AUDIO_EXT = ".mp3"
LOG_FILE = "transformation_log.json"
METADATA_FILE = "videos.json"  # name of the json that stores video meta
TRANSCRIBED_DIRNAME = "transcribed_videos"
CHAR_MAP = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
}
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+") # Sentence delimiter – tuned for German & English.

logger = get_logger(__name__)
# ---------------------------------------------------------------------------
# UTILS ------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                content = fh.read().strip()
                if not content:
                    return default  # Handle empty file
                return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {path}. Using default.")
            return default
    return default


def save_jsonl(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for o in obj:
            fh.write(json.dumps(o, ensure_ascii=False)+"\n")

def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)

def extract_audio(video_path: Path, audio_path: Path):
    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        AUDIO_CODEC,
        str(audio_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def clean_text(text: str) -> str:
    for old, new in CHAR_MAP.items():
        text = text.replace(old, new)
    return text.strip()


COURSE_META_PATH = Path("a_pipeline/a_crawling/course_ids/course_other.json")
COURSE_LOOKUP = {
    c["id"]: {
        "name": c["name"],
        "semester": c["semester"]
    }
    for c in load_json(COURSE_META_PATH, [])
}

# ---------------------------------------------------------------------------
# WINDOWED CHUNKING (character-capped, no external tokenizer)
# ---------------------------------------------------------------------------
def windowed_chunks(segments,
                    *,
                    sent_per_win: int = 3,
                    stride: int = 1,
                    max_chars: int = 1200):
    """
    Turn Whisper 'segments' -> overlapping windows of N sentences.
    • No tiktoken / tokenizer dependency.
    • Each chunk is capped to `max_chars` characters (≈ 256 Llama tokens).
    """
    sentences = []
    current   = []

    # -------- 1) explode word stream into sentences with timestamps --------
    for seg in segments:
        for w in seg["words"]:
            current.append(w)
            if w["text"].strip().endswith((".", "!", "?")):
                sentences.append(current)
                current = []
    if current:
        sentences.append(current)

    # -------- 2) slide a window over those sentences -----------------------
    chunks, i = [], 0
    while i < len(sentences):
        window = sentences[i:i + sent_per_win]

        # assemble raw text for the window
        def join_words(sent):
            return " ".join(w["text"] for w in sent)
        text  = " ".join(join_words(sent) for sent in window).strip()

        # shrink window if over the char budget
        while len(text) > max_chars and len(window) > 1:
            window = window[:-1]           # drop last sentence
            text   = " ".join(join_words(s) for s in window).strip()

        # fallback: single very-long sentence? keep it anyway
        if not window:
            window = [sentences[i]]
            text   = join_words(window[0]).strip()

        chunks.append({
            "text":  text,
            "start": float(window[0][0]["start"]),
            "end":   float(window[-1][-1]["end"]),
        })
        i += stride                        # overlap (sent_per_win-stride) sentences

    return chunks





# ---------------------------------------------------------------------------
# CORE TRANSCRIBE -------------------------------------------------------------
# ---------------------------------------------------------------------------

def transcribe_video(video_path: Path, meta: Dict, course_id: str, model_size: str):
    """Return list[dict] of sentence-level chunks for *video_path*."""
    tmp_audio = video_path.with_suffix(AUDIO_EXT)
    logger.info(f"Transcribing audio from {tmp_audio}")

    if not tmp_audio.exists():
        extract_audio(video_path, tmp_audio)

    model = load_model(model_size)
    result = transcribe_timestamped(model, str(tmp_audio), language="de")  # force German

    # raw_chunks = sentence_chunks(result["segments"])
    raw_chunks = windowed_chunks(result["segments"],
                                sent_per_win=3,
                                stride=1,
                                max_chars=1200)
    chunks = []
    ingest_ts = datetime.now(timezone.utc).isoformat()

    for i, stc in enumerate(raw_chunks):
        chunk = {
            "source": "video",
            "course_id": course_id,
            "course_name": COURSE_LOOKUP.get(course_id, {}).get("name", "Unknown Course"),
            "course_semester": COURSE_LOOKUP.get(course_id, {}).get("semester", "Unknown Semester"),
            "chunk_type": "transcript_window",
            "content": stc["text"],
            "metadata": {
                "lecture_title": clean_text(meta.get("title", video_path.stem)),
                "start": round(stc["start"], 2),
                "end": round(stc["end"], 2),
                "video_file": video_path.name,
                "video_url": meta.get("detail_url") or meta.get("download_url"),
                "collection": meta.get("collection_name"),
                "additional_info": {
                    "chunk_id": f"{course_id}_{video_path.stem}_{i}",
                    "prev_chunk_id": f"{course_id}_{video_path.stem}_{i-1}" if i > 0 else None,
                    "next_chunk_id": f"{course_id}_{video_path.stem}_{i+1}" if i < len(raw_chunks) - 1 else None,
                    "ingest_ts": ingest_ts
                }
            }
        }
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# PIPELINE --------------------------------------------------------------------
# ---------------------------------------------------------------------------

def process_course(course_dir: Path, model_size: str):
    course_id = course_dir.name.split("_")[-1]
    videos_dir = course_dir / "videos"
    if not videos_dir.is_dir():
        return

    meta_lookup: Dict[str, Dict] = {}
    meta_file = videos_dir / METADATA_FILE
    if meta_file.exists():
        metas = load_json(meta_file, [])
        meta_lookup = {
            m.get("saved_filename", "").strip(): m for m in metas if "saved_filename" in m
        }


    log_path = videos_dir / Path(TRANSCRIBED_DIRNAME) / LOG_FILE
    log = load_json(log_path, {})

    sorted_row = sorted(videos_dir.glob("*.mp4"), key=lambda p: int(p.stem.split("_")[1]))
    for mp4 in sorted_row:
        if log.get(str(mp4)) == "transformed":
            continue

        meta = meta_lookup.get(mp4.name.strip())
        
        chunks = transcribe_video(mp4, meta, course_id, model_size)
        if not chunks:
            logger.warning(f"No transcript chunks generated for {mp4}")

        out_dir = videos_dir / TRANSCRIBED_DIRNAME
        out_path = out_dir / f"{mp4.stem}.jsonl"
        save_jsonl(chunks, out_path)

        log[str(mp4)] = "transformed"
        save_json(log, log_path)

    # Remove temporary audio artifacts (*.mp3) to save space.
    for audio in videos_dir.glob(f"*{AUDIO_EXT}"):
        try:
            audio.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# ENTRY -----------------------------------------------------------------------
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Create sentence-level transcript chunks from video files.")
    #ap.add_argument("root", type=Path, help="Root directory that contains course_* folders")
    ap.add_argument("--model-size", default=MODEL_SIZE, help="Whisper model size to load (default: small)")
    args = ap.parse_args()

    #root = Path("./b_data").expanduser().resolve()
    root = Path("./simplified_llm").expanduser().resolve()    

    if not root.is_dir():
        sys.exit(f"Root path {root} does not exist or is not a directory.")

    for course_dir in sorted(root.glob("course_*"), key=lambda p: int(p.name.split("_")[1])):
        process_course(course_dir, args.model_size)

    logger.info("All videos processed.")


if __name__ == "__main__":
    main()
