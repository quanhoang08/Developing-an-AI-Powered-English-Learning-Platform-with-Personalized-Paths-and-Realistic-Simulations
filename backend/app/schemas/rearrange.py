from pydantic import BaseModel, Field


class RearrangeBlock(BaseModel):
	id: str
	text: str


class RearrangeResponse(BaseModel):
	# Blocks đã xáo trộn; không lộ thứ tự chuẩn. is_open_form chỉ có nghĩa với nhánh Writing.
	attempt_id: str
	blocks: list[RearrangeBlock]
	is_open_form: bool | None = None


class RearrangeSubmit(BaseModel):
	block_order: list[str] = Field(min_length=2, max_length=10)


class RearrangeSubmitResponse(BaseModel):
	# score thang 0-1 (số khối đúng vị trí / tổng số khối), làm tròn 2 chữ số.
	score: float
	correct_order: list[str]
	# "ollama" khi bài dạng mở được giám khảo LLM local xét; explanation là nhận xét của nó.
	graded_by: str = "rules"
	explanation: str | None = None
