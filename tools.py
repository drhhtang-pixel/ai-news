import os
from tavily import TavilyClient

TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for current information on a topic. "
            "Returns a summary of relevant results from multiple sources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string"
                }
            },
            "required": ["query"]
        }
    }
]


def execute_tool(name: str, input: dict) -> str:
    if name == "web_search":
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.search(query=input["query"], search_depth="basic")
            parts = []
            for item in result.get("results", []):
                title = item.get("title", "No title")
                content = item.get("content", "")
                url = item.get("url", "")
                parts.append(f"**{title}**\n{content}\nURL: {url}")
            return "\n\n".join(parts) if parts else "No results found."
        except Exception as e:
            return f"Error: {e}"
    return f"Error: Unknown tool '{name}'"
