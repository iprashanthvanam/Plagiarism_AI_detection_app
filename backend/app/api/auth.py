


from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError

from app.libs.auth import authenticate_user, create_access_token
from app.env import SECRET_KEY, ALGORITHM
from app.core.limitter import limiter


router = APIRouter()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = await authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

 
    payload = {
        "sub": user["user_id"],       # INTERNAL ID (DB)
        "username": user["username"],# DISPLAY / LOGIN
        "role": user["role"],        # admin | student
    }

    access_token = create_access_token(payload)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    }

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id = payload.get("sub")
        username = payload.get("username")
        role = payload.get("role")

        if not user_id or not username or not role:
            raise credentials_exception

        return {
            "id": user_id,
            "username": username,
            "role": role,
        }

    except JWTError:
        raise credentials_exception
