---
name: nano-pdf
description: Edit PDFs with natural-language instructions using the nano-pdf CLI.
whenToUse: |
  When the user wants to edit or manipulate PDF files using natural language instructions.
homepage: https://pypi.org/project/nano-pdf/
metadata: {"clawdbot":{"emoji":"📄","requires":{"bins":["nano-pdf"]},"install":[{"id":"uv","kind":"uv","package":"nano-pdf","bins":["nano-pdf"],"label":"Install nano-pdf (uv)"}]}}
---

# nano-pdf

Use `nano-pdf` to apply edits to a specific page in a PDF using a natural-language instruction.

## Quick start

```bash
nano-pdf edit deck.pdf 1 "Change the title to 'Q3 Results' and fix the typo in the subtitle"
```

## Examples

**Update a slide title:**
```bash
nano-pdf edit presentation.pdf 1 "Change the title to ‘Q3 Revenue Report’"
```
```
Edited page 1 of presentation.pdf -> presentation_edited.pdf
```

**Fix a typo on page 3:**
```bash
nano-pdf edit contract.pdf 3 "Replace ‘Janury’ with ‘January’"
```
```
Edited page 3 of contract.pdf -> contract_edited.pdf
```

**Redact sensitive info:**
```bash
nano-pdf edit invoice.pdf 1 "Replace the phone number with ‘[REDACTED]’"
```
```
Edited page 1 of invoice.pdf -> invoice_edited.pdf
```

Notes:
- Page numbers are 0-based or 1-based depending on the tool’s version/config; if the result looks off by one, retry with the other.
- Always sanity-check the output PDF before sending it out.
