import contextlib
from langgraph.checkpoint.base import BaseCheckpointSaver, JsonPlusSerializer
from langchain_core.runnables import RunnableConfig
import json
from typing import Any
from collections.abc import Iterator, Sequence
import shutil
import random
from pathlib import Path
import asyncio
import tempfile
import base64
import urllib.parse
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)


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

    def __init__(self, base_dir: str | Path | None = None, serde=None):
        super().__init__(serde=serde or JsonPlusSerializer())
        
        if base_dir is None:
            self._is_temp = True
            self.base_dir = Path(tempfile.mkdtemp())
        else:
            self._is_temp = False
            self.base_dir = Path(base_dir)
            self.base_dir.mkdir(parents=True,exist_ok=True)

        self._closed = False

    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self._cleanup()
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self._cleanup()
        return False
    
    def _cleanup(self):
        """清理临时目录（仅当是临时创建时）"""
        if not self._closed and self._is_temp and self.base_dir.exists():
            try:
                shutil.rmtree(self.base_dir, ignore_errors=True)
            except OSError:
                pass
        self._closed = True

    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> dict:
        """把 channel_values 里的 LangChain 对象序列化为可 JSON 存储的格式"""
        c = dict(checkpoint) # 浅拷贝
        serialized_values = {}
        
        # channel_Value里面放着的都是HumanMessage类的对象，直接序列化会报错    
        for channel, value in checkpoint["channel_values"].items():
            type_str, data_bytes = self.serde.dumps_typed(value)
            serialized_values[channel] = {
                "type": type_str,
                "data": base64.b64encode(data_bytes).decode("ascii") # bytes → str 方便 JSON 存储
            }
        c["channel_values"] = serialized_values

        serialized_sends = []
        for send in checkpoint.get("pending_sends", []):
            type_str, data_bytes = self.serde.dumps_typed(send)
            serialized_sends.append({
                "type": type_str,
                "data": data_bytes.decode("utf-8"),
            })
        c["pending_sends"] = serialized_sends
        return c
    
    def _deserialize_checkpoint(self, data: dict) -> dict:
      c = dict(data)
      restored = {}
      for channel, v in data["channel_values"].items():
          restored[channel] = self.serde.loads_typed(
            (v["type"], base64.b64decode(v["data"]))
          )
      c["channel_values"] = restored

      c["pending_sends"] = [
          self.serde.loads_typed((s["type"], s["data"].encode("utf-8")))
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

        safe_ns = urllib.parse.quote_plus(checkpoint_ns)
        FilePath = self.base_dir / thread_id / safe_ns / f"{checkpoint_id}.json"
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
        safe_ns = urllib.parse.quote_plus(checkpoint_ns)
        path = self.base_dir / thread_id / safe_ns

        if not path.exists():
            return None

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
            value = self.serde.loads_typed((w["value_type"], base64.b64decode(w["value_data"])))
            pending_writes.append((w["task_id"], w["channel"], value))

        return CheckpointTuple(
          config=data["config"],
          checkpoint=self._deserialize_checkpoint(data["checkpoint"]),
          metadata=data["metadata"],
          parent_config=data.get("parent_config"),
          pending_writes=pending_writes,
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

        safe_ns = urllib.parse.quote_plus(checkpoint_ns)
        files_path = self.base_dir / thread_id / safe_ns
        files_path.mkdir(parents=True, exist_ok=True)

        for idx, (channel, value) in enumerate(writes):
            vtype, vdata = self.serde.dumps_typed(value)
            w = {
                "task_id":task_id,
                "channel":channel,
                "value_type": vtype,                            # ← 存类型
                "value_data": base64.b64encode(vdata).decode("ascii"),
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
        if not self.base_dir:
            raise RuntimeError("base_dir is None. Ensure checkpointer is initialized or context is entered.")

        if config:
            thread_ids = [config["configurable"]["thread_id"]]
            config_checkpoint_ns = config["configurable"].get("checkpoint_ns")
            config_checkpoint_id = get_checkpoint_id(config)   # ← 新增
        else:
            thread_ids = [d.name for d in self.base_dir.iterdir() if d.is_dir()]
            config_checkpoint_ns = None
            config_checkpoint_id = None                        # ← 新增

        before_id = get_checkpoint_id(before) if before else None

        # 收集所有候选文件（先收集再统一排序，避免多次 IO 和逻辑碎片化）
        candidates = []
        """
        当 checkpoint_ns 为空字符串时：
        self.base_dir / thread_id / safe_ns / f"{checkpoint_id}.json"
        由于 Python pathlib 的特性，拼接空字符串不会产生中间目录，文件实际直接保存在 thread_id/ 根目录下。
        """
        if config_checkpoint_ns == None or config_checkpoint_ns == "":
            for thread_id in thread_ids:
                thread_path = self.base_dir / thread_id

                if not thread_path.exists():
                    continue

                for f in thread_path.glob("*.json"):
                    if f.name.startswith("writes_"):
                        continue
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        candidates.append((f, data))
                    except Exception:
                        continue
                    
        for thread_id in thread_ids:
            thread_path = self.base_dir / thread_id

            if not thread_path.exists():
                continue
            
            for ns_dir in thread_path.iterdir():
                if not ns_dir.is_dir():
                    continue
                
                raw_ns = urllib.parse.unquote_plus(ns_dir.name)

                if config_checkpoint_ns is not None and raw_ns != config_checkpoint_ns:
                    continue

                for f in ns_dir.glob("*.json"):
                    
                    if f.name.startswith("writes_"):
                        continue
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        candidates.append((f, data))
                    except Exception:
                        continue
            
        candidates.sort(key=lambda x:x[1]["checkpoint"].get("ts", 0), reverse=True)
        found_before = before_id is None
        yielded_count = 0

        print(f"[LIST] base_dir={self.base_dir}")
        print(f"[LIST] thread_ids={thread_ids}")
        print(f"[LIST] candidates found={len(candidates)}")

        for f, data in candidates:
            checkpoint_id = data["config"]["configurable"]["checkpoint_id"]

            if config_checkpoint_id is not None and checkpoint_id != config_checkpoint_id:
                continue
                    
            if not found_before:
                if checkpoint_id == before_id:
                    found_before = True
                continue
                    
            metadata = data["metadata"]

            if filter and not all(query_value == metadata.get(query_key) for query_key, query_value in filter.items()):
                continue
                    
            if limit is not None and yielded_count >= limit:
                break
            yielded_count += 1

            pending_writes = []
            ns_dir = f.parent

            writes_files = sorted(
                ns_dir.glob(f"writes_{checkpoint_id}_*.json"),
                key=lambda p: int(p.stem.rsplit("_", 1)[-1])  # 按末尾 idx 数字排序
            )

            for writes_file in writes_files:
                try:    
                    w = json.loads(writes_file.read_text())
                    value = self.serde.loads_typed((w["value_type"], base64.b64decode(w["value_data"])))
                    pending_writes.append((w["task_id"], w["channel"], value))
                except Exception:
                    pass

            yield CheckpointTuple(
                config=data["config"],
                checkpoint=self._deserialize_checkpoint(data["checkpoint"]),
                metadata=data["metadata"],
                parent_config=data.get("parent_config"),
                pending_writes=pending_writes,
            )

    def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints and writes associated with a thread ID."""
        thread_path = self.base_dir / thread_id
        if thread_path.exists() and thread_path.is_dir():
            try:
                shutil.rmtree(thread_path, ignore_errors=True)
            except OSError:
                pass
  
    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        
        next_v = current_v + 1
        next_h = random.random()

        return f"{next_v:032}.{next_h:016}"

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        # list() 是 generator，需要先 collect 再异步 yield
        items = await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )
        for item in items:
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id):
        return await asyncio.to_thread(self.delete_thread, thread_id)

@contextlib.asynccontextmanager
async def generate_checkpointer(base_dir: str = "./checkpoints"):
    """Yield a BaseCheckpointSaver, open for the duration of the server."""
    async with MyJsonFileCheckpointer(base_dir=base_dir) as saver:
        yield saver
