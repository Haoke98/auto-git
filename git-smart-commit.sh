#!/bin/bash

# Git智能提交信息生成器
# 基于LLM生成专业的git提交信息，并处理submodule变化

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 帮助信息
function show_help {
    echo -e "${BLUE}Git智能提交信息生成器${NC}"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help         显示帮助信息"
    echo "  -g, --generate     生成提交信息"
    echo "  -c, --commit       生成并直接提交"
    echo "  -m, --model NAME   指定LLM模型 (默认: mistral-nemo)"
    echo ""
    echo "示例:"
    echo "  $0 -g              生成提交信息"
    echo "  $0 -c              生成并直接提交"
    echo "  $0 -m llama3       使用llama3模型生成提交信息"
}

# 检查是否为git仓库
function check_git_repo {
    if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        echo -e "${RED}错误: 当前目录不是git仓库${NC}"
        exit 1
    fi
}

# 获取git变动内容
function get_git_changes {
    git diff --staged --name-status
    git diff --staged
}

# 获取git仓库全局信息
function get_repo_info {
    # 获取仓库名称
    repo_name=$(basename -s .git $(git config --get remote.origin.url 2>/dev/null || echo "未知仓库"))
    echo "仓库: $repo_name"
    
    # 获取当前分支
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached HEAD")
    echo "分支: $branch"
    
    # 获取最近几次提交信息作为上下文
    echo "最近提交记录:"
    git log -3 --pretty=format:"%h %s" 2>/dev/null || echo "无提交记录"
}

# 处理submodule变化
function process_submodules {
    local submodule_summary=""
    
    # 获取已暂存的submodule变化
    git diff --staged --submodule | grep "^Submodule" | while read -r line; do
        if [[ $line =~ Submodule\ ([^\ ]+)\ ([0-9a-f]+)\.\.([0-9a-f]+) ]]; then
            submodule_path="${BASH_REMATCH[1]}"
            old_hash="${BASH_REMATCH[2]}"
            new_hash="${BASH_REMATCH[3]}"
            
            echo -e "${YELLOW}检测到submodule变化: $submodule_path ($old_hash..$new_hash)${NC}"
            
            # 进入submodule目录
            pushd "$submodule_path" > /dev/null
            
            # 获取submodule提交信息
            local sub_commits=$(git log --pretty=format:"%h %s" $old_hash..$new_hash)
            
            # 如果有提交信息，添加到汇总
            if [ ! -z "$sub_commits" ]; then
                submodule_summary+="Submodule $submodule_path 更新:\n"
                submodule_summary+="$sub_commits\n\n"
            fi
            
            popd > /dev/null
        fi
    done
    
    echo -e "$submodule_summary"
}

# 使用LLM生成commit信息
function generate_commit_message {
    local changes=$1
    local repo_info=$2
    local submodule_info=$3
    local model=${4:-"mistral-nemo"}
    
    echo -e "${BLUE}正在使用 $model 生成提交信息...${NC}"
    
    # 构建提示
    prompt="请基于以下Git变更生成一个专业的、遵循最佳实践的commit message。\n\n"
    prompt+="仓库信息:\n$repo_info\n\n"
    prompt+="变更内容:\n$changes\n\n"
    
    if [ ! -z "$submodule_info" ]; then
        prompt+="Submodule变更:\n$submodule_info\n\n"
    fi
    
    prompt+="生成的commit message应该:\n"
    prompt+="1. 使用现在时态\n"
    prompt+="2. 第一行是简短的摘要 (50个字符以内)\n"
    prompt+="3. 留一个空行后再写详细描述\n"
    prompt+="4. 详细描述应当解释为什么进行更改，而不是如何更改\n"
    prompt+="5. 引用任何相关问题或工单编号"
    
    # 调用ollama
    ollama_response=$(echo -e "$prompt" | ollama run $model 2>/dev/null || echo "LLM调用失败")
    
    # 打印生成的commit message
    echo -e "${GREEN}生成的提交信息:${NC}"
    echo -e "$ollama_response"
    
    # 返回生成的message
    echo "$ollama_response"
}

# 执行提交
function do_commit {
    local message=$1
    
    # 提示用户确认
    echo -e "${YELLOW}是否使用此信息提交? (y/n)${NC}"
    read -r confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        git commit -m "$message"
        echo -e "${GREEN}提交成功!${NC}"
    else
        echo -e "${YELLOW}已取消提交${NC}"
    fi
}

# 主函数
function main {
    local generate=false
    local commit=false
    local model="mistral-nemo"
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -g|--generate)
                generate=true
                shift
                ;;
            -c|--commit)
                generate=true
                commit=true
                shift
                ;;
            -m|--model)
                model="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}未知选项: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 如果没有指定操作，显示帮助
    if [ "$generate" = false ]; then
        show_help
        exit 0
    fi
    
    # 检查是否是git仓库
    check_git_repo
    
    # 检查是否有暂存的更改
    if [ -z "$(git diff --staged)" ]; then
        echo -e "${RED}错误: 没有暂存的更改。请使用 'git add' 添加更改。${NC}"
        exit 1
    fi
    
    # 获取仓库信息
    repo_info=$(get_repo_info)
    
    # 获取变更内容
    changes=$(get_git_changes)
    
    # 处理submodule
    submodule_info=$(process_submodules)
    
    # 生成提交信息
    commit_message=$(generate_commit_message "$changes" "$repo_info" "$submodule_info" "$model")
    
    # 如果需要提交
    if [ "$commit" = true ]; then
        do_commit "$commit_message"
    fi
}

# 检查ollama是否安装
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}错误: 未找到ollama命令${NC}"
    echo -e "请安装ollama: https://github.com/ollama/ollama"
    exit 1
fi

# 执行主函数
main "$@" 