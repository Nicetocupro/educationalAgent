import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.runnables import RunnableConfig

class MyJsonCheckpointer(BaseCheckpointSaver):
    def __init__(self, *, serde = None):
        super().__init__(serde=serde)

    @contextlib.asynccontextmanager
    async def aget(self, config: RunnableConfig):
        yield

@contextlib.asynccontextmanager
async def generate_checkpointer():
    """Yield a BaseCheckpointSaver, open for the duration of the server."""
    
