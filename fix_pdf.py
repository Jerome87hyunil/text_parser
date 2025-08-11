#!/usr/bin/env python
"""
Utility script to fix corrupted Korean PDFs.
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdf_fixer import PDFFixer


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_pdf.py <input_pdf> [output_pdf]")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else input_pdf.replace('.pdf', '_fixed.pdf')
    
    if not Path(input_pdf).exists():
        print(f"Error: File not found: {input_pdf}")
        sys.exit(1)
    
    print(f"Fixing PDF: {input_pdf}")
    print(f"Output will be saved to: {output_pdf}")
    
    fixer = PDFFixer()
    if fixer.fix_pdf(input_pdf, output_pdf):
        print("PDF fixed successfully!")
    else:
        print("Failed to fix PDF.")
        sys.exit(1)


if __name__ == "__main__":
    main()