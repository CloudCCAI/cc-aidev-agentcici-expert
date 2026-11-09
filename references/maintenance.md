# 技能维护与发布

`cloudcc-ccagent` 的 `.agents/skills/cc-aidev-agentcici-expert/` 是唯一源码目录，随项目的 `master-cn` 管理。本机安装目录和 `CloudCCAI/cc-aidev-agentcici-expert` 是从该目录同步的分发副本。发布历史保存在 GitHub 仓库。

## 功能变更时同步技能

1. 每次 AgentCiCi 功能变更，依据实际实现与规格检查开发者会用到的 API、SDK、鉴权与权限、资源、清单、打包和安装流程。无影响时在任务验收中记录核对结论。
2. 在同一任务和合并变更中更新受影响的技能入口、参考文档、示例、脚本及测试。新能力写清适用平台版本和兼容边界。技能内容有变化时按 `SKILL.md` 的版本规则同步版本和更新说明。
3. 在技能目录执行 `python3 -m unittest discover -s scripts -p 'test_*.py'`，并校验 `SKILL.md` 与文档链接。本机安装需要同步时，从仓库源码更新受管技能文件，保留本机配置和凭据。

## 收到技能升级或发布指令后

用户明确要求升级或发布本技能时，从 `master-cn` 上经过验证的提交导出技能，发布到 `CloudCCAI/cc-aidev-agentcici-expert` 的 `main`，以技能内容作为目标仓库根目录。平台功能更新及其合并只触发仓库内维护。

1. 记录要发布的源码提交与技能版本。用 `git archive "${source_commit}:.agents/skills/cc-aidev-agentcici-expert"` 导出已提交的技能子树。发布范围仅包括该子树的受管文件。
2. 在全新的临时 GitHub 克隆中基于最新 `main` 同步导出目录，保留目标的 `.git` 和已有提交历史。源端删除的文件也要同步删除。发现 GitHub 有独立改动时先在主仓库核对、吸收并复验，再导出。
3. 审阅 `git diff --cached`，并确认目标 `git write-tree` 等于源码 `git rev-parse "${source_commit}:.agents/skills/cc-aidev-agentcici-expert"`。有差异才在发布仓库提交，使用普通快进推送。推送后回读 GitHub `main`，核对提交及根树并记录发布版本和源码提交。
