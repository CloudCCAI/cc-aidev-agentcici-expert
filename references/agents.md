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

当前创建接口至少需要 `agentId`、`name`、`model`。`model` 是历史兼容字段，统一传 `"platform-scene"`，无需创建者指定具体型号；实际对话模型由平台统一指定，智能体无法自行选择或切换。省略 `model` 仍会触发当前接口的必填校验。

编辑只发送要改变的字段，不通过修改 `model` 切换实际运行模型；绑定字段传空数组表示清空。删除前确认 `builtin=false`，历史版本、运行和审计证据仍会保留。

```json
{
  "agentId": "support-agent",
  "name": "售后智能体",
  "model": "platform-scene",
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

## 托管联网工具访问策略

智能体绑定 `managed_web_search` 或 `managed_web_extract` 后，可在同一次 `bind-tools` 请求中提交 `toolRuntimePolicies`。这是服务端可信策略，不要把超时和次数字段写进提示词或让模型作为工具参数传入。

```json
{
  "toolIds": ["managed_web_search", "managed_web_extract"],
  "toolLoadingModes": {
    "managed_web_search": "always-on",
    "managed_web_extract": "always-on"
  },
  "toolRuntimePolicies": {
    "managed_web_search": {
      "policyVersion": 2,
      "preset": "CUSTOM",
      "qualityMode": "CUSTOM",
      "totalRuntimeTimeoutMs": 110000,
      "acquisitionTimeoutMs": 70000,
      "answerTimeoutMs": 30000,
      "closingReserveMs": 10000,
      "maxPlannedQueries": 3,
      "targetCandidateSources": 8,
      "minDistinctDomains": 4,
      "minVerifiedPages": 4,
      "minDisplayedCitations": 4,
      "maxPagesToFetch": 6,
      "requirePrimarySource": true,
      "requireConflictCheck": false,
      "maxSourcesPerDomain": 3,
      "allowInsufficientAnswer": false
    },
    "managed_web_extract": {"preset": "BALANCED"}
  }
}
```

```bash
python3 /installed/agentcici/scripts/agentcici_manage.py agents bind-tools AGENT_ID --file /absolute/path/web-tools.json
```

`policyVersion: 2` 当前是实验策略，完成真实 UAT 前不作为新绑定默认值。无论 `qualityMode` 为 `QUICK_PREVIEW`、`BALANCED`、`DEEP` 还是 `CUSTOM`，`managed_web_search` 都只发现候选 URL，绝不自动抓取正文；其 `verifiedPageCount` 固定为0、`qualitySatisfied=false`。要形成网页证据，调用方必须对选中的明确 URL 显式调用 `managed_web_extract`。搜索工具可以单独绑定，不再因使用 v2 而强制同时绑定抓取工具；阻塞 `api` 渠道仍不允许 `DEEP`。

未带 `policyVersion` 的历史策略仍按v1解释，字段包括 `singleCallTimeoutMs`、`maxCallsPerRun`、`maxOutputTokens`、`responseMode`、`reasoningEffort`、`maxReturnedSources`、`sourceCollectionWindowMs`、`minReturnedSources`、`minDistinctDomains` 和 `maxSourcesPerDomain`。读取旧智能体后不要仅因普通保存改写成v2；只有用户明确升级并重新发布时才提交 `policyVersion: 2`。

`SOURCES_FIRST` 从首批有效结构化来源开始计算短窗口，并在来源数量与独立域名门槛满足、来源上限到达或窗口结束时返回。窗口与域名限制只影响 AgentCiCi 接收和筛选结果的方式；它们不会要求百炼必须检索指定数量的网站，也不会限制百炼单请求内部轮数。需要真正控制搜索策略、时效或站点范围时，应评估 DashScope 等支持对应参数的协议，不能把这些字段塞进 Responses 请求。

v1的 `maxCallsPerRun` 只限制 AgentCiCi 外层工具调用。百炼 Responses 在一次请求内仍可能自主执行多轮 `web_search_call`/`web_extractor_call`，当前协议没有可兑现的上游次数硬限制；不要使用 Responses 不支持的 `search_strategy`、`forced_search` 或 Anthropic `max_uses`。v2 结果分别返回计划查询、平台搜索/抓取请求和供应商内部调用；供应商 usage 不完整时内部次数为 `null`，不得用平台请求数代填。读取智能体详情时回读 `toolRuntimePolicies`，编译发布后再核对新策略进入运行版本。

### 联网结果证据状态

调用方必须读取 `evidenceStatus`，不能只看模型是否生成了 `answer`：

- `SUCCESS_WITH_EVIDENCE`：工具正常结束，且存在可审计结构化来源。
- `PARTIAL_WITH_EVIDENCE`：已经取得可审计来源，但来源窗口提前结束、流中断或上游随后失败。可以使用 `sources`，同时向用户说明结果不完整；`terminalErrorCode` 和 `earlyReturnReason` 用于诊断。
- `COMPLETED_WITHOUT_EVIDENCE`：上游生成了文字但没有结构化来源，工具返回 `success:false` 和 `MANAGED_WEB_NO_AUDITABLE_SOURCES`。不得把回答正文中的链接补写成已核验引用。
- `FAILED_WITHOUT_EVIDENCE`：调用失败且没有可用来源。
- `CANDIDATES_READY`：v2 搜索已返回候选来源，但尚未读取正文；不能据此生成完整事实结论。

`sources` 可包含 `url`、`title`、`summary`、`domain` 和 `sourceType`。搜索后先按子问题、来源类型和相关性筛选摘要；只有摘要不足的字段再调用 `managed_web_extract` 精读少量 URL。交易所/披露平台、政府监管机构和研究机构可由 `sourceType` 辅助排序，但来源类型不等于事实已核验。网页抓取先进行安全直读：连接最多 2 秒、首字节等待最多 3 秒，收到合法文本响应后直读总计最多 8 秒；预算允许时至少为百炼回退保留 20 秒。`directRead.status`、`httpStatus`、`firstByteLatencyMs`、`bytesRead` 和 `finalUrl` 用于区分站点、正文下载及中间网络问题，这些平台安全预算不作为工具绑定参数暴露。

用户明确要求“至少 N 个来源／链接／引用”时，最终回答会从本轮 `sources` 账本补足相关引用；补齐不会重新调用联网工具。账本本身不足时必须说明实际数量，不得用无关链接凑数。`minReturnedSources` 控制工具层收集目标，不等同于模型一定展示的引用数；验收必须同时检查工具来源和最终回答。

## 火山结构化联网工具访问策略

`structured_web_search`（火山联网搜索）和 `structured_web_fetch`（火山网页抓取）是另一组独立默认工具，不是 `managed_web_search`／`managed_web_extract` 的别名或回退通道。绑定哪一项就明确使用哪一种供应方式；两组可以同时绑定，但应在智能体流程中写清选择条件，避免对同一问题重复调用和重复计费。任一组失败时不得静默切换另一组。

```json
{
  "toolIds": ["structured_web_search", "structured_web_fetch"],
  "toolLoadingModes": {
    "structured_web_search": "always-on",
    "structured_web_fetch": "always-on"
  },
  "toolRuntimePolicies": {
    "structured_web_search": {
      "preset": "CUSTOM",
      "singleCallTimeoutMs": 15000,
      "maxCallsPerRun": 2,
      "maxAttemptsPerRun": 3,
      "maxResults": 20,
      "queryRewrite": true
    },
    "structured_web_fetch": {
      "preset": "FAST"
    }
  }
}
```

两项工具均支持 `FAST`、`BALANCED`、`DEEP`、`CUSTOM`。搜索自定义字段为 `singleCallTimeoutMs`（5000–30000）、`maxCallsPerRun`（1–3）、`maxAttemptsPerRun`（不得小于调用数，最多6）、`maxResults`（1–50）和 `queryRewrite`；抓取为超时、调用数（1–10）、真实 HTTP 尝试数（1–20）及 `maxContentChars`（5000–50000）。`maxCallsPerRun` 统计模型发起的逻辑调用，`maxAttemptsPerRun` 统计包含有限重试的真实 HTTP 请求；默认预设不会额外放大重试额度，只有显式提高 attempt 上限才可能对临时错误重试一次。

搜索结果的 `sources[].summary` 是结构化搜索摘要，不等于已抓取原文；需要正文证据时再对少量公开 URL 调用 `structured_web_fetch`。抓取正文只在当前运行和模型上下文内使用，持久化 Trace、会话状态和 SSE 工具结果会移除正文与摘要。同一运行对相同 URL 的成功结果或确定性失败可命中短期缓存，缓存不跨运行。`providerUsage.observedAttempts` 是本平台观察值而非供应商账单；`estimatedCost` 依赖平台配置，`billingConfirmed:false` 时不得称为已出账费用。

平台未配置、能力未单独检测通过、账号级 QPS、attempt 预算、URL 安全校验或上游权限不满足时，工具会以 `STRUCTURED_WEB_*` 错误失败关闭。`700429`、`10500`、`10502` 等临时错误才可能在同一绝对截止时间内有限重试；参数、权限、额度、合规拒绝、空正文不重试。

示例中的 `DRAFT_VERSION_NO` 必须替换为本次编译返回的 `draftVersionNo` 正整数，不写死版本号。编译会保存新草稿版本；先检查编译结果，再发布该版本，后端执行现有发布校验。通用发布不添加 API 渠道；开启运行 OpenAPI 参考运行接口文档。

生日邮件示例顺序：创建/编辑邮件技能 → 编译并发布技能 → 创建/编辑智能体 → 关联技能、知识库、工具 → 编译智能体 → 发布返回的版本。定义编辑和关联修改只有重新编译发布后才进入新的运行版本。


## 运行 API Key 管理

开发者 Token 可以创建、撤销 Agent API Key，不能代替生成的 Key 调用运行 API。两个接口都需要 `agent.write`；创建还检查凭据绑定成员的智能体 `OPENAPI` 权限。撤销本人创建的 Key 允许在智能体停用后进行，撤销其他人的 Key 仍检查 `OPENAPI` 权限。服务端未部署时不能改用后台登录接口绕过。

| 操作 | 方法与路径 |
|---|---|
| 创建 | `POST /openapi/v1/management/agents/{agentId}/api-keys` |
| 撤销 | `POST /openapi/v1/management/agents/{agentId}/api-keys/{credentialId}/revoke` |

创建请求 `name` 必填；可选字段为 `expiresAt`（UTC ISO 时间）、`allowedIps`、`rateLimitPerMinute`、`dailyQuota`、`maxPromptChars`、`maxResponseChars`、`allowStream`、`allowTraceRead`、`scopes`、`keyType`、`principalMemberId`。`runAsUserId` 仅为旧字段，当前服务端拒绝新建时传入非空值。创建本地测试 Key 时按[运行 Key 选型](agent-runtime-openapi.md#运行-key-选型与排查)显式传 `keyType`。下方示例用于不传 CRM 会话的普通对话。CRM 安装后的应用从宿主取得安装实例的 Key。`principalMemberId` 如指定，必须是本组织可用的 API_CLIENT 服务成员；省略时由服务端创建受管运行身份。普通调用可选 `scopes: ["chat"]`；省略时由服务端应用默认 scope，不等同于开发者 scope。

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
