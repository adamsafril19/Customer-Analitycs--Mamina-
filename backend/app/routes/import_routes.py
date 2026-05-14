"""
CSV Import API Endpoints

6 endpoints: preview + import for each of 3 dataset types.
All require JWT auth + admin role.
Accept multipart/form-data with 'file' field.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from flasgger import swag_from

from app.utils.errors import ValidationError
from app.utils.auth import admin_required

import_bp = Blueprint("import", __name__)


def _get_file_or_error():
    """Extract file from multipart request or raise."""
    if "file" not in request.files:
        raise ValidationError("No file uploaded", {"file": "File field is required"})
    f = request.files["file"]
    if not f.filename:
        raise ValidationError("Empty filename", {"file": "File must have a name"})
    if not f.filename.lower().endswith(".csv"):
        raise ValidationError("Invalid file type", {"file": "Only .csv files are accepted"})
    return f


# =========================================================================
# CUSTOMERS
# =========================================================================

@import_bp.route("/customers/preview", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Import"],
    "summary": "Preview customer CSV",
    "description": "Parse and validate customer CSV before import. Returns preview rows and validation report.",
    "security": [{"Bearer": []}],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "Preview and validation result"}}
})
def preview_customers():
    f = _get_file_or_error()
    from app.services.import_service import CSVImportService
    svc = CSVImportService()
    result = svc.preview_customers(f)
    return jsonify(result)


@import_bp.route("/customers", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Import"],
    "summary": "Import customer CSV",
    "description": "Import customer_master.csv into the customers table.",
    "security": [{"Bearer": []}],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "Import result summary"}}
})
def import_customers():
    f = _get_file_or_error()
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
@swag_from({
    "tags": ["Import"],
    "summary": "Preview transaction CSV",
    "description": "Parse and validate transaction CSV. Checks FK against existing customers.",
    "security": [{"Bearer": []}],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "Preview and validation result"}}
})
def preview_transactions():
    f = _get_file_or_error()
    from app.services.import_service import CSVImportService
    svc = CSVImportService()
    result = svc.preview_transactions(f)
    return jsonify(result)


@import_bp.route("/transactions", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Import"],
    "summary": "Import transaction CSV",
    "description": "Import transactions.csv into the transactions table.",
    "security": [{"Bearer": []}],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "Import result summary"}}
})
def import_transactions():
    f = _get_file_or_error()
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
@swag_from({
    "tags": ["Import"],
    "summary": "Preview WhatsApp message CSV",
    "description": "Parse and validate whatsapp_messages CSV. Checks FK and sender_type.",
    "security": [{"Bearer": []}],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "Preview and validation result"}}
})
def preview_messages():
    f = _get_file_or_error()
    from app.services.import_service import CSVImportService
    svc = CSVImportService()
    result = svc.preview_messages(f)
    return jsonify(result)


@import_bp.route("/messages", methods=["POST"])
@jwt_required()
@admin_required
@swag_from({
    "tags": ["Import"],
    "summary": "Import WhatsApp message CSV",
    "description": "Import whatsapp_messages.csv into feedback_raw + feedback_linked tables.",
    "security": [{"Bearer": []}],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "Import result summary"}}
})
def import_messages():
    f = _get_file_or_error()
    from app.services.import_service import CSVImportService
    svc = CSVImportService()
    result = svc.import_messages(f)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code
