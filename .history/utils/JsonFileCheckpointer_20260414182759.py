import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver, JsonPlusSerializer
from langchain_core.runnables import RunnableConfig
from os import path

class MyJsonFileCheckpointer(BaseCheckpointSaver):
    """
    把每个 checkpoint 存成一个 JSON 文件。
    目录结构：
      {base_dir}/
        {thread_id}/
          {checkpoint_ns}/
            {checkpoint_id}.json      ← checkpoint 主体
            writes_{checkpoint_id}.json  ← pending writes
    """

    def __init__(self, base_dir: str = "./checkpoints"):
        super.__init__(serde=JsonPlusSerializer())
        self.base_dir = path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)



@contextlib.asynccontextmanager
async def generate_checkpointer():
    """Yield a BaseCheckpointSaver, open for the duration of the server."""

