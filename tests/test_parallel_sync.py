"""Parallel sync helper tests."""

from qmt_quant.core.sync.parallel import iter_chunks, run_batches_parallel


def test_iter_chunks():
    assert iter_chunks(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]


def test_run_batches_parallel_serial():
    calls: list[str] = []

    def worker(chunk):
        calls.extend(chunk)
        return len(chunk)

    results = run_batches_parallel(
        [["a", "b"], ["c"]],
        concurrency=1,
        job_id=None,
        worker=worker,
    )
    assert results == [2, 1]
    assert calls == ["a", "b", "c"]
