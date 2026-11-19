"""Quick check: start the MCP server, list its tools and call each one.

Run from the project folder:  python tests/test_mcp_server.py
"""

import asyncio
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

SERVER = Path(__file__).resolve().parent.parent / "mcp_server.py"


async def main():
    client = MultiServerMCPClient(
        {
            "hr_db": {
                "command": sys.executable,
                "args": [str(SERVER)],
                "transport": "stdio",
            }
        }
    )
    tools = {t.name: t for t in await client.get_tools()}
    print("Tools found:", ", ".join(tools))

    checks = [
        ("get_leave_balance", {"employee_id": "E102"}),
        ("get_leave_balance", {"employee_id": "E102", "leave_type": "sick"}),
        ("get_employee_profile", {"employee_id": "E104"}),
        ("list_it_tickets", {"employee_id": "E102"}),
        ("get_leave_balance", {"employee_id": "E102'; DROP TABLE employees;--"}),
        ("get_employee_profile", {"employee_id": "E999"}),
    ]
    for name, args in checks:
        result = await tools[name].ainvoke(args)
        if isinstance(result, list):
            result = "".join(p.get("text", "") for p in result if isinstance(p, dict))
        print(f"\n> {name}({args})\n{result}")


asyncio.run(main())
