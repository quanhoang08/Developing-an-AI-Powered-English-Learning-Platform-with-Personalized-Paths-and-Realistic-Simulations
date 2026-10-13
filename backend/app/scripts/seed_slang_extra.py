"""Bổ sung 32 cụm thoại/slang vào slang_phrases cho đủ 80 (đề xuất ban đầu 80-120, migration 0010 chỉ seed 48).

Không đổi schema nên không cần migration; chạy lặp lại an toàn (bỏ qua cụm đã có, so không phân biệt hoa thường).
Cũng như 48 cụm gốc, source_reference chỉ là từ điển CẦN ĐỐI CHIẾU trước khi trích dẫn trong báo cáo.

Chạy (trong container api):
  docker exec -e PYTHONPATH=/app lumina_api python -m app.scripts.seed_slang_extra
"""
import asyncio

from sqlalchemy import func, select

from app.database import get_session_factory
from app.models.speaking import SlangPhrase

CAM, MW = "Cambridge Dictionary", "Merriam-Webster"

# (phrase, meaning, example, formality, topics, source)
EXTRA = [
	("break the ice", "make people feel more relaxed when they first meet", "He told a joke to break the ice.", "casual", ["conversation", "friends"], CAM),
	("under the weather", "slightly ill", "I'm feeling a bit under the weather today.", "casual", ["health", "everyday"], CAM),
	("hang in there", "keep trying in a difficult situation", "Hang in there, the exams finish on Friday.", "casual", ["encouragement"], CAM),
	("bite the bullet", "force yourself to do something unpleasant", "I had to bite the bullet and call the dentist.", "casual", ["everyday", "work"], CAM),
	("on the same page", "having the same understanding as other people", "Let's make sure we're all on the same page before the launch.", "casual", ["work"], CAM),
	("rain check", "a request to do something another time", "Can I take a rain check? I'm busy tonight.", "casual", ["plans", "friends"], MW),
	("my treat", "I will pay for it", "Coffee is my treat this time.", "casual", ["restaurant", "friends"], CAM),
	("you bet", "yes, certainly; you are welcome", "Thanks for helping me! - You bet.", "casual", ["everyday"], MW),
	("no way", "used to show surprise or disbelief", "You won the lottery? No way!", "casual", ["conversation"], CAM),
	("take your time", "there is no need to hurry", "Take your time, we are not in a rush.", "casual", ["everyday"], CAM),
	("I'm swamped", "I have too much work to do", "I'm swamped with work this week.", "casual", ["work"], MW),
	("hit the sack", "go to bed", "I'm exhausted, so I'm going to hit the sack.", "casual", ["everyday"], CAM),
	("over the moon", "extremely happy", "She was over the moon about her results.", "casual", ["feelings"], CAM),
	("out of the blue", "unexpectedly", "He called me out of the blue yesterday.", "casual", ["conversation"], CAM),
	("keep an eye on", "watch something or someone carefully", "Could you keep an eye on my bag for a minute?", "neutral", ["request", "everyday"], CAM),
	("figure out", "understand or solve something", "I can't figure out how this app works.", "neutral", ["study", "everyday"], CAM),
	("take care of", "look after someone or deal with something", "I'll take care of the booking.", "neutral", ["work", "everyday"], CAM),
	("get along with", "have a good relationship with someone", "I get along well with my roommate.", "neutral", ["friends", "everyday"], CAM),
	("run out of", "have no more of something", "We've run out of milk.", "neutral", ["shopping", "everyday"], CAM),
	("look forward to", "feel happy about something that will happen", "I'm looking forward to the trip.", "neutral", ["plans", "everyday"], CAM),
	("come up with", "think of an idea or plan", "Can you come up with a better plan?", "neutral", ["work", "study"], CAM),
	("get in touch", "contact someone", "Please get in touch if you have any questions.", "neutral", ["work", "request"], CAM),
	("in the long run", "over a long period of time", "Saving money now will help you in the long run.", "neutral", ["conversation"], CAM),
	("on the other hand", "used to introduce a different point of view", "The job pays well; on the other hand, the hours are long.", "neutral", ["conversation", "study"], CAM),
	("I would like to inquire about", "a formal way to ask for information", "I would like to inquire about the available rooms.", "formal", ["request", "work"], CAM),
	("at your earliest convenience", "as soon as it is easy for you", "Please reply at your earliest convenience.", "formal", ["work"], CAM),
	("I regret to inform you", "a formal way to begin bad news", "I regret to inform you that the position has been filled.", "formal", ["work"], CAM),
	("please do not hesitate to contact me", "a formal invitation to ask questions", "If you need more details, please do not hesitate to contact me.", "formal", ["work"], CAM),
	("pursuant to", "according to a rule or agreement (formal)", "Pursuant to our agreement, payment is due on Monday.", "formal", ["work"], MW),
	("on behalf of", "representing another person or group", "I am writing on behalf of the committee.", "formal", ["work"], CAM),
	("in accordance with", "following a rule, law or instruction", "The test was conducted in accordance with the guidelines.", "formal", ["work", "study"], CAM),
	("I would be delighted to", "a formal, enthusiastic way to accept", "I would be delighted to attend the ceremony.", "formal", ["greeting", "request"], CAM),
]


async def main() -> None:
	async with get_session_factory()() as db:
		have = {p.lower() for (p,) in (await db.execute(select(SlangPhrase.phrase_text))).all()}
		new = [row for row in EXTRA if row[0].lower() not in have]
		for phrase, meaning, example, formality, topics, source in new:
			db.add(SlangPhrase(phrase_text=phrase, meaning=meaning, example_sentence=example, formality_level=formality, topic_tags=topics, source_reference=source))
		await db.commit()
		total = (await db.execute(select(func.count()).select_from(SlangPhrase))).scalar_one()
	print(f"Thêm {len(new)} cụm, tổng {total}")


if __name__ == "__main__":
	asyncio.run(main())
