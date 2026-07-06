"""
main.py - decrypts a password-protected Bank statement PDF and returns
structured transaction rows.

"""
import csv
import io
import os
from datetime import datetime
import pikepdf
import pdfplumber
from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder, if present - no more manual $env: calls

CSV_FIELDS = ["date", "reference", "debit", "credit", "balance", "remarks"]


def decrypt_pdf(pdf_path_or_bytes, password: str) -> bytes:
    """Returns decrypted PDF bytes for a password-protected statement."""
    with pikepdf.open(pdf_path_or_bytes, password=password) as pdf:
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def _parse_amount(raw: str) -> float:
    """Strips thousands-separator commas and converts a debit/credit/balance
    cell to a float. Blank cells become 0.0."""
    if not raw:
        return 0.0
    cleaned = raw.replace(",", "").strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def _parse_date(raw: str):
    """Converts bank format 'DD-MMM-YYYY' text (e.g. '02-Oct-2024') into an ISO
    'YYYY-MM-DD' string. Returns None if the cell isn't a real date, so the
    caller can skip header/continuation rows."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_transactions(pdf_path_or_bytes, password: str) -> list[dict]:
    """
    Decrypts the statement and returns one dict per transaction row:
    date (ISO string), reference, debit (float), credit (float),
    balance (float), remarks.
    """
    decrypted_bytes = decrypt_pdf(pdf_path_or_bytes, password)
    rows = []
    with pdfplumber.open(io.BytesIO(decrypted_bytes)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            for raw_row in table[1:]:
                cells = [c.replace("\n", " ").strip() if c else "" for c in raw_row]
                if len(cells) < 7:
                    continue
                trans_date, value_date, reference, debit, credit, balance, branch = cells[:7]
                remarks = " ".join(cells[7:]).strip()

                iso_date = _parse_date(trans_date)
                if not iso_date:
                    continue 

                try:
                    debit_val = _parse_amount(debit)
                    credit_val = _parse_amount(credit)
                    balance_val = _parse_amount(balance)
                except ValueError:
                    continue  # garbage row - skip rather than send bad data downstream

                rows.append({
                    "date": iso_date,
                    "reference": reference,
                    "debit": debit_val,
                    "credit": credit_val,
                    "balance": balance_val,
                    "remarks": remarks,
                })
    return rows


def transactions_to_csv(rows: list[dict]) -> str:
    """Converts extracted transaction rows into CSV text, one row per transaction."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


if __name__ == "__main__":
    password = os.environ.get("STATEMENT_PASSWORD")
    if not password:
        raise SystemExit("STATEMENT_PASSWORD not set - put it in .env or export it before running.")

    test_file = "data/statement_june2026.pdf"
    txns = extract_transactions(test_file, password)
    print(f"Extracted {len(txns)} transactions")

    csv_text = transactions_to_csv(txns)
    out_path = "data/parsed_transactions.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        f.write(csv_text)
    print(f"Wrote {out_path}")
    print(csv_text[:500])
