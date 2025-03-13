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

def print_color(text, color, **kwargs):
    """使用颜色输出文本"""
    print(f"{color}{text}{Colors.NC}", **kwargs)

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

def generate_commit_message(changes, repo_info, submodule_info, model="mistral-nemo", language="english", num_options=1):
    """使用LLM生成commit信息"""
    print_color(f"正在使用 {model} 生成 {num_options} 个提交信息选项 (语言: {language})...", Colors.BLUE)
    debug_log(f"开始使用LLM({model})生成提交信息，语言: {language}，选项数量: {num_options}")
    
    # 构建提示，根据语言选择提示文本
    if language.lower() == "chinese" or language.lower() == "中文":
        prompt = f"请基于以下Git变更生成 {num_options} 个专业的、遵循最佳实践的commit message，使用中文。\n\n"
        prompt += f"仓库信息:\n{repo_info}\n\n"
        prompt += f"变更内容:\n{changes}\n\n"
        
        if submodule_info:
            prompt += f"Submodule变更:\n{submodule_info}\n\n"
        
        prompt += "生成的commit message应该:\n"
        prompt += "1. 使用现在时态\n"
        prompt += "2. 第一行是简短的摘要 (50个字符以内)\n"
        prompt += "3. 留一个空行后再写详细描述\n"
        prompt += "4. 详细描述应当解释为什么进行更改，而不是如何更改\n"
        prompt += "5. 引用任何相关问题或工单编号\n\n"
        
        if num_options > 1:
            prompt += f"请生成 {num_options} 个不同的选项，并使用'选项1:'、'选项2:'等标记每个选项。"
    else:  # 默认英文
        prompt = f"Based on the following Git changes, generate {num_options} professional, best-practice commit messages in English.\n\n"
        prompt += f"Repository Info:\n{repo_info}\n\n"
        prompt += f"Changes:\n{changes}\n\n"
        
        if submodule_info:
            prompt += f"Submodule Changes:\n{submodule_info}\n\n"
        
        prompt += "The commit messages should:\n"
        prompt += "1. Use present tense\n"
        prompt += "2. Have a short summary line (max 50 characters)\n"
        prompt += "3. Leave a blank line after the summary\n"
        prompt += "4. Explain why the change was made, not how\n"
        prompt += "5. Reference any related issues or tickets\n\n"
        
        if num_options > 1:
            prompt += f"Please generate {num_options} different options and mark each option with 'Option 1:', 'Option 2:', etc."
    
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
        
        # 如果需要多个选项，解析响应
        if num_options > 1:
            commit_options = parse_multiple_commits(ollama_response, num_options, language)
            debug_log(f"解析出 {len(commit_options)} 个提交信息选项")
            return commit_options
        else:
            return ollama_response
            
    except subprocess.CalledProcessError as e:
        print_color(f"LLM调用失败: {e}", Colors.RED)
        debug_log("LLM调用失败", str(e), "ERROR")
        return ["LLM调用失败"] if num_options > 1 else "LLM调用失败"
    except FileNotFoundError:
        print_color("错误: 未找到ollama命令", Colors.RED)
        debug_log("未找到ollama命令", level="ERROR")
        return ["LLM调用失败：未找到ollama命令"] if num_options > 1 else "LLM调用失败：未找到ollama命令"
    except Exception as e:
        print_color(f"调用LLM时发生异常: {e}", Colors.RED)
        debug_log("调用LLM时发生异常", str(e), "ERROR")
        return [f"LLM调用异常: {str(e)}"] if num_options > 1 else f"LLM调用异常: {str(e)}"

def parse_multiple_commits(response, num_options, language):
    """解析LLM返回的多个commit message"""
    debug_log("开始解析多个提交信息选项")
    debug_log("原始响应内容:", response)
    
    # 首先尝试检测是否已经有清晰的选项标记
    if language.lower() == "chinese" or language.lower() == "中文":
        option_patterns = [
            r"选项\s*(\d+)\s*[:：]",
            r"选项\s*(\d+)\s*[：:]",
            r"方案\s*(\d+)\s*[:：]"
        ]
    else:
        option_patterns = [
            r"Option\s*(\d+)\s*:",
            r"OPTION\s*(\d+)\s*:",
            r"Alternative\s*(\d+)\s*:"
        ]
    
    # 尝试查找所有选项的起始位置
    option_positions = []
    
    for pattern in option_patterns:
        matches = list(re.finditer(pattern, response))
        if matches:
            for match in matches:
                option_num = int(match.group(1))
                if 1 <= option_num <= num_options:
                    option_positions.append((option_num, match.start(), match.end()))
            
            # 如果找到了选项，跳出循环
            if option_positions:
                break
    
    # 根据找到的位置分割响应
    if option_positions:
        debug_log(f"找到 {len(option_positions)} 个选项标记")
        # 按位置排序
        option_positions.sort(key=lambda x: x[1])
        
        commit_options = []
        for i in range(len(option_positions)):
            current_pos = option_positions[i]
            # 如果是最后一个选项
            if i == len(option_positions) - 1:
                content = response[current_pos[2]:].strip()
            else:
                next_pos = option_positions[i+1]
                content = response[current_pos[2]:next_pos[1]].strip()
            
            commit_options.append(content)
            debug_log(f"解析选项 {current_pos[0]}: {content[:50]}...")
        
        if len(commit_options) == num_options:
            return commit_options
    
    # 尝试使用三个连续换行符分割
    if not option_positions:
        debug_log("未找到选项标记，尝试用三个换行符分割")
        parts = response.split('\n\n\n')
        if len(parts) >= num_options:
            return [part.strip() for part in parts[:num_options]]
    
    # 如果没有找到足够的选项，尝试直接解析响应中的选项标记
    if language.lower() == "chinese" or language.lower() == "中文":
        commit_parts = response.split("选项")
    else:
        commit_parts = response.split("Option")
    
    if len(commit_parts) > 1:  # 第一部分可能是介绍文本
        debug_log(f"使用简单分割，找到 {len(commit_parts)-1} 个部分")
        commit_options = []
        for part in commit_parts[1:]:  # 跳过第一部分
            if part.strip():
                # 移除选项编号
                cleaned_part = re.sub(r"^\d+\s*[:：]", "", part).strip()
                commit_options.append(cleaned_part)
                if len(commit_options) >= num_options:
                    break
    else:
        debug_log("无法解析多个选项，将整个响应作为一个选项")
        commit_options = [response]
    
    # 填充不足的选项
    while len(commit_options) < num_options:
        commit_options.append(f"选项 {len(commit_options)+1} (生成失败)")
    
    # 如果解析出的选项超过请求的数量，只保留请求的数量
    if len(commit_options) > num_options:
        commit_options = commit_options[:num_options]
    
    return commit_options

def select_commit_message(commit_options):
    """让用户选择喜欢的commit message"""
    if len(commit_options) == 1:
        return commit_options[0]
    
    print_color("\n请选择您喜欢的提交信息选项:", Colors.BLUE)
    
    for i, option in enumerate(commit_options, 1):
        print_color(f"\n--- 选项 {i} ---", Colors.YELLOW)
        print(option)
    
    while True:
        try:
            # 使用print而不是print_color来避免end参数问题
            print(f"{Colors.GREEN}请输入选项编号 (1-{len(commit_options)}): {Colors.NC}", end="")
            choice = int(input())
            if 1 <= choice <= len(commit_options):
                debug_log(f"用户选择了选项 {choice}")
                return commit_options[choice - 1]
            else:
                print_color("无效的选择，请重新输入", Colors.RED)
        except ValueError:
            print_color("请输入有效的数字", Colors.RED)

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

def handle_interactive_mode(commit_options, model, language, changes, repo_info, submodule_info, initial_message=None):
    """处理交互式对话模式，允许用户通过自然语言调整提交信息"""
    # 使用传入的初始消息，或者让用户选择
    selected_message = initial_message if initial_message else select_commit_message(commit_options)
    
    print_color("\n--- 交互模式 ---", Colors.BLUE)
    print_color("您可以通过自然语言对提交信息进行调整，例如：", Colors.BLUE)
    print("1. 合并选项1和选项2")
    print("2. 修改第一行，改为'修复xxx问题'")
    print("3. 添加更多关于xxx的细节")
    print("4. 使用这个提交信息")
    print("5. 退出")
    
    while True:
        print_color("\n请输入您的指令: ", Colors.GREEN, end="")
        user_input = input().strip()
        
        # 检查是否要使用当前信息或退出
        if user_input.lower() in ["使用这个提交信息", "使用", "4", "use this", "accept"]:
            debug_log("用户接受当前提交信息")
            return selected_message
        
        if user_input.lower() in ["退出", "5", "exit", "quit", "q"]:
            debug_log("用户退出交互模式")
            return None
        
        # 处理合并选项的特殊情况
        if "合并选项" in user_input or "combine option" in user_input.lower() or "merge option" in user_input.lower():
            selected_message = handle_merge_options(user_input, commit_options, model, language)
            print_color("\n修改后的提交信息:", Colors.GREEN)
            print(selected_message)
            continue
        
        # 其他自然语言指令处理
        debug_log(f"用户输入自然语言指令: {user_input}")
        print_color("\n正在处理您的请求...", Colors.BLUE)
        
        # 构建提示
        prompt = build_interactive_prompt(user_input, selected_message, language, commit_options)
        
        # 调用LLM处理请求
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            debug_log(f"发送交互提示到LLM({model})")
            debug_log("交互提示内容:", prompt)
            
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
            
            response = result.stdout.strip() if result.stdout else ""
            debug_log("LLM交互响应:", response)
            
            # 更新选中的消息
            selected_message = response
            
            print_color("\n修改后的提交信息:", Colors.GREEN)
            print(selected_message)
            
        except Exception as e:
            print_color(f"处理请求时发生错误: {e}", Colors.RED)
            debug_log("处理交互请求时发生错误", str(e), "ERROR")

def build_interactive_prompt(user_input, current_message, language, all_options=None):
    """构建用于交互式对话的提示"""
    if language.lower() == "chinese" or language.lower() == "中文":
        prompt = "作为Git提交信息生成助手，请根据用户的指令修改当前的提交信息。\n\n"
        prompt += f"当前的提交信息是:\n```\n{current_message}\n```\n\n"
        
        if all_options:
            prompt += "所有可用的选项有:\n"
            for i, option in enumerate(all_options, 1):
                prompt += f"--- 选项 {i} ---\n{option}\n\n"
        
        prompt += f"用户的指令是: {user_input}\n\n"
        prompt += "请直接返回修改后的完整提交信息，不要包含任何解释或其他内容。"
        prompt += "确保提交信息格式符合Git最佳实践：第一行是简短摘要，然后空一行，再写详细描述。"
        
    else:  # 英文
        prompt = "As a Git commit message assistant, please modify the current commit message according to the user's instructions.\n\n"
        prompt += f"The current commit message is:\n```\n{current_message}\n```\n\n"
        
        if all_options:
            prompt += "All available options are:\n"
            for i, option in enumerate(all_options, 1):
                prompt += f"--- Option {i} ---\n{option}\n\n"
        
        prompt += f"The user's instruction is: {user_input}\n\n"
        prompt += "Please return only the modified commit message, without any explanations or additional content."
        prompt += "Ensure the commit message follows Git best practices: a short summary on the first line, then a blank line, followed by a detailed description."
    
    return prompt

def handle_merge_options(user_input, commit_options, model, language):
    """处理合并选项的请求"""
    debug_log(f"处理合并选项请求: {user_input}")
    
    # 解析要合并的选项编号
    option_numbers = []
    
    # 从用户输入中提取数字
    numbers = re.findall(r'\d+', user_input)
    if numbers:
        option_numbers = [int(num) for num in numbers if 1 <= int(num) <= len(commit_options)]
    
    if not option_numbers or len(option_numbers) < 2:
        print_color("未能识别要合并的选项编号，请指定至少两个有效的选项编号", Colors.YELLOW)
        return commit_options[0]  # 默认返回第一个选项
    
    debug_log(f"要合并的选项编号: {option_numbers}")
    
    # 构建合并提示
    if language.lower() == "chinese" or language.lower() == "中文":
        prompt = "请将以下多个Git提交信息选项合并为一个更好的提交信息。合并时保留各选项的优点和重要信息。\n\n"
    else:
        prompt = "Please merge the following Git commit message options into a single, better commit message. Preserve the strengths and important information from each option.\n\n"
    
    for i, num in enumerate(option_numbers):
        option_index = num - 1
        if language.lower() == "chinese" or language.lower() == "中文":
            prompt += f"选项 {num}:\n```\n{commit_options[option_index]}\n```\n\n"
        else:
            prompt += f"Option {num}:\n```\n{commit_options[option_index]}\n```\n\n"
    
    if language.lower() == "chinese" or language.lower() == "中文":
        prompt += "请直接返回合并后的完整提交信息，不要包含任何解释或其他内容。"
    else:
        prompt += "Please return only the merged commit message, without any explanations or additional content."
    
    # 调用LLM处理合并请求
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        debug_log("发送合并选项提示到LLM")
        debug_log("合并提示内容:", prompt)
        
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
        
        response = result.stdout.strip() if result.stdout else ""
        debug_log("LLM合并响应:", response)
        
        if not response:
            print_color("合并选项失败，返回为空", Colors.RED)
            return commit_options[0]  # 默认返回第一个选项
        
        return response
        
    except Exception as e:
        print_color(f"合并选项时发生错误: {e}", Colors.RED)
        debug_log("合并选项时发生错误", str(e), "ERROR")
        return commit_options[0]  # 默认返回第一个选项

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
    parser.add_argument("-l", "--language", default="english", 
                        choices=["english", "chinese", "英文", "中文"], 
                        help="指定commit message的语言 (默认: english)")
    parser.add_argument("-n", "--num-options", type=int, default=1,
                        help="生成的提交信息选项数量 (默认: 1)")
    parser.add_argument("-i", "--interactive", action="store_true", help="启用交互模式，允许通过自然语言调整提交信息")
    
    args = parser.parse_args()
    
    # 确保选项数量合理
    if args.num_options < 1:
        print_color("选项数量必须大于0，设置为默认值1", Colors.YELLOW)
        args.num_options = 1
    elif args.num_options > 5:
        print_color("选项数量过多可能导致质量下降，已限制为最大值5", Colors.YELLOW)
        args.num_options = 5
    
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
    
    # 处理语言标识转换
    language = args.language
    if language == "英文":
        language = "english"
    elif language == "中文":
        language = "chinese"
    
    debug_log(f"选择的commit message语言: {language}")
    
    # 检查是否有变更
    staged_changes = run_git_command(["git", "diff", "--staged"], check=False)
    unstaged_changes = run_git_command(["git", "diff"], check=False)
    submodule_changes = run_git_command(["git", "status"], check=False)
    
    debug_log("检查仓库状态:", {
        "有已暂存更改": bool(staged_changes),
        "有未暂存更改": bool(unstaged_changes),
        "可能有子模块更改": "modified:" in submodule_changes
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
        if "modified:" in submodule_changes:
            print_color("检测到子模块更改但尚未暂存。", Colors.YELLOW)
            print_color("提示: 请使用 'git add <子模块路径>' 添加子模块更改。", Colors.YELLOW)
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
    
    # 生成提交信息选项
    commit_options = generate_commit_message(
        changes, 
        repo_info, 
        submodule_info, 
        args.model, 
        language, 
        args.num_options
    )
    
    # 首先让用户选择一个基础选项
    if isinstance(commit_options, str):
        selected_message = commit_options
        print_color("生成的提交信息:", Colors.GREEN)
        print(selected_message)
    else:
        print_color("\n请选择一个基础提交信息选项:", Colors.BLUE)
        selected_message = select_commit_message(commit_options)
    
    # 然后如果启用了交互模式，进入交互阶段
    if args.interactive:
        print_color("\n已选择基础提交信息，现在进入交互模式...", Colors.BLUE)
        interactive_result = handle_interactive_mode(
            commit_options, 
            args.model, 
            language, 
            changes, 
            repo_info, 
            submodule_info,
            selected_message  # 传递已选择的消息作为初始值
        )
        
        if interactive_result:
            selected_message = interactive_result
        else:
            return  # 用户退出
    
    # 如果需要提交
    if args.commit:
        do_commit(selected_message)
    
    if DEBUG:
        print_color("\n调试信息已保存到 git-smart-commit.log 文件", Colors.BLUE)
        print_color("可使用 '--view' 参数查看执行过程", Colors.BLUE)

if __name__ == "__main__":
    main() 