"""
PDF Processing Script for Trend Reports
Processes large PDF collections, extracts text (with OCR fallback), and stores in ChromaDB
"""

import os
from pathlib import Path
from tqdm import tqdm
import chromadb
from fastembed import TextEmbedding
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from dotenv import load_dotenv
import logging
import hashlib
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration with path validation
_reports_folder_raw = os.getenv("REPORTS_FOLDER", "2025 Trend Reports")
REPORTS_FOLDER = Path(_reports_folder_raw).resolve()

# Validate that the path doesn't escape project directory (security measure)
try:
    REPORTS_FOLDER.relative_to(Path.cwd().parent)  # Allow one level up for backend folder
except ValueError:
    logger.error(f"REPORTS_FOLDER must be within project directory: {_reports_folder_raw}")
    logger.error("This is a security measure to prevent directory traversal attacks")
    raise ValueError(f"Invalid REPORTS_FOLDER configuration: {_reports_folder_raw}")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
OVERLAP = int(os.getenv("OVERLAP", "150"))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_data")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF with OCR fallback for scanned documents

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as string
    """
    logger.info(f"Extracting text from: {pdf_path.name}")

    # Try pdfplumber first (faster for text-based PDFs)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(
                (page.extract_text() or "") for page in pdf.pages
            )
            if text.strip():
                logger.info(f"✓ Extracted {len(text)} characters via pdfplumber")
                return text
    except Exception as e:
        logger.warning(f"pdfplumber failed for {pdf_path.name}: {e}")

    # Fallback to OCR for scanned PDFs
    logger.info(f"Attempting OCR for {pdf_path.name}...")
    try:
        images = convert_from_path(pdf_path, dpi=200)
        text = "\n".join(
            pytesseract.image_to_string(img) for img in images
        )
        logger.info(f"✓ Extracted {len(text)} characters via OCR")
        return text
    except Exception as e:
        logger.error(f"OCR failed for {pdf_path.name}: {e}")
        return ""


def chunk_text_with_metadata(
    text: str,
    filename: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP
) -> list:
    """
    Split text into overlapping chunks with metadata

    Args:
        text: Full text to chunk
        filename: Source PDF filename
        chunk_size: Characters per chunk
        overlap: Overlapping characters between chunks

    Returns:
        List of dicts with 'text' and 'metadata'
    """
    chunks = []
    start = 0

    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk_text = text[start:end].strip()

        if chunk_text:  # Skip empty chunks
            # Estimate page number (rough: ~3000 chars per page)
            page_estimate = (start // 3000) + 1

            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "filename": filename,
                    "page": page_estimate,
                    "char_start": start,
                    "char_end": end
                }
            })

        start += chunk_size - overlap

    return chunks


def process_all_pdfs():
    """
    Main processing function:
    1. Finds all PDFs in REPORTS_FOLDER
    2. Extracts text (with OCR fallback)
    3. Chunks text with metadata
    4. Creates embeddings
    5. Stores in ChromaDB
    """
    logger.info("=" * 60)
    logger.info("Starting PDF Processing Pipeline")
    logger.info("=" * 60)

    # Initialize
    logger.info("Loading FastEmbed model (BAAI/bge-small-en-v1.5)...")
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    logger.info(f"Connecting to ChromaDB at: {CHROMA_DB_PATH}")
    chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Clear existing collection
    try:
        chroma.delete_collection(name="trend_reports")
        logger.info("✓ Cleared existing trend_reports collection")
    except:
        logger.info("No existing collection to clear")

    # Create collection with metadata for versioning
    collection = chroma.get_or_create_collection(
        name="trend_reports",
        metadata={
            "description": "2025 Advertising Trend Reports - Vector Search Database",
            "version": "1.0",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "chunk_size": str(CHUNK_SIZE),
            "overlap": str(OVERLAP),
            "model": "BAAI/bge-small-en-v1.5"
        }
    )

    # Find PDFs
    reports_path = REPORTS_FOLDER  # Already a Path object from config
    if not reports_path.exists():
        logger.error(f"Reports folder not found: {REPORTS_FOLDER}")
        logger.info("Please create the folder and add your PDF files")
        return

    pdf_files = list(reports_path.glob("*.pdf"))

    if not pdf_files:
        logger.error(f"No PDF files found in {REPORTS_FOLDER}")
        return

    total_size = sum(f.stat().st_size for f in pdf_files) / 1024**2
    logger.info(f"Found {len(pdf_files)} PDF files ({total_size:.1f} MB)")
    logger.info(f"Chunk settings: size={CHUNK_SIZE}, overlap={OVERLAP}")
    logger.info("=" * 60)

    # Process each PDF
    all_chunks = []
    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            logger.warning(f"⚠ No text extracted from {pdf_path.name}")
            continue

        chunks = chunk_text_with_metadata(text, pdf_path.name)
        all_chunks.extend(chunks)
        logger.info(f"  → Created {len(chunks)} chunks from {pdf_path.name}")

    if not all_chunks:
        logger.error("No text chunks created. Check your PDFs.")
        return

    logger.info("=" * 60)
    logger.info(f"Total chunks created: {len(all_chunks)}")
    logger.info("Creating embeddings and storing in ChromaDB...")
    logger.info("=" * 60)

    # Batch process embeddings
    batch_size = 100
    for i in tqdm(range(0, len(all_chunks), batch_size), desc="Embedding batches"):
        batch = all_chunks[i:i+batch_size]

        # Extract texts and create embeddings
        texts = [c["text"] for c in batch]
        embeddings = list(embedder.embed(texts))

        # Generate content-based IDs using SHA256 hashing (prevents collisions)
        ids = [
            hashlib.sha256(
                f"{c['metadata']['filename']}_{c['metadata']['char_start']}_{c['metadata']['char_end']}".encode()
            ).hexdigest()[:16]
            for c in batch
        ]

        # Store in ChromaDB (embeddings are already lists from fastembed)
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=[c["metadata"] for c in batch],
            ids=ids
        )

    logger.info("=" * 60)
    logger.info("✅ Processing Complete!")
    logger.info(f"  • Processed {len(pdf_files)} PDF files")
    logger.info(f"  • Created {len(all_chunks)} text chunks")
    logger.info(f"  • Stored in ChromaDB at: {CHROMA_DB_PATH}")
    logger.info("=" * 60)
    logger.info("Next steps:")
    logger.info("  1. Test the API: uvicorn main:app --reload")
    logger.info("  2. Test search: curl -X POST http://localhost:8000/search \\")
    logger.info('       -H "Content-Type: application/json" \\')
    logger.info('       -d \'{"query": "AI trends", "top_k": 3}\'')
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        process_all_pdfs()
    except KeyboardInterrupt:
        logger.info("\n⚠ Processing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}", exc_info=True)
