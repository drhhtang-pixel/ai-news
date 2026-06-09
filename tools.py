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
    },
    {
        "name": "extract_url",
        "description": (
            "Fetch the full content of a specific article URL using Tavily extract. "
            "Use this to verify a URL is a real article and check its publication date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the article to extract"
                }
            },
            "required": ["url"]
        }
    }
]


def execute_tool(name: str, input: dict) -> str:
    if name == "web_search":
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.search(query=input["query"], search_depth="basic", days=1)
            parts = []
            for item in result.get("results", []):
                title = item.get("title", "No title")
                content = item.get("content", "")
                url = item.get("url", "")
                parts.append(f"**{title}**\n{content}\nURL: {url}")
            return "\n\n".join(parts) if parts else "No results found."
        except Exception as e:
            return f"Error: {e}"
    if name == "extract_url":
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.extract(urls=[input["url"]])
            results = result.get("results", [])
            if not results:
                return "Error: No content extracted"
            item = results[0]
            title = item.get("title", "No title")
            content = (item.get("raw_content", "") or "")[:1000]
            date = item.get("published_date", "unknown") or "unknown"
            url = item.get("url", input["url"])
            return f"**{title}**\n{content}\nPublished: {date}\nURL: {url}"
        except Exception as e:
            return f"Error: {e}"
    return f"Error: Unknown tool '{name}'"
