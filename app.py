import io
import os
from flask import Flask, request, jsonify, Response
from main import extract_transactions, transactions_to_csv
from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder, if present - no more manual $env: calls

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "")
STATEMENT_PASSWORD = os.environ.get("STATEMENT_PASSWORD", "")


@app.route("/health", methods=["GET"])
def health():
    # Hit this first after deploying - confirms env vars actually loaded
    # before you ever send it a real file.
    return jsonify({
        "status": "ok",
        "api_key_set": bool(API_KEY),
        "statement_password_set": bool(STATEMENT_PASSWORD),
    })


@app.route("/parse", methods=["POST"])
def parse():
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "no file uploaded - expected multipart field 'file'"}), 400

    try:
        rows = extract_transactions(io.BytesIO(file.read()), STATEMENT_PASSWORD)
    except Exception as e:
        return jsonify({"error": "extraction_failed", "detail": str(e)}), 502

    csv_text = transactions_to_csv(rows)
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=transactions.csv",
            "X-Row-Count": str(len(rows)),
        },
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
