import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver
from 
class MyJsonCheckpointer(BaseCheckpointSaver):
    def __init__(self, *, serde = None):
        super().__init__(serde=serde)

    @contextlib.asynccontextmanager
    async def aget(self, config: )
