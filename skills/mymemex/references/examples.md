# Usage Examples

Real-world usage patterns for the MyMemex skill.

## Finding Documents

### Example 1: Natural language search

**User:** "Find my car insurance policy"

**Tool call:**
```
search_documents(query="car insurance policy", mode="semantic", limit=5)
```

**Response:**
```
Found 3 results for 'car insurance policy' (semantic search):

- Car Insurance - Allianz 2024.pdf (ID: 42, distance: 0.150)
  Complete car insurance policy document for the year 2024...
  Tags: insurance, car

- Vehicle Registration.pdf (ID: 15, distance: 0.280)
  Vehicle registration and insurance details...
  Tags: car, registration

- Insurance Renewal Letter.pdf (ID: 87, distance: 0.320)
  Annual renewal notice for all insurance policies...
  Tags: insurance
```

---

### Example 2: Keyword search

**User:** "Search for 'invoice' in my documents"

**Tool call:**
```
search_documents(query="invoice", mode="keyword", limit=10)
```

---

### Example 3: Page-specific retrieval

**User:** "Show me pages 2-4 of document 42"

**Tool call:**
```
get_document_text(document_id=42, page_start=2, page_end=4)
```

**Response:**
```
# Car Insurance - Allianz 2024
Pages 2-4 of 8

[Extracted text for pages 2-4]
```

---

## Browsing Documents

### Example 4: Recent documents

**User:** "Show me my recent documents"

**Tool call:**
```
list_documents(limit=10, sort="created_desc")
```

---

### Example 5: Filter by tag

**User:** "Show me all my tax documents"

**Tool call:**
```
list_documents(tag="tax", sort="created_desc")
```

---

### Example 6: Filter by status

**User:** "Are there any documents still being processed?"

**Tool call:**
```
list_documents(status="pending")
```

---

## Managing Tags

### Example 7: Adding a tag

**User:** "Mark the insurance document as important"

**Tool calls:**
1. First, find the document:
   ```
   search_documents(query="insurance", mode="keyword", limit=5)
   ```
2. Then tag it:
   ```
   add_tag(document_id=42, tag="important")
   ```

**Response:** `Tag 'important' added on document 42.`

---

### Example 8: Removing a tag

**User:** "Remove the 'review' tag from document 15"

**Tool call:**
```
remove_tag(document_id=15, tag="review")
```

**Response:** `Tag 'review' removed from document 15.`

---

## Uploading Documents

### Example 9: Upload via file path

**User:** "Add this invoice to my library"

**Tool call:**
```
upload_document(filename="invoice-2026-02.pdf", file_path="/home/user/downloads/invoice-2026-02.pdf")
```

**Response:**
```
Document uploaded successfully.
Filename: invoice-2026-02.pdf
Inbox path: /home/user/documents/_uploads/invoice-2026-02.pdf
Size: 245760 bytes
Status: Queued for processing
```

---

## Library Overview

### Example 10: Statistics

**User:** "How many documents do I have?"

**Tool call:**
```
get_library_stats()
```

**Response:**
```
# Library Statistics

## Documents
- Total: 142
- Processed: 138
- Pending: 2
- Error: 2

## Storage
- SQLite size: 45.3 MB

## Chunks
- Total: 2847

## Queue
- pending: 0
- running: 0
- completed: 140
- failed: 2
```
