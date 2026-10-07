# Hàm thuần trích text từ .docx/.doc/.pdf và chia chunk — không đụng DB/network, dễ unit test riêng.
import subprocess
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.utils.chunking import chunk_document

# ~120 từ/chunk theo thực nghiệm experiments/run_retrieval.py: chunk 60 từ mất ngữ cảnh, 200+ từ
# làm loãng embedding; chia theo câu + chồng lấp giữ trọn bằng chứng (coverage 1.0 ở mọi cỡ).
DEFAULT_CHUNK_WORDS = 120


def extract_docx_text(path: str) -> str:
	"""Trích toàn bộ text từ file .docx (theo thứ tự paragraph, bỏ paragraph rỗng)."""
	document = DocxDocument(path)
	paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
	return "\n".join(paragraph for paragraph in paragraphs if paragraph)


def extract_pdf_text(path: str) -> str:
	"""Trích text từ PDF có lớp text (PDF scan chỉ có ảnh sẽ ra rỗng -> ingest failed)."""
	pages = [(page.extract_text() or "").strip() for page in PdfReader(path).pages]
	return "\n".join(page for page in pages if page)


def extract_doc_text(path: str) -> str:
	"""Trích text từ .doc (Word 97-2003) qua antiword — python-docx không đọc được định dạng nhị phân cũ."""
	return subprocess.run(
		["antiword", path], capture_output=True, text=True, check=True, timeout=60
	).stdout.strip()


EXTRACTORS = {".docx": extract_docx_text, ".doc": extract_doc_text, ".pdf": extract_pdf_text}


def extract_text(path: str) -> str:
	"""Chọn hàm trích theo extension; KeyError nếu định dạng không hỗ trợ."""
	return EXTRACTORS[Path(path).suffix.lower()](path)


def chunk_text(text: str, max_words: int = DEFAULT_CHUNK_WORDS) -> list[str]:
	"""Chia text theo câu (có chồng lấp 1 câu) — giữ tên hàm cũ cho code gọi trực tiếp; pipeline ingest
	dùng chunk_document với cấu hình trong Settings (rag_service.ingest_document)."""
	return chunk_document(text, "sentence", max_words, overlap_sentences=1)
