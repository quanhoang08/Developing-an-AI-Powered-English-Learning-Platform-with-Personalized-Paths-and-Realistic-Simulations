# Hàm thuần trích text từ .docx và chia chunk — không đụng DB/network, dễ unit test riêng.
from docx import Document as DocxDocument

from app.utils.chunking import chunk_document

# ~120 từ/chunk theo thực nghiệm experiments/run_retrieval.py: chunk 60 từ mất ngữ cảnh, 200+ từ
# làm loãng embedding; chia theo câu + chồng lấp giữ trọn bằng chứng (coverage 1.0 ở mọi cỡ).
DEFAULT_CHUNK_WORDS = 120


def extract_docx_text(path: str) -> str:
	"""Trích toàn bộ text từ file .docx (theo thứ tự paragraph, bỏ paragraph rỗng)."""
	document = DocxDocument(path)
	paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
	return "\n".join(paragraph for paragraph in paragraphs if paragraph)


def chunk_text(text: str, max_words: int = DEFAULT_CHUNK_WORDS) -> list[str]:
	"""Chia text theo câu (có chồng lấp 1 câu) — giữ tên hàm cũ cho code gọi trực tiếp; pipeline ingest
	dùng chunk_document với cấu hình trong Settings (rag_service.ingest_document)."""
	return chunk_document(text, "sentence", max_words, overlap_sentences=1)
