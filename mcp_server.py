"""
MCP server that gives the helpdesk agent read-only access to the HR Postgres database.

Tools:
  - get_employee_profile(employee_id)
  - get_leave_balance(employee_id, leave_type="all")
  - list_it_tickets(employee_id, status="all")

Safety:
  - Every connection is opened in read-only mode, so no tool can change data.
  - All queries use parameters (no string building), so SQL injection is not possible.
  - employee_id must look like E123, otherwise the tool returns an error.

Run on its own (for testing):  python mcp_server.py
The agent starts it automatically over stdio.
"""

import os
import re
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env from this file's folder (the MCP launcher does not pass env vars on)
load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/helpdesk")
CURRENT_YEAR = date.today().year
EMPLOYEE_ID_PATTERN = re.compile(r"^E\d{3}$")

mcp = FastMCP("hr-helpdesk-db")


def _run_query(sql: str, params: tuple) -> list[dict]:
    """Run a SELECT in a read-only connection and return rows as dicts."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _clean_id(employee_id: str) -> str | None:
    employee_id = (employee_id or "").strip().upper()
    return employee_id if EMPLOYEE_ID_PATTERN.match(employee_id) else None


@mcp.tool()
def get_employee_profile(employee_id: str) -> dict:
    """Get an employee's profile: name, department, designation, manager,
    work email, phone, PAN, joining date and whether they are eligible for WFH.

    Args:
        employee_id: Employee ID like "E102".
    """
    emp_id = _clean_id(employee_id)
    if not emp_id:
        return {"error": "Invalid employee ID. Use the format E123."}

    rows = _run_query(
        """
        SELECT e.employee_id, e.full_name, e.department, e.designation,
               m.full_name AS manager_name, e.work_email, e.personal_phone,
               e.pan_number, e.date_of_joining, e.wfh_eligible
        FROM employees e
        LEFT JOIN employees m ON m.employee_id = e.manager_id
        WHERE e.employee_id = %s
        """,
        (emp_id,),
    )
    if not rows:
        return {"error": f"No employee found with ID {emp_id}."}

    profile = rows[0]
    profile["date_of_joining"] = profile["date_of_joining"].isoformat()
    return profile


@mcp.tool()
def get_leave_balance(employee_id: str, leave_type: str = "all") -> dict:
    """Get how many leave days an employee is entitled to, has used and has left
    this year.

    Args:
        employee_id: Employee ID like "E102".
        leave_type: "casual", "sick", "earned" or "all" (default).
    """
    emp_id = _clean_id(employee_id)
    if not emp_id:
        return {"error": "Invalid employee ID. Use the format E123."}

    leave_type = (leave_type or "all").strip().lower()
    if leave_type not in {"all", "casual", "sick", "earned"}:
        return {"error": "leave_type must be casual, sick, earned or all."}

    sql = """
        SELECT leave_type, entitled, used, entitled - used AS remaining
        FROM leave_balances
        WHERE employee_id = %s AND year = %s
    """
    params: tuple = (emp_id, CURRENT_YEAR)
    if leave_type != "all":
        sql += " AND leave_type = %s"
        params += (leave_type,)
    sql += " ORDER BY leave_type"

    rows = _run_query(sql, params)
    if not rows:
        return {"error": f"No leave records found for {emp_id} in {CURRENT_YEAR}."}

    return {
        "employee_id": emp_id,
        "year": CURRENT_YEAR,
        "balances": rows,
        "total_remaining": sum(r["remaining"] for r in rows),
    }


@mcp.tool()
def list_it_tickets(employee_id: str, status: str = "all") -> dict:
    """List the IT tickets raised by an employee.

    Args:
        employee_id: Employee ID like "E102".
        status: "Open", "In Progress", "Resolved" or "all" (default).
    """
    emp_id = _clean_id(employee_id)
    if not emp_id:
        return {"error": "Invalid employee ID. Use the format E123."}

    status_map = {"open": "Open", "in progress": "In Progress", "resolved": "Resolved"}
    status_key = (status or "all").strip().lower()
    if status_key != "all" and status_key not in status_map:
        return {"error": "status must be Open, In Progress, Resolved or all."}

    sql = """
        SELECT ticket_id, category, subject, status, created_on
        FROM it_tickets
        WHERE employee_id = %s
    """
    params: tuple = (emp_id,)
    if status_key != "all":
        sql += " AND status = %s"
        params += (status_map[status_key],)
    sql += " ORDER BY created_on DESC"

    rows = _run_query(sql, params)
    for r in rows:
        r["created_on"] = r["created_on"].isoformat()

    return {"employee_id": emp_id, "tickets": rows, "count": len(rows)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
