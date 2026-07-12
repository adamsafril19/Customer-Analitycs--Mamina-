"""
CSV Import Service — Data Ingestion Pipeline

Handles parsing, validation, and import of 3 CSV dataset types:
1. customer_master → customers table
2. transactions → transactions table
3. whatsapp_messages → feedback_raw + feedback_linked tables

Design decisions:
- SHA-256 phone hashing with normalization (strip +, spaces, non-digits → 628xxx)
- Skip duplicates (not upsert) — safer for research data
- Duplicate rows reported for audit
- DB transaction rollback on fatal error
- pandas for CSV parsing (handles quoted commas, multiline, BOM)
"""

import hashlib
import io
import logging
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import pandas as pd
import sqlalchemy as sa

from app import db
from app.models.customer import Customer
from app.models.feedback import FeedbackRaw
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

# =========================================================================
# CSV Column Definitions (CSV name → required/optional)
# =========================================================================

CUSTOMER_REQUIRED_COLS = ["customer_id", "customer_name", "phone_number", "join_date"]

TRANSACTION_REQUIRED_COLS = [
    "transaction_id",
    "customer_id",
    "transaction_date",
    "transaction_amount",
    "service_type",
    "transaction_status",
]
TRANSACTION_VALID_STATUSES = {"completed", "cancelled", "refunded"}

MESSAGE_REQUIRED_COLS = [
    "message_id",
    "phone_number",
    "message_timestamp",
    "sender_type",
    "message_text",
]
MESSAGE_VALID_SENDER_TYPES = {"customer", "admin"}
SENDER_TYPE_TO_DIRECTION = {"customer": "inbound", "admin": "outbound"}

PREVIEW_LIMIT = 20
MAX_ERRORS_REPORTED = 200


class CSVImportService:
    """CSV Import Service for behavioral risk scoring data pipeline."""

    @staticmethod
    def _cell_text(value: Any) -> str:
        """Normalize a CSV cell to text without turning missing values into 'nan'."""
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    # =====================================================================
    # Phone Hashing
    # =====================================================================

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone number to consistent format.
        Steps: strip whitespace → remove +, -, (, ) → digits only → convert 0 prefix to 62.
        """
        if not phone:
            return ""
        phone = str(phone).strip()
        phone = re.sub(r"[^\d]", "", phone)  # digits only
        if phone.startswith("0"):
            phone = "62" + phone[1:]
        return phone

    @staticmethod
    def _hash_phone(phone: str) -> str:
        """SHA-256 hash of normalized phone number."""
        normalized = CSVImportService._normalize_phone(phone)
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # =====================================================================
    # CSV Parsing
    # =====================================================================

    @staticmethod
    def _parse_csv(file_storage) -> pd.DataFrame:
        """
        Parse uploaded CSV file into DataFrame.
        Handles UTF-8 BOM, quoted commas, multiline text.
        """
        try:
            content = file_storage.read()
            # Try UTF-8 with BOM first, fallback to latin-1
            for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
                try:
                    df = pd.read_csv(
                        io.BytesIO(content),
                        encoding=encoding,
                        dtype=str,
                        keep_default_na=False,
                        na_values=[""],
                    )
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV with any supported encoding")

            # Normalize column names: strip whitespace, lowercase
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            return df
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {str(e)}")

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize uploaded table columns to the import schema convention."""
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df

    @staticmethod
    def _parse_tabular_file(file_storage) -> pd.DataFrame:
        """Parse customer/transaction upload from CSV or Excel."""
        filename = (file_storage.filename or "").lower()
        if filename.endswith((".xlsx", ".xls")):
            try:
                content = file_storage.read()
                df = pd.read_excel(
                    io.BytesIO(content),
                    dtype=str,
                    keep_default_na=False,
                )
                return CSVImportService._normalize_columns(df)
            except ImportError as e:
                raise ValueError(
                    "Failed to parse Excel: dependency openpyxl/xlrd belum tersedia"
                ) from e
            except Exception as e:
                raise ValueError(f"Failed to parse Excel: {str(e)}")
        return CSVImportService._parse_csv(file_storage)

    @staticmethod
    def _decode_uploaded_text(file_storage) -> str:
        """Decode uploaded text with common WhatsApp export encodings."""
        content = file_storage.read()
        for encoding in ["utf-8-sig", "utf-8", "utf-16", "latin-1"]:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode TXT with any supported encoding")

    @staticmethod
    def _parse_whatsapp_txt(
        file_storage,
        phone_number: Optional[str] = None,
        customer_sender_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Parse a single-chat WhatsApp TXT export into the same schema as message CSV.

        WhatsApp TXT exports usually contain sender display names, not phone
        numbers, so callers must provide the customer phone number separately.
        """
        phone_number = str(phone_number or "").strip()
        if not phone_number:
            raise ValueError("phone_number is required for WhatsApp TXT import")

        text = CSVImportService._decode_uploaded_text(file_storage)
        message_re = re.compile(
            r"^\[?(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s+"
            r"(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?(?:\s?[APMapm]{2})?)\]?"
            r"\s+(?:-\s+)?(?P<body>.*)$"
        )
        rows = []
        current = None

        for raw_line in text.splitlines():
            line = raw_line.strip("\ufeff")
            match = message_re.match(line)
            if match:
                if current:
                    rows.append(current)

                body = match.group("body")
                if ": " not in body:
                    current = None
                    continue

                sender, message_text = body.split(": ", 1)
                sender = sender.strip()
                message_text = message_text.strip()
                timestamp = (
                    f"{match.group('date')} {match.group('time').replace('.', ':')}"
                )
                current = {
                    "sender": sender,
                    "message_timestamp": timestamp,
                    "message_text": message_text,
                }
            elif current and line:
                current["message_text"] = f"{current['message_text']}\n{line}"

        if current:
            rows.append(current)

        if not rows:
            raise ValueError("No WhatsApp messages found in TXT export")

        customer_sender_name = str(customer_sender_name or "").strip()
        if customer_sender_name:
            customer_names = {customer_sender_name.casefold()}
        else:
            customer_names = {rows[0]["sender"].casefold()}

        normalized_phone = CSVImportService._normalize_phone(phone_number)
        records = []
        for idx, row in enumerate(rows, start=1):
            sender_type = (
                "customer" if row["sender"].casefold() in customer_names else "admin"
            )
            timestamp = CSVImportService._parse_datetime(row["message_timestamp"])
            timestamp_key = (
                timestamp.strftime("%Y%m%d%H%M%S") if timestamp else str(idx)
            )
            message_id = hashlib.sha256(
                f"{normalized_phone}|{timestamp_key}|{row['sender']}|{row['message_text']}".encode(
                    "utf-8"
                )
            ).hexdigest()[:32]
            records.append(
                {
                    "message_id": f"wa_txt_{message_id}",
                    "phone_number": phone_number,
                    "message_timestamp": row["message_timestamp"],
                    "sender_type": sender_type,
                    "message_text": row["message_text"],
                }
            )

        return pd.DataFrame.from_records(records, columns=MESSAGE_REQUIRED_COLS)

    @staticmethod
    def _parse_message_file(
        file_storage,
        phone_number: Optional[str] = None,
        customer_sender_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """Parse WhatsApp messages from CSV or TXT upload."""
        filename = (file_storage.filename or "").lower()
        if filename.endswith(".txt"):
            return CSVImportService._parse_whatsapp_txt(
                file_storage,
                phone_number=phone_number,
                customer_sender_name=customer_sender_name,
            )
        return CSVImportService._parse_csv(file_storage)

    # =====================================================================
    # Datetime Parsing
    # =====================================================================

    @staticmethod
    def _parse_datetime(value: str) -> Optional[datetime]:
        """Parse datetime string with multiple format support."""
        if not value or pd.isna(value):
            return None
        value = str(value).strip()
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%y %H:%M",
            "%d/%m/%y %I:%M:%S %p",
            "%d/%m/%y %I:%M %p",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%d-%m-%y %H:%M:%S",
            "%d-%m-%y %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%y %I:%M:%S %p",
            "%m/%d/%y %I:%M %p",
            "%m/%d/%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        # Last resort: pandas parser
        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return None

    # =====================================================================
    # Schema Validation
    # =====================================================================

    @staticmethod
    def _validate_schema(df: pd.DataFrame, required_cols: List[str]) -> List[Dict]:
        """Check that all required columns exist."""
        errors = []
        df_cols = set(df.columns)
        for col in required_cols:
            if col not in df_cols:
                errors.append(
                    {
                        "row": 0,
                        "column": col,
                        "message": f"Required column '{col}' not found in CSV",
                    }
                )
        return errors

    # =====================================================================
    # Summary Statistics
    # =====================================================================

    @staticmethod
    def _compute_summary(
        df: pd.DataFrame, id_col: str, ts_col: Optional[str] = None
    ) -> Dict:
        """Compute summary stats for preview."""
        missing = {
            col: int(df[col].isna().sum())
            for col in df.columns
            if df[col].isna().sum() > 0
        }
        duplicates = int(df[id_col].duplicated().sum()) if id_col in df.columns else 0

        invalid_ts = 0
        if ts_col and ts_col in df.columns:
            for val in df[ts_col].dropna():
                if CSVImportService._parse_datetime(val) is None:
                    invalid_ts += 1

        return {
            "missing_values": missing,
            "duplicates": duplicates,
            "invalid_timestamps": invalid_ts,
        }

    # =====================================================================
    # CUSTOMER Preview & Import
    # =====================================================================

    def preview_customers(self, file_storage) -> Dict[str, Any]:
        """Preview + validate customer CSV before import."""
        df = self._parse_tabular_file(file_storage)
        schema_errors = self._validate_schema(df, CUSTOMER_REQUIRED_COLS)
        if schema_errors:
            return {
                "success": False,
                "validation": {
                    "valid_rows": 0,
                    "invalid_rows": len(df),
                    "errors": schema_errors,
                },
            }

        errors = []
        seen_ids = set()
        seen_phones = set()

        for row_num, (_, row) in enumerate(df.iterrows(), start=2):
            cid = str(row.get("customer_id", "")).strip()
            if not cid:
                errors.append(
                    {
                        "row": row_num,
                        "column": "customer_id",
                        "message": "customer_id is empty",
                    }
                )
            elif cid in seen_ids:
                errors.append(
                    {
                        "row": row_num,
                        "column": "customer_id",
                        "message": f"Duplicate customer_id: {cid}",
                    }
                )
            else:
                seen_ids.add(cid)

            phone = str(row.get("phone_number", "")).strip()
            if phone:
                norm = self._normalize_phone(phone)
                if norm in seen_phones:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "phone_number",
                            "message": "Duplicate phone_number",
                        }
                    )
                else:
                    seen_phones.add(norm)

            jd = str(row.get("join_date", "")).strip()
            if jd and self._parse_datetime(jd) is None:
                errors.append(
                    {
                        "row": row_num,
                        "column": "join_date",
                        "message": f"Invalid date format: {jd}",
                    }
                )

            if len(errors) >= MAX_ERRORS_REPORTED:
                break

        summary = self._compute_summary(df, "customer_id", "join_date")
        valid_rows = len(df) - len(set(e["row"] for e in errors))

        return {
            "success": len(errors) == 0,
            "preview": {
                "columns": list(df.columns),
                "rows": df.head(PREVIEW_LIMIT).fillna("").to_dict(orient="records"),
                "total_rows": len(df),
                "summary": summary,
            },
            "validation": {
                "valid_rows": max(0, valid_rows),
                "invalid_rows": len(set(e["row"] for e in errors)),
                "errors": errors[:MAX_ERRORS_REPORTED],
            },
        }

    def import_customers(self, file_storage) -> Dict[str, Any]:
        """Import customer CSV into database."""
        df = self._parse_tabular_file(file_storage)
        schema_errors = self._validate_schema(df, CUSTOMER_REQUIRED_COLS)
        if schema_errors:
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": schema_errors,
            }

        imported = 0
        skipped = 0
        duplicates_ignored = 0
        errors = []

        # Pre-fetch existing IDs for skip-duplicate check
        existing_eids = set()
        for row in (
            db.session.query(Customer.external_id)
            .filter(Customer.external_id.isnot(None))
            .all()
        ):
            existing_eids.add(row[0])

        existing_phones = set()
        for row in (
            db.session.query(Customer.phone_hash)
            .filter(Customer.phone_hash.isnot(None))
            .all()
        ):
            existing_phones.add(row[0])

        try:
            for row_num, (_, row) in enumerate(df.iterrows(), start=2):
                cid = str(row.get("customer_id", "")).strip()
                name = str(row.get("customer_name", "")).strip()
                phone = str(row.get("phone_number", "")).strip()
                join_date_str = str(row.get("join_date", "")).strip()

                if not cid:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "customer_id",
                            "message": "Empty customer_id",
                        }
                    )
                    skipped += 1
                    continue

                # Skip duplicate by external_id
                if cid in existing_eids:
                    duplicates_ignored += 1
                    continue

                phone_hash = self._hash_phone(phone) if phone else None
                if phone_hash and phone_hash in existing_phones:
                    duplicates_ignored += 1
                    continue

                join_date = self._parse_datetime(join_date_str)
                if not join_date:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "join_date",
                            "message": f"Invalid date: {join_date_str}",
                        }
                    )
                    skipped += 1
                    continue

                customer = Customer(
                    customer_id=uuid.uuid4(),
                    external_id=cid,
                    name=name or f"Customer {cid}",
                    phone_hash=phone_hash,
                    consent_given=True,
                    is_active=True,
                    is_provisional=False,
                    created_at=join_date,
                )
                db.session.add(customer)
                existing_eids.add(cid)
                if phone_hash:
                    existing_phones.add(phone_hash)
                imported += 1

            db.session.commit()
            logger.info(
                f"Imported {imported} customers, skipped {skipped}, duplicates {duplicates_ignored}"
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Customer import failed: {e}")
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": [{"row": 0, "column": "", "message": str(e)}],
            }

        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "duplicates_ignored": duplicates_ignored,
            "errors": errors[:MAX_ERRORS_REPORTED],
            "import_timestamp": datetime.utcnow().isoformat(),
        }

    # =====================================================================
    # TRANSACTION Preview & Import
    # =====================================================================

    def preview_transactions(self, file_storage) -> Dict[str, Any]:
        """Preview + validate transaction CSV."""
        df = self._parse_tabular_file(file_storage)
        schema_errors = self._validate_schema(df, TRANSACTION_REQUIRED_COLS)
        if schema_errors:
            return {
                "success": False,
                "validation": {
                    "valid_rows": 0,
                    "invalid_rows": len(df),
                    "errors": schema_errors,
                },
            }

        # Load valid customer external_ids for FK check
        valid_cids = set()
        for row in (
            db.session.query(Customer.external_id)
            .filter(Customer.external_id.isnot(None))
            .all()
        ):
            valid_cids.add(row[0])

        errors = []
        seen_ids = set()
        invalid_fk = 0

        for row_num, (_, row) in enumerate(df.iterrows(), start=2):
            tid = str(row.get("transaction_id", "")).strip()
            cid = str(row.get("customer_id", "")).strip()

            if not tid:
                errors.append(
                    {
                        "row": row_num,
                        "column": "transaction_id",
                        "message": "Empty transaction_id",
                    }
                )
            elif tid in seen_ids:
                errors.append(
                    {
                        "row": row_num,
                        "column": "transaction_id",
                        "message": "Duplicate transaction_id",
                    }
                )
            else:
                seen_ids.add(tid)

            if cid and cid not in valid_cids:
                errors.append(
                    {
                        "row": row_num,
                        "column": "customer_id",
                        "message": f"Customer ID not found: {cid}",
                    }
                )
                invalid_fk += 1

            amt = str(row.get("transaction_amount", "")).strip()
            try:
                amt_val = float(amt) if amt else 0
                if amt_val < 0:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "transaction_amount",
                            "message": "Amount must be >= 0",
                        }
                    )
            except (ValueError, TypeError):
                errors.append(
                    {
                        "row": row_num,
                        "column": "transaction_amount",
                        "message": f"Invalid amount: {amt}",
                    }
                )

            status = str(row.get("transaction_status", "")).strip().lower()
            if status and status not in TRANSACTION_VALID_STATUSES:
                errors.append(
                    {
                        "row": row_num,
                        "column": "transaction_status",
                        "message": f"Invalid status: {status}",
                    }
                )

            td = str(row.get("transaction_date", "")).strip()
            if td and self._parse_datetime(td) is None:
                errors.append(
                    {
                        "row": row_num,
                        "column": "transaction_date",
                        "message": f"Invalid date: {td}",
                    }
                )

            if len(errors) >= MAX_ERRORS_REPORTED:
                break

        summary = self._compute_summary(df, "transaction_id", "transaction_date")
        summary["invalid_fk"] = invalid_fk
        valid_rows = len(df) - len(set(e["row"] for e in errors))

        return {
            "success": len(errors) == 0,
            "preview": {
                "columns": list(df.columns),
                "rows": df.head(PREVIEW_LIMIT).fillna("").to_dict(orient="records"),
                "total_rows": len(df),
                "summary": summary,
            },
            "validation": {
                "valid_rows": max(0, valid_rows),
                "invalid_rows": len(set(e["row"] for e in errors)),
                "errors": errors[:MAX_ERRORS_REPORTED],
            },
        }

    def import_transactions(self, file_storage) -> Dict[str, Any]:
        """Import transaction CSV into database."""
        df = self._parse_tabular_file(file_storage)
        schema_errors = self._validate_schema(df, TRANSACTION_REQUIRED_COLS)
        if schema_errors:
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": schema_errors,
            }

        # Build external_id → customer UUID mapping
        cid_map = {}
        for row in (
            db.session.query(Customer.external_id, Customer.customer_id)
            .filter(Customer.external_id.isnot(None))
            .all()
        ):
            cid_map[row[0]] = row[1]

        imported = 0
        skipped = 0
        duplicates_ignored = 0
        errors = []
        seen_tids = set()

        try:
            for row_num, (_, row) in enumerate(df.iterrows(), start=2):
                tid = str(row.get("transaction_id", "")).strip()
                cid = str(row.get("customer_id", "")).strip()
                td_str = str(row.get("transaction_date", "")).strip()
                amt_str = str(row.get("transaction_amount", "")).strip()
                stype = str(row.get("service_type", "")).strip()
                status = str(row.get("transaction_status", "")).strip().lower()

                if not tid or tid in seen_tids:
                    duplicates_ignored += 1
                    continue
                seen_tids.add(tid)

                if cid not in cid_map:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "customer_id",
                            "message": f"Customer not found: {cid}",
                        }
                    )
                    skipped += 1
                    continue

                tx_date = self._parse_datetime(td_str)
                if not tx_date:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "transaction_date",
                            "message": f"Invalid date: {td_str}",
                        }
                    )
                    skipped += 1
                    continue

                try:
                    amount = Decimal(amt_str) if amt_str else Decimal("0")
                except InvalidOperation:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "transaction_amount",
                            "message": f"Invalid amount: {amt_str}",
                        }
                    )
                    skipped += 1
                    continue

                if status not in TRANSACTION_VALID_STATUSES:
                    status = "completed"

                tx = Transaction(
                    tx_id=uuid.uuid4(),
                    customer_id=cid_map[cid],
                    tx_date=tx_date,
                    service_type=stype or "unknown",
                    amount=amount,
                    status=status,
                )
                db.session.add(tx)
                imported += 1

            db.session.commit()
            logger.info(f"Imported {imported} transactions, skipped {skipped}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Transaction import failed: {e}")
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": [{"row": 0, "column": "", "message": str(e)}],
            }

        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "duplicates_ignored": duplicates_ignored,
            "errors": errors[:MAX_ERRORS_REPORTED],
            "import_timestamp": datetime.utcnow().isoformat(),
        }

    # =====================================================================
    # MESSAGE Preview & Import
    # =====================================================================

    def preview_messages(
        self,
        file_storage,
        phone_number: Optional[str] = None,
        customer_sender_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Preview + validate WhatsApp message CSV or single-chat TXT export."""
        try:
            df = self._parse_message_file(
                file_storage,
                phone_number=phone_number,
                customer_sender_name=customer_sender_name,
            )
        except ValueError as e:
            return {
                "success": False,
                "validation": {
                    "valid_rows": 0,
                    "invalid_rows": 0,
                    "errors": [{"row": 0, "column": "file", "message": str(e)}],
                },
            }
        schema_errors = self._validate_schema(df, MESSAGE_REQUIRED_COLS)
        if schema_errors:
            return {
                "success": False,
                "validation": {
                    "valid_rows": 0,
                    "invalid_rows": len(df),
                    "errors": schema_errors,
                },
            }

        valid_phones = set()
        for row in (
            db.session.query(Customer.phone_hash)
            .filter(Customer.phone_hash.isnot(None))
            .all()
        ):
            valid_phones.add(row[0])

        errors = []
        invalid_row_numbers = set()
        seen_ids = set()
        provisional_phone_rows = 0
        provisional_phone_hashes = set()

        def add_error(row: int, column: str, message: str) -> None:
            invalid_row_numbers.add(row)
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(
                    {"row": row, "column": column, "message": message}
                )

        for row_num, (_, row) in enumerate(df.iterrows(), start=2):
            mid = self._cell_text(row.get("message_id", ""))
            phone = self._cell_text(row.get("phone_number", ""))

            if not mid:
                add_error(row_num, "message_id", "Empty message_id")
            elif mid in seen_ids:
                add_error(row_num, "message_id", "Duplicate message_id")
            else:
                seen_ids.add(mid)

            if not phone:
                add_error(row_num, "phone_number", "Empty phone_number")
            else:
                phone_hash = self._hash_phone(phone)
                if phone_hash not in valid_phones:
                    provisional_phone_rows += 1
                    provisional_phone_hashes.add(phone_hash)

            sender = self._cell_text(row.get("sender_type", "")).lower()
            if sender and sender not in MESSAGE_VALID_SENDER_TYPES:
                add_error(
                    row_num,
                    "sender_type",
                    f"Invalid sender_type: {sender}",
                )

            ts = self._cell_text(row.get("message_timestamp", ""))
            if ts and self._parse_datetime(ts) is None:
                add_error(
                    row_num,
                    "message_timestamp",
                    f"Invalid timestamp: {ts}",
                )

            text = self._cell_text(row.get("message_text", ""))
            if not text:
                add_error(row_num, "message_text", "Empty message_text")

        summary = self._compute_summary(df, "message_id", "message_timestamp")
        summary["invalid_phone_fk"] = 0
        summary["provisional_phone_rows"] = provisional_phone_rows
        summary["provisional_phone_count"] = len(provisional_phone_hashes)
        valid_rows = len(df) - len(invalid_row_numbers)

        return {
            "success": len(invalid_row_numbers) == 0,
            "preview": {
                "columns": list(df.columns),
                "rows": df.head(PREVIEW_LIMIT).fillna("").to_dict(orient="records"),
                "total_rows": len(df),
                "summary": summary,
            },
            "validation": {
                "valid_rows": max(0, valid_rows),
                "invalid_rows": len(invalid_row_numbers),
                "errors": errors,
                "errors_truncated": len(invalid_row_numbers) > len(errors),
            },
        }

    def import_messages(
        self,
        file_storage,
        phone_number: Optional[str] = None,
        customer_sender_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import WhatsApp message CSV or single-chat TXT export.
        Creates FeedbackRaw, then maps messages to customers through LinkingService.
        """
        if self._feedback_raw_customer_id_is_not_null():
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": [
                    {
                        "row": 0,
                        "column": "feedback_raw.customer_id",
                        "message": (
                            "Database schema masih legacy: feedback_raw.customer_id masih NOT NULL. "
                            "Jalankan migration 025_feedback_raw_identity_nullable / alembic upgrade head "
                            "pada database backend yang sedang dipakai."
                        ),
                    }
                ],
            }

        try:
            df = self._parse_message_file(
                file_storage,
                phone_number=phone_number,
                customer_sender_name=customer_sender_name,
            )
        except ValueError as e:
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "duplicates_ignored": 0,
                "errors": [{"row": 0, "column": "file", "message": str(e)}],
            }
        schema_errors = self._validate_schema(df, MESSAGE_REQUIRED_COLS)
        if schema_errors:
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": schema_errors,
            }

        # Validasi phone tidak dilakukan di sini — LinkingService yang menangani.
        # Pesan dengan phone tidak dikenal akan masuk feedback_raw dan
        # LinkingService akan membuat provisional customer otomatis.

        imported = 0
        skipped = 0
        duplicates_ignored = 0
        errors = []
        seen_mids = set()

        try:
            for row_num, (_, row) in enumerate(df.iterrows(), start=2):
                mid = self._cell_text(row.get("message_id", ""))
                phone = self._cell_text(row.get("phone_number", ""))
                ts_str = self._cell_text(row.get("message_timestamp", ""))
                sender = self._cell_text(row.get("sender_type", "")).lower()
                text = self._cell_text(row.get("message_text", ""))

                if not mid or mid in seen_mids:
                    duplicates_ignored += 1
                    continue
                seen_mids.add(mid)

                phone_hash = self._hash_phone(phone) if phone else None
                if not phone_hash:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "phone_number",
                            "message": "Empty phone_number",
                        }
                    )
                    skipped += 1
                    continue

                ts = self._parse_datetime(ts_str)
                if not ts:
                    errors.append(
                        {
                            "row": row_num,
                            "column": "message_timestamp",
                            "message": f"Invalid timestamp: {ts_str}",
                        }
                    )
                    skipped += 1
                    continue

                direction = SENDER_TYPE_TO_DIRECTION.get(sender, "inbound")

                raw = FeedbackRaw(
                    msg_id=uuid.uuid4(),
                    phone_number=phone_hash,  # Store hash, not raw
                    direction=direction,
                    text=text if text else None,
                    timestamp=ts,
                    raw_meta={"message_id": mid, "sender_type": sender},
                )
                db.session.add(raw)
                imported += 1

            db.session.flush()
            from app.services.linking_service import LinkingService

            linking_stats = LinkingService().link_unlinked_messages()
            db.session.commit()
            logger.info(f"Imported {imported} messages, skipped {skipped}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Message import failed: {e}")
            return {
                "success": False,
                "imported": 0,
                "skipped": 0,
                "errors": [{"row": 0, "column": "", "message": str(e)}],
            }

        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "duplicates_ignored": duplicates_ignored,
            "linking": linking_stats,
            "errors": errors[:MAX_ERRORS_REPORTED],
            "import_timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _feedback_raw_customer_id_is_not_null() -> bool:
        """Detect legacy schema before bulk insert produces a long DB error."""
        inspector = sa.inspect(db.engine)
        try:
            columns = inspector.get_columns("feedback_raw")
        except Exception:
            return False

        for column in columns:
            if column["name"] == "customer_id":
                return not column.get("nullable", True)
        return False
