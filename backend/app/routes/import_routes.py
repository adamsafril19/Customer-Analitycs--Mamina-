"""
CSV Import API Endpoints

7 endpoint groups: template download + preview + import for each of 3 dataset types.
All (except template) require JWT auth + admin role.
Accept multipart/form-data with 'file' field.
"""

import csv
import io

from flasgger import swag_from
from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from app.utils.auth import admin_required
from app.utils.errors import ValidationError

import_bp = Blueprint("import", __name__)

# =========================================================================
# CSV TEMPLATE DEFINITIONS (headers + sample rows)
# =========================================================================

_TEMPLATES = {
    "customers": {
        "filename": "template_customer_master.xlsx",
        "headers": ["customer_id", "customer_name", "phone_number", "join_date"],
        "sample_rows": [
            ["CUST-001", "Budi Santoso", "081234567890", "2024-01-15"],
            ["CUST-002", "Siti Aminah", "089876543210", "2024-03-22"],
        ],
    },
    "transactions": {
        "filename": "template_transactions.xlsx",
        "headers": [
            "transaction_id",
            "customer_id",
            "transaction_date",
            "transaction_amount",
            "service_type",
            "transaction_status",
        ],
        "sample_rows": [
            ["TRX-001", "CUST-001", "2024-06-01 10:30:00", "350000", "baby_spa", "completed"],
            ["TRX-002", "CUST-002", "2024-06-05 14:00:00", "275000", "pijat_laktasi", "completed"],
        ],
    },
    "messages": {
        "filename": "template_whatsapp_messages.csv",
        "headers": [
            "message_id",
            "phone_number",
            "message_timestamp",
            "sender_type",
            "message_text",
        ],
        "sample_rows": [
            ["MSG-001", "081234567890", "2024-06-01 09:15:00", "customer", "Halo, saya mau booking baby spa untuk hari Sabtu"],
            ["MSG-002", "081234567890", "2024-06-01 09:20:00", "admin", "Baik Bunda, untuk hari Sabtu jam berapa ya?"],
        ],
    },
}


# =========================================================================
# TEMPLATE DOWNLOAD (no auth required)
# =========================================================================


@import_bp.route("/template/<dataset_type>", methods=["GET"])
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Download CSV template",
        "description": "Download a CSV template file with headers and sample data for the specified dataset type.",
        "parameters": [
            {
                "name": "dataset_type",
                "in": "path",
                "type": "string",
                "required": True,
                "enum": ["customers", "transactions", "messages"],
                "description": "Dataset type: customers, transactions, or messages",
            }
        ],
        "responses": {
            200: {"description": "CSV file download"},
            404: {"description": "Invalid dataset type"},
        },
    }
)
def download_template(dataset_type):
    """Serve a downloadable template with sample data."""
    template = _TEMPLATES.get(dataset_type)
    if not template:
        return jsonify({"error": f"Unknown dataset type: {dataset_type}"}), 404

    if dataset_type in {"customers", "transactions"}:
        try:
            import pandas as pd

            buf = io.BytesIO()
            df = pd.DataFrame(template["sample_rows"], columns=template["headers"])
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=dataset_type)
            buf.seek(0)
            return Response(
                buf.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f'attachment; filename="{template["filename"]}"'
                },
            )
        except Exception as exc:
            return jsonify({"error": f"Gagal membuat template Excel: {exc}"}), 500

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(template["headers"])
    for row in template["sample_rows"]:
        writer.writerow(row)

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{template["filename"]}"'
        },
    )


def _get_file_or_error(allowed_extensions=None):
    """Extract file from multipart request or raise."""
    allowed_extensions = allowed_extensions or {".csv"}
    if "file" not in request.files:
        raise ValidationError("No file uploaded", {"file": "File field is required"})
    f = request.files["file"]
    if not f.filename:
        raise ValidationError("Empty filename", {"file": "File must have a name"})
    filename = f.filename.lower()
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        accepted = ", ".join(sorted(allowed_extensions))
        raise ValidationError(
            "Invalid file type", {"file": f"Only {accepted} files are accepted"}
        )
    return f


# =========================================================================
# CUSTOMERS
# =========================================================================


@import_bp.route("/customers/preview", methods=["POST"])
@jwt_required()
@admin_required
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Preview customer CSV",
        "description": "Parse and validate customer CSV before import. Returns preview rows and validation report.",
        "security": [{"Bearer": []}],
        "consumes": ["multipart/form-data"],
        "parameters": [
            {"name": "file", "in": "formData", "type": "file", "required": True}
        ],
        "responses": {200: {"description": "Preview and validation result"}},
    }
)
def preview_customers():
    f = _get_file_or_error({".csv", ".xlsx", ".xls"})
    from app.services.import_service import CSVImportService

    svc = CSVImportService()
    result = svc.preview_customers(f)
    return jsonify(result)


@import_bp.route("/customers", methods=["POST"])
@jwt_required()
@admin_required
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Import customer CSV",
        "description": "Import customer_master.csv into the customers table.",
        "security": [{"Bearer": []}],
        "consumes": ["multipart/form-data"],
        "parameters": [
            {"name": "file", "in": "formData", "type": "file", "required": True}
        ],
        "responses": {200: {"description": "Import result summary"}},
    }
)
def import_customers():
    f = _get_file_or_error({".csv", ".xlsx", ".xls"})
    from app.services.import_service import CSVImportService

    svc = CSVImportService()
    result = svc.import_customers(f)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


# =========================================================================
# TRANSACTIONS
# =========================================================================


@import_bp.route("/transactions/preview", methods=["POST"])
@jwt_required()
@admin_required
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Preview transaction CSV",
        "description": "Parse and validate transaction CSV. Checks FK against existing customers.",
        "security": [{"Bearer": []}],
        "consumes": ["multipart/form-data"],
        "parameters": [
            {"name": "file", "in": "formData", "type": "file", "required": True}
        ],
        "responses": {200: {"description": "Preview and validation result"}},
    }
)
def preview_transactions():
    f = _get_file_or_error({".csv", ".xlsx", ".xls"})
    from app.services.import_service import CSVImportService

    svc = CSVImportService()
    result = svc.preview_transactions(f)
    return jsonify(result)


@import_bp.route("/transactions", methods=["POST"])
@jwt_required()
@admin_required
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Import transaction CSV",
        "description": "Import transactions.csv into the transactions table.",
        "security": [{"Bearer": []}],
        "consumes": ["multipart/form-data"],
        "parameters": [
            {"name": "file", "in": "formData", "type": "file", "required": True}
        ],
        "responses": {200: {"description": "Import result summary"}},
    }
)
def import_transactions():
    f = _get_file_or_error({".csv", ".xlsx", ".xls"})
    from app.services.import_service import CSVImportService

    svc = CSVImportService()
    result = svc.import_transactions(f)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


# =========================================================================
# MESSAGES
# =========================================================================


@import_bp.route("/messages/preview", methods=["POST"])
@jwt_required()
@admin_required
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Preview WhatsApp message CSV or TXT",
        "description": "Parse and validate whatsapp_messages CSV or a single-chat WhatsApp TXT export. TXT uploads require phone_number form data.",
        "security": [{"Bearer": []}],
        "consumes": ["multipart/form-data"],
        "parameters": [
            {"name": "file", "in": "formData", "type": "file", "required": True}
        ],
        "responses": {200: {"description": "Preview and validation result"}},
    }
)
def preview_messages():
    f = _get_file_or_error({".csv", ".txt"})
    from app.services.import_service import CSVImportService

    svc = CSVImportService()
    result = svc.preview_messages(
        f,
        phone_number=request.form.get("phone_number"),
        customer_sender_name=request.form.get("customer_sender_name"),
    )
    return jsonify(result)


@import_bp.route("/messages", methods=["POST"])
@jwt_required()
@admin_required
@swag_from(
    {
        "tags": ["Import"],
        "summary": "Import WhatsApp message CSV or TXT",
        "description": "Import whatsapp_messages.csv or a single-chat WhatsApp TXT export into feedback_raw + feedback_linked tables. TXT uploads require phone_number form data.",
        "security": [{"Bearer": []}],
        "consumes": ["multipart/form-data"],
        "parameters": [
            {"name": "file", "in": "formData", "type": "file", "required": True}
        ],
        "responses": {200: {"description": "Import result summary"}},
    }
)
def import_messages():
    f = _get_file_or_error({".csv", ".txt"})
    from app.services.import_service import CSVImportService

    svc = CSVImportService()
    result = svc.import_messages(
        f,
        phone_number=request.form.get("phone_number"),
        customer_sender_name=request.form.get("customer_sender_name"),
    )
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code
