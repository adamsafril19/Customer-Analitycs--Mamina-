from io import BytesIO

from werkzeug.datastructures import FileStorage

from app.services.import_service import CSVImportService


def _txt_upload(content: str) -> FileStorage:
    return FileStorage(
        stream=BytesIO(content.encode("utf-8")),
        filename="chat.txt",
        content_type="text/plain",
    )


def _csv_upload(content: str) -> FileStorage:
    return FileStorage(
        stream=BytesIO(content.encode("utf-8")),
        filename="messages.csv",
        content_type="text/csv",
    )


def test_parse_whatsapp_txt_export_with_customer_sender_name():
    upload = _txt_upload(
        "10/06/26, 09.15 - Budi: Halo admin\n"
        "10/06/26, 09.16 - Mamina: Halo kak, ada yang bisa dibantu?\n"
    )

    df = CSVImportService._parse_whatsapp_txt(
        upload,
        phone_number="08123456789",
        customer_sender_name="Budi",
    )

    assert list(df.columns) == [
        "message_id",
        "phone_number",
        "message_timestamp",
        "sender_type",
        "message_text",
    ]
    assert len(df) == 2
    assert df.iloc[0]["sender_type"] == "customer"
    assert df.iloc[1]["sender_type"] == "admin"
    assert df.iloc[0]["phone_number"] == "08123456789"


def test_parse_whatsapp_txt_export_keeps_multiline_messages():
    upload = _txt_upload(
        "[10/06/2026, 09:15:10] Budi: Pesan pertama\n"
        "lanjutan pesan pertama\n"
        "[10/06/2026, 09:16:00] Admin: Balasan\n"
    )

    df = CSVImportService._parse_whatsapp_txt(upload, phone_number="08123456789")

    assert len(df) == 2
    assert df.iloc[0]["sender_type"] == "customer"
    assert df.iloc[0]["message_text"] == "Pesan pertama\nlanjutan pesan pertama"


def test_message_preview_reports_unmatched_phone_as_provisional(app):
    upload = _csv_upload(
        "message_id,phone_number,message_timestamp,sender_type,message_text\n"
        "m1,08123456789,2026-06-10 09:15:00,customer,Halo\n"
        "m2,08123456789,2026-06-10 09:16:00,admin,Halo kak\n"
    )

    with app.app_context():
        result = CSVImportService().preview_messages(upload)

    assert result["success"] is True
    assert result["validation"]["valid_rows"] == 2
    assert result["validation"]["invalid_rows"] == 0
    assert result["preview"]["summary"]["provisional_phone_rows"] == 2
    assert result["preview"]["summary"]["provisional_phone_count"] == 1


def test_message_preview_counts_all_invalid_rows_but_caps_error_details(app):
    rows = [
        f"m{i},,2026-06-10 09:15:00,customer,Halo"
        for i in range(250)
    ]
    upload = _csv_upload(
        "message_id,phone_number,message_timestamp,sender_type,message_text\n"
        + "\n".join(rows)
        + "\n"
    )

    with app.app_context():
        result = CSVImportService().preview_messages(upload)

    assert result["success"] is False
    assert result["validation"]["valid_rows"] == 0
    assert result["validation"]["invalid_rows"] == 250
    assert len(result["validation"]["errors"]) == 200
    assert result["validation"]["errors_truncated"] is True
