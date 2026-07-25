from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from src.config import settings

def get_llm(model_name : str):
    return ChatGroq(
        model = model_name,
        temperature = 0.3
    )


class ChatState(TypedDict):
    messages : Annotated[list[BaseMessage], add_messages]


def chat_node(state : ChatState):

    messages = state['messages']

    llm = get_llm(settings.MODEL_NAME)

    response = llm.invoke(messages)

    return {
        "messages" : [response]
    }


check_point = MemorySaver()

graph = StateGraph(ChatState)

graph.add_node('chat_node', chat_node)

graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

chatbot = graph.compile(checkpointer = check_point)