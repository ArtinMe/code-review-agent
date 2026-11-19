import threading

visits = 0


def record_visit() -> None:
    global visits
    visits += 1


def simulate(n_threads: int = 8, per_thread: int = 10_000) -> int:
    threads = [
        threading.Thread(target=lambda: [record_visit() for _ in range(per_thread)])
        for _ in range(n_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return visits
