# 知识库开发者管理

需要部署包含本扩展的AgentCiCi后端。404或缺少scope时停止相应操作并报告，不能拿开发者Token调用后台/kb接口替代。

## 权限与API

路径前缀 /openapi/v1/management/knowledge-bases，当前组织来自开发者Token，不能由请求体传入companyId。knowledge.read读取，并按凭据责任人的实际知识库访问权限过滤；knowledge.write创建/编辑/上传/索引，knowledge.delete删除，写入和删除还需责任人具有kb.manage。已有开发者凭据不自动增加这些scope，需组织管理员在开发者管理中授权。

| 操作 | 方法与相对路径 | scope |
| --- | --- | --- |
| 列表、详情 | GET 空路径、/{kbId} | knowledge.read |
| 创建、完整更新名称说明 | POST 空路径、PUT /{kbId} | knowledge.write |
| 查询访问策略 | GET /{kbId}/access | knowledge.read |
| 替换访问策略 | PUT /{kbId}/access | knowledge.access.write，责任人同时须有 kb.manage |
| 删除知识库 | DELETE /{kbId} | knowledge.delete |
| 文档列表 | GET /{kbId}/documents | knowledge.read |
| 上传资料 | POST /{kbId}/documents，multipart file | knowledge.write |
| 发布并索引、重建索引 | POST /documents/{documentId}/publish、/reindex | knowledge.write |
| 删除文档 | DELETE /documents/{documentId} | knowledge.delete |
| 检索测试 | POST /{kbId}/retrieval/test | knowledge.read |

创建请求只包含 name 和 description。支持该接口的新版平台中，新建知识库默认组织成员可读（`COMPANY_OPEN`），包括同组织有效的 API_CLIENT 机器成员。应用安装时新建的库使用相同默认值，复用现有库时沿用其访问策略。资料需要限制访问时，在上传前用 `get-access` 核对策略并用 `set-access` 设置。被智能体或已安装应用引用的知识库仍受现有删除约束。

先用 `get-access` 读取 `mode`、`roleIds` 和 `version`。授权范围已确认后，用 `set-access` 提交完整策略，把读取到的 `version` 传为 `expectedVersion`。示例角色 ID 和版本须替换为实查值。`ROLE_RESTRICTED` 需要至少一个当前组织的有效角色 ID，传入列表会替换原有授权角色。`ADMIN_ONLY` 和 `COMPANY_OPEN` 均传空角色列表。组织开放允许同组织有效的 API_CLIENT 机器成员读取。按角色授权时，运行 Key 的执行成员必须拥有目标角色。冲突时重新读取并复核策略后再提交。

## 命令流程

在用户项目目录调用已安装技能脚本绝对路径；将下方 `/installed/agentcici` 替换为实际技能安装目录：

```bash
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge list
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge create --json '{"name":"应用产品资料","description":"已获授权的知识资料"}'
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge get 123
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge update 123 --json '{"description":"新的说明"}'
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge get-access 123
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge set-access 123 --json '{"mode":"ROLE_RESTRICTED","roleIds":["example-role-id"],"expectedVersion":0}'
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge upload 123 --file /project/approved/product-guide.pdf
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge publish-document 456
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge documents 123
python3 /installed/agentcici/scripts/agentcici_manage.py knowledge retrieve 123 --json '{"query":"目标产品的适用范围是什么？"}'
python3 /installed/agentcici/scripts/agentcici_manage.py agents bind-knowledge app-agent --json '{"knowledgeBaseIds":[123]}'
```

123/456为示例，使用本次返回的真实ID。先读取智能体并保留已有知识库关联，不能直接套用示例覆盖。资料上传后检查文档状态与indexedAt；INDEXING不是完成，FAILED要读取错误；索引完成后必须以实际问题验证命中内容，再绑定或编译发布智能体。接口复用现有文件类型/大小、商业额度及索引限制，不无限轮询。上传结果未知先查询文档列表，CLI不会自动重复上传。

重建索引用reindex-document；删除前确认精确目标，delete和delete-document均要求相同--confirm-id。只上传用户允许使用的资料，真实客户数据和测试资料不自动进入应用ZIP。开发时先将获授权的源文件保存在项目knowledge/<ref>/目录，并在knowledgeBases[].documents声明。应用包携带原文件及摘要，不携带向量；安装时同名库直接复用且不覆盖资料，不存在才创建并导入索引。正常卸载和失败回滚均在无其他应用、智能体、有效技能引用时删除关联库，有引用则保留。旧包无源文件只能复用现成库，不能新建空库。
