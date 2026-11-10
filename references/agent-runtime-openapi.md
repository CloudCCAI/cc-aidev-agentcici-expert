# 单智能体运行 OpenAPI 教程

## 与管理 OpenAPI 的区别

运行 OpenAPI 用于让外部应用与一个已发布智能体对话、维护会话和上传文件。它使用该智能体自己的 Agent API Key：`Authorization: Bearer <AGENTCICI_API_KEY>`。开发者管理 Token 不能调用运行 API，Agent API Key 也不能管理平台资产。

Agent API Key 可由有权限的开发者通过[管理命令](agents.md#运行-api-key-管理)创建和撤销，也可由组织管理员在智能体详情的“开放 API 文档/密钥管理”中创建、限制来源并管理生命周期。

## apiBase 与请求路径

- `apiBase` 是完整运行 API 基地址，包含 `/openapi/v1`。生产嵌入模式直接使用宿主 runtime 返回的 `context.apiBase`。
- 本地测试在未提交的本地配置中提供完整 `apiBase`，例如 `http://127.0.0.1:8080/openapi/v1`；curl 示例中的 `AGENTCICI_API_BASE` 使用同样的完整地址。这与管理脚本使用的平台根地址 `AGENTCICI_BASE_URL` 不同。
- 业务请求代码不得包含 `/openapi/v1` 字面量、前缀常量或补齐逻辑；只去掉 `apiBase` 末尾的斜杠，再拼接相对端点。HTTP 端点不得提取 origin 或使用根路径覆盖 `apiBase` 已有路径；语音 WebSocket 按服务端返回的 `websocketPath` 解析，见[实时语音输入](voice-input.md)。

以下 `standard` 请求示例用于说明 URL 拼接。CRM 内嵌应用采用默认选型时，请求体按下文携带 `cloudccContext`。

```js
const apiBase = context.apiBase.replace(/\/$/, '');
const response = await fetch(`${apiBase}/chat-messages`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${context.apiKey}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ user: context.user, query, responseMode: 'blocking' })
});
```

验收时确认本地配置包含前缀，最终请求地址中的前缀恰好出现一次；带或不带末尾斜杠的 `apiBase` 都得到相同端点。源码与构建产物中的运行请求代码不得硬编码该前缀；本地配置缺失时修正配置，不在请求代码中兜底补齐。

## 快速调用

以下 curl 示例使用 `standard` Key，适用于已明确无需当前 CRM 用户会话的调用。

```bash
curl -X POST "${AGENTCICI_API_BASE%/}/chat-messages" \
  -H "Authorization: Bearer $AGENTCICI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-question-001" \
  -d '{"user":"customer-001","query":"我的订单到哪里了？","responseMode":"blocking"}'
```

- `user` 是调用方稳定用户标识。
- `query` 是本轮问题。
- `responseMode` 使用 `blocking` 获取 JSON，或 `streaming` 获取 SSE。
- 后续轮次传回 `conversationId`；有副作用的请求应设置稳定的 `Idempotency-Key`。

## 运行端点

以下路径均相对于 `apiBase`，表中的开头斜杠仅用于与基地址拼接。

| 能力 | 方法与相对路径 |
|---|---|
| 参数信息 | `GET /parameters` |
| 发送消息 | `POST /chat-messages` |
| 停止流式任务 | `POST /chat-messages/{taskId}/stop` |
| 会话列表 | `GET /conversations` |
| 消息列表 | `GET /messages` |
| 会话改名 | `POST /conversations/{conversationId}/name` |
| 删除会话 | `DELETE /conversations/{conversationId}` |
| 消息反馈 | `POST /messages/{messageId}/feedbacks` |
| 推荐问题 | `GET /messages/{messageId}/suggested` |
| 上传文件 | `POST /files/upload` |
| 导入远程文件 | `POST /files/import` |
| 申请语音凭证 | `POST /voice-sessions?scene=voice-asr` |

上传接口返回文件 `id` 后，在 `chat-messages.files[].upload_file_id` 中引用。文件类型、大小、模型能力或解析失败都应作为明确错误处理，不要静默忽略附件。

## 发布与凭据相互独立

开启 API 渠道即可满足发布入口条件，不要求先创建 Key。未发布的智能体也可创建 Key，开发者管理接口仍检查智能体存在及 OPENAPI 权限。创建 Key 不会自动发布或开启渠道；实际调用仍需要满足运行端的鉴权、发布及渠道条件。

## 运行 Key 选型与排查

新应用在 `application.json` 显式声明 `agent.keyType`，让联调和安装使用同一类型。

| 场景 | `agent.keyType` | `chat-messages` 请求 |
| --- | --- | --- |
| CRM 内嵌应用接入智能体，默认选型 | `cloudcc` | 使用同一宿主 runtime 的 `apiKey`、`apiBase`、`user` 和 `cloudccContext` |
| 已明确智能体无需当前 CRM 用户会话，例如独立应用的普通对话，或 CRM 内嵌应用中仅由 Web 独立访问 CRM、智能体只做文本处理 | `standard` | 省略整个 `cloudccContext` |

`cloudcc` 请求体携带 `cloudccContext: { accessToken, baseUrl, readPageInfo: false }`，其中 Token 和网关来自当前 CRM 用户会话，`user` 使用宿主给出的当前 CRM 用户标识。服务端验证 Token、网关与 Key 所属租户的 CRM 组织关系，再将该会话用于本次工具调用。Token 只用于鉴权，禁止放进模型 query、metadata、URL 或日志，也不要借用管理凭据或其他用户的 Token。

**遇到 `cloudcc_context_not_allowed`（HTTP 400）或提示 `cloudccContext is only allowed for cloudcc API keys` 时**，服务端实际解析到了 `standard` Key，同时请求携带了 CRM 上下文。按调用场景排查：

1. 已明确智能体无需当前 CRM 用户会话时，保留 `standard`，构造请求时省略整个 `cloudccContext`。宿主可能为 Web 直调自定义类提供 CRM 上下文，不能把宿主对象整体合并进智能体请求。
2. CRM 内嵌应用采用默认选型时，核对源清单 `agent.keyType`、发布包 `installationManifest.agentRuntime.keyType` 和已安装应用的 `context.keyType` 都为 `cloudcc`。旧安装仍使用 `standard` 时，通过安装或升级流程生成对应类型的运行 Key，再从 CRM 入口重新打开。检查实际请求是否使用本次宿主返回的 Key，排除本地测试 Key、旧缓存或环境错配。修改客户端的 `keyType` 字符串不会改变服务端凭据类型。
3. 本地联调检查测试凭据的 `credential.keyType`，与目标调用链一致。目标 CRM 验收至少跑一次实际对话，涉及 CRM MCP 时核对工具确实以当前用户执行。诊断记录只保留类型、环境、请求 ID 和错误码，省略 Key 与 Token。

0.3.0智能分析前端还要求blocking响应metadata.runtime.toolCallCount提供本轮服务端工具执行计数；缺失时不展示ready数据。此计数表示执行过工具，不代替具体工具成功、权限和数据完整性验收。

## 实时语音输入

应用需要麦克风转文字时，读取[语音接入指南](voice-input.md)，按宿主身份刷新、audio权限、短期凭证与WebSocket握手接入；指南包含音频格式、转写拼接、停止清理和接入验收。语音只产生文字，发送智能体继续使用本教程的chat-messages。

持续语音问答、平台播报和插话优先使用[通用持续通话SDK](voice-call.md)，由SDK组合ASR、chat-messages与voice-speech；对照其中的权限、会话、停止和合成契约，不把转写自动当成一次聊天。
