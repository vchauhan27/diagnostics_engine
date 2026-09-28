import os
from dotenv import load_dotenv

load_dotenv()

# embedding_model = "baai/bge-m3" 

# def get_agent_model():

#     from langchain_openrouter import ChatOpenRouter
#     return ChatOpenRouter(
#         model="dots-studio/dots-3-note-preview:free",
#         temperature=0.3,
#     )

#     # from langchain_google_genai import ChatGoogleGenerativeAI
#     # return ChatGoogleGenerativeAI(
#     #     model="gemini-flash-lite-latest",
#     #     temperature=0.3,
#     # )


def get_judge_model():

    from deepeval.models import GeminiModel
    return GeminiModel(
        model="gemini-flash-lite-latest",       # Supports structured JSON output natively — no N/A parse crashes
        api_key=os.environ.get("GOOGLE_API_KEY"),
        temperature=0,
    )

    # Fallback: free-tier OpenRouter (unreliable structured output — causes N/A metric scores)
    # from deepeval.models import OpenRouterModel
    # return OpenRouterModel(
    #     model="nvidia/nemotron-3-super-120b-a12b:free",
    #     api_key=os.environ.get("OPENROUTER_API_KEY"),
    #     temperature=0
    # )
 