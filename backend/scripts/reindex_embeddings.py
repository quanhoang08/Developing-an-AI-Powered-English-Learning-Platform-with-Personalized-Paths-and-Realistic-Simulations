# Tạo embedding_local (bge-m3, 1024 chiều) cho các chunk ĐÃ CÓ trong DB — dùng sau migration 0011 để
# tài liệu upload từ trước vẫn chat được khi chạy EMBEDDING_PROVIDER=ollama.
# Chỉ đọc cột content và ghi cột embedding_local; không sửa/xóa embedding Gemini cũ, chạy lại an toàn.
# Chạy (từ thư mục backend):  python scripts/reindex_embeddings.py [--all]
#   mặc định chỉ chunk chưa có embedding_local; --all tính lại toàn bộ.
import asyncio
import selectors
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import get_session_factory  # noqa: E402
from app.models.notebook import DocumentChunk  # noqa: E402
from app.services import llm_service  # noqa: E402

BATCH = 50


async def reindex(everything: bool) -> int:
	done = 0
	async with get_session_factory()() as session:
		query = select(DocumentChunk).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
		if not everything:
			query = query.where(DocumentChunk.embedding_local.is_(None))
		chunks = list((await session.execute(query)).scalars().all())
		print(f"{len(chunks)} chunk cần embed", flush=True)
		for chunk in chunks:
			if not chunk.content.strip():
				continue
			chunk.embedding_local = await asyncio.to_thread(llm_service._embed_ollama_sync, chunk.content)
			done += 1
			if done % BATCH == 0:
				await session.commit()
				print(f"  {done}/{len(chunks)}", flush=True)
		await session.commit()
	return done


if __name__ == "__main__":
	# psycopg async không chạy được trên ProactorEventLoop mặc định của Windows.
	total = asyncio.run(
		reindex("--all" in sys.argv),
		loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
	)
	print(f"xong: {total} chunk")
