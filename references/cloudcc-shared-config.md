# 应用 cloudcc 工程与根目录共用配置

## 目录和职责

应用开发只在 `applications/<appCode>/` 进行。CloudCC 资源集中在应用 `cloudcc/`：类源码为 `cloudcc/backend/classes/<ClassName>/`，对象/字段等定义为 `cloudcc/metadata/`，相关工具为 `cloudcc/scripts/`。不需要 AgentCiCi 平台源码、根 backend/frontend/deploy 工程，也不向这些目录写入类或临时映射。

项目根目录共享 `cloudcc-agentcici.config.json`、`cloudcc-cli.config.json` 和 `.cloudcc-cache.json`。前者用于 AgentCiCi 管理；后两者由 CloudCC CLI 管理 CRM 环境和身份。配置与缓存不提交、不打包，不在应用内维护副本。

CloudCC CLI 按 `<projectPath>/backend/classes` 定位类；本技能把应用 `cloudcc/` 作为类操作的 projectPath。`create classes` 使用工作目录，format/validate/publish 同时显式传入此工程根。类目录和类级 `config.json` 由 CLI 维护，只编辑源码 SOURCE 区域。

## 共用配置适配器

使用 `scripts/agentcici_cloudcc_class.py`，不修改 CloudCC CLI：

1. 确认应用目录和根 CRM 配置存在，拒绝越出应用的目录/文件链接，不覆盖已有类。
2. 为同一项目取得系统临时目录中的进程锁；锁文件不含凭据，避免多个适配操作并发刷新共用缓存。已有独立 CLI 操作也应避免同时切换该项目环境。
3. 在应用 cloudcc/ 下临时创建指向根配置及根缓存的符号链接。它们是本次操作的引用，不是凭据副本；执行结束后清理。根缓存尚未生成时使用悬空链接，由 CLI 首次写入真实缓存，不伪造身份。
4. CLI 在 cloudcc/ 内操作真实类源码。若刷新时删除链接并重建缓存，把 CLI 新文件移动回根缓存；若 CLI 删除后未重建，清除根旧缓存，避免继续使用失效 Token。不会合并另一环境的缓存身份。
5. 正常完成、CLI返回失败、进程启动异常时均执行清理。平台不支持或拒绝符号链接时明确失败，不回退到复制凭据。被强制终止可能留下链接；确认没有进程运行且目标确为根配置后，只清理残留链接，不删除链接目标。

已有应用 cloudcc/ 内配置、缓存或链接一律报告冲突，不擅自覆盖；先核对环境并归并到根配置。同名环境不一致时明确处理。旧应用 `backend/classes` 布局不自动搬迁，也不为同名类再创建一份；用户确认规范化后再统一所有引用。

## 使用方式

在目标应用目录调用安装技能的绝对脚本路径；下面 /project 和 /installed 是路径占位：

```bash
python3 /installed/agentcici/scripts/agentcici_cloudcc_class.py \
  --cli /installed/cloudcc/tools/bin/cloudcc \
  --root /project --app story-expander create StoryService

python3 /installed/agentcici/scripts/agentcici_cloudcc_class.py \
  --cli /installed/cloudcc/tools/bin/cloudcc \
  --root /project --app story-expander validate StoryService

python3 /installed/agentcici/scripts/agentcici_cloudcc_class.py \
  --cli /installed/cloudcc/tools/bin/cloudcc \
  --root /project --app story-expander format StoryService --check

python3 /installed/agentcici/scripts/agentcici_cloudcc_class.py \
  --cli /installed/cloudcc/tools/bin/cloudcc \
  --root /project --app story-expander publish StoryService
```

create/format --write/publish 会产生相应本地或远程写入，必须在用户授权范围内；validate 是真实平台 SDK 本地编译，不等于 CRM 发布或业务验收。format 缺省只检查。测试只需本地编译时不运行 publish。

对象/字段等不依赖类源码位置的操作，仍显式用根配置路径；定义文件在应用内，CLI从目标应用工作目录调用即可：

```bash
/installed/cloudcc/tools/bin/cloudcc doctor provider /project
/installed/cloudcc/tools/bin/cloudcc plan msapi /project fields @/project/applications/story-expander/cloudcc/metadata/content.json create
/installed/cloudcc/tools/bin/cloudcc apply msapi /project PLAN_ID
/installed/cloudcc/tools/bin/cloudcc get fields /project OBJECT_API_NAME
```

按安装的 CloudCC 专用技能先读资源介绍和指南；plan 不是实际创建，apply 后回读。AgentCiCi 与 CRM 配置的 use 独立，先核对实际地址/组织；不因同为 uat 就混用身份。CRM 缓存缺失或失效由 CLI 正规刷新，开发联调按当前环境安全标记选择 accessToken，不取缓存第一项。根凭据和缓存保持本机受限权限，Git 忽略应用内临时同名链接；打包器拒绝包含这些文件或链接的站点/资源。
