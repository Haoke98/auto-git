# AutoGit

一个基于LLM能够根据现有的代码变动自动汇总出commit message的git工具

## 初心 ❤️

打造出一个全智能的Git工具，把人类程序猿🐒从无脑🧠写commit message中解救出来 （Passion！！！）

## 功能清单 & ToDo：

- [x] 实现基本的命令集
- [x] 对未暂存的（git unstaged）变化进行检测
- [x] 针对submodule的变化进行深度追踪
    - [x] 如果submodule的内容没变，但是唯独其hash值变化了
        - [x] 实现能够自动获取submodule的old_hash和new_hash
        - [x] 获取submodule对应的仓库从old_hash（git 提交唯一标志）到 new_hash之间的每一次提交中的commit message
        - [x] 进行汇总再把这个汇总应用到主仓库的当前commit message的生成中
- [x] 基于LLM进行推理：
    - [x] Ollama
- [x] 调试模式
- [x] 执行过程可视化
- [x] 生成语言选择功能
- [x] 多个Commit消息推荐功能
- [x] 实现用户和工具之间的自然语言交互 （实则是跟LLM之间）
    - [x] 多轮对话
    - [x] 对话： 选项合并
- [ ] 应用RAG多路召回技术
    - [ ] 实现全局内容刨析，提高准确性
    - [ ] 学会/仿照/参考 用户的以往git commit message习惯
    - [ ] 在git提交日志的基础上实现记忆回显技术
- [ ] 集成ollama
- [ ] 集成git

## 预览

![img.png](assets/img.png)