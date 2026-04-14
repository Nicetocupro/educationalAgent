import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver, JsonPlusSerializer
from langchain_core.runnables import RunnableConfig
import json
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

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

    def __init__(self, serde: SerializerProtocol | None = None, base_dir: str = "./checkpoints"):
        super.__init__(serde=serde)
        self.base_dir = path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """put的作用是将checkpoint写入json中"""
        c = checkpoint.copy()

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = checkpoint["id"]

        FilePath = self.base_dir + "/" + thread_id + "/" + checkpoint_ns + "/" + checkpoint_id + ".json"

        data = {
            "config": config,
            "checkpoint": checkpoint,
            "metadata": metadata,
            "parent_config": config["configurable"].get("checkpoint_id")
        }
        with open(FilePath, "w") as f:
            json.dump(data, f, indent=2)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
    
    def delete_thread(self, thread_id: str) -> None:
        
    def get_next_version(self, current: str | None, channel: None) -> str:
@contextlib.asynccontextmanager
async def generate_checkpointer():
    """Yield a BaseCheckpointSaver, open for the duration of the server."""

