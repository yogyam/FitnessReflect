from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    livekit_url: str = os.getenv("LIVEKIT_URL", "")
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    vectorstore_dir: Path = Path(os.getenv("LUMA_VECTORSTORE_DIR", "./vectorstore"))
    collection_name: str = os.getenv("LUMA_COLLECTION_NAME", "fitness-log")
    embedding_model: str = os.getenv("LUMA_EMBEDDING_MODEL", "text-embedding-3-small")
    chat_model: str = os.getenv("LUMA_CHAT_MODEL", "gpt-4o-mini")
    stt_model: str = os.getenv("LUMA_STT_MODEL", "whisper-1")
    tts_voice: str = os.getenv("LUMA_TTS_VOICE", "alloy")


settings = Settings()
