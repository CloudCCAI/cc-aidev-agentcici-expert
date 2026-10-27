# 单智能体运行 OpenAPI 教程

## 与管理 OpenAPI 的区别

运行 OpenAPI 用于让外部应用与一个已发布智能体对话、维护会话和上传文件。它使用该智能体自己的 Agent API Key：`Authorization: Bearer <AGENTCICI_API_KEY>`。开发者管理 Token 不能调用运行 API，Agent API Key 也不能管理平台资产。

Agent API Key 可由有权限的开发者通过[管理命令](agents.md#运行-api-key-管理)创建和撤销，也可由组织管理员在智能体详情的“开放 API 文档/密钥管理”中创建、限制来源并管理生命周期。

## apiBase 与请求路径

- `apiBase` 是完整运行 API 基地址，包含 `/openapi/v1`。生产嵌入模式直接使用宿主 runtime 返回的 `context.apiBase`。
- 本地测试在未提交的本地配置中提供完整 `apiBase`，例如 `http://127.0.0.1:8080/openapi/v1`；curl 示例中的 `AGENTCICI_API_BASE` 使用同样的完整地址。这与管理脚本使用的平台根地址 `AGENTCICI_BASE_URL` 不同。
- 业务请求代码不得包含 `/openapi/v1` 字面量、前缀常量或补齐逻辑；只去掉 `apiBase` 末尾的斜杠，再拼接相对端点。不得提取 origin 或使用根路径覆盖 `apiBase` 已有路径。

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

上传接口返回文件 `id` 后，在 `chat-messages.files[].upload_file_id` 中引用。文件类型、大小、模型能力或解析失败都应作为明确错误处理，不要静默忽略附件。

## 发布与凭据相互独立

开启 API 渠道即可满足发布入口条件，不要求先创建 Key。未发布的智能体也可创建 Key，开发者管理接口仍检查智能体存在及 OPENAPI 权限。创建 Key 不会自动发布或开启渠道；实际调用仍需要满足运行端的鉴权、发布及渠道条件。

## 标准Key携带当前CRM会话（需服务端支持）

需要按当前CRM用户执行MCP的普通应用仍使用standard Key。部署支持后，在chat-messages请求体传`cloudccContext: {accessToken, baseUrl, readPageInfo: false}`，`user`取当前CRM userId；不得把Token放入query、metadata、URL或日志。后端要求Key所属租户启用CRM集成且配置orgId/网关，验证请求网关与配置一致、实时CRM用户与user一致、CRM组织与配置一致后，仅在本次MCP调用期间注入会话。Key的运行身份、授权、计费归属保持；不会借用管理员或开发Token。旧环境返回cloudcc_context_not_allowed时升级服务端，不改用cloudcc专用Key绕过。

0.3.0智能分析前端还要求blocking响应metadata.runtime.toolCallCount提供本轮服务端工具执行计数；缺失时不展示ready数据。此计数表示执行过工具，不代替具体工具成功、权限和数据完整性验收。
