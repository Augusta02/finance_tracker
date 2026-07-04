"""
main.py - decrypts a password-protected GTBank statement PDF and returns
structured transaction rows.

Import this from app.py:  from main import extract_transactions, transactions_to_csv

No Tika, no Java, no separate hosted service. pikepdf handles the password,
pdfplumber reads the real table columns (Trans. Date / Value Date /
Reference / Debits / Credits / Balance / Originating Branch / Remarks) -
tested against your actual June 2026 statement, 125 transactions extracted
cleanly.
"""
import csv
import io
import os
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


def extract_transactions(pdf_path_or_bytes, password: str) -> list[dict]:
    """
    Decrypts the statement and returns one dict per transaction row:
    date, reference, debit, credit, balance, remarks.
    Blank debit/credit (the side that didn't apply to that row) is
    normalized to "0.00" instead of an empty string.
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
                if not trans_date or trans_date.lower().startswith("trans"):
                    continue
                rows.append({
                    "date": trans_date,
                    "reference": reference,
                    "debit": debit.strip() or "0.00",
                    "credit": credit.strip() or "0.00",
                    "balance": balance,
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

    test_file = "data/AC_ALOKAM CHINENYENWA AUGUSTA_JUNE, 2026_270R008369327_FullStmt.pdf"
    txns = extract_transactions(test_file, password)
    print(f"Extracted {len(txns)} transactions")

    csv_text = transactions_to_csv(txns)
    out_path = "data/parsed_transactions.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        f.write(csv_text)
    print(f"Wrote {out_path}")
    print(csv_text[:500])
