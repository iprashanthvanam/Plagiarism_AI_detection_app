


from fastapi import APIRouter, Depends, HTTPException
from app.libs.database import db_service
from app.core.security import get_current_user



router = APIRouter()

@router.get("/dashboard")
async def student_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student only")

    return await db_service.get_documents_by_user(current_user["id"])
