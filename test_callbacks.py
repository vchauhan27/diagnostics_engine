import asyncio
from langchain_core.messages import HumanMessage
from AIAgent.agent.config import llm

async def main():
    try:
        res = await llm.ainvoke([HumanMessage(content="Hello")], config={"callbacks": []})
        print(res.content)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
