from pydantic import BaseModel, Field


class ArticleRelevance(BaseModel):
    article_id: int = Field(description="Id of one of the candidate articles supplied in the prompt")
    relevance: float = Field(description="0 to 1: how directly this article explains the move")
