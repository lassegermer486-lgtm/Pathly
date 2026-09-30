from .base import RegistryAdapter

class StubAdapter(RegistryAdapter):
    def fetch(self):
        raise NotImplementedError(
            f"{self.state_code}: registry source is configured, "
            "but its state-specific parser has not been implemented yet."
        )
