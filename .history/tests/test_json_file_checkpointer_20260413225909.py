import asyncio
from utils.JsonFileCheckpointer import MyJsonFileCheckpointer

from langgraph.checkpoint.conformance import checkpointer_test, validate


@checkpointer_test(name="MyJsonFileCheckpointer")
async def my_checkpointer():
    async with MyCheckpointer(...) as saver:
        yield saver


async def main():
    report = await validate(my_checkpointer)
    report.print_report()
    assert report.passed_all_base()


asyncio.run(main())