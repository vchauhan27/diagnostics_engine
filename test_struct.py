import asyncio
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from AIAgent.agent.config import llm

class CheckDecision(BaseModel):
    reasoning: str
    sufficient: bool
    feedback: str

async def main():
    prompt = "Evaluate the retrieved evidence for this test failure. Failure: NullPointerException. Evidence: none. Is this sufficient?"
    llm_with_struct = llm.with_structured_output(CheckDecision)
    try:
        res = await llm_with_struct.ainvoke([HumanMessage(content=prompt)])
        print(type(res))
        print(res)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
