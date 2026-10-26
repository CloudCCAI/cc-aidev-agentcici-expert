# AI 应用与发布申请包

新应用使用 [源清单与发布前问答](application-manifest.md)。源清单保存于应用自己的目录，由工具生成 ZIP 内的 application.json；源清单不被覆盖。

## 提交与权限

- `check` 检查源清单；`package` 打包；`validate` 校验v1/v2包；`submit` 上传并创建草稿；`draft` 重试草稿；`status` 查询申请；`list/get` 管理本组织应用与版本；`publish` 发布已上传版本；`release` 串联打包、上传、草稿和组织发布。
- POST `/openapi/v1/management/application-requests`，multipart file，需要 application.submit。
- GET `/openapi/v1/management/application-requests/{id}` 与 `/{id}/download`，需要 application.read，只允许本组织。
- POST `/openapi/v1/management/application-requests/{id}/draft`，需要 application.submit。开发者只能创建本组织拥有应用的草稿，不能认领平台应用或其他组织应用。组织发布使用下述独立权限，不自动上架市场。
- 平台管理员可用 POST `/platform/application-requests/{id}/draft` 将已提交包建立为平台应用草稿（仅新平台应用或原平台所有应用）。再走平台现有版本发布接口；开发者Token不能调用这两个平台操作。
- 同 org + ZIP SHA256 幂等；结果未知时重交原包，不重新打包冒充同一次重试。相同版本不可用不同包覆盖，已发布版本不可修改。
- 对既有平台思思的开发者提交可能上传成功、自动草稿被拒绝；保留申请ID交平台管理员，不更改appCode所有权或扩大开发者权限。

- GET `/openapi/v1/management/ai-applications/owned` 列出本组织开发的应用，GET `/{appCode}` 查询本组织拥有的应用及版本，需application.read；与已有“可安装目录”列表不同。
- POST `/openapi/v1/management/ai-applications/{appCode}/versions/{version}/publish` 需application.publish，复用组织发布的所有权、版本和制品校验，成功返回组织应用及版本状态。已有凭据需组织管理员明确增加该scope，不自动增权。
- 新API必须部署对应后端后才能调用；`release`失败区分上传、草稿、发布阶段。上传/发布结果未知先查询，不能重新打包覆盖同版本；可复用原ZIP调用submit、或单独draft/publish恢复。

包存储、OSS和最多5个版本清理见 [存储规范](application-storage.md)。开发者不需要OSS密钥。申请SUBMITTED、草稿DRAFT和市场已发布是不同状态。

## 选用智能体前核验类型

开发时选定智能体、生成源清单前，使用目标环境和目标组织的开发者凭据执行 `python3 scripts/agentcici_manage.py agents get AGENT_ID`（需要 `agent.read`），读取真实 `agentId`、`builtin`、`enabled`、`publishedVersionId` 与 `channels`。在应用交付记录中保存环境、核验时间和这些非敏感结果；打包提交前确认查询结果与清单一致。

- `builtin=true` 才可声明 `agent.type=platform`，生成 `platformAgent={ref}` 并保持 `agents` 为空；引用当前安装组织的内置实例，不导出或覆盖它。
- `builtin=false` 必须声明 `agent.type=custom`，提供原生 `.ciciagent` 导出包并按真实导出结果映射技能、知识库及其他依赖；即使该智能体在本组织已存在、已发布且 API 可调用，也不能改为平台引用。
- `builtin` 缺失、不是布尔值、读取失败或环境/组织身份未确认时，不能猜测类型；暂停智能体打包与提交，继续不依赖该判断的开发和只读核验。

名称含“平台”或“CRM”、组织内已存在、已发布、具有 `api` 渠道，均不能作为平台类型依据。`keyType=standard/cloudcc` 是运行鉴权方式，与 `builtin` 和打包类型独立；不通过修改 `builtin`、更换智能体或放宽安装校验来掩盖类型不符。

类型确认后另行核验启用、发布及运行权限；选择了平台引用的应用，在目标安装组织核验同一 ref 的内置实例、发布状态与权限。无法访问该组织时明确记录待验，不将源组织查询、包格式校验或模拟页面测试当作真实安装通过。

## 包内协议与兼容

外层 `format=agentcici-application-request`；不含CRM业务资源时为formatVersion=1，含对象/字段/类时为formatVersion=2。含 application.json、单个 site.zip（根层index.html）、自定义智能体 agents/<ref>.ciciagent、独立技能 skills/<ref>.zip。新清单入口代码写入 installationManifest.steps；仅旧menu格式额外生成 cloudcc/menu.json。sha256覆盖所有外层文件，application.json自身除外，原生包字节不变。

平台智能体使用可选platformAgent={ref}，agents为空；不打包它已有的托管技能/知识库。不需要智能体时agents为空且无platformAgent。自定义智能体仍完整校验导出依赖映射，不支持工具依赖或托管技能伪造导出。知识库定义至少ref/name，客户文档不随包上传。

旧源清单web.directory、agents/skills/knowledgeBases/menu仍可打包；新应用只使用schemaVersion=2。新源清单appType=web，不接受开发者自行声明官方发布身份。官网身份由平台管理员创建草稿时确定。

## 发布与安装

上传解析资源清单并持久化；查询不反复下载解压。平台发布将site.zip解压至Nginx aiapp/<app>/<version>/<摘要>/，目录755、文件644。renderConfig.entryPath为包内相对入口，发布确认文件存在；安装后setup用当前环境地址和已安装webUrl生成完整entryUrl。外部入口使用entryUrl。新入口解析要求部署本次AgentCiCi与setup代码。

setup调用已发布版本的安装清单和 POST `/openapi/v1/management/ai-applications/{app}/versions/{version}/install-resources`，需要application.install。自定义资源在当前org创建并绑定；平台智能体按ref读取当前org实例及已发布版本，不导出或覆盖客户修改。平台智能体不存在、无权限或未发布时明确失败，不跨org取资源。每个应用最多一个智能体和一个Web应用。

connectedApplications是可选布尔开关，缺省为true，转换为requiresConnectedApplication；setup为true时创建连接应用。只有用户明确不需要 CloudCC 身份/OpenAPI 时才设为false。运行时由宿主换取OpenAPI token，Secret不传入应用、Key和token不放URL。安装steps携带完整客户端脚本/菜单/按钮源码，由setup-svc固定适配器执行，setup-web只请求 /install 或 /uninstall。pendingManifest保存本次安装清单，installationManifest在成功后保存完整已安装快照；runtime只返回application/launchers/renderConfig等运行字段，不返回完整脚本清单。每步资源ID存入resources，首次安装失败按记录自动清理；升级失败保留升级失败状态和已有资源，不能当成首次安装删除。真实安装验收与本地验证分别记录。

## CloudCC 业务资源交付

第三方应用以一个 Web 应用为主体，UI不使用或依赖CRM自定义页面和自定义组件；旧菜单中的injectionComponent等自定义页面入口必须改为标准SDK Web挂载入口。需要存储时提供自定义对象及字段定义，需要业务逻辑时提供自定义类源码；Web 按 [调用规范](web-app-development.md#web-调用自定义类) 请求类，由类操作对象。明确每项资源的 API Name 和依赖顺序，对象先于字段、依赖资源先于调用它们的类；内部 ID 由安装 org 解析，业务数据与凭据不打包。

上文 `formatVersion=1` 和常用 `package` 命令描述现有 Web/AI 资源流程，不能据此声称已经打包业务资源。业务资源使用外层 `formatVersion=2`、`cloudccResources` 声明及 `installationManifest.schemaVersion=2`。执行前核对打包工具、发布接收端和 setup-svc 是否实际支持；技能打包器现支持从源清单cloudccResources读取object/field/class，写入v2包并验证资源白名单、路径、依赖和摘要；定义须遵循安装器允许的字段，不直接打包MetadataService plan或源org ID。服务端或setup-svc缺少支持时明确列出阻塞，不静默忽略资源。

业务资源安装归入当前 AI 应用安装流程，由 setup-svc 的原生能力创建对象、字段和类；不依赖 MetadataService，也不复用传统软件包安装器。schemaVersion=2 使用安装计划与服务端操作状态，不能套用前述旧 `/install` 流程或首次失败自动删除规则。升级、恢复及清理以目标环境已提供的能力为准；不得推断可自动修改/删除已有结构与类源码，或删除客户业务数据。

### 源清单业务资源示例

以下仅是完整application.json中的资源片段，Web、入口和AI依赖仍按其他章节配置：

```json
{
  "cloudccResources": [
    {"key":"record","kind":"object","file":"cloudcc/metadata/Record.json"},
    {"key":"record-content","kind":"field","file":"cloudcc/metadata/content.json","dependsOn":["record"]},
    {"key":"record-service","kind":"class","apiName":"RecordService","label":"记录服务","file":"cloudcc/backend/classes/RecordService.java","dependsOn":["record-content"]}
  ]
}
```

对象JSON可用apiName/label/nameLabel/dataType/showFormat/beginIndex/remark；字段JSON可用apiName/objectApiName/label/fieldType/length/decimalPlaces/lookupObjectApiName/childrelationName/remark/maxFiles/imageInputMode。支持字段类型S/N/P/c/C/D/T/B/E/U/Y/M/F/X/J/A/H/IMG/FL，平台其他字段能力不等于本安装器已支持；关系字段必须有目标API名和childrelationName，数值精度按平台限制。开发定义超出此范围时明确列出差异，不擅自丢字段。类交付文件是通过CLI创建并验证后的SOURCE内容，保留开发目录中的原始CLI文件，不打包其config.json中的远端ID。

MCP和工具声明在mcpServers/tools，工具依赖用agent.tools中的bindingRef→ref映射，技能与知识依赖同样按原生导出ref映射。MCP/工具配置见 [MCP模块](mcp-tools.md)，不要把源服务响应（含认证字段）整段复制进发布清单。

## 常用命令

```bash
python3 /installed/agentcici/scripts/agentcici_application.py check --manifest /project/applications/app-code/application.json
python3 /installed/agentcici/scripts/agentcici_application.py package --manifest /project/applications/app-code/application.json --output /project/applications/app-code/release/app-code-1.0.0.zip
python3 /installed/agentcici/scripts/agentcici_application.py validate /project/applications/app-code/release/app-code-1.0.0.zip
python3 /installed/agentcici/scripts/agentcici_application.py submit /project/applications/app-code/release/app-code-1.0.0.zip
python3 /installed/agentcici/scripts/agentcici_application.py status REQUEST_ID
python3 /installed/agentcici/scripts/agentcici_application.py list
python3 /installed/agentcici/scripts/agentcici_application.py get app-code
python3 /installed/agentcici/scripts/agentcici_application.py publish app-code --version 1.0.0
python3 /installed/agentcici/scripts/agentcici_application.py release --manifest /project/applications/app-code/application.json --output /project/applications/app-code/release/app-code-1.0.0.zip
```

## 删除本组织应用与全部版本包

DELETE `/openapi/v1/management/ai-applications/{appCode}` 需要 `application.delete`，仅能删除本组织拥有的应用，不能删除平台或其他组织应用。对应后端须已部署；已有开发者凭据不会自动获得删除scope，需要按用户授权调整权限。

```bash
python3 /installed/agentcici/scripts/agentcici_application.py get APP_CODE
python3 /installed/agentcici/scripts/agentcici_application.py delete APP_CODE --confirm-id APP_CODE
```

先get核对名称、代码及版本，取得用户对该精确应用的明确删除授权；`--confirm-id` 必须与目标appCode相同，不能凭占位符执行。此命令删除整个应用及全部版本包、资源文件和发布站点，成功返回appCode与deleted=true，不是只删除最新版本。不可恢复，需要保留时先下载原包。存在安装记录或市场引用时服务端拒绝；不自动卸载CRM资源、撤回市场申请或删除客户业务数据，不删除组织独立智能体/技能/知识库。失败展示原错误，不自动重试；响应丢失时先查询核实，不把超时当作删除成功。应用代码及已使用版本不会因删除变成可重用。


### 扩展字段长度与上传配置（1.7.6）

应用包安装使用setup-svc原生字段创建，三端按字段类型校验：

| 类型 | length默认值 | length范围 |
| --- | --- | --- |
| X 文本区 | 4000 | 1–4000 |
| J 长文本、A 富文本 | 32000 | 1–32000 |
| N/P/c 数值 | 18 | 1–18，且整数位+decimalPlaces不超过18 |
| 其他已支持类型 | 80 | 1–4000（保留原有协议，实际配额仍由CRM检查） |

显式length/decimalPlaces必须为JSON整数，不传字符串或浮点数。J的MetadataService专属131072上限不适用于此安装链路。IMG/FL可传maxFiles整数1–10，默认1；IMG可传imageInputMode=input或url，默认input。maxFiles映射为原生defaultValue，FL同时设置isrepeat；图片录入方式映射formulaType。暂不打包引用公式、水印配置或真实附件内容。不同字段的属性不可混用。

安装初始只给当前系统管理员字段权限；业务简档和受限财务字段需目标管理员按交付说明授权。L/Q/Z/V/MR/AD/LT/SCORE/加密文本尚未纳入此包协议；C虽在类型白名单，但完整累计汇总配置仍未交付，不以白名单通过代替可安装承诺。


### V2安装步骤数量（1.7.7）

V2应用不再设置120项或其他固定的安装步骤总数上限；按实际对象、字段、类和入口完整声明，禁止为绕过数量限制删减资源或拆散依赖。保留非空清单、资源类型/路径/摘要、重复API名、依赖存在性及无环校验，包体和清单大小限制仍适用。V1的30步兼容上限不变。目标AgentCiCi与CRM setup-service均需部署取消V2数量上限的版本；仅更新本机打包技能不能解除旧服务的限制。
