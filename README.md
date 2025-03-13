# AutoGit

一个基于LLM能够根据现有的代码变动自动汇总出commit message的git工具

## 初心&开发原始需求

脚本的功能如下：

1. 根据git变动内容，基于LLM（这里初步开发阶段使用ollama和mistral-nemo模型）来汇总所有改动内容并结合到项目全局内容编写出相对专业和标准的git
   commit message并推荐给用户使用。
2. 得有一个命令集，此外，做所有操作之前先得检测当前目录下是否有git仓库，如果有则正常继续下一步操作，否则提示用户
3. 得考虑到有submodule的情况， 如果submodule的内容没变，但是唯独其hash值变化了，则实现能够自动获取submodule的old_hash和new_hash并能够获取submodule
   对应的仓库从old_hash（git 提交唯一标志）到 new_hash之间的每一次提交中的commit message，并进行一个汇总再把这个汇总应用到主仓库的当前commit
   message的生成中
4. 我的最终目的是做一个可以跨多个平台的工具