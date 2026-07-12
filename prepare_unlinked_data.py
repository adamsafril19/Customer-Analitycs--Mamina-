"""
prepare_unlinked_data.py
========================
Melanjutkan prepare_import_data.py untuk data WhatsApp yang BELUM matched.

Output:
  dataset/ready_to_import/
    import_whatsapp_unlinked.csv     → 335 chat pure-unmatched + 50 review-pending
                                       Pakai untuk: topic model, sentiment, lead analytics
                                       TIDAK punya customer_id — import via ETL path, bukan /import/messages
    whatsapp_review_queue.csv        → 50 antrian manual review, format bersih untuk keputusan manusia
    whatsapp_review_decisions.csv    → Template kosong untuk mengisi approved_customer_id setelah review

Catatan sistem:
  - import_whatsapp_unlinked.csv TIDAK bisa lewat /import/messages (karena phone tidak ada di customer_master)
  - Import lewat admin ETL trigger: POST /api/admin/trigger-etl {"task": "process_whatsapp", "file_path": "..."}
  - Atau langsung insert ke tabel feedback_raw via script migrasi
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

GOLD_FILE = (
    BASE
    / "matched_random_chat_personal_only"
    / "whatsapp_customer_mapping_gold_silver.csv"
)
REVIEW_FILE = (
    BASE
    / "matched_random_chat_personal_only"
    / "whatsapp_customer_mapping_review_shortlist.csv"
)
CHAT_ROOT = BASE / "random chat"


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


def make_msg_id(phone, ts, text, prefix="ul"):
    raw = f"{prefix}|{phone}|{ts}|{text[:80]}"
    return f"wa_{prefix}_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def extract_messages_from_chat(chat_path, wa_phone, match_tier, chat_name):
    """Baca file CSV chat dan kembalikan list pesan dalam format standar."""
    try:
        chat = read_csv_robust(chat_path, low_memory=False)
    except Exception as e:
        return [], str(e)

    chat.columns = chat.columns.str.strip()
    if "Message Time" not in chat.columns:
        return [], "no Message Time column"

    rows = []
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

        rows.append(
            {
                "message_id": make_msg_id(wa_phone, ts_str, message_text),
                "phone_number": wa_phone,  # nomor WA asli (belum tentu ada di customer_master)
                "message_timestamp": ts_str,
                "sender_type": sender_type,
                "message_text": message_text,
                "match_tier": match_tier,  # unmatched / review_pending
                "chat_name": chat_name,  # nama chat WA (label/display saja)
            }
        )
    return rows, None


# ══════════════════════════════════════════════════════════════════
# Kumpulkan semua chat file yang ada
# ══════════════════════════════════════════════════════════════════
all_chat_files = {str(f.as_posix()) for f in CHAT_ROOT.rglob("*.csv")}

gold = read_csv_robust(GOLD_FILE)
review = read_csv_robust(REVIEW_FILE)

gold_files = set(gold["chat_file"].tolist())
review_files = set(review["chat_file"].dropna().tolist())

# Pure unmatched = semua file MINUS gold MINUS review
pure_unmatched_files = all_chat_files - gold_files - review_files

print("=" * 60)
print(f"Total chat files : {len(all_chat_files)}")
print(f"Gold (sudah done): {len(gold_files)}")
print(f"Manual review    : {len(review_files)}")
print(f"Pure unmatched   : {len(pure_unmatched_files)}")


# ══════════════════════════════════════════════════════════════════
# 1. UNLINKED MESSAGES (pure unmatched + review-pending)
# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("1. Menyiapkan import_whatsapp_unlinked.csv …")

# Buat lookup chat_file → (wa_phone, chat_name) dari review queue
review_lookup = {}
for _, r in review.iterrows():
    cf = str(r["chat_file"])
    review_lookup[cf] = {
        "wa_phone": normalize_phone(str(r["whatsapp_phone"])),
        "chat_name": str(r["chat_name"]),
    }

all_unlinked = []
skipped_files = []

# ── Pure unmatched ───────────────────────────────────────────────
print(f"  Memproses {len(pure_unmatched_files)} pure-unmatched …")
for chat_file in sorted(pure_unmatched_files):
    path = Path(chat_file)
    # Ambil wa_phone dari nama folder (biasanya nama folder = nama chat)
    folder_name = path.parent.name
    # Coba ekstrak nomor dari nama folder
    phone_match = re.sub(r"[^\d]", "", folder_name)
    wa_phone = normalize_phone(phone_match) if len(phone_match) >= 8 else folder_name

    msgs, err = extract_messages_from_chat(
        path, wa_phone, match_tier="unmatched", chat_name=folder_name
    )
    if err:
        skipped_files.append(f"{chat_file} ({err})")
        continue
    all_unlinked.extend(msgs)

# ── Review-pending (50 chat, belum dikonfirmasi) ─────────────────
print(f"  Memproses {len(review_files)} review-pending …")
for chat_file in sorted(review_files):
    path = Path(chat_file)
    info = review_lookup.get(chat_file, {})
    wa_phone = info.get("wa_phone", normalize_phone(path.parent.name))
    chat_name = info.get("chat_name", path.parent.name)

    msgs, err = extract_messages_from_chat(
        path, wa_phone, match_tier="review_pending", chat_name=chat_name
    )
    if err:
        skipped_files.append(f"{chat_file} ({err})")
        continue
    all_unlinked.extend(msgs)

ul_df = pd.DataFrame(all_unlinked)
before = len(ul_df)
ul_df = ul_df.drop_duplicates(subset=["message_id"])

out_path = OUT / "import_whatsapp_unlinked.csv"
ul_df.to_csv(out_path, index=False, encoding="utf-8")

tier_counts = ul_df["match_tier"].value_counts().to_dict()
sender_counts = ul_df["sender_type"].value_counts().to_dict()
unique_phones = ul_df["phone_number"].nunique()

print(f"  Raw messages   : {before:,}")
print(f"  Dedup messages : {len(ul_df):,} → {out_path}")
print(f"  Tier breakdown : {tier_counts}")
print(f"  Sender split   : {sender_counts}")
print(f"  Unique phones  : {unique_phones}")
if skipped_files:
    print(f"  ⚠️  Skipped {len(skipped_files)} files")
    for f in skipped_files[:5]:
        print(f"     - {f}")


# ══════════════════════════════════════════════════════════════════
# 2. REVIEW QUEUE — Antrian manual review yang bersih
# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("2. Menyiapkan whatsapp_review_queue.csv …")

# Satu baris per chat (bukan per kandidat)
queue = review[
    [
        "review_reason",
        "whatsapp_phone",
        "chat_name",
        "whatsapp_usernames",
        "message_count",
        "first_message",
        "last_message",
        "chat_file",
        "candidate_1",
        "candidate_2",
        "candidate_3",
        "candidate_4",
        "candidate_5",
        "approved_customer_id",
        "decision",
        "review_note",
    ]
].copy()

# Tambah kolom panduan
queue["action_required"] = queue.apply(
    lambda r: (
        "CONFIRM_DUPLICATE"
        if r["review_reason"] == "duplicate_customer_phone_exact_match"
        else "FILL_approved_customer_id_OR_reject"
    ),
    axis=1,
)

queue["status"] = queue["decision"].apply(
    lambda d: (
        "reviewed" if pd.notna(d) and str(d).strip() not in ["", "nan"] else "pending"
    )
)

# Urutkan: pending dulu, sudah diulas belakang
queue = queue.sort_values(["status", "review_reason"], ascending=[True, True])

out_path_q = OUT / "whatsapp_review_queue.csv"
queue.to_csv(out_path_q, index=False, encoding="utf-8")

pending_count = (queue["status"] == "pending").sum()
reviewed_count = (queue["status"] == "reviewed").sum()
dup_count = (queue["review_reason"] == "duplicate_customer_phone_exact_match").sum()

print(f"  Total antrian  : {len(queue)}")
print(f"  Pending review : {pending_count}")
print(f"  Sudah diulas   : {reviewed_count}")
print(f"  Duplikat phone : {dup_count} (perlu pilih 1 customer yang benar)")
print(f"  → {out_path_q}")

# ── Template keputusan ───────────────────────────────────────────
template = queue[queue["status"] == "pending"][
    [
        "whatsapp_phone",
        "chat_name",
        "message_count",
        "candidate_1",
        "candidate_2",
        "candidate_3",
        "approved_customer_id",
        "decision",
        "review_note",
    ]
].copy()
template["decision"] = ""  # isi: approve_<customer_id> / reject / skip
template["approved_customer_id"] = ""  # isi customer_id jika approve
template["review_note"] = ""

out_path_t = OUT / "whatsapp_review_decisions_template.csv"
template.to_csv(out_path_t, index=False, encoding="utf-8")
print(f"  Template keputusan: {out_path_t} ({len(template)} baris pending)")


# ══════════════════════════════════════════════════════════════════
# RINGKASAN AKHIR
# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("✅ SELESAI — Semua file:")
print(f"   📂 {OUT}/")
for f in sorted(OUT.iterdir()):
    size_kb = f.stat().st_size / 1024
    print(f"      {f.name:45s} ({size_kb:,.1f} KB)")

print()
print("Panduan penggunaan:")
print()
print("  import_customers.csv          → /api/import/customers       (2.779 customer)")
print(
    "  import_transactions.csv       → /api/import/transactions     (9.440 transaksi)"
)
print(
    "  import_whatsapp.csv           → /api/import/messages         (109 customer gold-tier)"
)
print(
    "  import_whatsapp_unlinked.csv  → ETL trigger / script migrasi (lead & unmatched messages)"
)
print(
    "  whatsapp_review_queue.csv     → Dibuka manual, isi kolom decision + approved_customer_id"
)
print("  whatsapp_review_decisions_template.csv → Template kosong untuk reviewer")
print()
print("  ⚠️  import_whatsapp_unlinked.csv TIDAK bisa via /import/messages")
print("      karena phone_number tidak ada di customer_master.")
print("      Gunakan: POST /api/admin/trigger-etl {task: process_whatsapp}")
print("      atau insert langsung ke tabel feedback_raw tanpa customer_id.")
print()
print("  Setelah review queue diisi dan di-approve:")
print("      → Jalankan script upgrade: promote_reviewed_matches.py (dibuat nanti)")
print("      → Chat yang approve bisa di-import ulang sebagai gold-reviewed tier")
