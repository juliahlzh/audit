import re
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from PIL import Image
from pypdf import PdfReader
from pytesseract import TesseractNotFoundError

from ..config import POPPLER_PATH, TESSERACT_CMD


@dataclass
class OCRResult:
    amount: float | None
    account_number: str | None
    transaction_date: str | None
    bank_name: str | None
    raw_text: str


AMOUNT_PATTERN = re.compile(r"(?:(?:rp|idr)\s*)?([\d\.\,]{4,})", re.IGNORECASE)
ACCOUNT_PATTERN = re.compile(r"\b\d{8,20}\b")
DATE_PATTERN = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b")
BANK_PATTERN = re.compile(r"\b(BCA|BRI|BNI|MANDIRI|CIMB|PERMATA|DANAMON|BSI|OCBC)\b", re.IGNORECASE)


def _configure_tesseract():
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def _normalize_amount(value: str) -> float | None:
    cleaned = value.replace("Rp", "").replace("rp", "").replace("IDR", "").replace("idr", "").replace(" ", "")
    if cleaned.count(",") == 1 and cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "").replace(".", "")
    try:
        number = float(cleaned)
        return number if number > 0 else None
    except ValueError:
        return None


def _extract_from_text(raw_text: str) -> OCRResult:
    amounts = [_normalize_amount(match) for match in AMOUNT_PATTERN.findall(raw_text)]
    amounts = [amount for amount in amounts if amount]
    accounts = ACCOUNT_PATTERN.findall(raw_text)
    dates = DATE_PATTERN.findall(raw_text)
    banks = BANK_PATTERN.findall(raw_text)
    return OCRResult(
        amount=max(amounts) if amounts else None,
        account_number=max(accounts, key=len) if accounts else None,
        transaction_date=dates[0] if dates else None,
        bank_name=banks[0].upper() if banks else None,
        raw_text=raw_text.strip(),
    )


def _ocr_image(file_path: Path) -> str:
    _configure_tesseract()
    try:
        return pytesseract.image_to_string(Image.open(file_path), lang="eng")
    except (TesseractNotFoundError, RuntimeError, OSError):
        return ""


def _ocr_pdf(file_path: Path) -> str:
    text_chunks = []
    try:
        reader = PdfReader(str(file_path))
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                text_chunks.append(extracted)
    except Exception:
        pass
    if text_chunks:
        return "\n".join(text_chunks)

    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(file_path), dpi=250, poppler_path=POPPLER_PATH or None)
        _configure_tesseract()
        return "\n".join(pytesseract.image_to_string(image, lang="eng") for image in images)
    except Exception:
        return ""


def extract_transfer_details(file_path: str) -> OCRResult:
    path = Path(file_path)
    raw_text = ""
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        raw_text = _ocr_image(path)
    elif path.suffix.lower() == ".pdf":
        raw_text = _ocr_pdf(path)
    return _extract_from_text(raw_text)
