import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        env={
            **os.environ,
            "MCP_AUTH_SUBJECT": "demo-user-001",
        },
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            try:
                result = await session.call_tool(
                    "search_memory",
                    {
                        "subject_id": "demo-user-002",
                        "intent": "What music does the user prefer?",
                    },
                )

                print("UNEXPECTED SUCCESS:")
                for content in result.content:
                    print(
                        content.text
                        if hasattr(content, "text")
                        else content
                    )

            except Exception as e:
                print("SECURITY TEST RESULT:")
                print(type(e).__name__)
                print(str(e))


if __name__ == "__main__":
    asyncio.run(main())