# Demo Data: Synthetic Document Generator

**Purpose:** Generate realistic synthetic documents for the MyMemex demo

---

## Document Types

| Type | Count | Purpose |
|------|-------|---------|
| Invoice | 10 | Show extraction of amounts, vendors, dates |
| Receipt | 8 | Show categorization, small amounts |
| Tax Document | 5 | Show tax extraction, aggregations |
| Contract | 3 | Show search, long documents |
| Correspondence | 5 | Show person tagging, dates |
| Bank Statement | 4 | Show transaction patterns |

**Total: ~35 documents**

---

## Libraries

```bash
pip install faker fpdf2
```

- **Faker** — Realistic fake data (names, addresses, companies, amounts)
- **FPDF2** — Simple PDF generation

---

## Sample Code Structure

```python
# scripts/seed_demo_data.py

import os
from datetime import date, timedelta
from random import randint, choice
from faker import Faker
from fpdf import FPDF

fake = Faker()

# Consistent entities across documents
VENDORS = ["Acme Corp", "TechSupply GmbH", "Global Services Ltd", "Nordic Solutions AB"]
PEOPLE = ["Goran", "Zeljana", "Maja"]  # Match user context
CATEGORIES = ["invoice", "receipt", "tax_return", "contract", "correspondence", "bank_statement"]

class DemoPDF(FPDF):
    def header(self):
        pass
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, 'SAMPLE DATA - DEMO', 0, 0, 'C')

def generate_invoice(pdf: FPDF, vendor: str, amount: float, invoice_date: date):
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'INVOICE', 0, 1, 'C')
    
    pdf.set_font('Helvetica', '', 12)
    pdf.ln(10)
    pdf.cell(0, 8, f'From: {vendor}', 0, 1)
    pdf.cell(0, 8, f'Invoice Number: INV-{fake.uuid4()[:8].upper()}', 0, 1)
    pdf.cell(0, 8, f'Date: {invoice_date.strftime("%B %d, %Y")}', 0, 1)
    
    pdf.ln(10)
    pdf.cell(0, 8, 'Bill To:', 0, 1)
    pdf.cell(0, 8, fake.name(), 0, 1)
    pdf.cell(0, 8, fake.address(), 0, 1)
    
    pdf.ln(10)
    pdf.cell(0, 8, f'Total Amount: EUR {amount:,.2f}', 0, 1)
    
    # Add some line items
    pdf.ln(5)
    for _ in range(randint(2, 5)):
        item = fake.sentence(nb_words=4)[:-1]
        qty = randint(1, 10)
        price = amount / qty / randint(2, 4)
        pdf.cell(0, 8, f'  - {item}: {qty} x EUR {price:.2f}', 0, 1)

def generate_receipt(pdf: FPDF, store: str, amount: float, receipt_date: date):
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, store.upper(), 0, 1, 'C')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Date: {receipt_date.strftime("%Y-%m-%d")}  Time: {fake.time()}', 0, 1, 'C')
    pdf.cell(0, 6, f'Receipt #: {fake.bothify(text="REC-####-####")}', 0, 1, 'C')
    
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Items
    remaining = amount
    for _ in range(randint(3, 8)):
        item_price = round(remaining / randint(2, 10), 2)
        if item_price > remaining:
            item_price = remaining
        remaining -= item_price
        pdf.cell(150, 6, fake.sentence(nb_words=3)[:-1], 0, 0)
        pdf.cell(40, 6, f'EUR {item_price:.2f}', 0, 1, 'R')
    
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(150, 8, 'TOTAL', 0, 0)
    pdf.cell(40, 8, f'EUR {amount:.2f}', 0, 1, 'R')

def generate_tax_document(pdf: FPDF, year: int, person: str):
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, f'TAX RETURN SUMMARY - {year}', 0, 1, 'C')
    
    pdf.set_font('Helvetica', '', 11)
    pdf.ln(10)
    pdf.cell(0, 8, f'Taxpayer: {person}', 0, 1)
    pdf.cell(0, 8, f'Tax Year: {year}', 0, 1)
    pdf.cell(0, 8, f'Document ID: TAX-{year}-{fake.uuid4()[:6].upper()}', 0, 1)
    
    pdf.ln(10)
    
    # Income
    income = randint(40000, 120000)
    tax_paid = int(income * 0.25)
    refund = randint(-2000, 3000)
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Income Summary', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 6, f'  Total Income: EUR {income:,}', 0, 1)
    pdf.cell(0, 6, f'  Taxable Income: EUR {int(income * 0.85):,}', 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Tax Calculation', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 6, f'  Tax Rate: 25%', 0, 1)
    pdf.cell(0, 6, f'  Tax Due: EUR {tax_paid:,}', 0, 1)
    pdf.cell(0, 6, f'  Tax Withheld: EUR {tax_paid - refund:,}', 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 14)
    if refund >= 0:
        pdf.cell(0, 10, f'REFUND DUE: EUR {refund:,}', 0, 1)
    else:
        pdf.cell(0, 10, f'AMOUNT OWING: EUR {abs(refund):,}', 0, 1)

def main():
    output_dir = os.environ.get("DEMO_DATA_DIR", "/tmp/demo_documents")
    os.makedirs(output_dir, exist_ok=True)
    
    dates = [date.today() - timedelta(days=randint(30, 1800)) for _ in range(35)]
    years = [2020, 2021, 2022, 2023, 2024, 2025]
    
    doc_count = 0
    
    # Generate invoices
    for i in range(10):
        pdf = DemoPDF()
        vendor = choice(VENDORS)
        amount = randint(100, 5000) + (randint(0, 99) / 100)
        doc_date = dates[i]
        generate_invoice(pdf, vendor, amount, doc_date)
        filename = f"{output_dir}/invoice_{vendor.replace(' ', '_')}_{doc_date.strftime('%Y%m%d')}.pdf"
        pdf.output(filename)
        doc_count += 1
    
    # Generate receipts
    stores = ["SuperMart", "TechStore", "Cafe Milano", "BookWorld", "PharmaPlus"]
    for i in range(8):
        pdf = DemoPDF()
        store = choice(stores)
        amount = randint(5, 150) + (randint(0, 99) / 100)
        doc_date = dates[10 + i]
        generate_receipt(pdf, store, amount, doc_date)
        filename = f"{output_dir}/receipt_{store}_{doc_date.strftime('%Y%m%d')}.pdf"
        pdf.output(filename)
        doc_count += 1
    
    # Generate tax documents
    for i, year in enumerate(years[:5]):
        for person in PEOPLE[:2]:  # Only first 2 people
            pdf = DemoPDF()
            generate_tax_document(pdf, year, person)
            filename = f"{output_dir}/tax_return_{person}_{year}.pdf"
            pdf.output(filename)
            doc_count += 1
    
    print(f"Generated {doc_count} demo documents in {output_dir}")

if __name__ == "__main__":
    main()
```

---

## Running

```bash
# Generate documents
python scripts/seed_demo_data.py

# Output in /tmp/demo_documents/
# - invoice_Acme_Corp_20240315.pdf
# - receipt_SuperMart_20240210.pdf
# - tax_return_Goran_2023.pdf
# etc.
```

---

## After Generation

1. Copy documents to demo instance's watch folder
2. Let MyMemex ingest and classify them
3. Verify all documents appear in search
4. Export the database as `demo_seed.db`
5. Use this database as the base for demo deployments

---

## Notes

- All documents have "SAMPLE DATA - DEMO" watermark
- Use consistent names (Goran, Zeljana, Maja) to demonstrate person tagging
- Cover multiple years (2020-2025) for date range queries
- Include various amounts for aggregation demos
- Mix of languages could be added (German, Serbian) for multi-language testing
