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

# 颜色定义
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # 无颜色

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
        return True
    except subprocess.CalledProcessError:
        print_color("错误: 当前目录不是git仓库", Colors.RED)
        return False

def run_git_command(command, check=True):
    """运行git命令并返回输出"""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            print_color(f"错误: 执行Git命令失败: {e}", Colors.RED)
            sys.exit(1)
        return ""

def get_git_changes():
    """获取git变动内容"""
    staged_files = run_git_command(["git", "diff", "--staged", "--name-status"])
    staged_diff = run_git_command(["git", "diff", "--staged"])
    return f"{staged_files}\n\n{staged_diff}"

def get_repo_info():
    """获取git仓库全局信息"""
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
    
    # 获取当前分支
    try:
        branch = run_git_command(["git", "symbolic-ref", "--short", "HEAD"], check=False)
        if not branch:
            branch = "detached HEAD"
    except:
        branch = "detached HEAD"
    
    # 获取最近几次提交信息作为上下文
    recent_commits = run_git_command(
        ["git", "log", "-3", "--pretty=format:%h %s"], 
        check=False
    )
    if not recent_commits:
        recent_commits = "无提交记录"
    
    return f"仓库: {repo_name}\n分支: {branch}\n最近提交记录:\n{recent_commits}"

def process_submodules():
    """处理submodule变化"""
    submodule_summary = ""
    
    # 获取已暂存的submodule变化
    submodule_diff = run_git_command(["git", "diff", "--staged", "--submodule"], check=False)
    
    # 查找所有submodule变更
    submodule_pattern = r"Submodule\s+([^\s]+)\s+([0-9a-f]+)\.\.([0-9a-f]+)"
    for match in re.finditer(submodule_pattern, submodule_diff):
        submodule_path = match.group(1)
        old_hash = match.group(2)
        new_hash = match.group(3)
        
        print_color(f"检测到submodule变化: {submodule_path} ({old_hash}..{new_hash})", Colors.YELLOW)
        
        # 进入submodule目录
        current_dir = os.getcwd()
        try:
            os.chdir(submodule_path)
            
            # 获取submodule提交信息
            sub_commits = run_git_command(
                ["git", "log", f"--pretty=format:%h %s", f"{old_hash}..{new_hash}"],
                check=False
            )
            
            # 如果有提交信息，添加到汇总
            if sub_commits:
                submodule_summary += f"Submodule {submodule_path} 更新:\n{sub_commits}\n\n"
                
        except Exception as e:
            print_color(f"处理submodule时出错: {e}", Colors.RED)
        finally:
            os.chdir(current_dir)
    
    return submodule_summary

def generate_commit_message(changes, repo_info, submodule_info, model="mistral-nemo"):
    """使用LLM生成commit信息"""
    print_color(f"正在使用 {model} 生成提交信息...", Colors.BLUE)
    
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
    
    # 调用ollama
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        ollama_response = result.stdout.strip()
    except subprocess.CalledProcessError:
        ollama_response = "LLM调用失败"
    except FileNotFoundError:
        print_color("错误: 未找到ollama命令", Colors.RED)
        ollama_response = "LLM调用失败：未找到ollama命令"
    
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
        run_git_command(["git", "commit", "-m", message])
        print_color("提交成功!", Colors.GREEN)
    else:
        print_color("已取消提交", Colors.YELLOW)

def check_ollama_installed():
    """检查ollama是否安装"""
    if not shutil.which("ollama"):
        print_color("错误: 未找到ollama命令", Colors.RED)
        print_color("请安装ollama: https://github.com/ollama/ollama", Colors.RED)
        return False
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Git智能提交信息生成器")
    parser.add_argument("-g", "--generate", action="store_true", help="生成提交信息")
    parser.add_argument("-c", "--commit", action="store_true", help="生成并直接提交")
    parser.add_argument("-m", "--model", default="mistral-nemo", help="指定LLM模型 (默认: mistral-nemo)")
    
    args = parser.parse_args()
    
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
    
    # 检查是否有暂存的更改
    staged_changes = run_git_command(["git", "diff", "--staged"], check=False)
    if not staged_changes:
        print_color("错误: 没有暂存的更改。请使用 'git add' 添加更改。", Colors.RED)
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

if __name__ == "__main__":
    main() 