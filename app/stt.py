from __future__ import annotations

from pathlib import Path
from typing import Optional

_model = None
_load_error: Optional[str] = None


def transcribe_file(path: str | Path, language: str = "ru") -> str:
    """Распознать аудио через faster-whisper, если пакет и модель доступны."""
    global _model, _load_error
    if _load_error:
        raise RuntimeError(_load_error)
    if _model is None:
        try:
            from faster_whisper import WhisperModel

            from app.config import WHISPER_MODEL

            _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        except Exception as exc:  # noqa: BLE001
            _load_error = (
                "Локальный Whisper недоступен "
                f"({exc}). Используйте распознавание в браузере (кнопка «говорить»)."
            )
            raise RuntimeError(_load_error) from exc

    segments, _info = _model.transcribe(str(path), language=language, vad_filter=True)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise RuntimeError("речь не распознана")
    return text
