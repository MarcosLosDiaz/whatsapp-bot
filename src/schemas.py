from pydantic import BaseModel, Field
from typing import List, Optional

class QueueMessagePayload(BaseModel):
    user_id: str = Field(..., description="The phone number of the user")
    
class StickerQueuePayload(QueueMessagePayload):
    sticker_id: str = Field(..., description="The ID of the sticker")
    media_id: str = Field(..., description="The Meta Graph media ID")

class QueryQueuePayload(QueueMessagePayload):
    query: str = Field(..., description="The search query for the sticker")

# Webhook Payloads
class MetaText(BaseModel):
    body: str

class MetaSticker(BaseModel):
    id: str

class MetaMessage(BaseModel):
    type: str
    from_: str = Field(alias="from")
    text: Optional[MetaText] = None
    sticker: Optional[MetaSticker] = None

class MetaValue(BaseModel):
    messages: Optional[List[MetaMessage]] = None

class MetaChange(BaseModel):
    value: MetaValue

class MetaEntry(BaseModel):
    changes: List[MetaChange]

class MetaWebhookPayload(BaseModel):
    object: str
    entry: List[MetaEntry]
