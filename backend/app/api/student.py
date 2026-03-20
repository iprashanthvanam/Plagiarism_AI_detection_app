from fastapi import APIRouter, Depends, HTTPException
from app.libs.database import db_service
from app.core.security import get_current_user

router = APIRouter()

@router.get("/student/dashboard")
async def student_dashboard(current_user: dict = Depends(get_current_user)):
    """✅ NEW: Get documents for current student."""
    
    # Verify it's a student
    if current_user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    
    # Get this student's documents
    user_id = current_user.get("id")
    documents = await db_service.get_documents_by_user(user_id)
    
    # ✅ CRITICAL: Return as array, not dict
    return documents if isinstance(documents, list) else []
