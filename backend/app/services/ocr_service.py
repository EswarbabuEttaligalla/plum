from __future__ import annotations

import subprocess
from typing import Optional
import io

try:
    from PIL import Image
except Exception:
    Image = None


class OCRService:
    """Simple OCR service. Uses Tesseract if available; otherwise raises.

    For MVP we expect developers to install Tesseract in the environment. This wrapper
    calls `tesseract` CLI to extract text from image bytes. If input is already text,
    it can be passed through.
    """

    def __init__(self, tesseract_cmd: str = "tesseract"):
        self.tesseract_cmd = tesseract_cmd

    def extract_text_from_image_file(self, image_path: str) -> str:
        # call tesseract to output to stdout via -
        try:
            res = subprocess.run([self.tesseract_cmd, image_path, "stdout"], capture_output=True, check=True, text=True)
            return res.stdout
        except Exception as e:
            raise RuntimeError(f"Tesseract OCR failed: {e}")

    def extract_text_from_bytes(self, b: bytes, tmpfile: Optional[str] = None) -> str:
        # write to a temp file and run tesseract
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            if Image:
                img = Image.open(io.BytesIO(b))
                img.save(path)
            else:
                with open(path, "wb") as fh:
                    fh.write(b)
            return self.extract_text_from_image_file(path)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
