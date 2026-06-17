import urllib.request
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# Kokoro TTS model files
# ---------------------------------------------------------------------------
KOKORO_MODELS = {
    "kokoro-v1.0.onnx": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/kokoro-v1.0.onnx"
    ),
    "voices-v1.0.bin": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/voices-v1.0.bin"
    ),
}


def download_file(url: str, dest: Path) -> None:
    if dest.exists():
        logger.info(f"{dest.name} already exists, skipping.")
        return
    logger.info(f"Downloading {dest.name} ...")
    try:
        urllib.request.urlretrieve(url, str(dest))
        logger.success(f"Downloaded {dest.name} successfully.")
    except Exception as e:
        logger.error(f"Failed to download {dest.name}: {e}")


def download_kokoro(models_dir: Path) -> None:
    for filename, url in KOKORO_MODELS.items():
        download_file(url, models_dir / filename)


def download_openwakeword_models() -> None:
    """Use openwakeword's built-in downloader to fetch pre-trained ONNX models."""
    try:
        import openwakeword
        logger.info("Downloading OpenWakeWord pre-trained models...")
        openwakeword.utils.download_models()
        logger.success("OpenWakeWord models downloaded.")
    except Exception as e:
        logger.error(f"Failed to download OpenWakeWord models: {e}")


def main():
    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    logger.info("--- Kokoro TTS models ---")
    download_kokoro(models_dir)

    logger.info("--- OpenWakeWord models ---")
    download_openwakeword_models()

    logger.success("All downloads complete.")


if __name__ == "__main__":
    main()
