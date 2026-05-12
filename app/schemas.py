from pydantic import BaseModel


class GreetingResponse(BaseModel):
    id: int
    content: str

    class Config:
        from_attributes = True