#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Query task management data via AGE Cypher (primary) or SQL (fallback).

Three query modes:
  --member 张三 [--iteration xxx]  → Member's tasks in an iteration
  --task xxx                       → All members on a task
  --iteration xxx --summary        → Iteration progress summary

Requires: KB_TREX_PG_URL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path

_sys_shared = str(_Path(__file__).resolve().parent.parent.parent / "_shared")
if _sys_shared not in sys.path:
    sys.path.insert(0, _sys_shared)

from config import env


def _get_conn():
    import psycopg2
    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        raise RuntimeError("KB_TREX_PG_URL not set.")
    return psycopg2.connect(conn_url)


# ---------------------------------------------------------------------------
# AGE helpers
# ---------------------------------------------------------------------------

def _age_available(conn) -> bool:
    """Check if AGE extension and task_graph exist."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'age'")
        if not cur.fetchone():
            return False
        cur.execute("LOAD 'age'")
        cur.execute("SET search_path = ag_catalog, trex_hub, public")
        cur.execute("SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'task_graph'")
        return cur.fetchone() is not None
    except Exception:
        conn.rollback()
        return False


def _cypher_query(conn, cypher: str, columns: list[str]) -> list[dict]:
    """Execute a Cypher query via AGE and return list of dicts.

    Args:
        conn: psycopg2 connection (AGE must be loaded, search_path set)
        cypher: Cypher query string
        columns: list of column names matching the RETURN clause
    """
    cur = conn.cursor()
    col_defs = ", ".join(f"{c} agtype" for c in columns)
    sql = f"SELECT * FROM cypher('task_graph', $$ {cypher} $$) AS ({col_defs})"
    cur.execute(sql)
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = {}
        for i, col in enumerate(columns):
            val = row[i]
            # agtype values are JSON strings, strip quotes
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            record[col] = val
        result.append(record)
    return result


# ---------------------------------------------------------------------------
# Query: Member tasks
# ---------------------------------------------------------------------------

def query_member_tasks_cypher(conn, member: str,
                               iteration: str | None = None) -> list[dict]:
    """Cypher: find all tasks for a member, optionally filtered by iteration."""
    if iteration:
        cypher = (
            f"MATCH (m:Member {{name: '{member}'}})-[w:WORKS_ON]->(t:Task)"
            f"-[:BELONGS_TO]->(i:Iteration {{name: '{iteration}'}}) "
            f"RETURN t.title, w.role, t.status, t.story_points, i.name"
        )
        columns = ["title", "role", "status", "story_points", "iteration"]
    else:
        cypher = (
            f"MATCH (m:Member {{name: '{member}'}})-[w:WORKS_ON]->(t:Task) "
            f"OPTIONAL MATCH (t)-[:BELONGS_TO]->(i:Iteration) "
            f"RETURN t.title, w.role, t.status, t.story_points, i.name"
        )
        columns = ["title", "role", "status", "story_points", "iteration"]
    return _cypher_query(conn, cypher, columns)


def query_member_tasks_sql(conn, member: str,
                            iteration: str | None = None) -> list[dict]:
    """SQL fallback: find all tasks for a member."""
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")
    if iteration:
        cur.execute("""
            SELECT t.title, tm.role, t.status, t.story_points, i.name AS iteration
            FROM tm_task_members tm
            JOIN tm_tasks t ON t.id = tm.task_id
            LEFT JOIN tm_iterations i ON i.id = t.iteration_id
            WHERE tm.member_name = %s AND i.name = %s
            ORDER BY t.id
        """, (member, iteration))
    else:
        cur.execute("""
            SELECT t.title, tm.role, t.status, t.story_points, i.name AS iteration
            FROM tm_task_members tm
            JOIN tm_tasks t ON t.id = tm.task_id
            LEFT JOIN tm_iterations i ON i.id = t.iteration_id
            WHERE tm.member_name = %s
            ORDER BY t.id
        """, (member,))
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Query: Task members
# ---------------------------------------------------------------------------

def query_task_members_cypher(conn, task_id: str) -> list[dict]:
    """Cypher: find all members working on a task."""
    cypher = (
        f"MATCH (m:Member)-[w:WORKS_ON]->(t:Task {{notable_id: '{task_id}'}}) "
        f"RETURN m.name, w.role, t.title, t.status"
    )
    return _cypher_query(conn, cypher, ["member", "role", "title", "status"])


def query_task_members_sql(conn, task_id: str) -> list[dict]:
    """SQL fallback: find all members on a task."""
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")
    cur.execute("""
        SELECT tm.member_name AS member, tm.role, t.title, t.status
        FROM tm_task_members tm
        JOIN tm_tasks t ON t.id = tm.task_id
        WHERE t.notable_id = %s
        ORDER BY tm.role, tm.member_name
    """, (task_id,))
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Query: Iteration summary
# ---------------------------------------------------------------------------

def query_iteration_summary_sql(conn, iteration: str) -> dict | None:
    """SQL (materialized view): iteration progress summary.
    Aggregation queries are better served by SQL, no Cypher version needed.
    """
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")
    cur.execute("""
        SELECT name, start_date, end_date, status,
               total_tasks, total_sp, done_tasks, done_sp, member_count
        FROM mv_iteration_progress
        WHERE name = %s
        LIMIT 1
    """, (iteration,))
    row = cur.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cur.description]
    summary = dict(zip(columns, row))

    # Enrich with per-member breakdown
    cur.execute("""
        SELECT member_name, role, task_count, total_story_points, completed_tasks
        FROM mv_member_iteration_summary
        WHERE iteration_name = %s
        ORDER BY total_story_points DESC
    """, (iteration,))
    members_cols = [desc[0] for desc in cur.description]
    summary["members"] = [dict(zip(members_cols, r)) for r in cur.fetchall()]

    # Convert date objects to strings for JSON serialization
    for k in ("start_date", "end_date"):
        if summary.get(k) and hasattr(summary[k], "isoformat"):
            summary[k] = summary[k].isoformat()

    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query task management data (AGE Cypher + SQL fallback)."
    )
    parser.add_argument("--member", help="Query tasks for this member name.")
    parser.add_argument("--task", help="Query members for this task (notable_id).")
    parser.add_argument("--iteration", help="Iteration name (filter or summary target).")
    parser.add_argument("--summary", action="store_true",
                        help="Show iteration progress summary (requires --iteration).")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="Output format (default: json).")
    parser.add_argument("--force-sql", action="store_true",
                        help="Skip AGE, use SQL only.")
    args = parser.parse_args()

    if not args.member and not args.task and not (args.iteration and args.summary):
        parser.error("Provide --member, --task, or --iteration --summary.")

    try:
        conn = _get_conn()
    except Exception as e:
        print(f"DB connection failed: {e}", file=sys.stderr)
        return 1

    use_cypher = not args.force_sql and _age_available(conn)
    if use_cypher:
        print("Using AGE Cypher queries.", file=sys.stderr)
    else:
        print("Using SQL fallback.", file=sys.stderr)

    try:
        if args.member:
            if use_cypher:
                results = query_member_tasks_cypher(conn, args.member, args.iteration)
            else:
                results = query_member_tasks_sql(conn, args.member, args.iteration)
            _output(results, args.format, f"Tasks for {args.member}")

        elif args.task:
            if use_cypher:
                results = query_task_members_cypher(conn, args.task)
            else:
                results = query_task_members_sql(conn, args.task)
            _output(results, args.format, f"Members on task {args.task}")

        elif args.iteration and args.summary:
            result = query_iteration_summary_sql(conn, args.iteration)
            if not result:
                print(f"Iteration '{args.iteration}' not found.", file=sys.stderr)
                return 1
            _output(result, args.format, f"Iteration: {args.iteration}")

    except Exception as e:
        print(f"Query failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    return 0


def _output(data, fmt: str, title: str = "") -> None:
    """Print results in requested format."""
    if fmt == "text":
        print(f"\n=== {title} ===")
        if isinstance(data, list):
            for i, row in enumerate(data, 1):
                print(f"\n--- {i} ---")
                for k, v in row.items():
                    print(f"  {k}: {v}")
            print(f"\nTotal: {len(data)} result(s)")
        elif isinstance(data, dict):
            for k, v in data.items():
                if k == "members" and isinstance(v, list):
                    print(f"\n  Members ({len(v)}):")
                    for m in v:
                        print(f"    {m.get('member_name')}: {m.get('role')} "
                              f"({m.get('completed_tasks')}/{m.get('task_count')} tasks, "
                              f"{m.get('total_story_points')} SP)")
                else:
                    print(f"  {k}: {v}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
