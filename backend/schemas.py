from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, Literal
from datetime import date

class Profile(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=25)
    is_student: bool = False
    university: str = Field(default='', max_length=150)
    research_field: str = Field(default='', max_length=150)
    krc: Optional[str] = Field(default=None, max_length=30)
    registration_date: Optional[date] = None

    @field_validator('krc')
    @classmethod
    def validate_krc(cls, value):
        import re
        if not value: return None
        value = value.strip().upper()
        if not re.fullmatch(r'KRC[A-Z0-9-]{1,27}', value): raise ValueError('رقم كورا غير صحيح')
        return value

class Register(Profile):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class Forgot(BaseModel):
    email: EmailStr

class Reset(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)

class Claim(BaseModel):
    token: str = Field(min_length=20, max_length=200)

class CourseInput(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=10000)
    category_id: str
    price: str = '0'
    free_for_students: bool = False
    published: bool = False

class LectureInput(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default='', max_length=3000)
    file_id: str
    order: int = Field(default=1, ge=1, le=999)

class Review(BaseModel):
    decision: Literal['approved', 'rejected']
    reason: str = Field(default='', max_length=1000)

class SettingsInput(BaseModel):
    currency: str = Field(default='', max_length=3)
    payment_instructions: str = Field(default='', max_length=3000)
    contact_email: str = Field(default='', max_length=200)
    contact_phone: str = Field(default='', max_length=50)
    address: str = Field(default='', max_length=500)
    about: str = Field(min_length=10, max_length=5000)
    services_text: str = Field(min_length=10, max_length=5000)
    hero_description: str = Field(min_length=10, max_length=500)

class UserEdit(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[Literal['active','blocked','inactive']] = None
    student_decision: Optional[Literal['approved','rejected']] = None
    role: Optional[Literal['visitor','employee']] = None
    krc: Optional[str] = Field(default=None, max_length=30)

class CategoryInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)

class ReceiptInput(BaseModel):
    file_id: str