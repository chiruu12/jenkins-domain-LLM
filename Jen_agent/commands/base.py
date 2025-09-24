from abc import ABC, abstractmethod

class BaseCommand(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, session) -> None:
        pass
