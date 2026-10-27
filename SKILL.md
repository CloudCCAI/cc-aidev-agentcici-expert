---
name: cc-aidev-agentcici-expert
metadata:
  version: "1.8.1"
description: 使用开发者密钥管理 AgentCiCi 组织内智能体、技能、知识库和 MCP 服务，发现并读取 MCP 工具后关联智能体；指导第三方 Web AI 应用开发、CloudCC 自定义对象与自定义类开发、站点与脚本菜单集成，并将前端产物、原生智能体包和技能包整理为发布申请 ZIP 并提交到已部署的接收接口。用于平台资源管理、应用开发与申请包准备；自动安装须先核对服务端能力。
---

# AgentCiCi 平台管理

当前技能版本：`1.8.1`。

本 Skill 同时服务两个阶段：设计阶段先理解模块职责与边界，实施阶段再调用明确的管理 API。不要在不了解现有资源的情况下直接写入。

## 技能版本号规范

- 技能版本统一为 `X.Y.Z`，三段均为一位数字 `0–9`，格式为 `^[0-9]\.[0-9]\.[0-9]$`，不使用多位数字或预发布后缀。
- 每次技能更新从最右位递增；该位为 9 时归零并向左进位，例如 `1.2.8 → 1.2.9 → 1.3.0`、`1.9.9 → 2.0.0`。
- 同步更新 frontmatter 的 `metadata.version`、正文版本及本地安装副本。系统内部的数字版本 ID 不受此规则影响。
- `9.9.9` 已达此格式上限，后续版本规则由用户决定，不回绕或重复使用旧版本。

## AI App 开发入口

创建或继续开发AI应用时，先读 [AI App七阶段开发流程](references/development-workflow.md)，按需求讨论、设计、平台文档、开发、本地联调、打包发布、CRM菜单系统功能测试推进。每个应用在自身docs中保存需求、设计与测试记录。资源范围含Web、对象/字段、自定义类、智能体、技能、知识库和MCP工具，按业务需要创建并关联；暂不扩展触发器或定时类。启动先分别检查AgentCiCi与CloudCC CRM两套开发配置，不混用凭据，测试密钥及缓存不得入发布包。CRM系统测试限当前用户桌面业务流程，不默认多用户、多角色或移动端测试。

### AI 应用的智能体、技能与工具选择

开发 AI 应用需要智能体时，优先新建该应用自己的智能体；继续开发时维护该应用已有智能体，不重复创建。技能和工具则先查询当前组织可用资源，核对用途、权限及版本，合适的优先复用并关联到应用智能体；现有技能不满足需求时再按需新建。MCP 工具通过服务发现、读取真实 schema 后关联，不杜撰或单独创建工具。用户明确指定使用已有智能体时遵循其选择，不为本应用擅自改动共享智能体、技能或工具定义。

## 入口类型与展示位置

完整枚举、生命周期及示例见 [资源清单类型](references/application-manifest.md)。新清单设 `layoutVersion: 2`，按“CRM资源 → 触发入口 → 展示位置 → 渲染方式”配置；严格限制入口与位置的组合，每个入口独立保存 iframe 或 Shadow DOM 渲染配置。同一应用每种 trigger 最多一项，第一展示位置为默认。列表／详情脚本按钮由清单传入实际 `objects` 和 `payload.objid`，不能套用后台手工新建时的客户对象默认值。脚本菜单可设 `sisiShortcut: true`，安装后的真实菜单 ID 用于思思快捷按钮。

## CRM 组织与 AI 资源归属

普通 AI 应用按标准 SDK/API Key 调用；后端以 API Key 所属 AgentCiCi 租户检查授权和计费。不要自行生成 `crmwb_` 身份、传入收费租户或复制官方应用专用认证流程。

官方 CRM 专用会话保留 CRM 业务隔离身份，通过开户保存的 CRM orgId → AgentCiCi companyId 映射解析正式资源租户。授权、模型配置、语音和模型 Credits 均归正式租户；映射缺失必须明确报错，不能回退到独立赠送额度。验收核对实际用量事件及结算租户，不能只看页面可打开或请求成功。

## CloudCC 资源开发前置要求

AI 应用涉及新建或修改 CloudCC 自定义类、对象、字段时，必须先检查开发者当前 AI 工具是否已安装并可读取 `cc-customization-expert-msapi`。技能来源为 [CloudCC 专用开发技能](https://github.com/CloudCCAI/cc-customization-expert-msapi)，不能仅凭通用 Java 知识或本 Skill 的示例生成平台资源。

- 检查当前工具的技能目录：必须有该技能的 `SKILL.md` 和可运行的 `tools/bin/cloudcc`。Codex 使用 `${CODEX_HOME:-$HOME/.codex}/skills/cc-customization-expert-msapi`；其他工具使用其实际技能目录，不把项目源码目录视为已安装。
- 未安装时，先从上述仓库安装完整技能包，再读取其 `SKILL.md` 并运行包内 `tools/bin/cloudcc --version`。Codex 优先使用 `skill-installer` 的 `scripts/install-skill-from-github.py --repo CloudCCAI/cc-customization-expert-msapi --path . --name cc-customization-expert-msapi`；仓库根目录就是技能根目录，不能只下载 `SKILL.md`。其他工具使用自身支持的技能安装方式。已安装时复用，不覆盖现有技能或环境配置；安装不完整时报告缺失项。
- **设计前先获取文档**：涉及自定义类、对象或字段时，必须先执行下列对应资源的两条命令，读取 `introduction`（资源介绍）和 `devguide`（开发指南），再进行该资源的设计、定义或源码生成。涉及多类资源时，逐类读取两份文档；不能先设计后补读，也不能等到开发或发布前才读。这里的 `cloudcc` 指已安装专用技能内的 `tools/bin/cloudcc`，实际调用使用该程序的绝对路径，不依赖全局 CLI。
- 同时遵守 CloudCC 技能要求的平台能力文档和按需文档，例如类调用外部 HTTP 前读取 `platform/apiRegistrar devguide`。按文档确认 API Name、字段类型/约束/关系、类结构、平台 SDK、权限与校验规则；修改前回读实际资源。
- 技能安装失败、CLI 不可运行或对应文档无法读取时，不继续猜测并生成这些资源；说明具体缺失，仍可继续不依赖这些资源的前端工作。

设计前按资源类型执行：

```bash
# 自定义类
cloudcc doc classes introduction
cloudcc doc classes devguide

# 自定义对象
cloudcc doc object introduction
cloudcc doc object devguide

# 自定义字段
cloudcc doc fields introduction
cloudcc doc fields devguide
```

这里安装的是开发者本机的开发技能，不是向客户 CRM org 安装业务资源。文档中的 CLI 元数据操作与 AI 应用包安装是不同通道：AI 应用业务资源仍由目标环境已部署的 setup-svc 原生能力安装，不因此引入 MetadataService 或传统软件包安装器依赖；直接操作开发 org 时则遵守 CloudCC 技能的 provider 要求。

## 第三方 Web 应用开发规范

应用使用原生 Web（HTML、CSS、JavaScript）开发，交付可部署的静态前端。 **AI 应用 UI 不得使用或依赖 CloudCC CRM 自定义页面（customPage/VisualPage）和自定义组件（pagecomponent/customComponent）。** 所有页面、表单、列表及交互均在 Web 前端中实现，通过本技能规定的宿主 SDK 以 iframe 或 Shadow DOM 挂载。菜单、按钮只负责调用 SDK 启动 Web，不跳转 injectionComponent 等自定义页面路由；整理旧应用时必须将这类入口改为标准 Web 入口。业务按需采用两条调用链，可在同一应用中组合：

- **Web → 自定义类 → 自定义对象**：由 CloudCC 提供数据存储、业务逻辑和权限校验。
- **Web → Agent（智能体）**：通过宿主 SDK 获取运行上下文，调用已发布智能体的运行 OpenAPI；按 [运行接口规范](references/agent-runtime-openapi.md) 处理鉴权、会话与流式响应。

- 脚本兼容：应用 `package.json` 不设置 `"type": "module"`，页面不使用 `<script type="module">`；发布产物使用普通 `.js` 脚本，不交付需要浏览器加载的 `.mjs` 或原生 ES Module。源码模块需经构建合并为 IIFE/普通脚本，具体要求见 [构建与站点](references/web-app-development.md#构建与站点)。
- 资源设计：构建 AI 应用时，默认优先新建归属当前应用的自定义对象（及所需字段）和自定义类；只有用户明确要求扩展已有资源时，才在其指定范围内新增字段、修改对象定义或扩展类逻辑。查询已有资源用于了解现状、检查 API Name 冲突和必要关联，不能据此擅自改为扩展已有资源；继续开发时保留本应用已创建的资源，不重复新建。
- 数据存储：创建 CloudCC 自定义对象和字段，保存业务数据；按上述资源设计规则核对已有对象与字段。 存储长文本内容时可选文本区字段（4000 字符）或文本区长字段（32000 字符），按预期长度选型，详见 [长文本字段选型](references/web-app-development.md#长文本字段选型)。对象、字段的业务引用使用 API Name，不在代码或可分发包中写死源 org 的内部 ID。
- 业务逻辑：使用 CloudCC 自定义类实现查询、写入、校验和业务规则。Web 负责展示、交互及必要的输入提示，最终校验和访问权限在自定义类中按当前用户与 org 执行；不信任前端传入的组织或用户身份。
- 调用方式：CRM 宿主中的 Web 通过 `window.$CCDK.CCCommon.post(className, methodName, params)` 调用自定义类；iframe Site 使用宿主 SDK 提供的 `cloudccContext`，通过 OpenAPI 调用同一自定义类。两者的 `params` 均按 Java 形参顺序传入 `{argType, argValue}` 对象。不要直接读取跨域 parent 的 CCDK，也不要把业务数据读写改为浏览器直接访问对象接口。
- 交付内容：除 Web 构建产物外，需要时提供对象、字段定义与自定义类源码，纳入 AI 应用包的业务资源。客户安装不依赖 MetadataService；直接开发CRM资源时遵守专用技能的provider规则，不复用传统软件包安装代码；具体打包与安装以目标环境已部署能力为准。

按需读取 [Web 应用开发中的数据与业务逻辑](references/web-app-development.md#cloudcc-数据存储与业务逻辑) 和 [业务资源交付](references/ai-applications.md#cloudcc-业务资源交付)。没有存储或业务规则的应用不强制增加对象或类。

## AI 应用项目组织

AI 应用开发的工作目录固定在 `applications/<appCode>/`；新建首个应用也采用此结构。不要求读取或修改 AgentCiCi 平台 backend/frontend/deploy 源码，不把平台维护列为应用开发前置步骤。每个应用独立维护 `application.json`、源码、构建和发布产物，根目录共用 `cloudcc-agentcici.config.json`、`cloudcc-cli.config.json` 和 `.cloudcc-cache.json`，多个应用不分别配置CRM凭据；源码、对象定义和文档仍在各自应用内。所有 CloudCC 资源放应用 `cloudcc/`，类源码为 `cloudcc/backend/classes/<ClassName>/`。CRM类操作使用 [共用配置适配入口](references/cloudcc-shared-config.md)，以应用 cloudcc 为CLI工程根，临时引用根共享配置；不向项目根创建 backend 类目录或搬移用户源码。详细目录、路径解析、Git 忽略及已有项目处理规则见 [项目与多应用目录](references/application-manifest.md#项目与多应用目录)。开始开发应用前读取该节；遵循用户明确指定的结构，不自动迁移已有项目，不把业务文件放入技能安装目录。

## 应用入口与安装职责

新应用的入口脚本向 `agentcici-app@1.1.0.js` 传 `appCode` 和稳定的 `launcherId`，不要传 name/icon/position。名称、图标、触发方式与入口级渲染配置保存到资源清单；公共 SDK 按 appCode 请求 setup runtime 的已安装快照。全局浮点使用 `start({appCode, launcherId})`，菜单/脚本按钮使用 `mount({appCode, launcherId})`。入口浮点、拖动、去重和清理属于公共 SDK，不在每个应用复制一份。

普通 iframe Web 应用也必须在子页面引入同一 SDK，用 `AgentCiCiApp.createClient(...)` 获取宿主上下文；不再自行实现 `message` 监听、requestId 关联、超时或来源校验，也不要预置部署域名白名单。本地模式仅在顶层 localhost 页面显式传入 `localContext`。完整用法与验收见 [Web 应用开发](references/web-app-development.md#web-应用子页-sdk)。

新 AI 应用默认创建并绑定 CloudCC 连接应用：源清单省略 `connectedApplications` 时按 `true` 编译，安装清单生成 `requiresConnectedApplication=true`。只有用户明确要求不创建、且应用不需要 CloudCC 用户身份或 OpenAPI 能力时，才显式设为 `false`。

打包工具默认生成完整启动 JS，放入 installationManifest.steps 的 scriptContent/functioncode；application/launchers/renderConfig 一起随包提交。setup-svc 安装时保存清单，解析 SDK 地址占位符并按固定资源类型创建客户端脚本、菜单、按钮；setup-web 只预览和发起安装，不再代为调用资源创建接口。旧版本安装不会自动获得新入口配置，需要发布新版本并升级。

新建页和编辑页入口未提供自定义 `file` 时，打包器自动生成 CRM 表单底部按钮的生命周期脚本；仍需确认对象范围并配置对应页面的 `pageType/onLoad` 资源参数。详见 [资源清单类型](references/application-manifest.md)。

详情页按钮的创建与布局分配是两个步骤。发布前按 [清单规范](references/application-manifest.md#详情按钮的布局分配) 核对 placement，不能把 positions 当成按钮布局配置，也不能以按钮创建成功代替页面可见验收。

## 入口脚本的 JS 缓存刷新

生成客户端脚本、菜单脚本、按钮脚本时，所有动态加载的 JS（包括 SDK）的 URL 都必须在加载时追加时间戳查询参数：使用 `new Date().getTime()`，不能在生成或打包时写死。自定义 `file` / `functioncode` 也遵守此规则。保留原有查询参数和 hash，推荐：

```js
const url = new URL(src, document.baseURI);
url.searchParams.set('_t', new Date().getTime());
script.src = url.href;
```

保留已有 SDK 单例和加载去重；时间戳用于实际发起 JS 请求时刷新缓存，不要求重复加载已初始化 SDK。

## 前置配置

优先使用管理后台“复制 AI 登录信息”得到的 Base64 文本。收到这类文本或用户要求登录/记住登录时，先读 [references/authentication.md](references/authentication.md)，通过 `python3 scripts/agentcici_auth.py login` 的标准输入或不回显交互输入传入，不把真实值写入命令参数、日志或回答；仅允许认证脚本写入下述本机凭据配置。

- Base64 解码后是三项 export 声明，脚本按数据解析，绝不 source/eval/执行它。
- 登录先调用 `/openapi/v1/developer/token` 验证，成功才将解码后的 `baseUrl`、`clientId`、`clientSecret` 直接保存到项目 `cloudcc-agentcici.config.json`；顶层 `use` 选择环境，每个环境独立保存凭据，不依赖系统钥匙串。
- 在 applications/<appCode> 内执行时固定使用主项目根配置，首次登录也在根创建；发现应用内旧配置先报冲突，不静默选用。其他资源管理工作目录沿父级查找最近配置，无则在当前目录创建。可用 `AGENTCICI_CONFIG_PATH` 指定完整路径。操作前确保工作目录或显式路径指向用户目标项目，不在技能安装目录保存业务凭据。
- `login --env uat` 保存并切换到该环境，`use uat` 切换已有环境；不指定时沿用当前环境，首次为 `dev`。`AGENTCICI_LOGIN_PROFILE` 可覆盖文件 `use`，认证命令 `--env` 优先级最高。
- 管理与应用提交命令自动读取同一配置并换取短期 Token，Token 只在进程内缓存。`status` 不输出 Secret；`logout --env uat` 仅移除该环境，不撤销服务端凭据。
- 保存时设置 POSIX 文件权限 `0600`，自动将配置及临时文件加入同目录 `.gitignore`；真实配置不提交、不打包、不回显。旧 `login.json` / `login-*.json` 及钥匙串不自动迁移，重新 login 写入新格式。
- 环境变量方式仍可用，必须同时设置 AGENTCICI_BASE_URL、AGENTCICI_CLIENT_ID、AGENTCICI_CLIENT_SECRET；优先于保存身份，禁止混合两组身份字段。
- 用户未提供登录信息时先检查保存状态；缺少时引导复制，不要求每次重新提供密钥。
- 管理 OpenAPI 不使用 Keycloak，也不接受单智能体运行 API Key。Secret 和 Base64 原文均按凭据处理，不写日志。

## 选择模块

- AI 应用开发或发布申请包：先读 [references/ai-applications.md](references/ai-applications.md)，开发前端时再读 [references/web-app-development.md](references/web-app-development.md)。使用 `scripts/agentcici_application.py check|package|validate|submit|draft|status|list|get|publish|release|delete`；本地打包成功不代表已提交、已发布或可自动安装。删除应用使用 `delete APP_CODE --confirm-id APP_CODE`，先查询并取得用户对精确目标的明确授权；删除范围与引用限制见该参考文档。
- 智能体/技能上传下载及知识库依赖：读 [references/resource-packages.md](references/resource-packages.md)。保留原生包，不用 CRUD 返回 JSON 冒充导出包；后台登录接口不能使用开发者 Token 冒充登录身份。
- 智能体设计、CRUD、关联资源或编译发布：先读 [references/agents.md](references/agents.md)，实施时运行 `scripts/agentcici_manage.py agents ...`。
- 创建或撤销智能体运行密钥：先读 [智能体密钥管理](references/agents.md#运行-api-key-管理)，使用 `agents create-api-key` / `agents revoke-api-key`；明文 Key 只保存到指定私密文件，不回显或打包。
- 调用已发布智能体：读 [references/agent-runtime-openapi.md](references/agent-runtime-openapi.md)。这套运行 API 使用 Agent API Key，不使用开发者密钥。
- 技能设计、CRUD 或编译发布：先读 [references/skills.md](references/skills.md)，实施时运行 `scripts/agentcici_manage.py skills ...`。
- MCP 服务设计、CRUD、工具发现与组织现有工具读取：先读 [references/mcp-tools.md](references/mcp-tools.md)，实施时运行 `scripts/agentcici_manage.py mcp ...` 或 `tools list`；工具只能读取并关联智能体，不单独创建。
- 知识库管理、资料上传、索引与检索：读 [references/knowledge-bases.md](references/knowledge-bases.md)，使用 `scripts/agentcici_manage.py knowledge ...`；随后将真实库ID关联到智能体并编译发布。
- 换票、scope、错误语义：读 [references/authentication.md](references/authentication.md)。

只读取当前任务所需的参考文件。

## 智能体运行接口地址

调用智能体运行 OpenAPI 时，`apiBase` 必须是包含 `/openapi/v1` 的完整 API 基地址。生产嵌入模式使用宿主 runtime 返回的 `context.apiBase`；本地测试配置的 `apiBase` 也必须包含该前缀。业务请求代码只拼接 `chat-messages`、`parameters` 等相对端点，不得包含、补齐、探测或重复拼接 `/openapi/v1`。具体示例与验收见 [运行 OpenAPI 教程](references/agent-runtime-openapi.md#apiBase-与请求路径)。

## Web UI 一致性

开发 Web 页面前必须阅读 [CloudCC CRM Web UI 规范](references/crm-web-ui.md)，按 CRM 的颜色、字体、控件密度、列表/表单/弹窗与操作布局实现。规则适用于 iframe 和 Shadow DOM；应用样式限定在自身容器内，导航、浮点与外壳关闭入口由宿主/公共 SDK 管理。交付前在实际桌面容器中对照 CRM 验收，不能只检查独立开发页面。

## Web 应用默认交付

新建 AI 应用使用独立目录与 `application.json` 资源清单。Web 应用未声明 `launchers` 时，默认生成 `menu` 触发入口并以 `page-content` 为默认展示位置，不再要求客户确认这个默认值；客户显式配置 launchers 时按其选择生成客户端脚本、菜单或按钮入口，不额外强制创建菜单。宿主获取当前 org 的 runtime 配置，通过 SDK 挂载 Shadow DOM 应用或经校验的 postMessage 注入 iframe；应用初始化兼容 iframe 与显式本地测试模式。具体协议与验收见 [references/web-app-development.md](references/web-app-development.md)。不能在菜单或 URL 中写入真实 Key，也不能仅交付 window.open 菜单。

## 实施工作流

1. 根据意图确定模块和所需 `*.read`、`*.write`、`*.delete` scope。
2. 编辑或删除前必须先 `get` 当前资源，核对 ID、来源、是否内置以及引用约束。
3. 创建和编辑只写入用户已明确的信息；不要擅自绑定知识库、工具、渠道或凭据。
4. 技能与 MCP 编辑使用完整 `PUT`，先读取原对象，再合并用户确认的变更，最后提交完整请求体。
5. 删除前向用户确认精确目标；命令行必须把相同 ID 再传给 `--confirm-id`。
6. 输出资源 ID、关键变更和任何约束；不得回显凭据或 Token。

## 命令入口

命令示例中的 `/installed/agentcici` 代表本技能的实际绝对安装路径，执行前替换；在用户项目目录运行，避免相对脚本路径或切换到技能目录导致配置解析到错误项目。

```bash
python3 /installed/agentcici/scripts/agentcici_manage.py agents list
python3 /installed/agentcici/scripts/agentcici_manage.py agents get AGENT_ID
python3 /installed/agentcici/scripts/agentcici_manage.py agents create --file /absolute/path/agent.json
python3 /installed/agentcici/scripts/agentcici_manage.py agents update AGENT_ID --json '{"summary":"新的说明"}'

python3 /installed/agentcici/scripts/agentcici_manage.py skills list
python3 /installed/agentcici/scripts/agentcici_manage.py skills create --file /absolute/path/skill.json
python3 /installed/agentcici/scripts/agentcici_manage.py skills update SKILL_ID --file /absolute/path/skill.json

python3 /installed/agentcici/scripts/agentcici_manage.py mcp list
python3 /installed/agentcici/scripts/agentcici_manage.py mcp create --file /absolute/path/mcp.json
python3 /installed/agentcici/scripts/agentcici_manage.py mcp update SERVER_ID --file /absolute/path/mcp.json
python3 /installed/agentcici/scripts/agentcici_manage.py mcp discover SERVER_ID
python3 /installed/agentcici/scripts/agentcici_manage.py mcp tools SERVER_ID
python3 /installed/agentcici/scripts/agentcici_manage.py tools list
python3 /installed/agentcici/scripts/agentcici_manage.py agents bind-tools AGENT_ID --file /absolute/path/binding.json
```

长数据优先使用 `--file`，减少 shell 转义和敏感内容进入终端历史的风险。

应用包必须且只能包含一个 Web 应用；智能体可选且最多一个，技能可包含多个。选用智能体前必须从目标环境管理 API 核验 `builtin`：只有 `true` 可作平台引用，`false` 使用自定义原生包，缺失或无法读取时不猜测。具体核验与交付规则见 [选用智能体前核验类型](references/ai-applications.md#选用智能体前核验类型)。

## 发布前问答

准备或发布 AI 应用时，先读 [清单与问答规范](references/application-manifest.md)。读取现有清单及客户已确认信息，运行 `check --manifest ...`，只问仍缺失或冲突的必填项，分组提问并将回答写回应用目录的清单。对象相关入口先用 CloudCC 开发技能查询实际对象，再让客户选择；不猜测对象 ID、已有资源 ref 或发布版本。不请求用户重复提供已确认信息。

缺失项未补齐前可继续开发和只读检查，但不得上传或声称可发布。补齐后构建、打包、校验并展示实际清单与资源摘要。开发者可按application.submit上传并创建本组织草稿，按application.publish发布本组织拥有的版本；平台应用发布与市场审核仍由平台管理员执行，不赋予跨组织或自动上架权限。
