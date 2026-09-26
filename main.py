import asyncio
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from AIAgent.agent.graph import graph_builder
from langgraph.checkpoint.memory import MemorySaver


async def main():
    print("Initializing Diagnostics Engine...")
    print("--------------------------------------------------")
    print("🌐 Want to use the graphical Web UI instead?")
    print("   1. Terminal 1: langgraph dev --port 2024  (from project root)")
    print("   2. Terminal 2: cd agent-ui && npm run dev")
    print("   3. Open: http://localhost:3000")
    print("--------------------------------------------------\n")
    print("Or continue below for the CLI mode.\n")

    cli_graph = graph_builder.compile(checkpointer=MemorySaver())

    config: RunnableConfig = {"configurable": {"thread_id": "cli-thread-1"}}

    from pathlib import Path
    log_path = Path(__file__).parent / "indexer" / "data" / "sample.log"
    print(f"Reading failure log from {log_path}...")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            user_input = f.read().strip()
        print("Successfully read sample.log.\n")
    except Exception as e:
        print(f"Failed to read sample.log: {e}")
        return

    state_input: Any = {"messages": [HumanMessage(content=user_input)]}

    while True:
        async for item in cli_graph.astream(
            state_input,
            config=config,
            stream_mode=["messages", "updates", "custom"],
            subgraphs=True
        ):
            if isinstance(item, tuple):
                if len(item) == 3:
                    _namespace, mode, payload = item
                else:
                    mode, payload = item
            else:
                continue

            if mode == "messages":
                token, _metadata = payload
                if hasattr(token, "content") and isinstance(token.content, str):
                    print(token.content, end="", flush=True)

            elif mode == "custom":
                print(f"\n[Tool Update] {payload.get('status', payload)}")

            elif mode == "updates":
                for node in payload:
                    print(f"\n[System] Node completed: {node}")

        print("\n")
        state_snapshot = cli_graph.get_state(config)

        # Check for HITL interrupts
        if state_snapshot.tasks and state_snapshot.tasks[0].interrupts:
            interrupt_data = state_snapshot.tasks[0].interrupts[0].value
            print(f"\n[HITL INTERRUPT] {interrupt_data}")
            decision = input("Decision (approve/reject/edit): ")

            from langgraph.types import Command
            if decision == "approve":
                state_input = Command(resume={"decisions": [{"type": "approve"}]})
            elif decision == "reject":
                state_input = Command(resume={"decisions": [{"type": "reject", "message": "User rejected this action."}]})
            else:
                print("Defaulting to reject.")
                state_input = Command(resume={"decisions": [{"type": "reject"}]})
            continue

        current_state = state_snapshot.values
        if current_state.get("diagnosis") is not None:
            print("Diagnosis complete and ticket filed. Exiting.")
            break

        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']:
            break

        state_input = {"messages": [HumanMessage(content=user_input)]}

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
