from abc import ABC, abstractmethod

class RegistryAdapter(ABC):
    def __init__(self, state_code: str, config: dict):
        self.state_code = state_code
        self.config = config

    @abstractmethod
    def fetch(self):
        raise NotImplementedError
