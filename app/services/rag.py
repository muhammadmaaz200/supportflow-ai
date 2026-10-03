import re
from pathlib import Path


class KnowledgeBase:

    def __init__(self, kb_dir=None):
        self.kb_dir = Path(kb_dir) if kb_dir else None

        # main.py expects kb.chunks
        self.chunks = []

        # compatibility
        self.documents = self.chunks

        # Load existing knowledge-base files
        if self.kb_dir:
            self._load_existing_files()

    # =========================================================
    # LOAD EXISTING FILES
    # =========================================================

    def _load_existing_files(self):

        if not self.kb_dir:
            return

        if not self.kb_dir.exists():
            self.kb_dir.mkdir(
                parents=True,
                exist_ok=True
            )
            return

        for file_path in sorted(
            self.kb_dir.iterdir()
        ):

            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in {
                ".txt",
                ".md",
                ".pdf"
            }:
                continue

            try:
                self.add_file(file_path)

            except Exception as exc:
                print(
                    f"Could not load "
                    f"{file_path.name}: {exc}"
                )

    # =========================================================
    # ADD FILE
    # =========================================================

    def add_file(self, file_path):

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Knowledge file not found: {file_path}"
            )

        suffix = file_path.suffix.lower()

        # -----------------------------------------------------
        # TXT / Markdown
        # -----------------------------------------------------

        if suffix in {".txt", ".md"}:

            text = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        # -----------------------------------------------------
        # PDF
        # -----------------------------------------------------

        elif suffix == ".pdf":

            text = self._extract_pdf_text(
                file_path
            )

        else:

            raise ValueError(
                "Unsupported knowledge-base file."
            )

        # Remove previous chunks for same file
        self._remove_file_chunks(
            file_path.name
        )

        # Add new chunks
        self.add_document(
            file_path.name,
            text
        )

    # =========================================================
    # PDF TEXT EXTRACTION
    # =========================================================

    def _extract_pdf_text(self, file_path):

        try:

            from pypdf import PdfReader

        except ImportError:

            raise RuntimeError(
                "pypdf is required for PDF files. "
                "Install it using: pip install pypdf"
            )

        reader = PdfReader(
            str(file_path)
        )

        pages = []

        for page in reader.pages:

            try:

                page_text = page.extract_text()

                if page_text:
                    pages.append(
                        page_text
                    )

            except Exception:
                continue

        return "\n\n".join(pages)

    # =========================================================
    # ADD DOCUMENT
    # =========================================================

    def add_document(
        self,
        filename,
        text
    ):

        if not text:
            return

        chunks = self._chunk_text(
            text
        )

        for chunk in chunks:

            chunk = chunk.strip()

            if not chunk:
                continue

            self.chunks.append(
                {
                    "filename": str(filename),
                    "text": chunk
                }
            )

    # =========================================================
    # REMOVE OLD FILE CHUNKS
    # =========================================================

    def _remove_file_chunks(
        self,
        filename
    ):

        self.chunks[:] = [
            chunk
            for chunk in self.chunks
            if chunk.get("filename")
            != filename
        ]

    # =========================================================
    # CHUNKING
    # =========================================================

    def _chunk_text(
        self,
        text,
        chunk_size=800
    ):

        if not text:
            return []

        # Normalize line endings
        text = re.sub(
            r"\r\n?",
            "\n",
            text
        )

        # Normalize spaces
        text = re.sub(
            r"[ \t]+",
            " ",
            text
        )

        # Normalize excessive blank lines
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        # -----------------------------------------------------
        # Split paragraphs
        # -----------------------------------------------------

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        paragraphs = [
            paragraph.strip()
            for paragraph in paragraphs
            if paragraph.strip()
        ]

        chunks = []

        current_chunk = ""

        for paragraph in paragraphs:

            # -------------------------------------------------
            # Normal paragraph
            # -------------------------------------------------

            if len(paragraph) <= chunk_size:

                if not current_chunk:

                    current_chunk = paragraph

                elif (
                    len(current_chunk)
                    + len(paragraph)
                    + 2
                    <= chunk_size
                ):

                    current_chunk += (
                        "\n\n"
                        + paragraph
                    )

                else:

                    chunks.append(
                        current_chunk
                    )

                    current_chunk = paragraph

            # -------------------------------------------------
            # Large paragraph
            # -------------------------------------------------

            else:

                if current_chunk:

                    chunks.append(
                        current_chunk
                    )

                    current_chunk = ""

                sentences = re.split(
                    r"(?<=[.!?])\s+",
                    paragraph
                )

                sentence_chunk = ""

                for sentence in sentences:

                    sentence = sentence.strip()

                    if not sentence:
                        continue

                    if not sentence_chunk:

                        sentence_chunk = sentence

                    elif (
                        len(sentence_chunk)
                        + len(sentence)
                        + 1
                        <= chunk_size
                    ):

                        sentence_chunk += (
                            " "
                            + sentence
                        )

                    else:

                        chunks.append(
                            sentence_chunk
                        )

                        sentence_chunk = sentence

                if sentence_chunk:

                    chunks.append(
                        sentence_chunk
                    )

        if current_chunk:

            chunks.append(
                current_chunk
            )

        return chunks

    # =========================================================
    # SEARCH
    # =========================================================

    def search(
        self,
        query,
        top_k=4
    ):

        if not query:
            return []

        query_words = self._clean_words(
            query
        )

        if not query_words:
            return []

        results = []

        for chunk in self.chunks:

            text = chunk.get(
                "text",
                ""
            )

            if not text:
                continue

            document_words = (
                self._clean_words(text)
            )

            if not document_words:
                continue

            common_words = (
                query_words
                & document_words
            )

            if not common_words:
                continue

            # Basic lexical relevance
            score = (
                len(common_words)
                / len(query_words)
            )

            results.append(
                {
                    "filename":
                        chunk.get(
                            "filename",
                            "Unknown"
                        ),

                    "text":
                        text,

                    "score":
                        round(
                            score,
                            4
                        )
                }
            )

        # Highest relevance first
        results.sort(
            key=lambda item:
                item["score"],
            reverse=True
        )

        return results[:top_k]

    # =========================================================
    # CLEAN WORDS
    # =========================================================

    def _clean_words(
        self,
        text
    ):

        text = text.lower()

        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text
        )

        stop_words = {
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",

            "a",
            "an",
            "and",
            "or",
            "but",

            "if",
            "then",
            "than",

            "to",
            "of",
            "for",
            "from",

            "in",
            "on",
            "at",
            "by",
            "with",

            "about",
            "into",
            "through",
            "during",
            "before",
            "after",

            "above",
            "below",

            "can",
            "could",
            "would",
            "should",

            "do",
            "does",
            "did",

            "have",
            "has",
            "had",

            "i",
            "me",
            "my",

            "we",
            "our",

            "you",
            "your",

            "they",
            "their",

            "what",
            "when",
            "where",
            "who",
            "why",
            "how"
        }

        return {
            word
            for word in words
            if word not in stop_words
        }

    # =========================================================
    # CLEAR
    # =========================================================

    def clear(self):

        self.chunks.clear()

        self.documents = self.chunks

    # =========================================================
    # COUNT
    # =========================================================

    def count(self):

        return len(
            self.chunks
        )