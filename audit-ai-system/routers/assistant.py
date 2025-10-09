from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.rag_assistant import ask_question

router = APIRouter(prefix="/api/assistant", tags=["Assistant"])

class QuestionRequest(BaseModel):
    question: str

class QuestionResponse(BaseModel):
    question: str
    answer: str

@router.post("/query", response_model=QuestionResponse)
async def query_assistant(request: QuestionRequest):
    """Ask a question to the AI assistant"""
    try:
        result = await ask_question(request.question)
        return result  # Returns dict with question and answer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
