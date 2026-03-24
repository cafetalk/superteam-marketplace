#!/usr/bin/env bash
set -euo pipefail

# ===========================================================================
# superteam-hub setup — 一键安装脚本（Plugin 模式）
# ===========================================================================

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     superteam-hub 安装向导           ║${NC}"
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
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$cmd"
            echo -e "  ${GREEN}✓${NC} 找到 $cmd ($version)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✗ 未找到 Python >= 3.9，请先安装 Python。${NC}"
    exit 1
fi

# ------------------------------------------------------------------
# Step 2: 创建虚拟环境并安装依赖
# ------------------------------------------------------------------
echo -e "${CYAN}[2/5] 创建虚拟环境并安装依赖...${NC}"

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON" -m venv "$VENV_DIR"
    echo -e "  ${GREEN}✓${NC} 虚拟环境创建于 $VENV_DIR"
else
    echo -e "  ${GREEN}✓${NC} 虚拟环境已存在"
fi

"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet psycopg2-binary
echo -e "  ${GREEN}✓${NC} psycopg2-binary 已安装"

# ------------------------------------------------------------------
# Step 3: 配置数据库连接
# ------------------------------------------------------------------
echo -e "${CYAN}[3/5] 配置数据库连接...${NC}"

CONFIG_DIR="$HOME/.superteam"
CONFIG_FILE="$CONFIG_DIR/config"

# 检查是否已有配置
if [ -f "$CONFIG_FILE" ] && grep -q "KB_TREX_PG_URL" "$CONFIG_FILE" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} 已有数据库配置，跳过"
    PG_URL=$(grep "KB_TREX_PG_URL" "$CONFIG_FILE" | cut -d'=' -f2-)
else
    echo ""
    echo "  请输入 PostgreSQL 数据库连接串："
    echo "  格式: postgresql://user:pass@host:port/dbname"
    echo ""
    read -p "  KB_TREX_PG_URL=" PG_URL

    if [ -z "$PG_URL" ]; then
        echo -e "  ${RED}⚠ 未输入连接串，跳过数据库配置。${NC}"
        echo "  稍后可手动编辑 $CONFIG_FILE"
    else
        mkdir -p "$CONFIG_DIR"
        echo "KB_TREX_PG_URL=$PG_URL" > "$CONFIG_FILE"
        echo -e "  ${GREEN}✓${NC} 已保存到 $CONFIG_FILE"
    fi
fi

# 测试连接
if [ -n "$PG_URL" ]; then
    CONNECTION_TEST=$(export KB_TREX_PG_URL="$PG_URL" && "$VENV_DIR/bin/python" -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['KB_TREX_PG_URL'])
    cur = conn.cursor()
    cur.execute('SET search_path TO trex_hub, public')
    conn.commit()
    cur.execute('SELECT count(*) FROM kb_trex_team_docs')
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f'OK:{count}')
except Exception as e:
    print(f'FAIL:{e}')
" 2>&1)

    if [[ "$CONNECTION_TEST" == OK:* ]]; then
        doc_count="${CONNECTION_TEST#OK:}"
        echo -e "  ${GREEN}✓${NC} 数据库连接成功！知识库中有 ${doc_count} 条文档记录。"
    else
        error="${CONNECTION_TEST#FAIL:}"
        echo -e "  ${RED}⚠ 数据库连接失败: $error${NC}"
        echo "  可能是网络或 IP 白名单限制，不影响安装。连接问题后续排查。"
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
echo ""
read -p "  输入编号（如 1 2 3）: " -a TOOLS

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
            cp -r "$SCRIPT_DIR/.claude-plugin" "$PLUGIN_DIR/"
            cp -r "$SCRIPT_DIR/skills" "$PLUGIN_DIR/"
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
            cp -r "$SCRIPT_DIR/.cursor-plugin" "$CURSOR_DIR/"
            cp -r "$SCRIPT_DIR/skills" "$CURSOR_DIR/"
            echo -e "    ${GREEN}✓${NC} 已安装到 $CURSOR_DIR"
            INSTALLED_ANY=true
            ;;
        3)
            echo ""
            echo -e "  ${CYAN}安装到 Nanobot...${NC}"
            NANOBOT_DIR="$HOME/.nanobot/workspace/skills/superteam"
            mkdir -p "$NANOBOT_DIR"
            cp -r "$SCRIPT_DIR/skills"/* "$NANOBOT_DIR/"
            echo -e "    ${GREEN}✓${NC} 已安装到 $NANOBOT_DIR"
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
echo "  superteam:hub           — 智能查询路由"
echo "  superteam:insight-docs  — 知识库搜索"
echo "  superteam:insight-data  — 数据洞察 (coming soon)"
echo "  superteam:insight-git   — Git 洞察 (coming soon)"
echo "  superteam:insight-linear — Linear 洞察 (coming soon)"
echo "  superteam:weekly-report — 周报生成 (coming soon)"
echo ""
echo "重启 Claude Code 会话后生效。使用 /superteam:hub 或直接提问即可。"
echo ""
