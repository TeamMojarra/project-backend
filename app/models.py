from sqlalchemy import Column, Integer, String
from app.database import Base


class Greeting(Base):
    __tablename__ = "greetings"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)