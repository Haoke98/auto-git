#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Git智能提交信息生成器
基于LLM生成专业的git提交信息，并处理submodule变化
"""

import argparse
import os
import subprocess
import sys
import re
import shutil
import json
from datetime import datetime

# 全局调试模式标志
DEBUG = False
LOG_FILE = "git-smart-commit.log"

# 颜色定义
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'  # 无颜色

def debug_log(message, data=None, level="INFO"):
    """记录调试信息"""
    if not DEBUG:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = Colors.BLUE
    
    if level == "ERROR":
        color = Colors.RED
    elif level == "WARNING":
        color = Colors.YELLOW
    elif level == "DEBUG":
        color = Colors.CYAN
    
    # 构建日志消息
    log_message = f"[{timestamp}] [{level}] {message}"
    
    # 输出到控制台
    print_color(f"🔍 {log_message}", color)
    
    # 如果有数据，以格式化方式显示
    if data:
        if isinstance(data, str) and len(data) > 500:
            # 如果数据是长字符串，限制显示长度
            print_color("数据内容（部分）:", Colors.MAGENTA)
            print(data[:500] + "...\n(内容过长，已截断。完整内容请查看日志文件)")
        else:
            print_color("数据内容:", Colors.MAGENTA)
            if isinstance(data, (dict, list)):
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(data)
    
    # 同时写入日志文件
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{log_message}\n")
        if data:
            if isinstance(data, (dict, list)):
                f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            else:
                f.write(str(data) + "\n")
        f.write("\n")

def print_color(text, color):
    """使用颜色输出文本"""
    print(f"{color}{text}{Colors.NC}")

def check_git_repo():
    """检查当前目录是否为git仓库"""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        debug_log("检查Git仓库：当前目录是有效的Git仓库")
        return True
    except subprocess.CalledProcessError:
        print_color("错误: 当前目录不是git仓库", Colors.RED)
        debug_log("检查Git仓库：当前目录不是Git仓库", level="ERROR")
        return False

def run_git_command(command, check=True):
    """运行git命令并返回输出"""
    debug_log(f"执行Git命令: {' '.join(command)}")
    
    try:
        # 设置环境变量，确保Git使用UTF-8输出
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"
        
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            text=True,
            encoding='utf-8',  # 明确指定编码为UTF-8
            errors='replace',  # 处理无法解码的字符
            env=env
        )
        
        if result.returncode != 0:
            debug_log(f"Git命令返回错误代码: {result.returncode}", result.stderr, "WARNING")
        else:
            # 只在调试模式下记录完整输出，避免日志过大
            if DEBUG and result.stdout:
                debug_log("Git命令输出:", result.stdout[:1000] + "..." if len(result.stdout) > 1000 else result.stdout)
        
        return result.stdout.strip() if result.stdout else ""
    except subprocess.CalledProcessError as e:
        if check:
            print_color(f"错误: 执行Git命令失败: {e}", Colors.RED)
            debug_log(f"Git命令执行失败", str(e), "ERROR")
            sys.exit(1)
        return ""
    except Exception as e:
        print_color(f"执行命令时发生异常: {e}", Colors.RED)
        debug_log(f"执行Git命令时发生异常", str(e), "ERROR")
        if check:
            sys.exit(1)
        return ""

def get_git_changes():
    """获取git变动内容"""
    debug_log("获取Git变动内容")
    staged_files = run_git_command(["git", "diff", "--staged", "--name-status"])
    debug_log("已暂存文件列表:", staged_files)
    
    staged_diff = run_git_command(["git", "diff", "--staged"])
    debug_log("已暂存的变更内容:", "内容过长，记录到日志文件")
    
    # 将完整差异内容写入日志
    if DEBUG:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n--- STAGED DIFF BEGIN ---\n")
            f.write(staged_diff)
            f.write("\n--- STAGED DIFF END ---\n\n")
    
    return f"{staged_files}\n\n{staged_diff}"

def get_repo_info():
    """获取git仓库全局信息"""
    debug_log("获取仓库信息")
    
    # 获取仓库名称
    try:
        remote_url = run_git_command(["git", "config", "--get", "remote.origin.url"], check=False)
        if remote_url:
            repo_name = os.path.basename(remote_url)
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
        else:
            repo_name = "未知仓库"
    except:
        repo_name = "未知仓库"
    
    debug_log(f"仓库名称: {repo_name}")
    
    # 获取当前分支
    try:
        branch = run_git_command(["git", "symbolic-ref", "--short", "HEAD"], check=False)
        if not branch:
            branch = "detached HEAD"
    except:
        branch = "detached HEAD"
    
    debug_log(f"当前分支: {branch}")
    
    # 获取最近几次提交信息作为上下文
    recent_commits = run_git_command(
        ["git", "log", "-3", "--pretty=format:%h %s"], 
        check=False
    )
    if not recent_commits:
        recent_commits = "无提交记录"
    
    debug_log("最近提交记录:", recent_commits)
    
    return f"仓库: {repo_name}\n分支: {branch}\n最近提交记录:\n{recent_commits}"

def process_submodules():
    """处理submodule变化"""
    debug_log("开始处理submodule变化")
    submodule_summary = ""
    
    # 获取已暂存的submodule变化
    submodule_diff = run_git_command(["git", "diff", "--staged", "--submodule"], check=False)
    debug_log("submodule差异:", submodule_diff)
    
    # 查找所有submodule变更
    submodule_pattern = r"Submodule\s+([^\s]+)\s+([0-9a-f]+)\.\.([0-9a-f]+)"
    matches = list(re.finditer(submodule_pattern, submodule_diff))
    
    if not matches:
        debug_log("未检测到submodule变更")
        return submodule_summary
    
    debug_log(f"检测到 {len(matches)} 个submodule变更")
    
    for match in matches:
        submodule_path = match.group(1)
        old_hash = match.group(2)
        new_hash = match.group(3)
        
        print_color(f"检测到submodule变化: {submodule_path} ({old_hash}..{new_hash})", Colors.YELLOW)
        debug_log(f"处理submodule: {submodule_path}", f"旧哈希: {old_hash}, 新哈希: {new_hash}")
        
        # 检查子模块目录是否存在
        if not os.path.isdir(submodule_path):
            print_color(f"警告: 子模块目录 {submodule_path} 不存在，跳过", Colors.YELLOW)
            debug_log(f"子模块目录 {submodule_path} 不存在，跳过", level="WARNING")
            continue
            
        # 进入submodule目录
        current_dir = os.getcwd()
        try:
            os.chdir(submodule_path)
            debug_log(f"进入子模块目录: {submodule_path}")
            
            # 检查子模块是否是git仓库
            if not os.path.isdir(".git") and not os.path.isfile(".git"):
                print_color(f"警告: {submodule_path} 不是git仓库，跳过", Colors.YELLOW)
                debug_log(f"{submodule_path} 不是git仓库，跳过", level="WARNING")
                os.chdir(current_dir)
                continue
                
            # 获取submodule提交信息
            command = ["git", "log", f"--pretty=format:%h %s", f"{old_hash}..{new_hash}"]
            debug_log(f"执行子模块命令: {' '.join(command)}")
            
            sub_commits = run_git_command(command, check=False)
            debug_log(f"子模块提交记录:", sub_commits)
            
            # 如果有提交信息，添加到汇总
            if sub_commits:
                submodule_summary += f"Submodule {submodule_path} 更新:\n{sub_commits}\n\n"
                debug_log(f"添加子模块 {submodule_path} 的提交信息到汇总")
                
        except Exception as e:
            print_color(f"处理submodule时出错: {e}", Colors.RED)
            debug_log(f"处理submodule时出错", str(e), "ERROR")
        finally:
            os.chdir(current_dir)
            debug_log(f"返回主仓库目录")
    
    debug_log("submodule处理完成，汇总信息:", submodule_summary)
    return submodule_summary

def generate_commit_message(changes, repo_info, submodule_info, model="mistral-nemo"):
    """使用LLM生成commit信息"""
    print_color(f"正在使用 {model} 生成提交信息...", Colors.BLUE)
    debug_log(f"开始使用LLM({model})生成提交信息")
    
    # 构建提示
    prompt = "请基于以下Git变更生成一个专业的、遵循最佳实践的commit message。\n\n"
    prompt += f"仓库信息:\n{repo_info}\n\n"
    prompt += f"变更内容:\n{changes}\n\n"
    
    if submodule_info:
        prompt += f"Submodule变更:\n{submodule_info}\n\n"
    
    prompt += "生成的commit message应该:\n"
    prompt += "1. 使用现在时态\n"
    prompt += "2. 第一行是简短的摘要 (50个字符以内)\n"
    prompt += "3. 留一个空行后再写详细描述\n"
    prompt += "4. 详细描述应当解释为什么进行更改，而不是如何更改\n"
    prompt += "5. 引用任何相关问题或工单编号"
    
    debug_log("构建完成的LLM提示:", prompt)
    
    # 可视化提示内容
    if DEBUG:
        print_color("\n=== LLM提示内容开始 ===", Colors.MAGENTA)
        print(prompt)
        print_color("=== LLM提示内容结束 ===\n", Colors.MAGENTA)
    
    # 调用ollama
    try:
        # 设置环境变量
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        debug_log(f"开始调用ollama，模型: {model}")
        
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            check=True
        )
        ollama_response = result.stdout.strip() if result.stdout else "LLM没有返回任何输出"
        
        debug_log("LLM响应:", ollama_response)
    except subprocess.CalledProcessError as e:
        print_color(f"LLM调用失败: {e}", Colors.RED)
        debug_log("LLM调用失败", str(e), "ERROR")
        ollama_response = "LLM调用失败"
    except FileNotFoundError:
        print_color("错误: 未找到ollama命令", Colors.RED)
        debug_log("未找到ollama命令", level="ERROR")
        ollama_response = "LLM调用失败：未找到ollama命令"
    except Exception as e:
        print_color(f"调用LLM时发生异常: {e}", Colors.RED)
        debug_log("调用LLM时发生异常", str(e), "ERROR")
        ollama_response = f"LLM调用异常: {str(e)}"
    
    # 打印生成的commit message
    print_color("生成的提交信息:", Colors.GREEN)
    print(ollama_response)
    
    return ollama_response

def do_commit(message):
    """执行提交"""
    # 提示用户确认
    print_color("是否使用此信息提交? (y/n)", Colors.YELLOW)
    confirm = input().lower()
    
    if confirm in ['y', 'yes']:
        debug_log("用户确认提交")
        run_git_command(["git", "commit", "-m", message])
        print_color("提交成功!", Colors.GREEN)
        debug_log("Git提交成功")
    else:
        print_color("已取消提交", Colors.YELLOW)
        debug_log("用户取消提交")

def check_ollama_installed():
    """检查ollama是否安装"""
    debug_log("检查ollama是否安装")
    if not shutil.which("ollama"):
        print_color("错误: 未找到ollama命令", Colors.RED)
        print_color("请安装ollama: https://github.com/ollama/ollama", Colors.RED)
        debug_log("未找到ollama命令", level="ERROR")
        return False
    debug_log("ollama已安装")
    return True

def view_process():
    """查看最近一次执行的过程"""
    if not os.path.exists(LOG_FILE):
        print_color("未找到日志文件，无法查看执行过程", Colors.YELLOW)
        return
    
    print_color("=== 最近执行过程 ===", Colors.BLUE)
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        print(f.read())

def clear_log():
    """清空日志文件"""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        print_color("日志文件已清空", Colors.GREEN)
    else:
        print_color("日志文件不存在", Colors.YELLOW)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Git智能提交信息生成器")
    parser.add_argument("-g", "--generate", action="store_true", help="生成提交信息")
    parser.add_argument("-c", "--commit", action="store_true", help="生成并直接提交")
    parser.add_argument("-m", "--model", default="mistral-nemo", help="指定LLM模型 (默认: mistral-nemo)")
    parser.add_argument("-a", "--all", action="store_true", help="包含所有更改，即使未暂存")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式，显示详细过程")
    parser.add_argument("-v", "--view", action="store_true", help="查看最近一次执行的过程")
    parser.add_argument("--clear-log", action="store_true", help="清空日志文件")
    
    args = parser.parse_args()
    
    # 设置全局调试模式
    global DEBUG
    DEBUG = args.debug
    
    # 查看最近的执行过程
    if args.view:
        view_process()
        return
    
    # 清空日志
    if args.clear_log:
        clear_log()
        return
    
    # 初始化日志文件
    if DEBUG:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始新的执行记录\n\n")
        print_color("调试模式已启用，详细过程将记录到 git-smart-commit.log", Colors.BLUE)
    
    # 如果没有指定操作，显示帮助
    if not args.generate and not args.commit:
        parser.print_help()
        return
    
    # 检查ollama是否安装
    if not check_ollama_installed():
        return
    
    # 检查是否是git仓库
    if not check_git_repo():
        return
    
    # 检查是否有变更
    staged_changes = run_git_command(["git", "diff", "--staged"], check=False)
    unstaged_changes = run_git_command(["git", "diff"], check=False)
    submodule_changes = run_git_command(["git", "status"], check=False)
    
    debug_log("检查仓库状态:", {
        "有已暂存更改": bool(staged_changes),
        "有未暂存更改": bool(unstaged_changes),
        "可能有子模块更改": "modified:" in submodule_changes and "orm_hub" in submodule_changes
    })
    
    # 如果使用-a参数并且有未暂存的更改，则先将所有更改暂存
    if args.all and (unstaged_changes or "modified:" in submodule_changes):
        print_color("自动暂存所有更改...", Colors.BLUE)
        run_git_command(["git", "add", "-A"])
        staged_changes = run_git_command(["git", "diff", "--staged"], check=False)
        debug_log("已自动暂存所有更改")
    
    # 如果没有任何暂存的更改，提示用户
    if not staged_changes:
        # 检查是否有未暂存的子模块更改
        if "modified:" in submodule_changes and "orm_hub" in submodule_changes:
            print_color("检测到子模块更改但尚未暂存。", Colors.YELLOW)
            print_color("提示: 请使用 'git add <子模块路径>' 添加子模块更改。", Colors.YELLOW)
            print_color("例如: git add orm_hub", Colors.YELLOW)
            debug_log("检测到未暂存的子模块更改", level="WARNING")
        # 检查是否有未暂存的普通更改
        elif unstaged_changes:
            print_color("检测到更改但尚未暂存。", Colors.YELLOW)
            print_color("提示: 请使用 'git add <文件路径>' 添加更改。", Colors.YELLOW)
            debug_log("检测到未暂存的文件更改", level="WARNING")
        else:
            print_color("错误: 没有检测到任何更改。", Colors.RED)
            debug_log("没有检测到任何更改", level="ERROR")
        
        # 询问用户是否要自动暂存所有更改
        if (unstaged_changes or "modified:" in submodule_changes) and not args.all:
            print_color("是否自动暂存所有更改并继续? (y/n)", Colors.YELLOW)
            confirm = input().lower()
            if confirm in ['y', 'yes']:
                debug_log("用户确认自动暂存所有更改")
                run_git_command(["git", "add", "-A"])
                staged_changes = run_git_command(["git", "diff", "--staged"], check=False)
                print_color("已暂存所有更改", Colors.GREEN)
            else:
                debug_log("用户取消自动暂存")
                return
        else:
            return
    
    # 获取仓库信息
    repo_info = get_repo_info()
    
    # 获取变更内容
    changes = get_git_changes()
    
    # 处理submodule
    submodule_info = process_submodules()
    
    # 生成提交信息
    commit_message = generate_commit_message(changes, repo_info, submodule_info, args.model)
    
    # 如果需要提交
    if args.commit:
        do_commit(commit_message)
    
    if DEBUG:
        print_color("\n调试信息已保存到 git-smart-commit.log 文件", Colors.BLUE)
        print_color("可使用 '--view' 参数查看执行过程", Colors.BLUE)

if __name__ == "__main__":
    main() 