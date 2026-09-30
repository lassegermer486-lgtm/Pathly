from abc import ABC, abstractmethod
from pathlib import Path


class RegistryAdapter(ABC):
    def __init__(self, state_code: str, config: dict):
        self.state_code = state_code
        self.config = config

    @abstractmethod
    def fetch(self):
        raise NotImplementedError

    def snapshot(self, filename: str, content: bytes | str) -> None:
        """
        Store a raw copy of a fetched source for provenance/debugging.
        Only happens when the run was started with --save (`_raw_dir` set);
        a normal run keeps everything in memory.
        """
        raw_dir = self.config.get("_raw_dir")
        if not raw_dir:
            return
        path = Path(raw_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
