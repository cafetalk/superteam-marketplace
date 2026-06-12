"""trex-delivery 测试隔离：保证 scripts/ 在 import path。
本 skill 纯逻辑 + subprocess 封装，不碰 _shared/db.py / psycopg2，故无需 mock DB，
也绝不 import _shared/db.py（避免污染其它 skill 的 pytest session）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
