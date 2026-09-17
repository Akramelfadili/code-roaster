import pytest

from app.services.chunker import CodeChunker

_FOO_LINES = ["def foo():", *(f"    a{i} = {i}" for i in range(9))]
_BAR_LINES = ["def bar():", *(f"    b{i} = {i}" for i in range(9))]
_TWO_FUNCTION_SOURCE = "\n".join(_FOO_LINES + _BAR_LINES)


class TestChunkFile:
    def test_returns_chunks_in_source_order(self) -> None:
        chunker = CodeChunker(max_chunk_lines=15)

        chunks = chunker.chunk_file("two_funcs.py", _TWO_FUNCTION_SOURCE, "python")

        assert len(chunks) == 2
        assert chunks[0].start_line < chunks[1].start_line
        assert "def foo" in chunks[0].content
        assert "def bar" in chunks[1].content

    def test_definition_aligned_chunking_splits_at_boundaries(self) -> None:
        chunker = CodeChunker(max_chunk_lines=15)

        chunks = chunker.chunk_file("two_funcs.py", _TWO_FUNCTION_SOURCE, "python")

        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 10
        assert chunks[0].content.splitlines()[0] == "def foo():"
        assert chunks[1].start_line == 11
        assert chunks[1].end_line == 20
        assert chunks[1].content.splitlines()[0] == "def bar():"

    def test_fixed_size_fallback_used_when_no_definitions_found(self) -> None:
        chunker = CodeChunker(
            fixed_chunk_size_lines=10, fixed_chunk_overlap_lines=3, min_chunk_lines=3
        )
        content = "\n".join(f"x{i} = {i}" for i in range(22))

        chunks = chunker.chunk_file("no_defs.py", content, "python")

        assert [(c.start_line, c.end_line) for c in chunks] == [
            (1, 10),
            (8, 17),
            (15, 22),
        ]

    def test_chunks_under_min_chunk_lines_are_dropped(self) -> None:
        chunker = CodeChunker(
            fixed_chunk_size_lines=10, fixed_chunk_overlap_lines=0, min_chunk_lines=5
        )
        content = "\n".join(f"x{i} = {i}" for i in range(12))

        chunks = chunker.chunk_file("short_tail.py", content, "python")

        assert len(chunks) == 1
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 10

    def test_blank_file_returns_empty_list(self) -> None:
        chunker = CodeChunker()

        assert chunker.chunk_file("blank.py", "\n \n\t\n", "python") == []

    def test_unsupported_language_raises_value_error(self) -> None:
        chunker = CodeChunker()

        with pytest.raises(ValueError, match="Unsupported language"):
            chunker.chunk_file("main.cob", "IDENTIFICATION DIVISION.", "cobol")
