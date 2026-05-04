from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
import sys
import os
import httpx

# Add parent directory to path to allow imports when running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
import models
import schemas
from auth_utils import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        name=user.name,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@router.post("/login", response_model=schemas.UserResponse)
def login_user(user: schemas.LoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not db_user.hashed_password:
        raise HTTPException(status_code=400, detail="Invalid email or password")
        
    if not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid email or password")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(db_user.id), "email": db_user.email}, expires_delta=access_token_expires
    )
    
    return {
        "id": db_user.id,
        "email": db_user.email,
        "name": db_user.name,
        "profile_image": db_user.profile_image,
        "token": access_token
    }

@router.post("/google", response_model=schemas.UserResponse)
def google_login(request: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    # ── Step 1: Verify the access_token with Google's API (SERVER-SIDE) ──
    try:
        google_res = httpx.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {request.access_token}"}
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Failed to contact Google servers")
    
    if google_res.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    
    google_user = google_res.json()
    
    # Extract verified user info from Google's response
    email = google_user.get("email")
    name = google_user.get("name", email)  # fallback to email if name is missing
    google_id = google_user.get("sub")
    profile_image = google_user.get("picture")
    
    if not email or not google_id:
        raise HTTPException(status_code=401, detail="Could not retrieve user info from Google")
    
    # ── Step 2: Find or create the user (same logic as before) ──
    db_user = db.query(models.User).filter(models.User.google_id == google_id).first()
    
    if not db_user:
        db_user = db.query(models.User).filter(models.User.email == email).first()
        if db_user:
            # Link existing email/password account with Google
            db_user.google_id = google_id
            if profile_image and not db_user.profile_image:
                db_user.profile_image = profile_image
            db.commit()
            db.refresh(db_user)
        else:
            # Create new Google user
            db_user = models.User(
                email=email,
                name=name,
                google_id=google_id,
                profile_image=profile_image,
                hashed_password=None
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
    # ── Step 3: Issue our JWT ──
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(db_user.id), "email": db_user.email}, expires_delta=access_token_expires
    )
    
    return {
        "id": db_user.id,
        "email": db_user.email,
        "name": db_user.name,
        "profile_image": db_user.profile_image,
        "token": access_token
    }

