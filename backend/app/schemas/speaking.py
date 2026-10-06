from pydantic import BaseModel, Field


class ScenarioResponse(BaseModel):
	id: str
	title: str
	description: str | None = None
	difficulty_level: str | None = None
	goal: str | None = None
	formality_level: str


class SessionCreateRequest(BaseModel):
	scenario_id: str
	persona_id: str | None = None


class SessionCreateResponse(BaseModel):
	session_id: str


class SuggestedPhrase(BaseModel):
	phrase: str
	meaning: str = ""
	source_note: str = ""


class LiteralTranslationNote(BaseModel):
	original: str
	natural: str
	explanation: str = ""


class TurnResponse(BaseModel):
	turn_id: str
	user_transcript: str | None = None
	response_text: str | None = None
	response_audio_url: str | None = None
	pronunciation_score: float | None = None
	pronunciation_advice: str | None = None
	pronunciation_assessment_failed: bool = False
	intent_score: float | None = None
	politeness_score: float | None = None
	intent_feedback: str | None = None
	politeness_feedback: str | None = None
	suggested_phrases: list[SuggestedPhrase] = []
	stt_provider_used: str | None = None
	natural_rephrase: str | None = None
	literal_translation: list[LiteralTranslationNote] = []


class SlangPhraseResponse(BaseModel):
	id: str
	phrase_text: str
	meaning: str
	example_sentence: str | None = None
	formality_level: str
	topic_tags: list[str] = []
	source_reference: str


class PhrasebookSaveRequest(BaseModel):
	# Ít nhất 1 trong slang_phrase_id / phrase_text (mục 2.4); phần còn lại là snapshot.
	slang_phrase_id: str | None = None
	conversation_turn_id: str | None = None
	phrase_text: str | None = None
	meaning: str | None = None
	example_sentence: str | None = None


class PhrasebookEntryResponse(BaseModel):
	id: str
	slang_phrase_id: str | None = None
	conversation_turn_id: str | None = None
	phrase_text: str
	meaning: str | None = None
	example_sentence: str | None = None
	formality_level: str | None = None
	source_reference: str | None = None


class SessionDetailResponse(BaseModel):
	session_id: str
	scenario_id: str | None = None
	status: str
	turns: list[TurnResponse]


class IeltsExamRequest(BaseModel):
	topic: str | None = None


class IeltsCueCard(BaseModel):
	topic: str
	bullets: list[str]


class IeltsExamResponse(BaseModel):
	part1_questions: list[str]
	cue_card: IeltsCueCard
	part3_questions: list[str]
	# Thời gian chuẩn của đề thật (giây) để client chạy đồng hồ.
	part2_prep_seconds: int = 60
	part2_speak_seconds: int = 120


class IeltsAnswerResponse(BaseModel):
	transcript: str
	pronunciation_score: float | None = None
	# Từ/phút từ transcript và thời lượng client gửi; None nếu thiếu thời lượng.
	words_per_minute: int | None = None
	# Báo cáo trôi chảy (backlog 2.4): số từ đệm (um, uh, you know...) và từ khác nhau / tổng từ.
	filler_count: int = 0
	lexical_diversity: float = 0.0


class IeltsAnswerItem(BaseModel):
	part: int = Field(ge=1, le=3)
	question: str
	transcript: str
	pronunciation_score: float | None = None
	words_per_minute: int | None = None
	# Chỉ số báo cáo Speaking (backlog 2.4) từ /ielts/answer; lưu cùng bài trong ielts_attempts.answers.
	filler_count: int | None = Field(default=None, ge=0)
	lexical_diversity: float | None = Field(default=None, ge=0, le=1)


class IeltsEstimateRequest(BaseModel):
	answers: list[IeltsAnswerItem] = Field(min_length=1, max_length=12)
	topic: str | None = Field(default=None, max_length=80)


class IeltsEstimateResponse(BaseModel):
	fluency_coherence: float
	lexical_resource: float
	grammatical_range: float
	pronunciation: float | None = None
	overall: float
	feedback_vi: str
	attempt_id: str
	# Overall của bài gần nhất trước đó (None nếu đây là bài đầu) để hiện tăng/giảm.
	previous_overall: float | None = None


class IeltsAttemptItem(BaseModel):
	id: str
	created_at: str
	topic: str | None = None
	overall: float
	fluency_coherence: float
	lexical_resource: float
	grammatical_range: float
	pronunciation: float | None = None
	words_per_minute: int | None = None
	# Tổng số từ đệm và độ đa dạng từ trung bình của cả bài; None với bài cũ lưu trước khi có chỉ số này.
	filler_count: int | None = None
	lexical_diversity: float | None = None
	feedback_vi: str
