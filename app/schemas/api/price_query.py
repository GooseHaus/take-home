from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: date | None = Field(None, description="First day. Default: start of the analysed period")
    end: date | None = Field(None, description="Last day. Default: end of the analysed period")

    @model_validator(mode="after")
    def check_date_order(self) -> "PriceQuery":
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end")
        return self
