"""Seed demo database with synthetic documents."""

from __future__ import annotations

import asyncio
import os
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
from fpdf import FPDF

# Import MyMemex components
# Note: Ensure PYTHONPATH is set to include src
from mymemex.config import load_config
from mymemex.storage.database import init_database, get_session
from mymemex.storage.repositories import DocumentRepository, TagRepository
from mymemex.processing.pipeline import handle_new_file
from mymemex.core.events import EventManager

fake = Faker()

class DemoPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "SAMPLE DATA - MYMEMEX DEMO - For demonstration purposes only", 0, 0, "C")

def create_invoice(output_path: Path):
    pdf = DemoPDF()
    pdf.add_page()
    
    vendor = fake.company()
    invoice_no = f"INV-{fake.random_number(digits=6)}"
    date = fake.date_between(start_date="-3y", end_date="today")
    amount = f"{random.uniform(10.0, 5000.0):.2f}"
    currency = random.choice(["USD", "EUR", "GBP"])
    
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, vendor, 0, 1)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, fake.street_address(), 0, 1)
    pdf.cell(0, 5, f"{fake.city()}, {fake.postcode()}", 0, 1)
    pdf.cell(0, 5, fake.country(), 0, 1)
    pdf.ln(10)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, f"INVOICE {invoice_no}", 0, 1)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 10, f"Date: {date}", 0, 1)
    pdf.ln(5)
    
    # Bill to
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, "Bill To:", 0, 1)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, fake.name(), 0, 1)
    pdf.cell(0, 5, fake.address(), 0, 1)
    pdf.ln(10)
    
    # Line items
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(100, 8, "Description", 1)
    pdf.cell(40, 8, "Amount", 1, 1)
    
    pdf.set_font("helvetica", "", 10)
    for _ in range(random.randint(1, 5)):
        pdf.cell(100, 8, fake.catch_phrase(), 1)
        pdf.cell(40, 8, f"{random.uniform(10.0, 500.0):.2f}", 1, 1)
    
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(100, 10, "TOTAL", 0)
    pdf.cell(40, 10, f"{currency} {amount}", 0, 1)
    
    pdf.output(str(output_path))

def create_receipt(output_path: Path):
    # Receipts are smaller
    pdf = DemoPDF(format=(80, 150))
    pdf.add_page()
    
    vendor = fake.company()
    date = fake.date_between(start_date="-1y", end_date="today")
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, vendor, 0, 1, "C")
    pdf.set_font("helvetica", "", 8)
    pdf.cell(0, 4, fake.address(), 0, 1, "C")
    pdf.ln(5)
    
    pdf.cell(0, 4, f"Date: {date}", 0, 1)
    pdf.cell(0, 4, f"Trans: {fake.random_number(digits=8)}", 0, 1)
    pdf.ln(3)
    
    total = 0
    for _ in range(random.randint(2, 8)):
        item = fake.word().capitalize()
        price = random.uniform(1.0, 50.0)
        total += price
        pdf.cell(40, 4, item, 0)
        pdf.cell(20, 4, f"{price:.2f}", 0, 1, "R")
    
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(40, 6, "TOTAL", 0)
    pdf.cell(20, 6, f"{total:.2f}", 0, 1, "R")
    
    pdf.output(str(output_path))

def create_contract(output_path: Path):
    pdf = DemoPDF()
    pdf.add_page()
    
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, "SERVICE AGREEMENT", 0, 1, "C")
    
    party_a = fake.company()
    party_b = fake.name()
    
    pdf.set_font("helvetica", "", 11)
    text = f"""
This Agreement is entered into as of {fake.date_between(start_date="-2y", end_date="-1y")} by and between {party_a} ("Company") and {party_b} ("Contractor").

1. SERVICES. Contractor agrees to perform the following services: {fake.job()}.

2. COMPENSATION. Company shall pay Contractor {random.randint(50, 200)} per hour.

3. TERM. This agreement shall remain in effect for {random.randint(6, 24)} months.

4. CONFIDENTIALITY. Both parties agree to keep all proprietary information confidential.

IN WITNESS WHEREOF, the parties have executed this Agreement.

Signed: __________________________ ({party_a})

Signed: __________________________ ({party_b})
"""
    pdf.multi_cell(0, 8, text)
    pdf.output(str(output_path))

def create_tax_doc(output_path: Path):
    pdf = DemoPDF()
    pdf.add_page()
    
    year = random.randint(2020, 2024)
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 15, f"{year} TAX RETURN SUMMARY", 0, 1, "C")
    
    name = fake.name()
    ssn = f"XXX-XX-{fake.random_number(digits=4)}"
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(50, 10, "Taxpayer Name:", 0)
    pdf.cell(0, 10, name, 0, 1)
    pdf.cell(50, 10, "SSN:", 0)
    pdf.cell(0, 10, ssn, 0, 1)
    pdf.ln(10)
    
    data = [
        ("Gross Income", random.uniform(40000, 150000)),
        ("Adjustments", random.uniform(1000, 10000)),
        ("Deductions", random.uniform(12000, 25000)),
        ("Taxable Income", random.uniform(30000, 120000)),
        ("Total Tax", random.uniform(5000, 30000)),
        ("Withholding", random.uniform(5000, 35000)),
    ]
    
    for label, val in data:
        pdf.cell(80, 10, label, 1)
        pdf.cell(50, 10, f"{val:,.2f}", 1, 1, "R")
        
    pdf.output(str(output_path))

async def seed_demo():
    print("🌱 Seeding demo data...")
    
    config = load_config()
    print(f"Using database: {config.database.path}")
    
    await init_database(config.database.path)
    
    # Use the data volume path for documents so they persist and are accessible
    docs_dir = Path("/var/lib/mymemex/demo_docs")
    if docs_dir.exists():
        shutil.rmtree(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    print("Generating synthetic PDFs...")
    # Invoices
    for i in range(10):
        create_invoice(docs_dir / f"invoice_{i}.pdf")
    # Receipts
    for i in range(5):
        create_receipt(docs_dir / f"receipt_{i}.pdf")
    # Contracts
    for i in range(3):
        create_contract(docs_dir / f"contract_{i}.pdf")
    # Tax docs
    for i in range(5):
        create_tax_doc(docs_dir / f"tax_{i}.pdf")
        
    print(f"Generated {len(list(docs_dir.glob('*.pdf')))} documents.")
    
    print("Ingesting documents into database...")
    events = EventManager()
    
    # We'll use the ingest pipeline directly
    for pdf_path in docs_dir.glob("*.pdf"):
        print(f"  Ingesting {pdf_path.name}...")
        await handle_new_file(str(pdf_path.absolute()), config, events)
        
    print("✅ Demo data seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed_demo())
