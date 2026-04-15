import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver, JsonPlusSerializer
from langchain_core.runnables import RunnableConfig
import json
from typing import Sequence
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

from os import Path

class MyJsonFileCheckpointer(BaseCheckpointSaver):
    """
    把每个 checkpoint 存成一个 JSON 文件。
    目录结构：
      {base_dir}/
        {thread_id}/
          {checkpoint_ns}/
            {checkpoint_id}.json      ← checkpoint 主体
            writes_{checkpoint_id}_{task_id}_{idx}.json  ← pending writes
            多文件 防止并发写冲突
    """

    def __init__(self, serde: SerializerProtocol | None = None, base_dir: str = "./checkpoints"):
        super().__init__(serde=serde)
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> dict:
        """把 channel_values 里的 LangChain 对象序列化为可 JSON 存储的格式"""
        c = dict(checkpoint) # 浅拷贝
        serialized_values = {}
        
        # channel_Value里面放着的都是HumanMessage类的对象，直接序列化会报错    
        for channel, value in checkpoint["channel_values"].items():
            type_str, data_bytes = self.serde.dumps_typed(value)
            serialized_values[channel] = {
                "type": type_str,
                "data": data_bytes.decode("latin-1") # bytes → str 方便 JSON 存储
            }
        c["channel_values"] = serialized_values

        serialized_sends = []
        for send in checkpoint.get("pending_sends", []):
            type_str, data_bytes = self.serde.dumps_typed(send)
            serialized_sends.append({
                "type": type_str,
                "data": data_bytes.decode("latin-1"),
            })
        c["pending_sends"] = serialized_sends
        return c
    
    def _deserialize_checkpoint(self, data: dict) -> dict:
      c = dict(data)
      restored = {}
      for channel, v in data["channel_values"].items():
          restored[channel] = self.serde.loads_typed(
            (v["type"], v["data"].encode("latin-1"))
          )
      c["channel_values"] = restored

      c["pending_sends"] = [
          self.serde.loads_typed((s["type"], s["data"].encode("latin-1")))
          for s in data.get("pending_sends", [])
      ]
      
      return c
    
    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """put的作用是将checkpoint写入json中"""

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
            
        data = {
            "config": {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            "checkpoint": self._serialize_checkpoint(checkpoint),
            "metadata": dict(metadata),
            "parent_config": parent_config
        }

        FilePath = self.base_dir / thread_id / checkpoint_ns / f"{checkpoint_id}.json"
        FilePath.parent.mkdir(parents=True, exist_ok=True)

        with open(FilePath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        "Get a checkpoint tuple from the in-memory storage."

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        path = self.base_dir / thread_id / checkpoint_ns
        if checkpoint_id := get_checkpoint_id(config):
            file_path = path / f"{checkpoint_id}.json"
        else:
            files = sorted(
                [f for f in path.glob("*.json") if not f.name.startswith("writes_")],
                reverse=True
            )
            file_path = files[0] if files else None

        if not file_path or not file_path.exists():
            return None
        
        data = json.loads(file_path.read_text())
        checkpoint_id = data["config"]["configurable"]["checkpoint_id"]
        
        pending_writes = []
        writes_files = sorted(
            path.glob(f"writes_{checkpoint_id}_*.json"),
            key=lambda p: int(p.stem.rsplit("_", 1)[-1])  # 按末尾 idx 数字排序
        )

        for writes_file in writes_files:
            w = json.loads(writes_file.read_text())
            value = self.serde.loads_typed((w["value_type"], w["value_data"].encode("latin-1")))
            pending_writes.append((w["task_id"], w["channel"], value))

        return CheckpointTuple(
          config=data["config"],
          checkpoint=self._deserialize_checkpoint(data["checkpoint"]),
          metadata=data["metadata"],
          parent_config=data.get("parent_config"),
          pending_writes=pending_writes or None,
      )
        
    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Save a list of writes to the in-memory storage."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        files_path = self.base_dir / thread_id / checkpoint_ns
        files_path.mkdir(parents=True, exist_ok=True)

        for idx, (channel, value) in enumerate(writes):
            vtype, vdata = self.serde.dumps_typed(value)
            w = {
                "task_id":task_id,
                "channel":channel,
                "value_type": vtype,                            # ← 存类型
                "value_data": vdata.decode("latin-1"), 
            }
            fname = f"writes_{checkpoint_id}_{task_id}_{idx}.json"
            (files_path / fname).write_text(
                json.dumps(w, indent=2, ensure_ascii=False)
            )
            
    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints from the in-memory storage."""

        if config:
            thread_ids = [config["configurable"]["thread_id"]]
            config_checkpoint_ns = config["configurable"].get("checkpoint_ns")
            config_checkpoint_id = get_checkpoint_id(config)   # ← 新增
        else:
            thread_ids = [d.name for d in self.base_dir.iterdir() if d.is_dir()]
            config_checkpoint_ns = None
            config_checkpoint_id = None                        # ← 新增

        before_id = get_checkpoint_id(before) if before else None

        for thread_id in thread_ids:
            thread_path = self.base_dir + thread_id

            if not thread_path:
                continue
            
            for ns_dir in thread_path.iterdir():
                if not ns_dir.is_dir():
                    continue
                
                checkpoint_ns = ns_dir.name

                if config_checkpoint_ns is not None and checkpoint_ns != config_checkpoint_ns:
                    continue
                
                files = sorted(
                    [f for f in ns_dir.glob("*.json") if not f.name.startswith("writes_")],
                    reverse=True,
                )

                for file_path in files:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    checkpoint_id = data["config"]["configurable"]["checkpoint_id"]

                    if config_checkpoint_id is not None and checkpoint_id != config_checkpoint_id:
                        continue
                    
                    if (before and checkpoint_id >= before_id):
                        continue
                    
                    metadata = data["metadata"]

                    if filter and not all(query_value == metadata.get(query_key) for query_key, query_value in filter.items()):
                        continue
                    
                    if limit is not None and limit <= 0:
                        break
                    elif limit is not None:
                        limit -= 1

                    pending_writes = []
                    writes_files = sorted(
                        ns_dir.glob(f"writes_{checkpoint_id}_*.json"),
                        key=lambda p: int(p.stem.rsplit("_", 1)[-1])  # 按末尾 idx 数字排序
                    )

                    for writes_file in writes_files:
                        w = json.loads(writes_file.read_text())
                        value = self.serde.loads_typed((w["value_type"], w["value_data"].encode("latin-1")))
                        pending_writes.append((w["task_id"], w["channel"], value))

                    yield CheckpointTuple(
                        config=data["config"],
                        checkpoint=self._deserialize_checkpoint(data["checkpoint"]),
                        metadata=data["metadata"],
                        parent_config=data.get("parent_config"),
                        pending_writes=pending_writes or None,
                    )
                
    def delete_thread(self, thread_id: str) -> None:
        
    def get_next_version(self, current: str | None, channel: None) -> str:
@contextlib.asynccontextmanager
async def generate_checkpointer():
    """Yield a BaseCheckpointSaver, open for the duration of the server."""

