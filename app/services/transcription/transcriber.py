"""
Audio transcription via faster-whisper (local, free — no API key,
no per-minute cost, no rate limits).

    video.mp4 -> ffmpeg extracts mono 16kHz wav -> faster-whisper -> segments

Model weights download once from Hugging Face on first run and are
cached locally after that.
"""

import os
import subprocess
import tempfile

from app.schemas.transcript import TranscriptResult, TranscriptSegment

_model = None  # lazy-loaded singleton so repeated calls don't reload weights


def _get_model(model_size: str = "base"):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        # int8 compute type keeps this usable on CPU-only laptops,
        # which is what most hackathon dev machines will be.
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


def _extract_audio(video_path: str, out_wav_path: str) -> None:
    """
    Pull mono 16kHz audio out of the video with ffmpeg. Whisper wants
    16kHz anyway, so resampling here avoids doing it inside Python.
    """
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000",
        "-loglevel", "error",
        out_wav_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")


def transcribe_video(video_path: str, model_size: str = "base") -> TranscriptResult:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    model = _get_model(model_size)

    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_path = os.path.join(tmp_dir, "audio.wav")
        _extract_audio(video_path, wav_path)

        segments_iter, info = model.transcribe(wav_path, beam_size=5)

        segments: list[TranscriptSegment] = []
        full_text_parts: list[str] = []
        for seg in segments_iter:
            text = seg.text.strip()
            segments.append(
                TranscriptSegment(start=round(seg.start, 2), end=round(seg.end, 2), text=text)
            )
            full_text_parts.append(text)

    return TranscriptResult(
        video_path=video_path,
        language=info.language,
        duration_sec=round(info.duration, 2) if info.duration else None,
        full_text=" ".join(full_text_parts),
        segments=segments,
    )