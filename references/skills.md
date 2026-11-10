# 技能模块

## 设计理解

技能是可复用的行为与流程资产，用于把提示片段、自然语言 Spec、工具/知识白名单、运行 API、输出契约和风险规则组合起来，再绑定给一个或多个智能体。

- `skillCode` 是稳定技术标识；名称和描述帮助用户及 AI 判断何时使用。
- `draftSpecText` 描述目标、触发、步骤和边界；`promptFragment` 是进入运行提示词的直接行为规则。
- `toolWhitelist`、`kbWhitelist` 应保持最小集合。
- `handoffRule` 明确转人工条件；`outputContract` 明确可验证输出；`riskLevel` 使用 `LOW`、`MEDIUM` 或 `HIGH`。
- 平台标准技能可读取，但通常不可编辑或删除；管理 API 创建的都是租户自定义技能。
- 创建与编辑只管理草稿；compile 预览编译，publish 重新编译校验并产生已发布快照。回滚、导入导出和智能编写另行核对接口。

## 管理 API

| 操作 | 方法与路径 | scope |
|---|---|---|
| 列表 | `GET /openapi/v1/management/skills` | `skill.read` |
| 详情 | `GET /openapi/v1/management/skills/{skillId}` | `skill.read` |
| 创建 | `POST /openapi/v1/management/skills` | `skill.write` |
| 完整编辑 | `PUT /openapi/v1/management/skills/{skillId}` | `skill.write` |
| 删除 | `DELETE /openapi/v1/management/skills/{skillId}` | `skill.delete` |

创建与编辑至少需要 `skillCode` 和 `name`。`PUT` 必须先读取现状，再提交合并后的完整对象。技能仍被智能体绑定或被已发布运行时引用时不能删除；删除请求可带 `{"reason":"..."}`。

```json
{
  "skillCode": "order-status-guide",
  "name": "订单状态说明",
  "description": "查询并解释订单状态",
  "enabled": true,
  "draftSpecText": "先确认订单号，再查询订单；涉及退款时转人工。",
  "promptFragment": "只基于订单查询结果回答，不得猜测。",
  "toolWhitelist": ["query_order"],
  "kbWhitelist": [],
  "handoffRule": "退款、改价或查询失败时转人工",
  "outputContract": "输出状态、依据和下一步动作",
  "runtimeApis": [],
  "riskLevel": "MEDIUM"
}
```

## 编译与发布

新增接口需要部署包含本次扩展的后端；404 时停止并报告服务端未提供能力，不改用后台登录接口。

- `POST /openapi/v1/management/skills/{skillId}/compile`，`skill.write`：编译已保存草稿，返回 warnings、compileSummary 等，不发布。
- `POST /openapi/v1/management/skills/{skillId}/publish`，`skill.write`：可传 `{"changeLog":"说明"}`，后端重新校验，阻塞错误会拒绝发布。
- CLI `skills update` 自动 GET 并合并可写字段，所以还需要 `skill.read`；未提供字段保留，列表提供 `[]` 则清空。

```bash
python3 /installed/agentcici/scripts/agentcici_manage.py skills compile SKILL_ID
python3 /installed/agentcici/scripts/agentcici_manage.py skills publish SKILL_ID --change-log '生日邮件技能初版'
python3 /installed/agentcici/scripts/agentcici_manage.py skills delete SKILL_ID --confirm-id SKILL_ID
```

检查编译警告后再发布，确认返回 `currentPublishedVersionId`。技能更新不会自动改变智能体已固定的发布快照；需要重新编译发布关联智能体。

## 任务级托管联网收紧策略

需要为某一明确业务任务进一步限制联网时，可在可信的已发布技能提示中使用版本化 `cici-task-profile`，由平台解析 `execution.managedWeb`。该配置只从已加载技能快照读取，不从用户消息、附件或网页内容读取。

```cici-task-profile
{
  "version": 2,
  "intentKeywords": ["招标", "公告"],
  "tools": ["managed_web_search", "managed_web_extract"],
  "execution": {
    "managedWeb": {
      "maxSearchCalls": 1,
      "maxExtractCalls": 2,
      "maxRuntimeMillis": 90000,
      "alternateExtractOnce": true
    }
  }
}
```

范围为搜索1–3次、抓取1–10次、总预算30000–360000毫秒。任务策略只能收紧智能体 `toolRuntimePolicies`，不能扩大绑定策略；智能体长期默认访问方式应配置在工具绑定上，不要为通用超时控制新建一个无业务意图的技能。两层次数都只约束 AgentCiCi 外层调用，不能限制百炼 Responses 单请求内部的自主检索轮数。
