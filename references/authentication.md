# 管理 OpenAPI 鉴权

## 换票

组织管理员在“开发者管理”创建凭据并授予最小 scope。客户端调用：

```http
POST /openapi/v1/developer/token
Content-Type: application/json

{"clientId":"cici-dev-...","clientSecret":"cici_cs_..."}
```

响应 `data` 包含 `accessToken`、`tokenType=Bearer`、`expiresIn` 和 `scopes`。后续管理请求使用 `Authorization: Bearer <accessToken>`。Token 默认有效 600 秒；脚本只在进程内缓存。

## Scope

| 模块 | 读取 | 创建/编辑 | 删除 |
|---|---|---|---|
| 智能体 | `agent.read` | `agent.write` | `agent.delete` |
| 技能 | `skill.read` | `skill.write` | `skill.delete` |
| MCP 服务 | `mcp.read` | `mcp.write` | `mcp.delete` |
| 知识库 | `knowledge.read` | `knowledge.write` | `knowledge.delete` |

## 错误语义

- `400`：请求字段或业务规则无效。
- `401`：开发者密钥、Token、组织或凭据责任人成员已失效。
- `403`：当前凭据缺少所需 scope。
- `404`：资源不存在或不属于当前组织。
- `409`：资源状态冲突或删除条件不满足。

管理 OpenAPI 不调用 `/auth/password/login`，不使用 Keycloak，不接受 Agent API Key。

## AI 应用申请

提交 ZIP 需要 application.submit；查询、下载本组织申请需要 application.read。已有凭据不会自动新增权限，组织管理员可在开发者管理中编辑权限。目标环境需已部署申请接收接口；本组织应用发布另需 application.publish，删除本组织应用及全部版本包另需 application.delete，不授予平台审核、平台应用发布或跨组织访问权限。OSS 凭据只由后端配置，不使用 org 开发者凭据作为 OSS 密钥。

## Base64 登录与多环境持久化（1.5.9）

在用户项目目录运行 `python3 /技能绝对路径/scripts/agentcici_auth.py login --env uat`，粘贴后台复制的 Base64 文本，交互输入不回显；自动化调用通过标准输入提供，不将原文写入临时文件、命令参数或日志。输入严格解析为 AGENTCICI_BASE_URL、AGENTCICI_CLIENT_ID、AGENTCICI_CLIENT_SECRET 三条 export，不执行解码内容。只接受 HTTPS origin 或 localhost/127.0.0.1/::1 的 HTTP 开发地址，拒绝重定向换票。

先调用开发者换票接口验证，成功后把解码后的三项凭据直接保存到 `cloudcc-agentcici.config.json`，结构参考随包提供的 `cloudcc-agentcici.config.example.json`：

```json
{
  "use": "uat",
  "dev": {
    "baseUrl": "http://localhost:8080",
    "clientId": "示例开发者ID",
    "clientSecret": "示例开发者Secret"
  },
  "uat": {
    "baseUrl": "https://uat.example.com",
    "clientId": "示例开发者ID",
    "clientSecret": "示例开发者Secret"
  }
}
```

从 applications/<appCode> 及其子目录执行时固定选择项目根配置，根尚无配置时首次登录也在根创建；发现应用内旧配置先报冲突。其他独立资源管理目录向父级查找最近配置，无则在当前目录创建；可以设置 `AGENTCICI_CONFIG_PATH` 明确指定完整路径。不要在技能安装目录登录，避免将业务凭据写入分发包。认证命令 `--env` 优先于 `AGENTCICI_LOGIN_PROFILE`，后者优先于文件 `use`；首次登录默认 `dev`。环境名只允许字母、数字、下划线和连字符，保留字段 `use` 不可作为环境名。同一部署的不同组织可用不同环境名称保存，不能根据 Client ID 猜测组织。

```bash
python3 /技能绝对路径/scripts/agentcici_auth.py login --env uat
python3 /技能绝对路径/scripts/agentcici_auth.py use uat
python3 /技能绝对路径/scripts/agentcici_auth.py status
python3 /技能绝对路径/scripts/agentcici_auth.py logout --env uat
```

新登录验证失败不覆盖旧文件；成功时只替换指定环境并更新 `use`，保留其他环境。`use` 验证环境存在后仅切换本地配置，不发送网络请求。保存采用同目录临时文件和原子替换，POSIX 权限 `0600`，自动将配置名及临时文件加入同目录 `.gitignore`。整个文件按凭据处理，不提交、不打包、不回显；Base64 仅是编码，落盘保存的是解码后的原始值，短期 Token 不落盘。

status 只报告本地保存状态、选中环境、地址、Client ID 和配置路径，不代表服务端凭据仍有效。logout 仅删除选中环境，不撤销远程凭据；删除当前环境后自动选择剩余环境，删除最后一个环境时移除配置文件。若仍设置三项凭据环境变量，管理命令仍优先使用环境变量；部分变量报错，不与文件混用。指定环境缺失、配置损坏或凭据不完整时明确报错，不回退到其他环境。

旧 `~/.config/agentcici/login.json`、`login-*.json` 和系统钥匙串保持原样，新版不再读取它们；需要使用旧身份时重新复制登录信息，在目标项目执行 login。管理命令与应用 submit/status 共用新配置读取逻辑；本地 package/validate 不需要登录。服务端停用或轮换密钥后重新 login，远程写入失败不自动重试以掩盖鉴权错误。
