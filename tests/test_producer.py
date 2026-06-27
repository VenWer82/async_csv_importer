import pytest

from src.services.producer import producer


class ChunkedUploadFile:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self._position = 0
        self.filename = "sample.csv"

    async def read(self, size: int) -> bytes:
        if self._position >= len(self._chunks):
            return b""

        chunk = self._chunks[self._position]
        self._position += 1
        return chunk


@pytest.mark.asyncio
async def test_producer_yields_complete_lines_and_preserves_remainder() -> None:
    file = ChunkedUploadFile([b"alpha", b"\nbe", b"ta", b"\n", b"gam", b"ma"])

    lines = [line async for line in producer(file, 3)]

    assert lines == ["alpha", "beta", "gamma"]


@pytest.mark.asyncio
async def test_producer_skips_empty_lines_and_handles_empty_file() -> None:
    file = ChunkedUploadFile([b"\n", b"first\n\n", b"second\n"])
    assert [line async for line in producer(file, 2)] == ["first", "second"]

    empty_file = ChunkedUploadFile([])
    assert [line async for line in producer(empty_file, 4)] == []
