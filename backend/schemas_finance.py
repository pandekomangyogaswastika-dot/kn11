"""Finance schemas (EPIC7) — Kas & Bank (7B), dipisah agar schemas.py < 800 baris.
Di-reexport oleh schemas.py."""
from typing import List, Optional
from pydantic import BaseModel


# ─── EPIC7-B: Kas & Bank (multi-akun + rekonsiliasi) ─────────────────────────

class BankAccountCreate(BaseModel):
    name: str                          # nama tampilan, mis. "BCA Operasional"
    account_type: str = "bank"         # bank | cash
    bank_name: str = ""                # nama bank (kosong utk cash)
    account_number: str = ""           # no rekening
    entity_id: str = ""                # pemilik akun; kosong = DEFAULT
    opening_balance: float = 0.0       # saldo awal
    currency: str = "IDR"
    note: str = ""


class BankAccountUpdate(BaseModel):
    name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    opening_balance: Optional[float] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class ReconcilePayload(BaseModel):
    reconciled: bool = True


# ─── EPIC7-C: Chart of Accounts + General Ledger ─────────────────────────────

class GLAccountCreate(BaseModel):
    code: str                          # kode akun, mis. "6-5000"
    name: str
    type: str                          # asset | liability | equity | income | expense
    parent_code: str = ""
    is_postable: Optional[bool] = True
    currency: str = "IDR"
    description: str = ""


class GLAccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_code: Optional[str] = None
    is_active: Optional[bool] = None
    is_postable: Optional[bool] = None


class JournalLineIn(BaseModel):
    account_code: str
    debit: float = 0.0
    credit: float = 0.0
    description: str = ""


class JournalEntryCreate(BaseModel):
    date: str = ""
    description: str = ""
    entity_id: str = ""
    lines: List[JournalLineIn] = []
