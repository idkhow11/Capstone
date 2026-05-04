from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
import models
import schemas
from services.agent import get_agent
from auth_utils import get_current_user

router = APIRouter(
    tags=["Search and History"]
)

# ─── Search (public — guests can search, auth optional) ────
@router.post("/search")
def perform_search(request: schemas.SearchRequest, db: Session = Depends(get_db)):
    agent = get_agent()
    
    try:
        # Call the DeepAgent
        result = agent.invoke({"messages": [{"role": "user", "content": request.query}]})
        final_message = result["messages"][-1].content
        
        # If user is logged in, save the conversation to Supabase
        conversation_id = request.conversation_id
        if request.user_id:
            if not conversation_id:
                # Create a new conversation
                conversation = models.Conversation(
                    user_id=request.user_id,
                    title=request.query[:100],  # First query becomes the title
                    platform=request.platform
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
                conversation_id = conversation.id
            
            # Save the user message
            user_msg = models.ChatMessage(
                conversation_id=conversation_id,
                role="user",
                content=request.query
            )
            db.add(user_msg)
            
            # Save the AI response
            ai_msg = models.ChatMessage(
                conversation_id=conversation_id,
                role="ai",
                content=final_message
            )
            db.add(ai_msg)
            db.commit()
        
        return {
            "products": [],
            "recommendation": final_message,
            "conversation_id": conversation_id
        }
    except Exception as e:
        print(f"Agent Error: {e}")
        raise HTTPException(status_code=500, detail="Error generating search results.")

# ─── Conversations (JWT-protected) ──────────────────────────
@router.get("/conversations", response_model=list[schemas.ConversationResponse])
def get_conversations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for the authenticated user."""
    conversations = (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user["id"])
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )
    return conversations

@router.get("/conversations/{conversation_id}", response_model=schemas.ConversationDetailResponse)
def get_conversation_detail(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single conversation with all its messages."""
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user["id"]
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation and all its messages (only if owned by current user)."""
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user["id"]
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)  # cascade deletes messages too
    db.commit()
    return {"message": "Deleted successfully"}

# ─── Legacy History Endpoints (JWT-protected) ───────────────
@router.get("/history", response_model=list[schemas.SearchHistoryResponse])
def get_history(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get search history for the authenticated user."""
    history = (
        db.query(models.SearchHistory)
        .filter(models.SearchHistory.user_id == current_user["id"])
        .order_by(models.SearchHistory.created_at.desc())
        .all()
    )
    return history

@router.post("/history", response_model=schemas.SearchHistoryResponse)
def save_history(
    history_item: schemas.SearchHistoryCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a search history item for the authenticated user."""
    new_history = models.SearchHistory(
        user_id=current_user["id"],  # Use JWT user, not request body
        query=history_item.query,
        platform=history_item.platform,
        result_summary=history_item.result
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)
    return new_history

@router.delete("/history/{item_id}")
def delete_history(
    item_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a history item (only if owned by current user)."""
    item = (
        db.query(models.SearchHistory)
        .filter(
            models.SearchHistory.id == item_id,
            models.SearchHistory.user_id == current_user["id"]
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="History not found")
    
    db.delete(item)
    db.commit()
    return {"message": "Deleted successfully"}
