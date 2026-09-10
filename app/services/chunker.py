"""Split source files into chunks for the RAG pipeline.

`CodeChunker` turns a file's text into a list of `Chunk`s — contiguous,
optionally overlapping line ranges — that the rest of the pipeline embeds and
stores in the vector database. `Chunk` is the standard data structure passed
between the pipeline's stages.
"""

import re
from dataclasses import dataclass

# Fixed-size fallback: used when a language exposes no recognisable definitions,
# and to break down any single definition longer than the maximum. Kept
# module-local rather than in app/constants.py because nothing outside this
# service refers to them.
_FIXED_CHUNK_SIZE_LINES = 50
_FIXED_CHUNK_OVERLAP_LINES = 10
_MIN_CHUNK_LINES = 5
_MAX_CHUNK_LINES = 100

_PYTHON_DEFINITION = re.compile(r"^[ \t]*(?:async[ \t]+def|def|class)[ \t]+[A-Za-z_]")

_JS_TS_DEFINITION = re.compile(
    r"""
    ^[ \t]*
    (?:export[ \t]+)?
    (?:default[ \t]+)?
    (?:
        (?:abstract[ \t]+)?(?:class|interface|enum|type)[ \t]+[A-Za-z_$]
      |
        (?:async[ \t]+)?function\b
      |
        (?:get|set|static|public|private|protected|async)[ \t]+[A-Za-z_$][\w$]*[ \t]*\(
      |
        (?:const|let|var)[ \t]+[A-Za-z_$][\w$]*
        [ \t]*(?::[^=\n]+?)?=[ \t]*
        (?:async[ \t]+)?
        (?:
            function\b
          |
            \([^)\n]*\)[ \t]*(?::[^=\n]+?)?=>
          |
            [A-Za-z_$][\w$]*[ \t]*=>
        )
    )
    """,
    re.VERBOSE,
)

_GO_DEFINITION = re.compile(
    r"""
    ^[ \t]*
    (?:
        func[ \t]+(?:\([^)]*\)[ \t]*)?[A-Za-z_]
      |
        type[ \t]+[A-Za-z_]\w*[ \t]+(?:struct|interface)\b
    )
    """,
    re.VERBOSE,
)

_RUST_DEFINITION = re.compile(
    r"""
    ^[ \t]*
    (?:pub(?:\([^)]*\))?[ \t]+)?
    (?:
        (?:async[ \t]+)?(?:const[ \t]+)?(?:unsafe[ \t]+)?
        (?:extern[ \t]+"[^"]*"[ \t]+)?fn[ \t]+[A-Za-z_]
      |
        (?:struct|enum|trait|union)[ \t]+[A-Za-z_]
      |
        impl(?:[ \t]|<)
    )
    """,
    re.VERBOSE,
)

_JAVA_DEFINITION = re.compile(
    r"""
    ^[ \t]*
    (?:@[\w.]+(?:\([^)]*\))?[ \t]*)*
    (?:(?:public|private|protected|static|final|abstract|sealed|default)[ \t]+)*
    (?:
        (?:class|interface|enum|record)[ \t]+[A-Za-z_]
      |
        (?:[A-Za-z_][\w.<>\[\]]*[ \t]+)+
        [A-Za-z_]\w*[ \t]*\([^;{}]*\)[ \t]*(?:throws[ \t][\w.,\s]+?)?\{?[ \t]*$
    )
    """,
    re.VERBOSE,
)

_DEFINITION_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": _PYTHON_DEFINITION,
    "typescript": _JS_TS_DEFINITION,
    "javascript": _JS_TS_DEFINITION,
    "go": _GO_DEFINITION,
    "rust": _RUST_DEFINITION,
    "java": _JAVA_DEFINITION,
}

_LANGUAGE_ALIASES: dict[str, str] = {
    "python": "python",
    "py": "python",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "typescript",
    "javascript": "javascript",
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "rs": "rust",
    "java": "java",
}

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(_DEFINITION_PATTERNS)


def _canonical_language(language: str) -> str:
    """Normalise a language name to its canonical form.

    Case-insensitive, and resolves common aliases (``"ts"`` -> ``"typescript"``,
    ``"golang"`` -> ``"go"``).

    Raises:
        ValueError: If ``language`` maps to none of ``SUPPORTED_LANGUAGES``.
    """
    canonical = _LANGUAGE_ALIASES.get(language.strip().lower())
    if canonical is None:
        supported = ", ".join(sorted(SUPPORTED_LANGUAGES))
        raise ValueError(f"Unsupported language {language!r}; supported: {supported}")
    return canonical


@dataclass(frozen=True, slots=True)
class Chunk:
    """A contiguous slice of a source file, ready for embedding and storage.

    This is the standard unit exchanged across the RAG pipeline: the chunker
    produces it, the embedder consumes its ``content``, and the vector store
    persists it alongside its coordinates.

    Attributes:
        content: The slice's source text, newline-joined.
        file_path: Path of the file the slice came from, exactly as passed to
            ``CodeChunker.chunk_file``.
        start_line: 1-indexed line number of the first line, inclusive.
        end_line: 1-indexed line number of the last line, inclusive.
        language: Canonical language name (one of ``SUPPORTED_LANGUAGES``).
    """

    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str


class CodeChunker:
    """Splits source files into overlapping line ranges for the RAG pipeline.

    Strategy, applied per file:

    1. Align chunks to ``function``/``class`` definitions for the file's
       language, merging adjacent definitions while the result stays within
       ``max_chunk_lines``.
    2. Break any single definition longer than ``max_chunk_lines``, and any
       file whose language exposes no recognisable definitions, into
       fixed-size windows of ``fixed_chunk_size_lines`` lines overlapping by
       ``fixed_chunk_overlap_lines`` lines.
    3. Drop any resulting chunk shorter than ``min_chunk_lines`` lines.
    """

    def __init__(
        self,
        *,
        max_chunk_lines: int = _MAX_CHUNK_LINES,
        min_chunk_lines: int = _MIN_CHUNK_LINES,
        fixed_chunk_size_lines: int = _FIXED_CHUNK_SIZE_LINES,
        fixed_chunk_overlap_lines: int = _FIXED_CHUNK_OVERLAP_LINES,
    ) -> None:
        """Create a chunker, optionally overriding the default size thresholds.

        Args:
            max_chunk_lines: Hard upper bound on lines per chunk; larger
                definition segments are broken down with the fixed-size window.
            min_chunk_lines: Chunks shorter than this are dropped.
            fixed_chunk_size_lines: Window length for the fixed-size fallback.
            fixed_chunk_overlap_lines: Lines shared between consecutive
                fixed-size windows; must be smaller than
                ``fixed_chunk_size_lines``.

        Raises:
            ValueError: If the overlap is not smaller than the window length.
        """
        if fixed_chunk_overlap_lines >= fixed_chunk_size_lines:
            raise ValueError(
                "fixed_chunk_overlap_lines must be smaller than fixed_chunk_size_lines"
            )
        self._max_chunk_lines = max_chunk_lines
        self._min_chunk_lines = min_chunk_lines
        self._fixed_chunk_size_lines = fixed_chunk_size_lines
        self._fixed_chunk_overlap_lines = fixed_chunk_overlap_lines

    def chunk_file(self, file_path: str, content: str, language: str) -> list[Chunk]:
        """Split one source file into chunks, in source order.

        Args:
            file_path: Path recorded on every produced ``Chunk``. Not read from
                disk — the caller supplies ``content`` directly.
            content: Full text of the file.
            language: Source language. Case-insensitive; common aliases such as
                ``"ts"`` or ``"golang"`` are accepted. See
                ``SUPPORTED_LANGUAGES``.

        Returns:
            The file's chunks. Empty if the file is blank or yields only
            fragments shorter than ``min_chunk_lines``.

        Raises:
            ValueError: If ``language`` is not one of the supported languages.
        """
        canonical_language = _canonical_language(language)
        lines = content.splitlines()
        if not any(line.strip() for line in lines):
            return []
        definition_pattern = _DEFINITION_PATTERNS[canonical_language]
        definition_indices = [
            index for index, line in enumerate(lines) if definition_pattern.match(line)
        ]
        if not definition_indices:
            return self._fixed_size_chunks(
                lines, file_path, canonical_language, 0, len(lines)
            )
        return self._chunk_by_definitions(
            lines, definition_indices, file_path, canonical_language
        )

    def _chunk_by_definitions(
        self,
        lines: list[str],
        definition_indices: list[int],
        file_path: str,
        language: str,
    ) -> list[Chunk]:
        """Build chunks aligned to the file's definition boundaries."""
        chunks: list[Chunk] = []
        for span_start, span_end, oversized in self._plan_spans(
            lines, definition_indices
        ):
            if oversized:
                chunks.extend(
                    self._fixed_size_chunks(
                        lines, file_path, language, span_start, span_end
                    )
                )
            else:
                self._add_chunk(
                    chunks, lines, span_start, span_end, file_path, language
                )
        return chunks

    def _plan_spans(
        self, lines: list[str], definition_indices: list[int]
    ) -> list[tuple[int, int, bool]]:
        """Merge definition segments into planned chunk spans.

        Returns ``(start, end, oversized)`` triples over half-open line ranges.
        Adjacent segments are merged while the combined span fits within
        ``max_chunk_lines``. A segment that exceeds that on its own is returned
        with ``oversized=True`` so the caller breaks it down with the
        fixed-size window instead of storing it whole.
        """
        planned: list[tuple[int, int, bool]] = []
        merge_start: int | None = None
        merge_end = 0
        for segment_start, segment_end in self._definition_segments(
            lines, definition_indices
        ):
            if segment_end - segment_start > self._max_chunk_lines:
                if merge_start is not None:
                    planned.append((merge_start, merge_end, False))
                    merge_start = None
                planned.append((segment_start, segment_end, True))
            elif merge_start is None:
                merge_start, merge_end = segment_start, segment_end
            elif segment_end - merge_start > self._max_chunk_lines:
                planned.append((merge_start, merge_end, False))
                merge_start, merge_end = segment_start, segment_end
            else:
                merge_end = segment_end
        if merge_start is not None:
            planned.append((merge_start, merge_end, False))
        return planned

    def _definition_segments(
        self, lines: list[str], definition_indices: list[int]
    ) -> list[tuple[int, int]]:
        """Cut ``lines`` into half-open ``[start, end)`` segments at each definition.

        Lines preceding the first definition (imports, ``package`` or ``use``
        declarations) form the leading segment.
        """
        starts = definition_indices
        ends = [*definition_indices[1:], len(lines)]
        segments: list[tuple[int, int]] = []
        if starts[0] > 0:
            segments.append((0, starts[0]))
        segments.extend(zip(starts, ends, strict=True))
        return segments

    def _fixed_size_chunks(
        self,
        lines: list[str],
        file_path: str,
        language: str,
        start: int,
        end: int,
    ) -> list[Chunk]:
        """Window ``lines[start:end]`` into overlapping fixed-size chunks."""
        chunks: list[Chunk] = []
        step = self._fixed_chunk_size_lines - self._fixed_chunk_overlap_lines
        window_start = start
        while window_start < end:
            window_end = min(window_start + self._fixed_chunk_size_lines, end)
            self._add_chunk(
                chunks, lines, window_start, window_end, file_path, language
            )
            if window_end == end:
                break
            window_start += step
        return chunks

    def _add_chunk(
        self,
        chunks: list[Chunk],
        lines: list[str],
        start: int,
        end: int,
        file_path: str,
        language: str,
    ) -> None:
        """Append a ``Chunk`` for ``lines[start:end]``, unless it is too short."""
        if end - start < self._min_chunk_lines:
            return
        chunks.append(
            Chunk(
                content="\n".join(lines[start:end]),
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                language=language,
            )
        )
