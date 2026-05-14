"""
Flask Application Entry Point
Sistem Prediksi Behavioral Risk - Mamina Baby Spa

Author: Skripsi Project
Description: Backend Flask untuk sistem prediksi risiko aktivitas pelanggan berbasis multimodal
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
