from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path

import chromadb
from openai import OpenAI
from pypdf import PdfReader


HEADING_PATTERN = re.compile(r"^(?:##\s+Day|Chapter\s+\d+:)", re.IGNORECASE)


def read_pdf(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return pages


def split_into_chunks(pages: list[str], source_name: str) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    current_chapter = "Introduction"

    for page_index, page_text in enumerate(pages, start=1):
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        buffer: list[str] = []

        for line in lines:
            if HEADING_PATTERN.match(line):
                if buffer:
                    chunks.append(
                        {
                            "chapter": current_chapter,
                            "text": " ".join(buffer).strip(),
                            "source": source_name,
                            "page": str(page_index),
                        }
                    )
                    buffer = []
                current_chapter = line
                continue

            buffer.append(line)
            if len(" ".join(buffer)) >= 700:
                chunks.append(
                    {
                        "chapter": current_chapter,
                        "text": " ".join(buffer).strip(),
                        "source": source_name,
                        "page": str(page_index),
                    }
                )
                buffer = []

        if buffer:
            chunks.append(
                {
                    "chapter": current_chapter,
                    "text": " ".join(buffer).strip(),
                    "source": source_name,
                    "page": str(page_index),
                }
            )

    return chunks


def embed_chunks(chunks: list[dict[str, str]], embedding_model: str, collection_name: str, persist_dir: Path) -> None:
    api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)
    chroma_client = chromadb.PersistentClient(path=str(persist_dir))
    collection = chroma_client.get_or_create_collection(name=collection_name)

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for chunk in chunks:
        document = chunk["text"]
        digest = hashlib.sha1(f"{chunk['chapter']}::{document}".encode("utf-8")).hexdigest()
        embedding = client.embeddings.create(
            model=embedding_model,
            input=document,
        ).data[0].embedding

        ids.append(digest)
        documents.append(document)
        metadatas.append(
            {
                "chapter": chunk["chapter"],
                "source": chunk["source"],
                "page": chunk["page"],
            }
        )
        embeddings.append(embedding)

    if ids:
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest The Luma Guide PDF into Chroma.")
    parser.add_argument("pdf", type=Path, help="Path to the source PDF")
    parser.add_argument("--collection", default=os.getenv("LUMA_COLLECTION_NAME", "luma-guide"))
    parser.add_argument("--persist-dir", type=Path, default=Path(os.getenv("LUMA_VECTORSTORE_DIR", "./vectorstore")))
    parser.add_argument("--embedding-model", default=os.getenv("LUMA_EMBEDDING_MODEL", "text-embedding-3-small"))
    args = parser.parse_args()

    pages = read_pdf(args.pdf)
    chunks = split_into_chunks(pages, source_name=args.pdf.name)
    embed_chunks(
        chunks=chunks,
        embedding_model=args.embedding_model,
        collection_name=args.collection,
        persist_dir=args.persist_dir,
    )

    print(f"Ingested {len(chunks)} chunks from {args.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
