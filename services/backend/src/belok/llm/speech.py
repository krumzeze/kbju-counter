import aiohttp

from belok.config import Settings
from belok.i18n import Language


class SpeechError(Exception):
    pass


class SpeechToText:
    """Client for an OpenAI-compatible /audio/transcriptions endpoint (Whisper and alikes)."""

    @classmethod
    def from_settings(cls, settings: Settings) -> "SpeechToText | None":
        if settings.stt_api_key is None:
            return None
        return cls(
            settings.stt_api_key.get_secret_value(), settings.stt_base_url, settings.stt_model
        )

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._url = f"{self._base}/audio/transcriptions"
        self.model = model

    async def ping(self) -> None:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as http,
            http.get(
                f"{self._base}/models", headers={"Authorization": f"Bearer {self._api_key}"}
            ) as response,
        ):
            if response.status != 200:
                raise SpeechError(f"HTTP {response.status}")

    async def transcribe(self, audio: bytes, language: Language) -> str:
        form = aiohttp.FormData()
        form.add_field("file", audio, filename="voice.ogg", content_type="audio/ogg")
        form.add_field("model", self.model)
        form.add_field("language", language.value)
        form.add_field("response_format", "json")
        try:
            async with (
                aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http,
                http.post(
                    self._url, data=form, headers={"Authorization": f"Bearer {self._api_key}"}
                ) as response,
            ):
                if response.status != 200:
                    raise SpeechError(f"transcription failed with HTTP {response.status}")
                data = await response.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SpeechError("transcription request failed") from exc
        return str(data.get("text", "")).strip()
