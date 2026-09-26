"""Slang/cụm thoại + Sổ tay (feature-speaking.md mục 2, 4): tạo slang_phrases và
user_phrasebook_entries (chưa tồn tại trong DB thật) và seed bản đầu tiên.

Seed chỉ chứa cụm từ lịch sự/không tục tĩu (mục 4.2). Nghĩa và ví dụ do nhóm biên soạn lại;
source_reference là từ điển cần đối chiếu khi trích dẫn trong báo cáo — nội dung cần được người
phụ trách review thủ công trước khi coi là bản cuối (mục 4.3).
"""

from alembic import op
from sqlalchemy import ARRAY, CheckConstraint, Column, DateTime, ForeignKey, String, Text, inspect, text
from sqlalchemy.dialects.postgresql import UUID


revision = "20260919_0010"
down_revision = "20260919_0009"
branch_labels = None
depends_on = None

CAM = "Cambridge Dictionary"
OXF = "Oxford Learner's Dictionaries"
MW = "Merriam-Webster"

# (phrase, meaning, example, formality, topics, source)
SEED = [
    # ---- casual
    ("no worries", "it is fine; do not feel bad", "Sorry I'm late! - No worries, we just started.", "casual", ["everyday", "apology"], CAM),
    ("catch up", "talk to someone you have not seen for a while", "Let's grab a coffee and catch up this weekend.", "casual", ["friends", "everyday"], CAM),
    ("hang out", "spend relaxed time with someone", "We usually hang out at the park after class.", "casual", ["friends"], CAM),
    ("I'm down", "I agree to do it; I am happy to join", "Pizza tonight? - I'm down!", "casual", ["friends", "plans"], MW),
    ("sounds good", "I agree with that plan", "We can meet at six. - Sounds good.", "casual", ["plans", "everyday"], CAM),
    ("my bad", "it was my mistake", "Oh, my bad, I sent you the wrong file.", "casual", ["apology"], MW),
    ("no big deal", "not important or serious", "Forgot your pen? No big deal, you can borrow mine.", "casual", ["everyday", "apology"], CAM),
    ("piece of cake", "very easy", "The quiz was a piece of cake.", "casual", ["study", "everyday"], CAM),
    ("break a leg", "good luck, especially before a performance", "You have the audition today? Break a leg!", "casual", ["encouragement"], CAM),
    ("cut it out", "stop doing something annoying", "Cut it out, I'm trying to study!", "casual", ["friends"], CAM),
    ("give it a shot", "try something", "I've never cooked Thai food, but I'll give it a shot.", "casual", ["encouragement", "everyday"], CAM),
    ("take it easy", "relax; do not work too hard", "You look tired. Take it easy this evening.", "casual", ["everyday"], CAM),
    ("what's up", "a casual greeting: how are you / what is happening", "Hey Sam, what's up?", "casual", ["greeting"], CAM),
    ("keep me posted", "keep telling me about new information", "Keep me posted on how the interview goes.", "casual", ["work", "friends"], CAM),
    ("I'm beat", "I am very tired", "I'm beat after that long trip.", "casual", ["everyday"], MW),
    ("let's call it a day", "stop working for today", "We've done enough. Let's call it a day.", "casual", ["work"], CAM),
    ("it's on me", "I will pay for it", "Dinner is on me tonight.", "casual", ["restaurant", "friends"], CAM),
    ("you nailed it", "you did it very well", "Great presentation, you nailed it!", "casual", ["encouragement", "study"], CAM),
    ("hit the books", "start studying seriously", "I have to hit the books before the exam.", "casual", ["study"], CAM),
    ("call it a night", "stop for the evening and go to bed", "It's late, let's call it a night.", "casual", ["everyday"], CAM),
    ("heads up", "a short warning about something", "Just a heads up, the meeting starts early.", "casual", ["work"], CAM),
    ("I'm all ears", "I am listening carefully", "Tell me your idea, I'm all ears.", "casual", ["conversation"], CAM),
    ("long time no see", "a greeting for someone you have not seen for a long time", "Long time no see! How have you been?", "casual", ["greeting", "friends"], CAM),
    ("fair enough", "I accept your point", "You want to leave early? Fair enough.", "casual", ["conversation"], CAM),
    ("no hard feelings", "I am not angry with you", "You won the game, no hard feelings.", "casual", ["friends", "apology"], CAM),
    ("cheer up", "become happier", "Cheer up, tomorrow will be better.", "casual", ["encouragement", "friends"], CAM),
    # ---- neutral
    ("could you give me a hand", "could you help me", "Could you give me a hand with these boxes?", "neutral", ["request", "everyday"], CAM),
    ("I'd like to", "a polite way to say what you want", "I'd like to order the chicken salad, please.", "neutral", ["restaurant", "request"], CAM),
    ("what do you recommend", "asking someone to suggest something", "What do you recommend for a light lunch?", "neutral", ["restaurant", "shopping"], CAM),
    ("could I have the check", "asking the waiter for the bill", "Excuse me, could I have the check, please?", "neutral", ["restaurant"], CAM),
    ("I'm just looking", "telling a shop assistant you do not need help yet", "I'm just looking, thanks.", "neutral", ["shopping"], CAM),
    ("do you happen to know", "a polite way to ask if someone knows something", "Do you happen to know where the station is?", "neutral", ["request", "travel"], CAM),
    ("it doesn't work", "something is broken", "The headset doesn't work, so I'd like a refund.", "neutral", ["shopping", "complaint"], CAM),
    ("I'd appreciate it if", "a polite request that shows thanks in advance", "I'd appreciate it if you could reply by Friday.", "neutral", ["request", "work"], CAM),
    ("as far as I know", "based on the information I have", "As far as I know, the store opens at nine.", "neutral", ["conversation"], CAM),
    ("to be honest", "I am going to say what I really think", "To be honest, I found the film a bit slow.", "neutral", ["conversation"], CAM),
    ("I see what you mean", "I understand your point", "I see what you mean, but I'd try another way.", "neutral", ["conversation"], CAM),
    ("thanks for having me", "thanking a host after a visit", "Thanks for having me, dinner was wonderful.", "neutral", ["greeting", "friends"], CAM),
    ("I'll get back to you", "I will answer you later", "Let me check and I'll get back to you tomorrow.", "neutral", ["work"], CAM),
    ("could you say that again", "asking someone to repeat", "Sorry, could you say that again more slowly?", "neutral", ["conversation", "study"], CAM),
    ("it's up to you", "you can decide", "We can go by bus or train, it's up to you.", "neutral", ["plans"], CAM),
    # ---- formal
    ("I would be grateful if", "a formal way to make a request", "I would be grateful if you could send the details.", "formal", ["request", "work"], OXF),
    ("with regard to", "about; concerning", "With regard to your question, the answer is yes.", "formal", ["work"], OXF),
    ("I apologize for the inconvenience", "a formal apology for causing trouble", "I apologize for the inconvenience caused by the delay.", "formal", ["apology", "work"], OXF),
    ("please find attached", "used in emails to say a file is attached", "Please find attached the report you requested.", "formal", ["work", "email"], OXF),
    ("I look forward to hearing from you", "a formal way to end a message", "Thank you for your time. I look forward to hearing from you.", "formal", ["work", "email"], OXF),
    ("would you mind", "a polite way to ask someone to do something", "Would you mind closing the window?", "formal", ["request"], OXF),
    ("it would be a pleasure", "a formal way to say you would be happy to do it", "Join us for dinner? It would be a pleasure.", "formal", ["greeting", "plans"], OXF),
]


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if "slang_phrases" not in existing:
        op.create_table(
            "slang_phrases",
            Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")),
            Column("phrase_text", String(150), nullable=False),
            Column("meaning", Text(), nullable=False),
            Column("example_sentence", Text(), nullable=True),
            Column("formality_level", String(20), nullable=False, server_default=text("'neutral'")),
            Column("topic_tags", ARRAY(String()), nullable=True),
            Column("source_reference", String(150), nullable=False),
            CheckConstraint("source_reference <> ''", name="ck_slang_source_not_empty"),
        )

    if "user_phrasebook_entries" not in existing:
        op.create_table(
            "user_phrasebook_entries",
            Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")),
            Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            Column("slang_phrase_id", UUID(as_uuid=True), ForeignKey("slang_phrases.id", ondelete="SET NULL"), nullable=True),
            Column("conversation_turn_id", UUID(as_uuid=True), ForeignKey("conversation_turns.id", ondelete="SET NULL"), nullable=True),
            # Snapshot: giữ nội dung dù slang_phrases sau này đổi/xoá (mục 2.5).
            Column("phrase_text", String(150), nullable=False),
            Column("meaning", Text(), nullable=True),
            Column("example_sentence", Text(), nullable=True),
            Column("formality_level", String(20), nullable=True),
            Column("created_at", DateTime(timezone=True), server_default=text("now()")),
        )

    bind = op.get_bind()
    if not bind.execute(text("SELECT count(*) FROM slang_phrases")).scalar():
        for phrase, meaning, example, formality, topics, source in SEED:
            bind.execute(
                text(
                    "INSERT INTO slang_phrases (phrase_text, meaning, example_sentence, formality_level,"
                    " topic_tags, source_reference) VALUES (:p, :m, :e, :f, :t, :s)"
                ),
                {"p": phrase, "m": meaning, "e": example, "f": formality, "t": topics, "s": source},
            )


def downgrade() -> None:
    op.drop_table("user_phrasebook_entries")
    op.drop_table("slang_phrases")
