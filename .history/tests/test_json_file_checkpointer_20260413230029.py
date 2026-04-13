from utils.JsonFileCheckpointer import MyJsonFileCheckpointer
from langgraph.checkpoint.conformance import checkpointer_test, validate
import pytest


@checkpointer_test(name="MyJsonFileCheckpointer")
async def my_checkpointer():
    async with MyJsonFileCheckpointer() as saver:
        yield saver

@pytest.mark.asyncio
async def test_conformance():
    report = await validate(my_checkpointer)
    report.print_report()
    assert report.passed_all_base()