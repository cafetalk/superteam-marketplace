#!/usr/bin/env bash
set -euo pipefail

# ===========================================================================
# superteam setup — 一键安装脚本（Plugin 模式）
# ===========================================================================

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       superteam 安装向导             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ------------------------------------------------------------------
# Step 1: 检测 Python 环境
# ------------------------------------------------------------------
echo -e "${CYAN}[1/5] 检测 Python 环境...${NC}"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$cmd"
            echo -e "  ${GREEN}✓${NC} 找到 $cmd ($VERSION)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✗ 未找到 Python >= 3.9，请先安装 Python。${NC}"
    exit 1
fi

if ! command -v uv &>/dev/null; then
    echo -e "  ${RED}✗ 未找到 uv，请先安装 uv（https://docs.astral.sh/uv/）${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} 找到 uv ($(uv --version | awk '{print $2}'))"

# ------------------------------------------------------------------
# Step 2: 初始化 uv 环境并安装依赖
# ------------------------------------------------------------------
echo -e "${CYAN}[2/5] 初始化 uv 环境并安装依赖...${NC}"
uv sync --python "$PYTHON" --quiet
echo -e "  ${GREEN}✓${NC} uv 依赖已安装（默认组）"

# ------------------------------------------------------------------
# Step 3: 配置 MCP 连接
# ------------------------------------------------------------------
echo -e "${CYAN}[3/5] 配置 MCP 连接...${NC}"

CONFIG_DIR="$HOME/.superteam"
CONFIG_FILE="$CONFIG_DIR/config"

MCP_URL="https://superteam-mcp.dipbit.xyz/mcp"
MCP_TOKEN=""

if [ -f "$CONFIG_FILE" ] && grep -q "SUPERTEAM_API_TOKEN" "$CONFIG_FILE" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} 已有 MCP 配置，跳过"
    MCP_TOKEN=$(grep "SUPERTEAM_API_TOKEN" "$CONFIG_FILE" | cut -d'=' -f2-)
else
    echo ""
    echo -e "  MCP 服务地址: ${GREEN}$MCP_URL${NC}"
    echo ""
    echo "  请输入 API Token（由管理员提供）："
    read -p "  SUPERTEAM_API_TOKEN=" MCP_TOKEN

    if [ -z "$MCP_TOKEN" ]; then
        echo -e "  ${RED}⚠ Token 未填写，跳过。${NC}"
        echo "  稍后可手动编辑 $CONFIG_FILE"
    else
        mkdir -p "$CONFIG_DIR"
        cat > "$CONFIG_FILE" <<CONF
SUPERTEAM_MCP_URL=$MCP_URL
SUPERTEAM_API_TOKEN=$MCP_TOKEN
CONF
        echo -e "  ${GREEN}✓${NC} 已保存到 $CONFIG_FILE"
    fi
fi

# 配置 superteam-git 默认 workspace（用于 /superteam-git 直接查询）
echo ""
if [ -f "$CONFIG_FILE" ] && grep -q "^SUPERTEAM_GIT_WORKSPACE=" "$CONFIG_FILE" 2>/dev/null; then
    EXISTING_WS=$(grep "^SUPERTEAM_GIT_WORKSPACE=" "$CONFIG_FILE" | cut -d'=' -f2-)
    echo -e "  ${GREEN}✓${NC} 已有 Git workspace 配置: $EXISTING_WS"
else
    DEFAULT_GIT_WS="$HOME/code"
    read -p "  superteam-git 默认 workspace（回车使用 ${DEFAULT_GIT_WS}；多个目录用 : 分隔）: " GIT_WS_INPUT
    GIT_WS="${GIT_WS_INPUT:-$DEFAULT_GIT_WS}"
    mkdir -p "$CONFIG_DIR"
    if [ -f "$CONFIG_FILE" ]; then
        echo "SUPERTEAM_GIT_WORKSPACE=$GIT_WS" >> "$CONFIG_FILE"
    else
        cat > "$CONFIG_FILE" <<CONF
SUPERTEAM_GIT_WORKSPACE=$GIT_WS
CONF
    fi
    echo -e "  ${GREEN}✓${NC} 已保存 SUPERTEAM_GIT_WORKSPACE=$GIT_WS（多目录示例: $HOME/proj:$HOME/work）"
fi

# 测试连接
if [ -n "$MCP_URL" ] && [ -n "$MCP_TOKEN" ]; then
    HEALTH_CHECK=$(uv run --python "$PYTHON" python -c "
import httpx
try:
    base = '${MCP_URL}'.rsplit('/mcp', 1)[0]
    r = httpx.get(f'{base}/health', timeout=10)
    if r.status_code == 200:
        print(f'OK:{r.json().get(\"superteam-version\", \"unknown\")}')
    else:
        print(f'FAIL:HTTP {r.status_code}')
except Exception as e:
    print(f'FAIL:{e}')
" 2>&1)

    if [[ "$HEALTH_CHECK" == OK:* ]]; then
        VERSION="${HEALTH_CHECK#OK:}"
        echo -e "  ${GREEN}✓${NC} MCP 服务连接成功！版本: $VERSION"
    else
        error="${HEALTH_CHECK#FAIL:}"
        echo -e "  ${RED}⚠ MCP 连接失败: $error${NC}"
        echo "  不影响安装。连接问题后续排查。"
    fi
fi

# ------------------------------------------------------------------
# Step 4: 选择安装目标
# ------------------------------------------------------------------
echo -e "${CYAN}[4/5] 选择要安装的 AI 工具...${NC}"
echo ""
echo "  请选择要安装到哪些工具（可多选，用空格分隔）："
echo "    1) Claude Code"
echo "    2) Cursor"
echo "    3) Nanobot"
echo "    4) Codex"
echo ""
read -p "  输入编号（如 1 2 3 4）: " -a TOOLS

INSTALLED_ANY=false

for tool in "${TOOLS[@]}"; do
    case "$tool" in
        1)
            echo ""
            echo -e "  ${CYAN}安装到 Claude Code...${NC}"
            PLUGIN_DIR="$HOME/.claude/plugins/local/superteam"

            # 清理旧的 skill 安装方式
            if [ -d "$HOME/.claude/skills/superteam" ]; then
                rm -r "$HOME/.claude/skills/superteam"
                echo -e "    ${GREEN}✓${NC} 已清理旧版 skill 安装"
            fi

            mkdir -p "$PLUGIN_DIR"
            rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
                "$SCRIPT_DIR/.claude-plugin" "$PLUGIN_DIR/"
            rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
                "$SCRIPT_DIR/skills" "$PLUGIN_DIR/"
            echo -e "    ${GREEN}✓${NC} Plugin 文件已安装到 $PLUGIN_DIR"

            # 配置 shell alias，启动 claude 时自动加载 plugin
            ALIAS_LINE="alias claude='claude --plugin-dir $PLUGIN_DIR'"
            SHELL_RC=""
            if [ -f "$HOME/.zshrc" ]; then
                SHELL_RC="$HOME/.zshrc"
            elif [ -f "$HOME/.bashrc" ]; then
                SHELL_RC="$HOME/.bashrc"
            fi

            if [ -n "$SHELL_RC" ]; then
                if ! grep -q "plugin-dir.*superteam" "$SHELL_RC" 2>/dev/null; then
                    echo "" >> "$SHELL_RC"
                    echo "# Superteam Hub plugin for Claude Code" >> "$SHELL_RC"
                    echo "$ALIAS_LINE" >> "$SHELL_RC"
                    echo -e "    ${GREEN}✓${NC} 已添加 alias 到 $SHELL_RC"
                    echo -e "    ${CYAN}提示：运行 source $SHELL_RC 或重开终端生效${NC}"
                else
                    echo -e "    ${GREEN}✓${NC} Shell alias 已存在（跳过）"
                fi
            else
                echo -e "    ${RED}⚠${NC} 未找到 .zshrc 或 .bashrc"
                echo -e "    请手动添加到 shell 配置: $ALIAS_LINE"
            fi
            INSTALLED_ANY=true
            ;;
        2)
            echo ""
            echo -e "  ${CYAN}安装到 Cursor...${NC}"
            CURSOR_DIR="$HOME/.cursor/plugins/local/superteam"
            mkdir -p "$CURSOR_DIR"
            rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
                "$SCRIPT_DIR/.cursor-plugin" "$CURSOR_DIR/"
            rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
                "$SCRIPT_DIR/skills" "$CURSOR_DIR/"
            echo -e "    ${GREEN}✓${NC} 已安装到 $CURSOR_DIR"
            INSTALLED_ANY=true
            ;;
        3)
            echo ""
            echo -e "  ${CYAN}安装到 Nanobot...${NC}"
            NANOBOT_SKILLS="$HOME/.nanobot/workspace/skills"
            NANOBOT_DIR="$NANOBOT_SKILLS/superteam"

            # 清理旧的扁平安装
            for old_dir in "$NANOBOT_SKILLS"/superteam-*; do
                [ -d "$old_dir" ] && rm -rf "$old_dir"
            done
            [ -L "$NANOBOT_SKILLS/_shared" ] && rm -f "$NANOBOT_SKILLS/_shared"

            # 嵌套安装：全量复制到 skills/superteam/
            # nanobot 会扫描子目录，每个 sub-skill 的 SKILL.md 独立注册
            mkdir -p "$NANOBOT_DIR"
            rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
                "$SCRIPT_DIR/skills/" "$NANOBOT_DIR/"
            echo -e "    ${GREEN}✓${NC} 已安装到 $NANOBOT_DIR"

            # 更新 AGENTS.md 中的 superteam 说明
            AGENTS_MD="$HOME/.nanobot/workspace/AGENTS.md"
            if [ -f "$AGENTS_MD" ]; then
                "$PYTHON" -c "
import re, pathlib
p = pathlib.Path('$AGENTS_MD')
text = p.read_text()
new_section = '''## superteam Skills（知识库插件）

superteam skills 安装在 \`skills/superteam/\` 目录下。每个 sub-skill 有自己的 \`SKILL.md\` 和 \`scripts/\` 目录。

**脚本执行路径格式：** \`uv run --python python3 skills/superteam/<skill-name>/scripts/<script>.py\`

| Skill 名称 | 用途 |
|------------|------|
| \`superteam\` | 智能查询路由（意图识别 → 分发） |
| \`superteam-knowledgebase\` | 语义搜索、文档列表、完整文档获取 |
| \`superteam-member\` | 成员查询、成员解析、成员资料管理（管理员） |
| \`superteam-data\` | 业务数据查询（MCP agentic_data；非 Linear/研发任务） |
| \`superteam-report\` | 周报生成 |
| \`superteam-version\` | 版本号、已装 skill、配置状态 |

### 快速使用

\\\`\\\`\\\`bash
# 通用路由（推荐入口）
uv run --python python3 skills/superteam/superteam/scripts/route.py --query \"搜索内容\" --execute

# 语义搜索（返回相关片段）
uv run --python python3 skills/superteam/superteam-knowledgebase/scripts/search_docs.py \"关键词\"

# 获取单篇文档完整内容（按文档名）
uv run --python python3 skills/superteam/superteam-knowledgebase/scripts/get_doc.py --name \"文档名\"

# 深度搜索（先搜索再获取完整原文）
uv run --python python3 skills/superteam/superteam-knowledgebase/scripts/deep_search.py \"搜索词\"

# 成员列表（只读沙箱兼容）
PYTHONDONTWRITEBYTECODE=1 uv run --python python3 skills/superteam/superteam-member/scripts/list_members.py list

# 版本信息
uv run --python python3 skills/superteam/superteam-version/scripts/version.py
\\\`\\\`\\\`

### ⚠️ 重要规则

1. 用户要「完整文档/全文/原文」→ 用 \`get_doc.py\` 或 \`deep_search.py\`，**禁止**用 \`search_docs.py\`（它只返回片段）
2. 用户问「版本号」→ 用 \`version.py\`，不要查 pip 或系统信息
3. 所有脚本输出都是结构化数据，agent 负责合成自然语言回答
4. 详细用法参考各 skill 的 SKILL.md

### 配置

配置文件：\`~/.superteam/config\`（INI 格式）
- \`SUPERTEAM_MCP_URL\` — MCP 服务地址
- \`SUPERTEAM_API_TOKEN\` — 认证 token'''

pattern = r'## superteam Skills.*?(?=\n## (?!superteam)|\\Z)'
if re.search(pattern, text, re.DOTALL):
    text = re.sub(pattern, new_section, text, flags=re.DOTALL)
    p.write_text(text)
    print('updated')
else:
    print('not_found')
" 2>&1 && echo -e "    ${GREEN}✓${NC} AGENTS.md 已更新" || true
            fi
            INSTALLED_ANY=true
            ;;
        4)
            echo ""
            echo -e "  ${CYAN}安装到 Codex...${NC}"
            CODEX_SKILLS="$HOME/.codex/skills"
            mkdir -p "$CODEX_SKILLS"

            # Codex scans each direct child of ~/.codex/skills for SKILL.md.
            # Keep Codex's built-in .system skills intact, and sync only this
            # repository's skill directories one by one.
            for skill_dir in "$SCRIPT_DIR"/skills/*; do
                [ -d "$skill_dir" ] || continue
                skill_name="$(basename "$skill_dir")"
                mkdir -p "$CODEX_SKILLS/$skill_name"
                rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
                    "$skill_dir/" "$CODEX_SKILLS/$skill_name/"
            done
            echo -e "    ${GREEN}✓${NC} 已同步 skills 到 $CODEX_SKILLS"
            echo -e "    ${CYAN}提示：重启 Codex 会话后，新/更新的 skills 会重新加载${NC}"
            INSTALLED_ANY=true
            ;;
        *)
            echo -e "    ${RED}⚠${NC} 未知选项: $tool（跳过）"
            ;;
    esac
done

if [ "$INSTALLED_ANY" = false ]; then
    echo -e "  ${RED}⚠ 未选择任何工具，skills 未安装。${NC}"
    echo "  你可以稍后手动复制 skills/ 目录到对应工具的 plugin 目录。"
fi

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo "已安装 superteam plugin，包含以下 skills："
echo "  superteam           — 智能查询路由"
echo "  superteam-knowledgebase  — 知识库搜索"
echo "  superteam-member — 成员查询与资料管理"
echo "  superteam-data  — 业务数据洞察"
echo "  superteam-git   — Git 洞察（支持 /superteam-git 自然语言时间范围）"
echo "  superteam-daily-report — 日报数据流水线（含 Git 裸仓同步等）"
echo "  superteam-linear — Linear 洞察 (coming soon)"
echo "  superteam-report — 周报生成 (coming soon)"
echo ""
echo "重启对应 AI 工具会话后生效。使用 /superteam 或直接提问即可。"
echo ""
