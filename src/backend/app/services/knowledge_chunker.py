"""Knowledge Document Chunking Service (WS-13, ADR 0011).

Provides sliding-window text chunking strategies for tenant knowledge documents,
preserving contextual continuity across chunk boundaries and building structured metadata.
"""

import re
from typing import Any


class KnowledgeChunker:
    """Sliding-window text chunker for tenant RAG document processing."""

    def __init__(
        self,
        default_chunk_size: int = 600,
        default_chunk_overlap: int = 100,
    ) -> None:
        """Initialize chunker with configurable default window parameters."""
        if default_chunk_size < 50:
            raise ValueError("chunk_size must be at least 50 characters")
        if default_chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if default_chunk_overlap >= default_chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")

        self.default_chunk_size = default_chunk_size
        self.default_chunk_overlap = default_chunk_overlap

    def chunk_text(
        self,
        text: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Split source document text into structured overlapping chunks.

        Args:
            text: The full raw document text.
            chunk_size: Optional character target limit per chunk.
            chunk_overlap: Optional overlapping character count.
            extra_metadata: Base metadata dictionary to attach to every chunk.

        Returns:
            List of chunk dict payloads with keys:
            - chunk_index: int
            - chunk_content: str
            - metadata_jsonb: dict[str, Any]
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            return []

        eff_chunk_size = chunk_size if chunk_size is not None else self.default_chunk_size
        eff_chunk_overlap = (
            chunk_overlap if chunk_overlap is not None else self.default_chunk_overlap
        )

        if eff_chunk_size < 50:
            raise ValueError("chunk_size must be at least 50 characters")
        if eff_chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if eff_chunk_overlap >= eff_chunk_size:
            eff_chunk_overlap = max(0, eff_chunk_size - 50)

        step = eff_chunk_size - eff_chunk_overlap

        # Split text into natural boundary blocks (paragraphs or sentence groupings)
        text_length = len(cleaned_text)
        chunks: list[dict[str, Any]] = []

        if text_length <= eff_chunk_size:
            chunk_meta = dict(extra_metadata or {})
            chunk_meta.update(
                {
                    "start_char": 0,
                    "end_char": text_length,
                    "char_count": text_length,
                    "word_count": len(cleaned_text.split()),
                }
            )
            return [
                {
                    "chunk_index": 0,
                    "chunk_content": cleaned_text,
                    "metadata_jsonb": chunk_meta,
                }
            ]

        # Use natural boundary sliding window
        start_idx = 0
        chunk_index = 0

        while start_idx < text_length:
            end_idx = min(start_idx + eff_chunk_size, text_length)

            # If not at document end, attempt to find a clean boundary (newline or sentence break)
            if end_idx < text_length:
                boundary = self._find_best_boundary(cleaned_text, start_idx, end_idx)
                if boundary > start_idx + 50:  # Ensure chunk is not truncated too small
                    end_idx = boundary

            chunk_str = cleaned_text[start_idx:end_idx].strip()
            if chunk_str:
                chunk_meta = dict(extra_metadata or {})
                chunk_meta.update(
                    {
                        "start_char": start_idx,
                        "end_char": end_idx,
                        "char_count": len(chunk_str),
                        "word_count": len(chunk_str.split()),
                    }
                )
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "chunk_content": chunk_str,
                        "metadata_jsonb": chunk_meta,
                    }
                )
                chunk_index += 1

            if end_idx >= text_length:
                break

            # Advance window by step relative to end_idx or start_idx
            next_start = end_idx - eff_chunk_overlap
            if next_start <= start_idx:
                next_start = start_idx + step
            start_idx = next_start

        return chunks

    def _find_best_boundary(self, text: str, start_idx: int, end_idx: int) -> int:
        """Find best paragraph, sentence, or whitespace boundary within search window."""
        sub = text[start_idx:end_idx]

        # Look for double newline (paragraph break)
        para_match = [m.end() for m in re.finditer(r"\n\s*\n", sub)]
        if para_match:
            return start_idx + para_match[-1]

        # Look for sentence end (.!? followed by space or newline)
        sentence_match = [m.end() for m in re.finditer(r"[.!?]\s", sub)]
        if sentence_match:
            return start_idx + sentence_match[-1]

        # Look for single newline
        newline_match = [m.end() for m in re.finditer(r"\n", sub)]
        if newline_match:
            return start_idx + newline_match[-1]

        # Look for space
        space_match = [m.end() for m in re.finditer(r"\s", sub)]
        if space_match:
            return start_idx + space_match[-1]

        return end_idx
