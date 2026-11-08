from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import HTTPException

class ResearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=5,max_length=180)
    description: str = Field(min_length=20,max_length=10000)
    research_field: str = Field(min_length=2,max_length=120)
    service_type: Literal['data_collection','postgraduate','graduation','analysis','other'] = 'other'
    privacy_consent: Literal[True]

class QuoteInput(BaseModel):
    amount: str
    scope: str = Field(min_length=10,max_length=4000)
    delivery_days: int = Field(ge=1,le=730)

class QuoteDecision(BaseModel):
    quote_id: str
    decision: Literal['accepted','rejected']
    reason: str = Field(default='',max_length=1000)

class ResearchAction(BaseModel):
    action: Literal['claim','return','start','deliver','revision','complete','cancel','approve_cancel','reject_cancel','reopen_assignment']
    note: str = Field(default='',max_length=2000)

class ResearchReceipt(BaseModel):
    file_id: str
    amount: str

class ResearchReceiptReview(BaseModel):
    receipt_id: str
    decision: Literal['approved','rejected']
    reason: str = Field(default='',max_length=1000)

def minor_amount(value, zero=False):
    try:
        amount=Decimal(value)
        if not amount.is_finite() or amount < 0 or (not zero and amount == 0) or amount > 10000000 or amount.as_tuple().exponent < -2:
            raise InvalidOperation()
        return int(amount*100)
    except (InvalidOperation,ValueError,TypeError):
        raise HTTPException(422,'أدخل مبلغًا صحيحًا أكبر من صفر وبمنزلتين عشريتين على الأكثر')

def discounted_amount(amount, percent):
    return int((Decimal(amount)*Decimal(100-percent)/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))