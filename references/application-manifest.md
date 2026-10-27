# 资源清单与发布前问答

## 项目与多应用目录

AI应用的源码、资源、文档、构建与发布工作都在 `applications/<appCode>/`。项目根只共享本机配置，不要求存在平台 backend/frontend/deploy 或平台公共SDK源码。新建的第一个应用也放在 `applications/` 下，后续应用并列添加；用户明确指定其他结构时遵循用户要求。接手已有项目先识别现有清单和目录，不自动搬迁或重建已有应用。

```text
项目根目录/
├── cloudcc-agentcici.config.json        # AgentCiCi多环境凭据，Git忽略
├── cloudcc-cli.config.json             # 多应用共用CRM配置，Git忽略
├── .cloudcc-cache.json                 # 多应用共用CLI缓存，Git忽略
├── .gitignore
└── applications/
    ├── customer-insight/
    │   ├── application.json            # 该应用的源清单
    │   ├── package.json                # 前端工具需要时创建
    │   ├── docs/                       # 需求、设计、联调和系统测试记录
    │   ├── cloudcc/                   # 该应用全部CloudCC资源
    │   │   ├── backend/classes/       # CLI维护的类目录及config.json
    │   │   ├── metadata/              # 对象/字段等定义
    │   │   └── scripts/               # CloudCC相关工具
    │   ├── src/                        # 该应用源码
    │   ├── scripts/                    # 按需放构建和验证脚本
    │   ├── resources/                  # 有依赖时保存原生资源包
    │   │   ├── assistant.ciciagent
    │   │   └── analysis-skill.zip
    │   ├── dist/                       # 静态构建结果，Git 忽略
    │   └── release/                    # 带版本号的申请 ZIP，Git 忽略
    └── contract-review/
        ├── application.json
        └── src/
```

- 每个应用有独立的 `application.json`、appCode、版本、构建产物和发布包。只创建实际需要的目录，不为无智能体或技能依赖的应用建立空资源目录；前端使用原生 HTML、CSS、JavaScript，按需保留构建配置。
- 项目根目录默认共用一份 `cloudcc-agentcici.config.json`，在其中管理 dev、uat、prod 等环境。首次登录在项目根目录执行，使用已安装技能脚本的绝对路径；从应用及其子目录调用时固定选择主项目根配置，首次登录也写根目录；遇应用内旧配置先报冲突。如用户明确要求应用独立身份，可在该应用目录保存独立配置或通过 `AGENTCICI_CONFIG_PATH` 指定，避免无意创建配置覆盖项目共用身份。选择配置取决于当前工作目录或显式配置路径，与 `--manifest` 所指目录无关。
- CloudCC CRM配置与缓存同样统一放项目根目录，不在应用内复制配置；对象/字段命令明确传根目录，类通过 [共用配置适配入口](cloudcc-shared-config.md) 操作，真实源码保留在应用cloudcc/backend/classes，CLI工程根为应用cloudcc；适配器临时引用根配置和缓存，不创建根backend映射。不要复制凭据或自动迁移已有源码。
- 清单中 `outputDir`、资源 `file` 等文件路径相对于该清单所在应用目录解析，例如 `dist`、`resources/assistant.ciciagent`。打包输入必须位于该应用目录内，不能通过 `../` 或符号链接跨应用引用；确需复用的原生资源包在各应用目录内保留其完整原包，并在各自清单声明。
- 智能体 `.ciciagent` 和技能 ZIP 保留平台导出的完整原包；`resources/` 为建议名称，实际路径以清单为准。CloudCC 对象、字段定义和自定义类源码按业务需要保存在对应应用内；能否随包安装须核对目标能力，见 [业务资源交付](ai-applications.md#cloudcc-业务资源交付)。
- 源码、应用清单、必要构建脚本及不含真实凭据的配置示例纳入版本管理；真实配置、`node_modules/`、各应用的 `dist/` 和 `release/` 加入 Git 忽略。真实密钥不得进入前端构建目录或发布包。
- 发布产物在各自 `release/` 下按版本保存，如 `customer-insight-1.0.0.zip`；旧版本保留用于追溯，不覆盖同版本文件。
- 开发技能安装目录独立于业务项目，应用源码、登录配置和产物都不写入技能目录。本技能目前没有项目初始化命令，AI 按上述规则创建和维护目录，不杜撰脚手架命令。


## 必填与条件项

- schemaVersion固定2；appCode全局唯一；name名称；version三位0–9、逢9进位；summary非空描述。
- 新四层配置设 `layoutVersion: 2`；未设置的旧清单保持原有兼容行为。
- appType固定web；outputDir为单个构建目录，根层必须有index.html；entry为包内相对入口或完整HTTP(S)地址；renderer=iframe/shadow-dom。JS应用需实现AgentCiCiApp.register挂载协议。
- host 为必填对象，使用最新统一宿主协议：closeBehavior 只能是 hide/confirm-destroy，hostLayer 只能是 content/assistant。需要 CloudCC SSO 票据的 iframe 应用在 host.authentication 中声明 type=cloudcc-sso-ticket、query、targetPath、ticketPrefix 和可选 localeParam；这些业务值属于应用清单，公共 SDK 不按 appCode 写死。
- connectedApplications可选布尔，缺省为true并创建连接应用；只有用户明确不需要 CloudCC 身份/OpenAPI 时才写false。不要扩展为客户端权限对象。
- agent可选且最多一个：platform包含type/ref，仅引用管理 API 已确认 `builtin=true` 的当前 org 内置实例；组织已有的 `builtin=false` 智能体仍属custom，选用前按 [类型核验规则](ai-applications.md#选用智能体前核验类型) 查询；不能附file/skills/knowledges以重绑客户资源。custom包含type/ref/file，skills每项ref/file/bindingRef，knowledges每项ref/name/bindingRef。bindingRef来自原生智能体导出的依赖ref。可选keyType为cloudcc或standard；新普通应用显式使用standard，只有确认需要CRM专用运行身份时使用cloudcc。为兼容旧清单，编译器省略该字段仍按cloudcc处理，不将其当作新应用推荐值。
- launchers 可选；Web 应用未声明时，打包器默认生成一个 `menu` 入口，展示位置为 `page-content`，菜单名使用应用名称，内部标识由 appCode 安全生成。显式提供时必须是非空数组；每项id（稳定且唯一）、name、trigger、positions（有序）、payload（查询确认的CRM安装字段）；可选icon/order/objects/placement/renderer/entry。打包器生成完整启动JS并传 appCode + launcherId；每个入口的 renderer 和 entry 可覆盖应用默认值。file仅用于确有业务自定义脚本的场景，必须位于应用目录内，内容原样打包。菜单图标和排序须映射为CRM payload字段，不能假定各入口字段相同。脚本菜单可设 `sisiShortcut: true`，由安装回执中的菜单 ID 生成思思快捷链接。
- installationManifest 同时保存 application（appCode/name/summary）、launchers（入口元数据）、renderConfig 和 steps（完整JS与资源字段）。SDK地址占位符 `__AGENTCICI_SDK_URL__` 由setup-svc根据服务端AgentCiCi域名解析，不需要客户填写name/icon/position或硬编码环境域名。
- 同一应用每种trigger最多配置一项；这一项可配置多个不重复的positions，第一项为默认位置，其余可切换。入口 id 用于安装资源回执和 SDK 入口级配置选择。

## trigger：触发方式

| 类型 | 含义 | CloudCC安装资源 |
| --- | --- | --- |
| global-floating | 全局浮点入口 | 全局客户端脚本，由SDK创建浮点 |
| create-button | 新建页底部按钮 | 客户端脚本 |
| edit-button | 编辑页底部按钮 | 客户端脚本 |
| menu | 自定义菜单入口 | 自定义脚本菜单 |
| detail-button | 详情页按钮 | 自定义脚本按钮 |
| list-button | 列表页按钮 | 自定义脚本按钮 |

对象相关入口必须提供客户确认的 `objects` 及对应 CRM payload。先通过 CloudCC 开发技能查询对象再请客户选择，不编造对象 ID；后台手工新建按钮的默认客户对象不适用于技能打包。新建/编辑页底部按钮未提供 `file` 时，打包器自动生成参考智能录入的页面生命周期脚本：读取 `obj.formId`，在 `[devid="footerButton"]` 中挂载按钮，点击后携带 `launcherId` 和 `launchContext.formId` 打开应用，表单关闭后清理实例。自定义 `file` 仍优先使用。CRM payload 应绑定对应新建页 `pageId=add` 或编辑页 `pageId=edit` 的 `pageType/onLoad`；多表单场景需核实底部容器定位。

列表／详情脚本按钮参考 AI 听记的 CRM 参数结构：`payload.objid` 是查询得到的实际对象标识，`payload.tpSysButtonVO` 使用 `btnType=listBtn/detailBtn`、`category=CustomButton`、`event=lightning-script` 等目标 CRM 所需字段。打包器生成 `functionCode`，不覆盖传入的对象。详情页如需安装后可见，还要指定 `placement`；列表页不要使用详情布局分配值。

脚本字段按资源类型区分：客户端脚本使用 scriptContent，菜单使用 functioncode，按钮使用 tpSysButtonVO.functionCode（大写 C）。打包后核对非空脚本，安装后读取按钮确认保存内容，不能仅以资源 ID 返回判定脚本可用。

## 详情按钮的布局分配

`objects` 指定入口对象范围，`payload.objid` 是实际安装对象标识；`positions` 只控制应用窗口打开后的展示位置，不会把按钮加入 CRM 页面布局。

- 用户要求详情页可用的按钮时，应明确布局分配范围。当前安装器支持在 launcher 上配置 `"placement": "allObjectDetailLayouts"`，编译后进入对应 `installationManifest.steps[].placement`，安装时将按钮加入目标对象的全部详情布局。
- 缺少 placement 时仅创建按钮，不自动分配布局。仅当用户选择手动分配时才有意省略，并在交付中说明；用户只要求指定布局时，不擅自扩大到全部布局，当前该字段不支持指定布局列表。
- 此值仅用于 detail-button，且 payload 必须有真实 objid、tpSysButtonVO.btnType=detailBtn、category=CustomButton；不得照搬到列表、新建或编辑入口。
- 发布前检查生成的安装步骤确实保留 placement；安装后检查资源回执 layoutIds 和目标详情布局中按钮可见，不能仅检查按钮资源存在。
- 已发布版本不可覆盖。补配需使用新版本；本地修改不会修复已安装布局。现有 setup-svc 对已有按钮升级会报“已有按钮暂不支持升级”，应先核对目标环境支持，再确定补分配或重新安装方案，不承诺升级会自动修复。

入口配置片段（其余必填字段仍需补齐）：

```json
{
  "trigger": "detail-button",
  "positions": ["detail-right"],
  "placement": "allObjectDetailLayouts"
}
```

## positions：展示位置

| 清单类型 | 含义与生命周期 | SDK内部值 |
| --- | --- | --- |
| global-floating | 可拖动浮窗，跨页面保留 | float |
| global-right | 全局右侧占位，跨页面保留 | right |
| detail-right | 详情页右侧占位，离开当前详情页隐藏或清理 | detail-right |
| list-right | 列表页右侧占位，离开当前列表页隐藏或清理 | list-right |
| dialog | 居中模态弹窗，关闭后隐藏 | dialog |
| page-content | 菜单对应内容区，离开菜单销毁 | home |
| fullscreen | 网页视口内全屏，覆盖CRM区域；不是浏览器原生全屏 | fullscreen |

trigger里的global-floating表示小浮点入口，positions里的同名值表示打开后的浮窗，两者职责不同。

`layoutVersion: 2` 时严格使用以下关系：`global-floating` 只可选择 `global-floating`、`global-right`、`fullscreen`；`create-button` 和 `edit-button` 只可选 `dialog`；`menu` 只可选 `page-content`；`detail-button` 只可选 `detail-right`；`list-button` 只可选 `list-right`。每个 launcher 编译为独立的 `renderConfig`，包含该入口的有序位置、iframe/Shadow DOM 渲染方式及加载地址。入口渲染方式与应用默认值不同时，必须给该入口配置匹配的 `entry`，避免 iframe 指向 JS 或 Shadow DOM 指向 HTML。

全局浮点入口的外观、二维拖动、打开隐藏、关闭恢复和销毁由公共 SDK 统一实现；应用只能提供入口 name/icon，不提供业务专属入口样式或拖动规则。

```json
{
  "trigger": "global-floating",
  "positions": ["global-floating", "global-right", "fullscreen"]
}
```

以上为单个入口的类型配置片段；完整入口还需id/name/payload等字段。该例默认浮窗，可切换右侧或全屏。

入口脚本调用 `mount({appCode, launcherId})`；全局浮点调用 `start({appCode, launcherId})`。SDK 按 launcherId 读取入口级 renderConfig，旧清单仍使用应用级 renderConfig。

## 问答流程

1. 先读已有清单、代码、导出包和会话中已确认信息，执行check。不问已知答案。
2. 首轮只问应用标识/名称/描述/候选版本的缺失项；可展示建议值，让客户确认。确认版本需结合平台已有版本，不自行覆盖。
3. Web 应用未指定入口时直接使用默认的 `menu` + `page-content`，不再追问；只在用户要求其他入口或展示位置时确认具体配置。再确认是否引用智能体；连接应用默认创建，不单独询问，只在用户明确要求关闭时设为false。对象相关入口调用CloudCC开发技能读取实际对象候选，再请客户选对象；无法查询时明确等待对象信息，禁止编造ID。
4. 对条件缺失项定向提问：平台智能体ref，或自定义智能体导出包和真实依赖；加载入口及目标环境是否已部署固定版本SDK。密钥通过登录工具处理，不写入清单。
5. 每轮将回答写回application.json。check返回missing为空后继续构建、package、validate；存在缺失则停止上传，继续不依赖答案的本地工作。
6. 上传前展示appCode/version、资源类型、入口/展示位置、连接应用开关及目标环境。只有用户请求提交时submit；仅请求开发/准备时交付包。上架仍要求平台管理员身份，不能用开发者Token越权。

示例问法：
“还缺应用描述。请补充一句用途说明；脚本菜单默认在菜单内容区打开。”
“已查询到客户、联系人、商机对象。这个详情页按钮需要安装在哪些对象？”

源清单填写完成只说明信息完整，不等于已部署接口、已上架或真实客户安装成功。测试证据与真实业务验收分别报告。
