"""
prepare_import_data.py
======================
Menyiapkan 3 file CSV siap import ke sistem Mamina:

  1. import_customers.csv      → /api/import/customers
  2. import_transactions.csv   → /api/import/transactions
  3. import_whatsapp.csv       → /api/import/messages  (SEMUA chat personal)

Untuk WhatsApp, sistem sudah menangani pemisahan otomatis via LinkingService:
  - Phone match ke customer_master → feedback_linked (link_status="probable")
  - Phone tidak dikenal           → provisional customer + link_status="provisional"
  Jadi kita cukup satu file untuk semua chat personal — tidak perlu pisah.

Filter chat yang DIKELUARKAN:
  - Grup (nama mengandung "smart parents", "team", "daily", dll.)
  - Terapis/konselor/staf (mengandung: terapis, therapist, konselor, dll.)
  - Kontak internal Mamina (HC MAMINA, Mas Farid, Mb Varent, dll.)
  - Rekanan/non-customer bisnis

Sumber data:
  - dataset/customerMaster/customers (2).csv  (sep=;, latin-1)
  - dataset/transaksi/sales (1).csv           (sep=;, latin-1)
  - dataset/random chat/**/*.csv              (semua chat personal)

Output: dataset/ready_to_import/
"""

import hashlib
import re
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path("dataset")
OUT = BASE / "ready_to_import"
OUT.mkdir(exist_ok=True)

CUSTOMER_FILE = BASE / "customerMaster" / "customers (2).csv"
SALES_FILE = BASE / "transaksi" / "sales (1).csv"
CHAT_ROOT = BASE / "random chat"

STATUS_MAP = {
    "paid": "completed",
    "cancelled": "cancelled",
    "refunded": "refunded",
}

# ── Aturan eksklusi chat ─────────────────────────────────────────
# Kata kunci (case-insensitive) di nama folder/chat yang otomatis dikeluarkan
EXCLUDE_KEYWORDS = [
    "terapis",
    "therapist",
    "therapis",  # staf terapis
    "konselor",  # staf konselor
    "bidan iiq",
    "bidan fadhila",  # staf bidan spesifik
]

# Nama folder persis yang dikeluarkan (staf & kontak non-customer)
EXCLUDE_EXACT = {
    "HC MAMINA",
    "Mamina Daily",
    "Mamina Malang",
    "Mamina Smart Parents (Malang)",
    "Mamina Suhat",
    "Mamina Team Malang",
    "Mamina Tech",
    "Mas Farid Mamina",
    "Mb Varent Mamina",
    "Mbak Devi ATK",
    "Rekanan Dr.evoo",
    "CS Rekanan dr. evoo",
    "Reva Mamina",
    "Fyana - Glints ID",
    "Yoga Mamina Sawojajar",
    "Yoga Mamina Suhat",
    "Bidan Iiq Mamina",
    "Bidan Fadhila Terapis Mamina",
    "Bukti pengeluaran mamina soehat",
    "Konselor Hesti",
    "Konselor Menyusui Mamina",
    "Sofy Terapis Mamina",
    "Terapis Citra Mamina",
    "Terapis Dessy Mamina",
    "Terapis Indah Mamina",
    "Therapis Bidan Salma Mamina",
    "Therapist Bidan Gadis Filosofia Mamina",
}


def is_excluded(folder_name: str) -> bool:
    """True jika folder/chat harus dikeluarkan."""
    if folder_name in EXCLUDE_EXACT:
        return True
    name_lower = folder_name.lower()
    return any(kw in name_lower for kw in EXCLUDE_KEYWORDS)


# ── Helper ──────────────────────────────────────────────────────


def read_csv_robust(path, **kwargs):
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Tidak bisa membaca: {path}")


def normalize_phone(phone):
    if not phone or pd.isna(phone):
        return ""
    phone = re.sub(r"[^\d]", "", str(phone))
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    return phone


def make_message_id(phone, ts, text):
    raw = f"{phone}|{ts}|{text[:100]}"
    return "wa_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:28]


# ══════════════════════════════════════════════════════════════════
# 1. CUSTOMERS
# ══════════════════════════════════════════════════════════════════
print("=" * 60)
print("1. Menyiapkan data customers …")

cust_raw = read_csv_robust(CUSTOMER_FILE, sep=";", low_memory=False)
cust_raw.columns = cust_raw.columns.str.strip()

cust_out = pd.DataFrame()
cust_out["customer_id"] = cust_raw["id"].astype(str)
cust_out["customer_name"] = cust_raw["name"].fillna("").str.strip()
cust_out["phone_number"] = cust_raw["phone"].astype(str).apply(normalize_phone)
cust_out["join_date"] = pd.to_datetime(
    cust_raw["created_at"], errors="coerce"
).dt.strftime("%Y-%m-%d %H:%M:%S")

before = len(cust_out)
cust_out = cust_out[
    (cust_raw["is_active"].fillna(0).astype(int) == 1)
    & (cust_out["customer_name"].str.len() > 0)
    & (cust_out["phone_number"].str.len() >= 10)
    & cust_out["join_date"].notna()
].copy()
cust_out = cust_out.drop_duplicates(subset=["phone_number"], keep="first")
cust_out = cust_out.drop_duplicates(subset=["customer_id"], keep="first")

cust_out.to_csv(OUT / "import_customers.csv", index=False, encoding="utf-8")
valid_cust_ids = set(cust_out["customer_id"])

print(f"   Raw      : {before:,}")
print(f"   Exported : {len(cust_out):,} → import_customers.csv")


# ══════════════════════════════════════════════════════════════════
# 2. TRANSACTIONS
# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("2. Menyiapkan data transaksi …")

sales_raw = read_csv_robust(SALES_FILE, sep=";", low_memory=False)
sales_raw.columns = sales_raw.columns.str.strip()

tx_out = pd.DataFrame()
tx_out["transaction_id"] = sales_raw["id"].astype(str).apply(lambda x: f"sale_{x}")
tx_out["customer_id"] = sales_raw["customer_id"].astype(str)
tx_out["transaction_date"] = pd.to_datetime(
    sales_raw["date"].fillna(sales_raw["created_at"]), errors="coerce"
).dt.strftime("%Y-%m-%d %H:%M:%S")
tx_out["transaction_amount"] = (
    pd.to_numeric(sales_raw["total"], errors="coerce").fillna(0).clip(lower=0)
)
tx_out["service_type"] = sales_raw["sale_type"].fillna("Outlet").str.strip()
tx_out["transaction_status"] = sales_raw["status"].apply(
    lambda s: (
        STATUS_MAP.get(str(s).strip().lower(), "completed")
        if pd.notna(s)
        else "completed"
    )
)

before = len(tx_out)
tx_out = (
    tx_out[
        tx_out["customer_id"].isin(valid_cust_ids) & tx_out["transaction_date"].notna()
    ]
    .drop_duplicates(subset=["transaction_id"])
    .copy()
)

tx_out.to_csv(OUT / "import_transactions.csv", index=False, encoding="utf-8")

print(f"   Raw      : {before:,}")
print(
    f"   Skipped  : {before - len(tx_out):,} (customer tidak di master / tanggal kosong)"
)
print(f"   Exported : {len(tx_out):,} → import_transactions.csv")
print(f"   Tipe     : {tx_out['service_type'].value_counts().to_dict()}")
print(f"   Zero amt : {(tx_out['transaction_amount'] == 0).sum():,} transaksi")


# ══════════════════════════════════════════════════════════════════
# 3. WHATSAPP — SEMUA CHAT PERSONAL (gold + unmatched)
# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("3. Menyiapkan data WhatsApp (semua chat personal) …")
print("   Sistem akan otomatis memisahkan via LinkingService:")
print("   - Phone dikenal → feedback_linked (probable, confidence=1.0)")
print("   - Phone baru    → provisional customer (provisional, confidence=0.5)")
print()

all_messages = []
excluded_dirs = []
skipped_files = []
included_dirs = []

all_chat_dirs = sorted([d for d in CHAT_ROOT.iterdir() if d.is_dir()])

for chat_dir in all_chat_dirs:
    folder_name = chat_dir.name

    # ── Filter: keluarkan non-customer ──────────────────────────
    if is_excluded(folder_name):
        excluded_dirs.append(folder_name)
        continue

    # Cari file CSV di dalam folder
    csv_files = list(chat_dir.glob("*.csv"))
    if not csv_files:
        skipped_files.append(f"{folder_name} (no CSV)")
        continue

    chat_path = csv_files[0]

    try:
        chat = read_csv_robust(chat_path, low_memory=False)
    except Exception as e:
        skipped_files.append(f"{folder_name} ({e})")
        continue

    chat.columns = chat.columns.str.strip()
    if "Message Time" not in chat.columns:
        skipped_files.append(f"{folder_name} (no Message Time column)")
        continue

    # Ekstrak nomor WA dari kolom Phone Number (ambil non-"You" pertama)
    wa_phone = ""
    if "Phone Number" in chat.columns:
        phone_vals = chat[
            chat["Username"].astype(str).str.strip().str.lower() != "you"
        ]["Phone Number"].dropna()
        if not phone_vals.empty:
            wa_phone = normalize_phone(str(phone_vals.iloc[0]))

    # Fallback: ekstrak dari nama folder
    if not wa_phone or len(wa_phone) < 8:
        phone_match = re.sub(r"[^\d]", "", folder_name)
        if len(phone_match) >= 8:
            wa_phone = normalize_phone(phone_match)
        else:
            wa_phone = folder_name  # simpan nama sebagai identifier

    included_dirs.append(folder_name)

    for _, msg in chat.iterrows():
        username = str(msg.get("Username", "")).strip()
        ts_raw = str(msg.get("Message Time", "")).strip()

        is_admin = username.lower() == "you"
        sent_txt = str(msg.get("Sent Message", "")).strip()
        recv_txt = str(msg.get("Received Message", "")).strip()

        if is_admin:
            sender_type = "admin"
            message_text = sent_txt if sent_txt and sent_txt != "nan" else ""
        else:
            sender_type = "customer"
            message_text = recv_txt if recv_txt and recv_txt != "nan" else ""

        if not message_text:
            continue

        ts_parsed = pd.to_datetime(ts_raw, errors="coerce", format="%Y/%m/%d %H:%M:%S")
        if pd.isna(ts_parsed):
            ts_parsed = pd.to_datetime(ts_raw, errors="coerce")
        if pd.isna(ts_parsed):
            continue

        ts_str = ts_parsed.strftime("%Y-%m-%d %H:%M:%S")

        all_messages.append(
            {
                "message_id": make_message_id(wa_phone, ts_str, message_text),
                "phone_number": wa_phone,
                "message_timestamp": ts_str,
                "sender_type": sender_type,
                "message_text": message_text,
            }
        )

wa_out = pd.DataFrame(all_messages)
before_wa = len(wa_out)
wa_out = wa_out.drop_duplicates(subset=["message_id"])

wa_out.to_csv(OUT / "import_whatsapp.csv", index=False, encoding="utf-8")

print(f"   Chat dirs total     : {len(all_chat_dirs)}")
print(f"   Dikeluarkan (filter): {len(excluded_dirs)}")
print(f"   Dilewati (error)    : {len(skipped_files)}")
print(f"   Diproses            : {len(included_dirs)}")
print(f"   Raw messages        : {before_wa:,}")
print(f"   Setelah dedup       : {len(wa_out):,} → import_whatsapp.csv")
print(f"   Sender split        : {wa_out['sender_type'].value_counts().to_dict()}")

if excluded_dirs:
    print(f"\n   Dikeluarkan ({len(excluded_dirs)} chat):")
    for name in excluded_dirs:
        print(f"      ✗ {name}")

if skipped_files:
    print(f"\n   ⚠️  Error ({len(skipped_files)} file):")
    for f in skipped_files[:5]:
        print(f"      - {f}")


# ══════════════════════════════════════════════════════════════════
# RINGKASAN AKHIR
# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("✅ SELESAI — File siap import:")
print(f"   📂 {OUT}/")
for f in sorted(OUT.iterdir()):
    size_kb = f.stat().st_size / 1024
    print(f"      {f.name:40s} ({size_kb:,.1f} KB)")

print()
print("Urutan import ke sistem:")
print("  1. import_customers.csv    → /api/import/customers")
print("  2. import_transactions.csv → /api/import/transactions")
print("  3. import_whatsapp.csv     → /api/import/messages")
print()
print("Setelah import WhatsApp, sistem otomatis:")
print("  - Phone dikenal  → FeedbackLinked (probable,    confidence=1.0)")
print(
    "  - Phone baru     → Provisional customer + FeedbackLinked (provisional, confidence=0.5)"
)
