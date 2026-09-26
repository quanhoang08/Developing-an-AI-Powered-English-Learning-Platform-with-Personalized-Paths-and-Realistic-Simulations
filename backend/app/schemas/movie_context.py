from pydantic import BaseModel


class MovieContextMatchItem(BaseModel):
	match_id: str
	source_type: str
	phrase_text: str
	audio_url: str
	is_saved: bool


class MovieContextSearchResponse(BaseModel):
	matches: list[MovieContextMatchItem]
