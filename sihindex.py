"""
sihindex.py
===========
LEGAL & SOP DOCUMENT INDEXER FOR RAG ENGINE

Reads all PDF documents from the `./legal_docs` directory, splits them into
manageable text chunks, generates vector embeddings via Ollama, and stores 
them in `./legal_vector_db`.

This feeds directly into `sihsoprag.py` and `sihdashboard.py`.
"""

import os
import time
import gc
import warnings

# Suppress harmless LangChain community deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Configuration — aligned with sihdashboard.py & sihsoprag.py
PDF_FOLDER = "./legal_docs"
VECTOR_DB_DIR = "./legal_vector_db"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150
BATCH_SIZE = 100

start_time = time.time()

# Ensure directories exist
if not os.path.exists(PDF_FOLDER):
    os.makedirs(PDF_FOLDER)
    print(f"📁 Created folder '{PDF_FOLDER}'. Please drop your SOP / Legal PDFs here.")

embeddings = OllamaEmbeddings(model=EMBED_MODEL)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, 
    chunk_overlap=CHUNK_OVERLAP
)

print("⚡ Starting SIH Legal & SOP Indexer...")

pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith(".pdf")]

if not pdf_files:
    print(f"\n⚠️ No PDF files found in '{PDF_FOLDER}'.")
    print(f"Please place your PDF files inside '{PDF_FOLDER}' and run this script again.")
    exit()

vectorstore = None
total_chunks_indexed = 0

for idx, file_name in enumerate(pdf_files, 1):
    pdf_path = os.path.join(PDF_FOLDER, file_name)
    print(f"\n[{idx}/{len(pdf_files)}] Reading: {file_name}")
    
    try:
        loader = PyMuPDFLoader(pdf_path)
        docs = loader.load()
        chunks = text_splitter.split_documents(docs)
        
        if not chunks:
            print(f"  ⚠️ Skipped: No readable text found (Scanned Image or Empty PDF).")
            continue

        print(f"  -> Extracted {len(chunks)} text chunks. Indexing in safe batches...")

        # Process in batches to prevent context/HTTP timeout issues in Ollama
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            
            if vectorstore is None:
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    persist_directory=VECTOR_DB_DIR
                )
            else:
                vectorstore.add_documents(documents=batch)
            
            time.sleep(0.05)

        total_chunks_indexed += len(chunks)
        print(f"  ✅ Finished indexing: {file_name}")

    except Exception as e:
        print(f"  ❌ Error processing {file_name}: {e}")

    # Explicit memory release per PDF
    if 'docs' in locals(): del docs
    if 'chunks' in locals(): del chunks
    gc.collect()

total_duration = round(time.time() - start_time, 2)
print(f"\n🎉 Done! Indexed {total_chunks_indexed} total chunks into '{VECTOR_DB_DIR}' in {total_duration}s.")