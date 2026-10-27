# 资源包与知识库能力

## 智能体原生包

后台 GET `/agents/{agentId}/package` 下载 `.ciciagent`，其内容为 ZIP，只有 manifest.json 和 agent.json，最大 5 MiB。manifest.format 为 agentcici-agent-package、formatVersion=1、snapshot=SAVED_DRAFT，sha256 校验 agent.json。原样放入应用包，不改名成 JSON 或重建校验信息。

后台 POST `/agents/packages/preview` 使用 multipart file；POST `/agents/packages/import` 使用 multipart file 与 JSON 字符串 mapping。要求组织管理员与对应资源权限；这些不是开发者 OpenAPI，使用平台正常登录流程操作，不将开发者 Token 发给它们。

导出保存的是草稿快照，包含技能快照和知识/工具依赖引用。导入前读取 preview 返回的依赖、选项和警告，按实际 ImportCommand 契约映射目标组织资源，避免按名称猜 ID；新建后仍需配置运行身份/渠道与发布。应用清单 skillBindings 将包内技能 ref 映射到独立技能 ZIP 的 ref，安装器据此复用已导入技能，避免双份创建。

## 技能 ZIP

已有技能 CRUD 见 [skills.md](skills.md)。后台 POST `/skills/{id}/exports` 创建导出，随后 GET `/skills/exports/{exportId}/download` 下载；未发布草稿导出需要明确选择 allowDraft。后台 POST `/skills/imports` 上传 multipart file，预览后 POST `/skills/imports/{importId}/create` 创建。平台支持的上传包格式以实际预览结果为准；不要将任意 SKILL.md ZIP 声称为已验证可导入。

导出标准格式为 universal-skill-package@1.0，包含 manifest.json、SKILL.md、cici-skill.md、prompt.md、contract.json、resources.json 等。应用打包工具要求此标准导出格式，保留完整原包。后台技能绑定通过 GET/PUT `/skills/agents/{agentId}/bindings`；管理 CRUD 并不涵盖此接口。智能体关联技能已支持管理 CLI，见 agents.md；导出下载使用下述开发者接口，导入仍使用已登录后台界面。

## 知识库

知识库开发者API、CLI、资料上传和索引检索流程见 [知识库管理](knowledge-bases.md)。使用knowledge.read/write/delete，并保留实际知识权限；与智能体绑定后重新编译发布。
应用外层清单只描述目标组织需新建的知识库 ref/name，不携带开发组织数据或 ID。无知识依赖则 knowledgeBases=[]。有依赖则包内全部 knowledge refs 都要映射；知识检索是否可用还需目标组织上传资料并完成索引，打包校验不能替代它。

## 开发者原生导出下载

在目标应用目录执行，使用目标服务的已部署开发者导出接口，不需要平台源码或后台登录Token：

```bash
mkdir -p resources
python3 /installed/agentcici/scripts/agentcici_manage.py agents export customer-email-assistant --output resources/customer-email-assistant.ciciagent
python3 /installed/agentcici/scripts/agentcici_manage.py skills export 36 --output resources/birthday-writer.zip
```

- 智能体：GET `/openapi/v1/management/agents/{agentId}/package`，需要 agent.read 及绑定成员的 MANAGE 权限，复用原生保存草稿快照导出。
- 技能：POST `/openapi/v1/management/skills/{skillId}/package`，需要 skill.read；默认导出已发布版本，显式 `--allow-draft` 发送 allowDraft=true。仅允许当前组织自定义可编辑技能，沿用原生导出校验。
- 返回原始 ZIP 字节，CLI 校验 ZIP 类型和大小，保存到 --output 并返回路径、字节数及 SHA-256；不覆盖已有文件，不解压或重写包。
- 应用打包前，先对清单中的资源逐一导出，再将输出路径填入 skills[].file 和 agents[].file；读取原生 agent.json 中的引用构建映射。已有有效原包可复用，不重复导出。
- 404 表示目标服务可能尚未部署新接口，不将管理 Token 发给后台导出地址；失败时停止打包并报告原因。
