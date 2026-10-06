import os
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

print("[*] Initializing Vector Database Pipeline...")

# Relative paths — portable, no hardcoded drive letters
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
kb_dir = os.path.join(BASE_DIR, "knowledge_base")
db_dir = os.path.join(BASE_DIR, "chroma_db_storage")

db_client = chromadb.PersistentClient(path=db_dir)

try:
    collection = db_client.get_or_create_collection(name="cybersec_intelligence_pool")
    print("[+] Connected to ChromaDB collection.")
except Exception as e:
    print(f"[-] Database initialization failed: {str(e)}")
    exit()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)

def ingest_file_to_vector_db(file_name, source_tag):
    file_path = os.path.join(kb_dir, file_name)
    if not os.path.exists(file_path):
        print(f"[-] Source file missing: {file_name}. Skipping.")
        return

    print(f"[*] Reading and chunking: {file_name}...")
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    chunks = text_splitter.split_text(raw_text)
    print(f"[+] Chunks generated from {file_name}: {len(chunks)}")

    for idx, chunk in enumerate(chunks):
        chunk_id = f"{source_tag}_chunk_{idx}"
        collection.add(
            documents=[chunk],
            metadatas=[{"source": source_tag}],
            ids=[chunk_id]
        )
    print(f"[+] Indexed {file_name}.")

if __name__ == "__main__":
    print("\n--- Starting Ingestion ---")
    ingest_file_to_vector_db("cve_threat_intel.txt", "CVE_ThreatIntel")
    ingest_file_to_vector_db("darkweb_fraud_intel.txt", "DarkWeb_FraudIntel")
    ingest_file_to_vector_db("safety_bypass_intel.txt", "AdvBench_SafetyBypass")
    ingest_file_to_vector_db("lab_scope.txt", "Lab_ScopeDefinition")

    print(f"\n[+] Ingestion complete. Data stored in {db_dir}")