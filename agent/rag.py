from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import chromadb
from openai import AsyncOpenAI

from agent.config import settings


@dataclass
class RetrievedChunk:
    chapter: str
    text: str
    source: str
    score: float


class ReflectRetriever:
    def __init__(
        self,
        persist_dir: Path | None = None,
        collection_name: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.persist_dir = persist_dir or settings.vectorstore_dir
        self.collection_name = collection_name or settings.collection_name
        self.embedding_model = embedding_model or settings.embedding_model
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        self.openai: AsyncOpenAI | None = None

    async def _embed(self, text: str) -> list[float]:
        if self.openai is None:
            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required for retrieval.")
            self.openai = AsyncOpenAI(api_key=api_key)

        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def search(self, query: str, limit: int = 4) -> list[RetrievedChunk]:
        if self.collection.count() == 0:
            return []

        embedding = await self._embed(query)
        result = await asyncio.to_thread(
            self.collection.query,
            query_embeddings=[embedding],
            n_results=limit,
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        chunks: list[RetrievedChunk] = []

        for document, metadata, distance in zip(documents, metadatas, distances):
            chapter = (metadata or {}).get("chapter", "Unknown chapter")
            source = (metadata or {}).get("source", "The Fitness Journal")
            score = 1 - float(distance) if distance is not None else 0.0
            chunks.append(
                RetrievedChunk(
                    chapter=chapter,
                    text=document,
                    source=source,
                    score=score,
                )
            )
        return chunks

    async def search_as_context(self, query: str, limit: int = 4) -> str:
        chunks = await self.search(query=query, limit=limit)
        if not chunks:
            return ""

        sections = []
        for chunk in chunks:
            sections.append(
                f"[{chunk.chapter}] {chunk.text}"
            )
        return "\n\n".join(sections)
