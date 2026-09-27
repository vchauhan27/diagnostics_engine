import asyncio
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from AIAgent.agent.config import llm

async def main():
    try:
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="", tool_calls=[{"name": "start_diagnosis", "args": {}, "id": "call_1"}]),
            ToolMessage(content="Evidence gathered", tool_call_id="call_1")
        ]
        res = await llm.ainvoke(msgs)
        print("Success:", res.content)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
