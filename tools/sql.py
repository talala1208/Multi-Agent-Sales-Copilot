# python/m5/tools/sql.py
"""chinook-analyst 子 agent 的 SQL 工具。

三个工具，数据库信任边界内建其中：

* ``query_chinook``    — 只读 SELECT。连接以 SQLite 只读 URI 模式打开，
  且语句校验为单条 SELECT，模型生成的查询无法修改或删除数据。
* ``introspect_schema`` — 返回完整 DDL，供分析师首次使用时学习并记忆 schema。
* ``add_customer``     — 唯一写入路径：参数化 INSERT 仅写入 Customer 表，
  范围限定为当前登录代表。在构建子 agent 处配置人机协同审批，未经明确同意不添加行。

全程将模型生成的 SQL 视为不可信输入。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from langchain.tools import tool

# 数据库随 agent 放在 data/ 下。读路径使用只读 URI，
# 即使巧妙的 SELECT（如 sqlite PRAGMA 写操作）也无法修改文件。
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chinook.db"
_RO_URI = f"file:{DB_PATH}?mode=ro"

# 角色：Jane Peacock，销售支持代表。「我的客户」= SupportRepId。
REP_EMPLOYEE_ID = 3

# 只读查询中不得出现的语句，作为只读连接之上的纵深防御。
_FORBIDDEN = (
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "pragma", "vacuum",
)


def _read_only_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_RO_URI, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@tool
def query_chinook(sql: str) -> str:
    """对 Chinook 数据库执行只读 SQL SELECT。

    返回行对象的 JSON 数组。仅允许单条 SELECT 语句 —
    任何修改数据库的尝试都会被拒绝。用于所有查询：目录价格、
    客户购买历史、辖区指标等。
    """
    stripped = sql.strip().rstrip(";").strip()
    lowered = stripped.lower()

    if not lowered.startswith(("select", "with")):
        return json.dumps({"error": "Only SELECT queries are allowed."})
    if ";" in stripped:
        return json.dumps({"error": "Only a single statement is allowed."})
    if any(f" {word} " in f" {lowered} " for word in _FORBIDDEN):
        return json.dumps({"error": "Query contains a forbidden (write) keyword."})

    conn = _read_only_connection()
    try:
        rows = [dict(r) for r in conn.execute(stripped).fetchall()]
        return json.dumps(rows, default=str)
    except sqlite3.Error as exc:
        return json.dumps({"error": f"SQL error: {exc}"})
    finally:
        conn.close()


@tool
def introspect_schema() -> str:
    """返回完整数据库 schema（每张表的 CREATE 语句）。

    首次调用以学习 schema，然后记入记忆，避免每次任务重新发现。
    """
    conn = _read_only_connection()
    try:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return "\n\n".join(r["sql"] for r in rows if r["sql"])
    finally:
        conn.close()


@tool
def add_customer(
    first_name: str,
    last_name: str,
    email: str,
    company: str = "",
    city: str = "",
    state: str = "",
    country: str = "",
    phone: str = "",
) -> str:
    """向数据库添加*新*客户，分配给当前销售代表。

    仅在确认客户尚不在系统中后使用（先按邮箱或姓名搜索）。
    执行前需人工审批此写入。成功时返回新 CustomerId。
    """
    if not email or "@" not in email:
        return json.dumps({"error": "A valid email is required."})

    # 参数化插入，仅 Customer 表。其他表不可达，
    # 代表分配在服务端强制，不由模型提供。
    conn = sqlite3.connect(DB_PATH)
    try:
        # 防止邮箱重复。
        existing = conn.execute(
            "SELECT CustomerId FROM Customer WHERE lower(Email) = lower(?)", (email,)
        ).fetchone()
        if existing:
            return json.dumps(
                {"error": f"Customer with email {email} already exists "
                          f"(CustomerId {existing[0]})."}
            )

        cursor = conn.execute(
            """
            INSERT INTO Customer
                (FirstName, LastName, Company, City, State, Country, Phone,
                 Email, SupportRepId)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                first_name,
                last_name,
                company or None,
                city or None,
                state or None,
                country or None,
                phone or None,
                email,
                REP_EMPLOYEE_ID,
            ),
        )
        conn.commit()
        return json.dumps(
            {"status": "created", "customer_id": cursor.lastrowid,
             "name": f"{first_name} {last_name}", "email": email}
        )
    except sqlite3.Error as exc:
        return json.dumps({"error": f"SQL error: {exc}"})
    finally:
        conn.close()
