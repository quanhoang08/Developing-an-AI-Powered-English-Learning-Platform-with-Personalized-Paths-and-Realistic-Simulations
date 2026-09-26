from pydantic import BaseModel


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
