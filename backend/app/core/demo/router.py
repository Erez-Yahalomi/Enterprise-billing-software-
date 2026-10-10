from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.demo import service
from app.demo.schemas import DemoGenerateRequest, DemoGenerateResponse
from app.demo.service import SIZE_TIERS

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/generate", response_model=DemoGenerateResponse)
def generate_demo(data: DemoGenerateRequest, db: Session = Depends(get_db)) -> DemoGenerateResponse:
    if data.size not in SIZE_TIERS:
        raise HTTPException(status_code=400, detail=f"size must be one of: {', '.join(SIZE_TIERS)}")
    result = service.generate_demo(db, data.size, data.include_uci)
    return DemoGenerateResponse(**result)


@router.post("/reset")
def reset_demo(db: Session = Depends(get_db)) -> dict:
    service.reset_demo(db)
    return {"status": "reset"}
