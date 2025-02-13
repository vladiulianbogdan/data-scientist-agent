import base64
import os
import json
from langchain_genezio import GenezioInterpreter
from langchain_anthropic import ChatAnthropic
from fastapi import FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Annotated
from langgraph.prebuilt import ToolNode 
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from fastapi import FastAPI, Form, UploadFile
from typing import List, Optional
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

tool=GenezioInterpreter(
    url=os.environ["GENEZIO_PYTHON_EXECUTOR_URL"] + "/execute",
    librariesAlreadyInstalled=["matplotlib", "pandas"])
tools = [tool]

tool_node = ToolNode(tools=tools)

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
llm_with_tools = llm.bind_tools(tools)


def chatbot(state: State):
    def process_human(msg):
        return { "role": "human", "content": msg.content }
    
    def process_ai(msg):
        return msg
    
    def process_tool(msg):
        if isinstance(msg, list):
            return msg
        elif hasattr(msg, "content") and isinstance(msg.content, str):
            j = json.loads(msg.content)
            j.pop("files", None)

            return {"role": "tool", "content": j, "name": msg.name, "tool_call_id": msg.tool_call_id} 
        else:
            print("Error!")

    def process_unknown(msg):
        print("Processing Unknown message:")

    processed_messages = list(map(lambda x: process_human(x) if x.type == "human" 
                              else process_ai(x) if x.type == "ai" 
                              else process_tool(x) if x.type == "tool" 
                              else process_unknown(x), 
                              state["messages"]))
    message = llm_with_tools.invoke(processed_messages)

    return {"messages": [message]}

def route_tools(
    state: State,
):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return END


# The `tools_condition` function returns "tools" if the chatbot asks to use a tool, and "END" if
# it is fine directly responding. This conditional routing defines the main agent loop.
graph_builder.add_conditional_edges(
    "chatbot",
    route_tools,
    {"tools": "tools", END: END},
)
# Any time a tool is called, we return to the chatbot to decide the next step
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("chatbot", chatbot)

graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile(checkpointer=memory)



app = FastAPI()
# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserInput(BaseModel):
    message: str

def encode_files(files: Optional[List[UploadFile]]) -> List[dict]:
    """Encodes uploaded files as base64."""
    encoded_files = []
    if files:
        for file in files:
            try:
                content = file.file.read()
                encoded_content = base64.b64encode(content).decode("utf-8")
                encoded_files.append({
                    "filename": file.filename,
                    "content": encoded_content,
                    "content_type": file.content_type,
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error encoding file {file.filename}: {str(e)}")
    return encoded_files

def stream_graph_updates(user_input: str, thread_id, files: Optional[List[UploadFile]] = None):
    responses = []
    file_outputs = []
    try:
        config = {"configurable": {"thread_id": thread_id}}
        for event in graph.stream(
            {"messages": [{"role": "user", "content": user_input, "files": encode_files(files)}]}, 
            config
        ):
            for value in event.values():
                print(value)
                lastMessage = value["messages"][-1]
                if lastMessage.type == "tool":
                    jsonContent = json.loads(lastMessage.content)
                    file_outputs = jsonContent.get("files", {})
                else:
                    responses.append(lastMessage.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return responses, file_outputs

@app.post("/generate")
async def generate_response(
    input: str = Form(...),
    files: Optional[List[UploadFile]] = None
):
    responses, file_outputs = stream_graph_updates(input, 100, files=files)
    fs = {}

    if hasattr(file_outputs, "items") and callable(file_outputs.items):
        for filename, content in file_outputs.items():
            fs[filename] = content

    response_data = {
        "messages": responses,
        "files": fs  # Base64 encoded files
    }
    
    return JSONResponse(content=response_data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5043)

