from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# ─── Auth Schemas ───────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class GoogleLoginRequest(BaseModel):
    access_token: str  # Chrome Identity API token — backend verifies this with Google

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    token: Optional[str] = None
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True

# ─── Search Schemas ─────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    platform: str = "danawa"
    conversation_id: Optional[int] = None  # If continuing an existing conversation

class ProductResponse(BaseModel):
    product_id: Optional[str] = None
    name: str
    brand: Optional[str] = None
    price: Optional[int] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    reason: Optional[str] = None
    score: Optional[float] = None

class SearchResponse(BaseModel):
    products: list[ProductResponse]
    recommendation: str
    conversation_id: Optional[int] = None

# ─── Chat Message Schemas ───────────────────────────
class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Conversation Schemas ───────────────────────────
class ConversationResponse(BaseModel):
    id: int
    title: str
    platform: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ConversationDetailResponse(ConversationResponse):
    messages: list[ChatMessageResponse] = []

# ─── Legacy Search History (backward compat) ────────
class SearchHistoryCreate(BaseModel):
    user_id: int
    query: str
    platform: str
    result: Optional[str] = None

class SearchHistoryResponse(BaseModel):
    id: int
    query: str
    platform: str
    created_at: datetime

    class Config:
        from_attributes = True
