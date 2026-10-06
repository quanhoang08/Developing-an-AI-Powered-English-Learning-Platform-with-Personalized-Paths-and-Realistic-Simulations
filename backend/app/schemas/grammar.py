from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GrammarQuestion(BaseModel):
	question_id: str
	topic: str
	sentence: str
	options: list[str]


class GrammarAnswer(BaseModel):
	question_id: str = Field(max_length=10)
	choice: str = Field(max_length=80)


class GrammarSubmitRequest(BaseModel):
	answers: list[GrammarAnswer] = Field(min_length=1, max_length=36)
	topic: Literal["tenses", "articles", "prepositions", "agreement", "word_form", "error_correction", "daily"] | None = None


class GrammarResult(BaseModel):
	question_id: str
	topic: str
	is_correct: bool
	correct_answer: str
	explanation_vi: str
	contrast_vi: str | None = None
	why_chosen_vi: str | None = None


class GrammarTopicScore(BaseModel):
	correct: int
	total: int


class GrammarSubmitResponse(BaseModel):
	score: int
	total: int
	results: list[GrammarResult]
	by_topic: dict[str, GrammarTopicScore]
	previous_by_topic: dict[str, GrammarTopicScore] | None = None


class GrammarAttemptItem(BaseModel):
	model_config = {"from_attributes": True}

	topic: str | None
	score: int
	total: int
	by_topic: dict[str, GrammarTopicScore]
	created_at: datetime


class GrammarDaily(BaseModel):
	topic: str | None
	reason_vi: str
	questions: list[GrammarQuestion]
