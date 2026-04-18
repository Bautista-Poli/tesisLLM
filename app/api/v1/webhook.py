import logging
from fastapi import APIRouter, HTTPException, Query, Request
from app.core.config import settings
from app.dialog.conversation_manager import ConversationManager
from app.nlu.nlu_service import nlu_service

logger = logging.getLogger(__name__)
router = APIRouter()
conversation_manager = ConversationManager()

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Token inválido.")

@router.post("")
async def receive_message(request: Request):
    payload = await request.json()
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok"}
        message = messages[0]
        phone = message.get("from")
        if message.get("type") != "text":
            return {"status": "ok", "detail": "Tipo no soportado."}
        user_text = message["text"]["body"]
        nlu_result = nlu_service.analyze(user_text)
        bot_reply = conversation_manager.process_turn(phone, user_text, nlu_result.entities)
        return {"status": "ok", "reply": bot_reply}
    except (IndexError, KeyError) as e:
        raise HTTPException(status_code=400, detail="Payload malformado.")

@router.get("/session/{phone}")
async def get_session_state(phone: str):
    state = conversation_manager.get_session_state(phone)
    if not state:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return state
