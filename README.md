# AgentCiCi 开发与管理 Skill

`cc-aidev-agentcici-expert` 是给 Codex 等 AI 智能体使用的 AgentCiCi 技能包。用户只需要用自然语言说明想做什么，Skill 会自动读取必要规范、调用内置工具并返回结果。

它可以帮你：

- 登录 AgentCiCi 并安全保存开发者身份。
- 查看和管理组织内的智能体、技能和 MCP 服务；发现并读取 MCP 工具。
- 读取现有工具并管理智能体与技能、知识库、工具的关联；不创建工具。
- 编译、发布和导出 AgentCiCi 原生资源包。
- 创建和撤销智能体运行 Agent API Key，明文仅保存到私密文件。
- 开发 AI Web 应用，生成 CloudCC 菜单、按钮或全局入口。
- 准备、校验和提交 AI 应用发布申请包。

当前版本：`1.8.1`

## 1.8.1 更新说明

- 安装示例明确使用仓库根目录和技能目录名 `cc-aidev-agentcici-expert`，保留原GitHub仓库地址及已有环境配置，避免按仓库名安装成旧技能名。

## 1.8.0 更新说明

- 应用开发限定 applications/<appCode>，CloudCC资源统一放cloudcc/，不依赖平台源码。
- 类适配器在应用cloudcc工程内执行，通过临时链接共享根配置/缓存，处理缓存失效重建、并发与失败清理，不再创建根backend映射。
- 从应用内首次登录也使用根共享配置；旧应用内配置先报冲突，显式路径仍可使用独立身份。
- 统一已发布SDK/runtime接入、普通应用运行身份、旧菜单显式SDK地址及平台运维边界，清理固定环境和过期示例。
- 保留1.7.9纯Web/AI/MCP显式V2支持及旧包校验兼容；本机验证不代替目标环境安装。

## 安装 Skill

把本仓库地址发给 Codex，然后说：

> 请从 https://github.com/CloudCCAI/cc-aidev-agent-guidelines-common 的仓库根目录安装技能，安装目录名指定为 cc-aidev-agentcici-expert；已有安装按当前工具的升级流程处理，保留环境配置。

使用 Codex 的 `skill-installer` 首次安装时，向其 `scripts/install-skill-from-github.py` 传入 `--repo CloudCCAI/cc-aidev-agent-guidelines-common --path . --name cc-aidev-agentcici-expert`。执行时使用安装器的实际绝对路径；目标已存在时不要直接重复首次安装命令，也不要清空配置。其他AI工具同样保留该技能目录名。仓库名与技能名不同，不按仓库名推导安装目录。

安装后，可以显式指定 Skill：

> 使用 $cc-aidev-agentcici-expert 查看当前组织的智能体。

也可以直接描述 AgentCiCi 相关任务，由 Codex 自动选择本 Skill。

## AI App开发

Web 使用原生 HTML、CSS、JavaScript；业务按需采用 Web → 自定义类 → 自定义对象、Web → Agent（智能体）两条调用链。

按 [七阶段流程](references/development-workflow.md) 完成需求、设计、开发、本地联调、打包组织发布和CRM菜单系统测试。支持Web、对象/字段、自定义类，以及智能体、技能、知识库和MCP关联；分别配置AgentCiCi与CloudCC CRM开发凭据。新增知识库管理及组织应用发布需部署对应后端并授予scope，不能将本地工具更新视为线上接口已生效。

## 多应用项目

AI 应用开发只在 `applications/<appCode>/` 进行，不需要平台 backend/frontend/deploy 源码。每个应用有自己的清单、源码和发布产物，项目根目录共用AgentCiCi配置、CloudCC CLI配置和CRM缓存；应用源码和文档仍各自保存。CloudCC资源集中在应用cloudcc/，类为cloudcc/backend/classes；[共用配置适配入口](references/cloudcc-shared-config.md)临时链接根配置/缓存，在应用cloudcc工程内调用CLI，无根backend映射。完整结构与管理规则见 [项目与多应用目录](references/application-manifest.md#项目与多应用目录)。已有项目保留其结构，不自动迁移。

## 登录 AgentCiCi

1. 在 AgentCiCi 管理后台点击“复制 AI 登录信息”。
2. 把复制的完整内容粘贴给 Codex。
3. 告诉 Codex：

> 这是 AgentCiCi 后台复制的 AI 登录信息，请帮我登录并记住登录状态。

Skill 会解析并验证登录信息，成功后把解码后的地址、Client ID 和 Secret 直接写入项目 `cloudcc-agentcici.config.json`。通过 `use` 选择当前环境，可同时保存 dev、uat、prod 等多组凭据。文件自动加入 `.gitignore`，POSIX 权限设为 `0600`；Token 不落盘。

可以直接告诉 Codex：“把这组登录信息保存为 uat 环境”或“切换到 prod 环境”。旧版钥匙串登录需要重新 login 写入新配置，旧记录保留。详细命令见 [认证说明](references/authentication.md)。

其他常用说法：

> 查看我是否已经登录 AgentCiCi。

> 清除这台电脑上保存的 AgentCiCi 登录信息。

不要把登录信息发到公开对话、工单或代码仓库。Skill 也不会在回答中回显 Secret 或 Token。

## 查看和管理资源

直接告诉 Codex 你想查看哪类资源：

> 列出当前组织的所有智能体，显示 ID、名称和发布状态。

> 查看这个智能体的详情，以及它关联的技能、知识库和工具。

> 列出当前组织的技能。

> 列出当前组织的 MCP 服务。

创建或修改资源时，说明目标即可：

> 创建一个用于生成客户拜访总结的智能体。先跟我确认名称、说明和需要关联的资源，再创建。

> 把“客户资料检索”技能关联到这个智能体，保留它现有的其他关联。

> 更新这个 MCP 服务的说明和服务地址，其他配置保持不变。

> 编译这个智能体；成功后把新版本号告诉我，先不发布。

> 发布这个技能，变更说明是“增加客户行业判断”。

Skill 会在更新前先读取当前资源，保留用户没有要求修改的字段。删除操作会在执行前核对精确目标。

## 导入和导出资源包

> 把智能体“客户助手”以 AgentCiCi 原生包导出到当前项目的 `exports` 目录。

> 导出技能“生日邮件生成”，不覆盖已有文件。

> 用这个原生智能体包和这两个技能包准备一个 AI 应用发布包，先检查依赖映射，不要提交。

应用包中的自定义智能体必须使用 AgentCiCi 原生导出包，不能用普通 JSON 代替。

## 开发 AI Web 应用

可以从业务目标开始：

> 开发一个“客户摘要”AI Web 应用。它在 CloudCC 里打开，使用当前登录组织的 AgentCiCi 配置。先准备可本地验证的前端和应用清单，不要提交发布申请。

如果没有特别说明入口，Web 应用默认使用：

- CloudCC 自定义脚本菜单触发。
- 在菜单对应的内容区展示。

只在需要其他入口时额外说明：

> 这个应用不要使用默认菜单，改为全局浮点入口，打开后默认显示在右侧。

> 在客户详情页增加按钮入口。先查询真实对象信息，让我选择安装范围。

## 准备和提交发布申请

> 检查这个 AI 应用还缺哪些发布信息，只问我尚未确认的必填项。

> 构建并校验这个 AI 应用的发布申请包。完成后告诉我实际清单和产物路径，不要上传。

> 把刚才校验通过的发布申请包提交到 AgentCiCi，然后返回申请 ID 和状态。

“准备发布包”不等于“上传”，“上传申请”也不等于“平台上架”。平台上架仍由平台管理员执行。

## 调用已发布智能体

> 使用这个 Agent API Key 调用已发布的“客户助手”，发送消息“总结今天的客户跟进”。不要把 Key 写入项目文件。

调用已发布智能体使用 Agent API Key；管理智能体、技能、MCP 和应用使用开发者登录信息。两类凭据不能混用。

## Skill 的操作原则

- 查看、分析或设计时，不会擅自修改平台资源。
- 修改前先读取当前资源，只更改用户已确认的内容。
- 不擅自绑定知识库、技能、工具、渠道或凭据。
- 删除前确认精确目标，并检查引用约束。
- 不在回答、日志、URL 或项目文件中暴露凭据。
- Web 应用默认创建 CloudCC 连接应用；只有用户明确说明不需要时才关闭。
- 发布前区分本地校验、申请提交、草稿创建和平台上架。

## 详细规范

README 只提供对话式使用入口。Skill 会在执行任务时按需读取以下规范：

- [Skill 完整工作流](SKILL.md)
- [认证、scope 与错误语义](references/authentication.md)
- [智能体管理](references/agents.md)
- [技能管理](references/skills.md)
- [MCP 服务管理](references/mcp-tools.md)
- [智能体运行 OpenAPI](references/agent-runtime-openapi.md)
- [AI 应用与发布申请包](references/ai-applications.md)
- [应用资源清单](references/application-manifest.md)
- [Web 应用开发规范](references/web-app-development.md)
- [原生资源包](references/resource-packages.md)

## License

本仓库尚未声明开源许可证。在复制、分发或修改前，请先向 CloudCCAI 确认授权范围。
