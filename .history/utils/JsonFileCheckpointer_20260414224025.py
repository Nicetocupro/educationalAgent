import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver, JsonPlusSerializer
from langchain_core.runnables import RunnableConfig
import json
import os
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
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        parent_config = (
          {
            "configurable": {
              "thread_id": thread_id,
              "checkpoint_ns": checkpoint_ns,
              "checkpoint_id": parent_checkpoint_id,
          }
        }
          if parent_checkpoint_id
          else None
        )
            
        FilePath = self.base_dir + "/" + thread_id + "/" + checkpoint_ns + "/" + checkpoint_id + ".json"
        os.makedirs(os.path.dirname(FilePath), exist_ok=True)

        # channel_Value里面放着的都是HumanMessage类的对象，直接序列化会报错
        serialized_values = {}
        for channel, value in checkpoint["channel_values"].items():
            type_str, data_bytes = self.serde.dumps_typed(value)
            serialized_values[channel] = {
                "type": type_str,
                "data": data_bytes.decode("latin-1") # bytes → str 方便 JSON 存储
            }
            

        data = {
            "config": config,
            "checkpoint": checkpoint,
            "metadata": metadata,
            "parent_config": parent_config
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

