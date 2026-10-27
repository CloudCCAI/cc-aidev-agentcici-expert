# 智能体模块

## 设计理解

智能体是可运行的业务角色，组合模型、系统提示词、自然语言流程 Spec、知识库、工具、技能、渠道和安全/转人工策略。设计时先明确目标用户、触发请求、必要数据与工具、输出契约、风险动作和人工确认点。用于 AI 应用开发时，按 [资源选择规则](../SKILL.md#ai-应用的智能体技能与工具选择) 优先新建应用自己的智能体，合适的已有技能和工具优先复用；继续维护本应用智能体或用户明确选择已有智能体时不重复创建。

- `agentId` 是稳定技术标识，创建后不可修改；`name` 是用户可见名称。
- `summary`、`greeting` 描述用途和开场；`systemPrompt`、`specText` 决定行为与流程。
- `knowledgeBaseIds`、`toolIds`、`channels` 只在用户明确要求且对应资源已存在时绑定。
- `BALANCED`/`STRICT` 与 `COPILOT`/`AUTO` 会影响执行策略；高风险场景应优先人工确认。
- 管理 API 编辑的是定义草稿，不等于发布新版本。

## 管理 API

| 操作 | 方法与路径 | scope |
|---|---|---|
| 列表 | `GET /openapi/v1/management/agents` | `agent.read` |
| 详情 | `GET /openapi/v1/management/agents/{agentId}` | `agent.read` |
| 创建 | `POST /openapi/v1/management/agents` | `agent.write` |
| 部分编辑 | `PATCH /openapi/v1/management/agents/{agentId}` | `agent.write` |
| 软删除 | `DELETE /openapi/v1/management/agents/{agentId}` | `agent.delete` |

创建至少需要 `agentId`、`name`、`model`。编辑只发送要改变的字段；绑定字段传空数组表示清空。删除前确认 `builtin=false`，历史版本、运行和审计证据仍会保留。

```json
{
  "agentId": "support-agent",
  "name": "售后智能体",
  "model": "qwen3.7-plus",
  "summary": "回答售后问题，复杂事项转人工",
  "safetyLevel": "STRICT",
  "executionMode": "COPILOT"
}
```

## 关联资源与编译发布

新增接口需要部署包含本次扩展的后端；404 时停止并报告，不以管理后台接口替代。开发者凭据限定 org，新接口还检查凭据绑定成员的智能体权限。

| 操作 | 方法与路径 | scope / 智能体权限 |
|---|---|---|
| 查询技能关联 | `GET /openapi/v1/management/agents/{agentId}/skills` | agent.read / VIEW |
| 替换技能关联 | `PUT /openapi/v1/management/agents/{agentId}/skills` | agent.write / EDIT |
| 编译当前草稿 | `POST /openapi/v1/management/agents/{agentId}/compile` | agent.write / EDIT |
| 发布指定版本 | `POST /openapi/v1/management/agents/{agentId}/publish` | agent.write / PUBLISH |

技能关联请求为 `{"bindings":[{"skillId":123,"activationMode":"always-on","priority":10,"enabled":true}]}`。也可使用已有 skillCode。先查询完整列表，再加入或移除目标；提交空列表清空可手动管理的关联，系统内部关联遵循服务端保留规则。技能、知识库和工具必须来自当前 org 可使用资源，不复制其他 org 的 ID。

知识库和工具通过现有 PATCH 接口关联，以下命令仅改变对应字段。三种 bind 命令均替换完整列表，操作前先读取现状保留其他关联。

```bash
python3 /installed/agentcici/scripts/agentcici_manage.py agents skills AGENT_ID
python3 /installed/agentcici/scripts/agentcici_manage.py agents bind-skills AGENT_ID --file /absolute/path/bindings.json
python3 /installed/agentcici/scripts/agentcici_manage.py agents bind-knowledge AGENT_ID --json '{"knowledgeBaseIds":[123]}'
python3 /installed/agentcici/scripts/agentcici_manage.py agents bind-tools AGENT_ID --json '{"toolIds":["query_customer"]}'
python3 /installed/agentcici/scripts/agentcici_manage.py agents compile AGENT_ID
python3 /installed/agentcici/scripts/agentcici_manage.py agents publish AGENT_ID --version-no DRAFT_VERSION_NO
python3 /installed/agentcici/scripts/agentcici_manage.py agents delete AGENT_ID --confirm-id AGENT_ID
```

示例中的 `DRAFT_VERSION_NO` 必须替换为本次编译返回的 `draftVersionNo` 正整数，不写死版本号。编译会保存新草稿版本；先检查编译结果，再发布该版本，后端执行现有发布校验。通用发布不添加 API 渠道；开启运行 OpenAPI 参考运行接口文档。

生日邮件示例顺序：创建/编辑邮件技能 → 编译并发布技能 → 创建/编辑智能体 → 关联技能、知识库、工具 → 编译智能体 → 发布返回的版本。定义编辑和关联修改只有重新编译发布后才进入新的运行版本。


## 运行 API Key 管理

开发者 Token 可以创建、撤销 Agent API Key，不能代替生成的 Key 调用运行 API。两个接口都需要 `agent.write`；创建还检查凭据绑定成员的智能体 `OPENAPI` 权限。撤销本人创建的 Key 允许在智能体停用后进行，撤销其他人的 Key 仍检查 `OPENAPI` 权限。服务端未部署时不能改用后台登录接口绕过。

| 操作 | 方法与路径 |
|---|---|
| 创建 | `POST /openapi/v1/management/agents/{agentId}/api-keys` |
| 撤销 | `POST /openapi/v1/management/agents/{agentId}/api-keys/{credentialId}/revoke` |

创建请求 `name` 必填；可选字段为 `expiresAt`（UTC ISO 时间）、`allowedIps`、`rateLimitPerMinute`、`dailyQuota`、`maxPromptChars`、`maxResponseChars`、`allowStream`、`allowTraceRead`、`scopes`、`keyType`、`principalMemberId`。`runAsUserId` 仅为旧字段，当前服务端拒绝新建时传入非空值。普通应用使用 `keyType: "standard"`，不要自行使用 CloudCC 专用身份。`principalMemberId` 如指定，必须是本组织可用的 API_CLIENT 服务成员；省略时由服务端创建受管运行身份。普通调用可选 `scopes: ["chat"]`；省略时由服务端应用默认 scope，不等同于开发者 scope。

创建运行密钥时，默认显式传入 `maxPromptChars: 64000`（输入字符上限，含消息和页面信息）和 `maxResponseChars: 128000`（回答字符上限），不要依赖服务端较低的默认值。CLI 自动补齐未指定的字段；通过 Python `Client` 或其他方式直接调用时也须传入这两个默认值。用户明确指定其他上限时使用其指定值。

```bash
python3 /installed/agentcici/scripts/agentcici_manage.py agents get AGENT_ID
python3 /installed/agentcici/scripts/agentcici_manage.py agents create-api-key AGENT_ID --json '{"name":"短期联调","keyType":"standard","scopes":["chat"],"maxPromptChars":64000,"maxResponseChars":128000}' --output /私密目录/agent-key.json
python3 /installed/agentcici/scripts/agentcici_manage.py agents revoke-api-key AGENT_ID CREDENTIAL_ID --confirm-id CREDENTIAL_ID
```

需要短期Key时按实际联调时间补充未来的expiresAt，不使用固定示例日期；省略过期值不代表短期联调Key会自动失效。创建前回读目标智能体，确认组织、ID、用途；需要运行时核对已发布版本和 API 渠道，不擅自发布或修改渠道。撤销前核对目标 credential ID 和所属智能体；用户已授权的测试清理无需再次询问。

创建响应包含 `credential` 和只返回一次的 `plainKey`。CLI 必须指定 `--output`，以独占创建、POSIX `0600` 权限保存完整响应，已有文件不覆盖；终端只输出文件路径和 `credentialId`。输出必须位于仓库/发布目录外的私密目录或已明确忽略且不参与打包的位置，不把 Key 放入命令参数、日志、回答或发布包。自动联调也可通过 Python `Client` 在进程内接收结果并于 finally 撤销，不需要落盘。临时 Key 验证后撤销，删除本机明文文件不等于撤销远端 Key。

创建发生超时或保存失败时，结果可能未知，停止且通过后台核对，不能自动重试以免重复生成 Key；输出文件可能为空或不完整。404 可能为接口未部署或资源不可见，先用 `agents get` 区分；401/403 是登录或权限问题，不能据此断言接口不存在。当前管理接口没有列出 Key 的命令，不杜撰列表接口。

## 验证边界

本地测试只能证明参数、私密文件处理和调用顺序；创建/撤销接口、运行鉴权和实际额度须在目标环境按用户授权核验。历史环境的成功记录不能证明其他组织或新部署可用，不将固定credential ID、智能体ID或过期时间作为通用示例。
