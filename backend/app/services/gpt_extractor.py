from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

import httpx

# A minimal GPT-4o wrapper to extract structured fields from OCR text.
# This module expects an environment variable OPENAI_API_KEY to be set and
# will call the OpenAI HTTP API / responses or chat completions endpoint depending on availability.

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/responses")


class GPTExtractor:
    """Simple wrapper for GPT-4o structured extraction prompts.

    Note: In production you'd want retries, backoff, and robust error handling.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY must be set to use GPTExtractor")

    def _build_prompt(self, ocr_text: str, doc_type: str) -> str:
        # concise extraction instruction
        examples = (
            "Return a JSON object with keys: doctor_name, doctor_reg, patient_name, patient_age, "
            "bill_date, bill_no, diagnosis, line_items (list of {description,amount,category})," 
            "and field_confidences (map of field->0-1). Only output JSON."
        )
        prompt = f"{examples}\n\nDOC_TYPE: {doc_type}\n\nOCR_TEXT:\n{ocr_text}\n\nRespond with JSON only."
        return prompt

    async def extract_from_text(self, ocr_text: str, doc_type: str = "prescription") -> Dict[str, Any]:
        prompt = self._build_prompt(ocr_text, doc_type)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-4o",
            "input": prompt,
            # keep deterministic output for structured extraction
            "temperature": 0.0,
            "max_tokens": 1500,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OPENAI_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # The responses API can vary; try to find a text output
        text_out = None
        if isinstance(data, dict):
            # try common shapes
            if "output" in data:
                # Responses API
                out = data.get("output")
                if isinstance(out, list) and out:
                    # find first textual content
                    for item in out:
                        if isinstance(item, dict) and "content" in item:
                            cont = item.get("content")
                            if isinstance(cont, list):
                                # content list contains objects
                                for c in cont:
                                    if c.get("type") == "output_text":
                                        text_out = c.get("text")
                                        break
                            elif isinstance(cont, str):
                                text_out = cont
                                break
            if text_out is None and data.get("choices"):
                # Chat completions style
                try:
                    text_out = data["choices"][0]["message"]["content"]
                except Exception:
                    text_out = data["choices"][0].get("text")

        if not text_out:
            raise RuntimeError("No textual output from GPT response")

        # try to parse as JSON
        parsed = {}
        try:
            parsed = json.loads(text_out.strip())
        except Exception:
            # try to extract JSON substring
            import re

            m = re.search(r"\{.*\}", text_out, flags=re.S)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = {"raw_text": text_out}
            else:
                parsed = {"raw_text": text_out}

        # Ensure field_confidences present
        if "field_confidences" not in parsed:
            parsed["field_confidences"] = {k: 0.9 for k in parsed.keys() if k != "field_confidences"}

        return {
            "doc_type": doc_type,
            "extracted_json": parsed,
            "field_confidences": parsed.get("field_confidences"),
            "raw_text": ocr_text,
        }

    async def extract_from_document(self, file_bytes: bytes, doc_type: str = "prescription") -> Dict[str, Any]:
        # For simplicity, assume caller will run OCR and pass text. If not, convert bytes to text via OCR service.
        raise NotImplementedError("extract_from_document not implemented in GPTExtractor; use extract_from_text with OCR output")
