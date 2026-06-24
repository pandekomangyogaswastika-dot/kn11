"""Sub-fase 1.13 — UOM Conversion Engine (Multi-UOM).

Mendukung konversi multi-unit untuk penjualan/pembelian kain:
- FIXED (global, dari koleksi `uoms.factor_to_base` + kanonik): meter=1, yard=0.9144,
  cm=0.01, inch=0.0254. (base_type = length)
- VARIABLE (per produk, dari `product.uom_conversions[]`): mis. 1 roll = 50 m
  ({from_unit:"roll", to_unit:"meter", factor:50}). Beda tiap produk.

Resolusi faktor: unit sama → 1.0 → FIXED langsung → VARIABLE langsung → 1-hop via base unit.
Jika tidak ada faktor → HTTPException 400 (TIDAK diam-diam pakai 1).

Semua qty inventori/reservasi/movement SELALU disimpan dalam BASE UNIT produk (default meter).
Fungsi inti bersifat pure (tanpa I/O) supaya mudah diuji; `load_fixed_factors()` async hanya
membaca peta faktor FIXED dari DB sekali per request.
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException
from db import db

# Faktor length kanonik (meter per 1 unit) — fallback bila uoms belum punya factor_to_base.
CANONICAL_LENGTH_FACTORS: Dict[str, float] = {
    "meter": 1.0, "m": 1.0, "mtr": 1.0,
    "yard": 0.9144, "yd": 0.9144, "yrd": 0.9144,
    "cm": 0.01, "centimeter": 0.01,
    "inch": 0.0254, "in": 0.0254,
}


def _norm(u: Optional[str]) -> str:
    return (u or "").strip().lower()


async def load_fixed_factors() -> Dict[str, float]:
    """Peta {unit(lowercase) -> meter per 1 unit} dari uoms (base_type=length) + kanonik."""
    factors: Dict[str, float] = dict(CANONICAL_LENGTH_FACTORS)
    uoms = await db.uoms.find({"base_type": "length"}, {"_id": 0}).to_list(200)
    for u in uoms:
        f = u.get("factor_to_base")
        if f in (None, 0):
            continue
        for key in (u.get("name"), u.get("code")):
            if key:
                factors[_norm(key)] = float(f)
    return factors


def _fixed(from_u: str, to_u: str, fixed: Dict[str, float]) -> Optional[float]:
    a, b = fixed.get(from_u), fixed.get(to_u)
    if a is not None and b not in (None, 0):
        return a / b
    return None


def _variable(product: Dict[str, Any], from_u: str, to_u: str) -> Optional[float]:
    for c in product.get("uom_conversions", []) or []:
        cf, ct, fac = _norm(c.get("from_unit")), _norm(c.get("to_unit")), c.get("factor")
        if not fac:
            continue
        if cf == from_u and ct == to_u:
            return float(fac)
        if cf == to_u and ct == from_u and float(fac) != 0:
            return 1.0 / float(fac)
    return None


def product_kg_per_meter(product: Dict[str, Any]) -> float:
    """Faktor catch-weight: kg per 1 BASE unit (meter).

    Prioritas: field eksplisit `kg_per_meter` (>0) → else turunan `gramasi(gsm) × lebar(m) / 1000`.
    Mengembalikan 0.0 bila tidak tersedia (produk tanpa data berat).
    """
    try:
        explicit = float(product.get("kg_per_meter") or 0)
    except (TypeError, ValueError):
        explicit = 0.0
    if explicit > 0:
        return explicit
    try:
        gsm = float(product.get("gramasi") or 0)
        width = float(product.get("lebar") or 0)
    except (TypeError, ValueError):
        return 0.0
    v = gsm * width / 1000.0
    return v if v > 0 else 0.0


def _catch_weight(product: Dict[str, Any], from_u: str, to_u: str) -> Optional[float]:
    """Sub-fase 1.13 / Fase 8 — konversi kg ↔ base(meter) via catch-weight.
    kg per 1 meter = `kg_per_meter` eksplisit, atau gramasi(gsm) × lebar(meter) / 1000.
    """
    base = _norm(product.get("base_unit", "meter"))
    kg_per_base = product_kg_per_meter(product)
    if kg_per_base <= 0:
        return None
    if from_u == "kg" and to_u == base:
        return 1.0 / kg_per_base          # meter per 1 kg
    if from_u == base and to_u == "kg":
        return kg_per_base                # kg per 1 meter
    return None


def _resolve(product: Dict[str, Any], from_u: str, to_u: str, fixed: Dict[str, float]) -> Optional[float]:
    if from_u == to_u:
        return 1.0
    direct = _fixed(from_u, to_u, fixed)
    if direct is not None:
        return direct
    var = _variable(product, from_u, to_u)
    if var is not None:
        return var
    cw = _catch_weight(product, from_u, to_u)
    if cw is not None:
        return cw
    # 1-hop lewat base unit produk (mis. roll -> meter -> yard, atau kg -> meter -> yard)
    base = _norm(product.get("base_unit", "meter"))
    if from_u != base and to_u != base:
        f1 = _fixed(from_u, base, fixed)
        if f1 is None:
            f1 = _variable(product, from_u, base)
        if f1 is None:
            f1 = _catch_weight(product, from_u, base)
        f2 = _fixed(base, to_u, fixed)
        if f2 is None:
            f2 = _variable(product, base, to_u)
        if f2 is None:
            f2 = _catch_weight(product, base, to_u)
        if f1 is not None and f2 is not None:
            return f1 * f2
    return None


def convert(product: Dict[str, Any], qty: float, from_unit: str, to_unit: str,
            fixed_factors: Dict[str, float], precision: int = 2) -> float:
    """Konversi `qty` dari `from_unit` ke `to_unit`. Raise 400 bila faktor tak tersedia."""
    f = _resolve(product, _norm(from_unit), _norm(to_unit), fixed_factors)
    if f is None:
        raise HTTPException(status_code=400, detail=(
            f"Konversi unit '{from_unit}' → '{to_unit}' tidak tersedia untuk produk "
            f"{product.get('sku') or product.get('id')}. Tambahkan faktor di uom_conversions."
        ))
    return round(float(qty) * f, precision)


def to_base(product: Dict[str, Any], qty: float, unit: str,
            fixed_factors: Dict[str, float], precision: int = 2) -> float:
    """Konversi qty (dalam `unit`) ke BASE UNIT produk."""
    return convert(product, qty, unit, product.get("base_unit", "meter"), fixed_factors, precision)


def from_base(product: Dict[str, Any], base_qty: float, unit: str,
              fixed_factors: Dict[str, float], precision: int = 2) -> float:
    """Konversi qty (dalam base unit) ke `unit` tampilan."""
    return convert(product, base_qty, product.get("base_unit", "meter"), unit, fixed_factors, precision)


def resolve_roll_measures(product: Dict[str, Any], task_unit: str,
                          length_in: float, weight_in: float,
                          fixed_factors: Dict[str, float]) -> Dict[str, float]:
    """Fase 8 (Catch-weight) — resolusi ukuran SATU roll fisik saat Goods Receipt.

    Mengembalikan dict {length_base, weight_kg, task_qty}:
      - length_base : panjang roll dlm BASE unit produk (meter) → qty stok inventori.
      - weight_kg   : berat roll (kg) → catch-weight aktual yg disimpan di roll.
      - task_qty    : kontribusi roll thd qty diterima dlm SATUAN TASK (utk validasi Σ).

    Aturan (pilihan owner: faktor default per-produk + override AKTUAL saat GR):
      • task_unit == 'kg' (PO per berat):
          - weight = weight_in; length = length_in (meter aktual) bila diisi,
            else turunan weight/kgpm (butuh faktor). task_qty = weight.
      • task_unit panjang (meter/yard/…):
          - length_base = to_base(length_in); weight = weight_in (aktual) bila diisi,
            else estimasi length_base × kgpm (0 bila tak ada faktor). task_qty = length_in.
    """
    base = _norm(product.get("base_unit", "meter"))
    tu = _norm(task_unit) or base
    kgpm = product_kg_per_meter(product)
    L = float(length_in or 0)
    W = float(weight_in or 0)
    sku = product.get("sku") or product.get("id") or "?"

    if tu == "kg":
        if W <= 0 and L <= 0:
            raise HTTPException(status_code=400, detail=f"Roll {sku}: isi berat (kg) atau panjang (m).")
        weight = round(W if W > 0 else L * kgpm, 3)
        if L > 0:
            length_base = round(L, 2)
        else:
            if kgpm <= 0:
                raise HTTPException(status_code=400, detail=(
                    f"Roll {sku}: tak bisa menurunkan panjang dari berat — "
                    f"isi gramasi & lebar (atau kg_per_meter) produk, atau masukkan panjang aktual."))
            length_base = round(W / kgpm, 2)
        task_qty = weight
    else:
        if L <= 0:
            raise HTTPException(status_code=400, detail=f"Roll {sku}: panjang ({task_unit}) harus > 0.")
        length_base = to_base(product, L, task_unit, fixed_factors)
        weight = round(W if W > 0 else length_base * kgpm, 3)
        task_qty = round(L, 2)

    return {"length_base": length_base, "weight_kg": weight, "task_qty": round(task_qty, 3)}
