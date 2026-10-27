# 第三方 Web 应用规范

## UI技术边界

本技能开发或迁移的AI应用全部使用原生HTML/CSS/JavaScript静态Web前端。禁止使用、创建或依赖CRM自定义页面customPage/VisualPage、自定义组件pagecomponent/customComponent承载UI。页面、表单、列表、编辑器及交互统一在Web实现；按宿主SDK的iframe或Shadow DOM协议挂载。CRM菜单/按钮仅使用SDK启动入口，不跳转injectionComponent等原生自定义页面路由。旧应用若存在这类依赖，迁移时改为标准Web入口，不把手工预装页面或组件留给安装者。


开发前必须先读 [CloudCC CRM Web UI 规范](crm-web-ui.md)，统一视觉变量、紧凑工具栏、列表密度、表单与弹窗样式，并按其桌面验收流程核查；不要让 AI App 在 CRM 中呈现另一套产品外观。

## 构建与站点

使用原生 Web（HTML、CSS、JavaScript）开发，交付静态构建目录，根层必须有 index.html。不要交付 node_modules、开发服务器、SSR 服务或源码目录。资源地址相对站点目录；多页面应用应明确入口，SPA 默认使用 hash 路由，除非实际站点已验证 history fallback。在非根子路径验证 JS/CSS、图片、字体、动态加载和页面刷新，不能只测试开发服务器。

### 脚本格式兼容要求

- 应用 `package.json` 不设置 `"type": "module"`；Node 构建脚本使用 CommonJS，按需使用 `.cjs` 扩展名。
- 页面使用普通 `<script src="./app.js" defer></script>`，不使用 `<script type="module">`，动态创建的 script 也不得设置 `type = "module"`。
- 发布的浏览器脚本使用 `.js`，不发布需要浏览器请求的 `.mjs` 文件。原生 JavaScript 源码可使用 import/export，但须在构建阶段合并为 IIFE/普通脚本；最终产物不依赖浏览器原生 import/export、动态 import()、顶层 await 或 modulepreload。异步初始化放入 async 函数中执行。
- 发布前检查实际构建目录的 HTML 与 JS，而非仅检查源码或开发服务器。部署后核对脚本响应为 JavaScript MIME 类型，并在 CRM 实际容器中验证 SDK 握手和业务启动；HTTP 200 不代表脚本可执行。已发布版本不可直接覆盖，兼容修复使用新版本。

现有 UAT 静态资源服务对 `.mjs` 返回 `application/octet-stream`，浏览器会拒绝将其作为模块执行，从而导致应用初始化超时。上述规则是 AI App 的交付约束，不要求修改平台自身或其他独立项目的模块方案。

构建工具、解析库等依赖版本和构建参数以项目锁文件及已安装工具为准；这不改变原生Web源码与普通脚本产物要求。不要引入一个未经提供或发布的 AgentCiCi SDK 包。调用层使用应用自有小模块封装，接真实平台能力前可以用明确标注的 mock；mock 成功不能写成智能体联调成功。

构建包只包含运行必需文件，排除 .env、源码映射、凭据、真实客户数据。VITE_* 等构建变量会进入浏览器，不是密钥存储。打包工具仅做文件名与结构检查，不能证明编译后代码没有敏感内容。

## CloudCC 数据存储与业务逻辑

涉及自定义类、对象或字段时，先执行 [CloudCC 资源开发前置要求](../SKILL.md#cloudcc-资源开发前置要求)：检查并按需安装专用技能，读取其 `SKILL.md`，并执行前置要求列出的各资源 `introduction` 与 `devguide` 命令、读取两份文档后，再开始设计或生成定义与源码；不得把文档读取推迟到实现或发布阶段。

CRM开发凭据与CLI缓存由多个应用共用项目根目录文件，类源码仍由CLI维护在对应应用内；类操作使用 [共用配置适配入口](cloudcc-shared-config.md)，不在各应用另配凭据或移动代码。

业务架构包含 **Web → 自定义类 → 自定义对象** 与 **Web → Agent（智能体）** 两条调用链，按业务需要选择或组合。CloudCC 提供数据存储和业务逻辑，Agent 提供 AI 对话与任务处理；Web 按上述方式构建、部署和嵌入。智能体调用要求见下文 [用户与智能体接入](#用户与智能体接入)。

需要持久化时，先核对目标业务模型，默认优先新建本应用的 CloudCC 自定义对象和字段；自定义类同样优先新建。只有用户明确要求扩展已有资源时，才按指定范围实施，具体见 [资源设计规则](../SKILL.md#第三方-web-应用开发规范)。明确对象/字段 API Name、类型、关系和访问权限；代码使用 API Name 引用，在目标 org 安装时再解析平台接口所需的内部 ID。不要把业务数据存入浏览器 localStorage 作为正式存储，也不要求开发者另外搭建数据库。

有业务逻辑时，编写 CloudCC 自定义类，集中完成读取、写入、业务校验及权限检查。类的方法和参数应形成清楚的业务契约，返回前端需要的数据；浏览器不直接操作对象来绕过类中的规则。对象定义、字段定义和类源码随业务资源交付，真实客户记录不随包提交。

### 长文本字段选型

创建自定义对象的字段、存储正文或其他长文本内容时，按预期内容长度选择：

| 字段类型 | 支持长度 |
| --- | --- |
| 文本区字段 | 4000 字符 |
| 文本区长字段 | 32000 字符 |

在对象/字段设计中记录所选类型及长度上限。具体字段类型参数仍须按设计前读取的 CloudCC 字段介绍、开发指南及目标环境能力确认，不根据显示名称猜测 CLI/API 类型编码。

### Web 调用自定义类

CRM 宿主页面具备 CCDK 时，通过 `window.$CCDK.CCCommon.post(className, methodName, params)` 调用自定义类。参数格式以已安装 CloudCC 专用技能的 `cloudcc doc pagecomponent devguide`「在组件中调用自定义类」为依据。跨域 iframe Site 通过公共 SDK 获取上下文，使用 OpenAPI；不默认 Site 已加载 CCDK，不直接访问 `parent.$CCDK`。

iframe 中的调用顺序：等待 `client.ready`，从每次请求时的 `client.getContext().cloudccContext` 读取最新 `accessToken` 和 `ccex-apitsf`，向该服务的 `/api/openCall/common` 发起 POST：

```js
const crm = client.getContext().cloudccContext;
const abortController = new AbortController();
const response = await fetch(
  crm['ccex-apitsf'].replace(/\/$/, '') + '/api/openCall/common',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', accessToken: crm.accessToken },
    body: JSON.stringify({
      className: 'OrderApplication',
      methodName: 'saveOrder',
      params: [
        { argType: 'java.lang.String', argValue: JSON.stringify(orderInput) }
      ]
    }),
    signal: abortController.signal
  }
);
const result = await response.json();
if (!response.ok || result.result !== true) {
  throw new Error(result.returnInfo || '自定义类调用失败');
}
const order = result.data;
```

`OrderApplication`、`saveOrder` 为示例，假设后端方法签名为 `saveOrder(String orderJson)`，接收业务对象序列化后的 JSON 字符串；实际调用必须替换为已安装的类、方法及其真实参数类型。`params` 按 Java 方法的形参顺序组织，每项必须包含 `argType`（Java 类型）和 `argValue`（参数值），不能直接传原始字符串或业务对象数组。字符串使用完整类型名 `java.lang.String`；其他类型须按目标方法与平台文档确认，不能把所有参数统一转成字符串。

多参数示例：假设后端方法为 `createDraft(String title, String keywords, String tone)`，请求参数须按此顺序传入：

```js
{
  className: 'ExampleApplication',
  methodName: 'createDraft',
  params: [
    { argType: 'java.lang.String', argValue: '月光下的相遇' },
    { argType: 'java.lang.String', argValue: '月亮、旧车站、猫' },
    { argType: 'java.lang.String', argValue: '温暖治愈' }
  ]
}
```

以上 `params` 结构同样适用于 `CCCommon.post` 和下述 `callClass` 辅助方法。Token 对自定义类调用通用，但 AgentCiCi 的 `apiKey` 和开发者 Token 不能替代这里的 CloudCC Token。CloudCC 服务地址使用 `ccex-apitsf`，不要拼到智能体的 `context.apiBase`。

示例中的 `client` 是已初始化的 SDK client，`orderInput` 是调用方准备的业务对象。页面卸载、身份切换或超时处理可调用 `abortController.abort()`；取消浏览器请求不保证服务端停止写入，保存结果未知时仍须先核实，不能据此自动重发。

目标环境已部署 `agentcici-cloudcc@1.0.0.js` 时，可以加载该辅助脚本并用 `AgentCiCiCloudCC.createCaller(client).callClass(className, methodName, params)` 封装上述请求；它依赖已初始化的公共 SDK client。未部署时使用应用自身的小调用模块，不假设辅助脚本已上线。动态加载 JS 仍遵守技能入口的时间戳缓存规则。

调用层检查 HTTP 与业务返回，处理超时、取消和错误；切换用户/org/Token 时取消旧请求，页面卸载时清理调用器与 client。写入请求失败或超时后先核实结果，不自动重复提交。Token 不进入 URL、日志、localStorage 或构建产物。跨域 OpenAPI 调用仍需目标服务允许站点 Origin；没有上下文、未安装类、无权限或 CORS 不通时明确报错，不退回测试身份。

验收应使用实际 org 验证：Web 调用已安装类成功、类读写正确对象与字段、无权限被拒绝、org 之间数据隔离；模拟返回成功不等于真实业务联调通过。

## 用户与智能体接入

**Web → Agent（智能体）** 使用已发布智能体的运行 OpenAPI，宿主 SDK 提供当前安装实例的运行上下文；具体接口见 [agent-runtime-openapi.md](agent-runtime-openapi.md)，使用 Agent API Key；开发者密钥用于管理，不能直接用于运行。Web 前端不嵌入开发者 Secret 或长期 Agent API Key。

运行请求直接使用 `context.apiBase`，它已包含 `/openapi/v1`；业务代码只追加相对端点，不得硬编码该前缀或在缺失时自动补齐。独立本地测试的 `localContext.apiBase` 必须配置完整 API 基地址，例如 `http://127.0.0.1:8080/openapi/v1`。地址拼接与验收见 [运行接口地址规范](agent-runtime-openapi.md#apiBase-与请求路径)。

应用清单声明逻辑agent ref，已部署的标准应用runtime按当前登录org和安装实例解析运行身份，宿主SDK把完整apiBase等上下文交给子应用。SDK负责安装配置、换票和iframe；它不是另一套模型代理网关。目标环境尚未部署标准runtime或尚未安装应用时，报告该具体缺失，不猜网关、不复用官方应用私有认证，也不为完成普通应用任务自行开发平台后端。

静态站点可访问不代表调用已获授权。站点与 CRM 可能跨域，不能默认读取 parent 的 CCDK、Cookie 或 localStorage。嵌入式登录桥接必须核对实际接口，若采用 postMessage，双方校验精确 origin、消息来源及请求关联；不要把 CRM Token 放 URL。菜单在 CloudCC 宿主页面获取运行配置，再按下述协议传给 iframe；不得把密钥字面值写进脚本。

应用处理 loading、错误、取消与重试，卸载页面终止在途请求。会话 ID 仅复用于同一用户、org、安装实例和智能体；身份切换清空。文件上传结果只能用于所属会话权限范围。流式接口按 SSE 事件边界增量解析，支持跨网络分片，不假设一次 read 就是完整 JSON。

## 业务输出契约示例（生日邮件，不是通用功能要求）

桌面端先完成输入表单、生成按钮、主题/正文编辑区和复制反馈。示例契约为 `{"subject":"...","body":"..."}`，提示词约定不代表服务端强制 schema；前端校验缺失字段，保留可理解的失败反馈。用纯文本展示用户输入和模型输出，不直接注入 innerHTML。重复点击不能产生并行请求覆盖结果，重试由用户触发。

生日邮件第一期只生成草稿，不创建发送能力。真实姓名、生日或邮件正文不写入调试日志，默认不持久化。知识库是可选的企业写作依据，不是此例必需资源。

## 历史CloudCC站点接口（按需兼容）

新应用通过AgentCiCi标准应用发布和安装流程交付站点，不把直接调用站点接口作为默认步骤。仅在用户明确维护历史独立站点时核验下列接口；不擅自迁移或重复建站。历史站点接口包括 POST `/api/site/saveSite`、`/api/site/uploadZip`、`/api/site/querySiteDetail`、`/api/site/enableSite`。这是 CloudCC 登录接口，不是 AgentCiCi 开发者 OpenAPI。

现有保存参数包含 first、label、apiname、sitecontact、defaultrecordowner、sitepath、fullurl、description、activehomepage、inactivehomepage、isenable、zipid、zipname；负责人、组织前缀等来自目标组织。先创建站点取得 ID，再上传 ZIP。上传为 multipart，字段 `files`、`sitePath`（当前组织/站点路径）、`filesName`、`siteId`。按实际响应与查询结果确认上传成功，不把 HTTP 200 单独当作完成。

安装脚本菜单的业务 JSON 为 tabName、pname、type=script、functioncode；现有安装器按菜单接口补全目标组织简档与应用范围。站点入口运行后，安装器才能生成最终 functioncode。默认生成 CRM 内嵌菜单，参照下述宿主初始化流程。容器选择器以实际 CloudCC 环境和互动工作台实现为准，不杜撰 CCDK 方法，不移除或替换 CRM 自身节点。

## 默认菜单与 iframe 初始化（必须遵守）

创建 Web 应用时，未声明 launchers 则默认生成 `menu` 触发入口并在 `page-content` 展示；显式声明时按用户配置生成入口。菜单类型创建一个 CloudCC 自定义脚本菜单，填写 menu.tabName、menu.pname、menu.type=script 和 menu.functioncode。菜单随应用打包，不把“手动添加菜单”留给安装客户。旧menu.json格式的functioncode保留 `__AGENTCICI_SITE_URL__` 兼容标记；新schemaVersion=2通过installationManifest提供完整JS；实际站点 URL 读取 runtime.webUrl；打包工具原样保留自定义脚本。仅打开新窗口的兼容模板不满足新应用交付要求。

CloudCC 菜单、按钮和浮动入口统一加载目标服务提供的 `sdk/agentcici-app@1.1.0.js`，再以 `appCode` 调用通用宿主 SDK。应用路由、认证、关闭方式和宿主层级必须声明在应用自己的 `application.json`，不要在公共 SDK 或菜单脚本中实现应用专属逻辑。

宿主执行顺序：

1. 使用 `$CCDK.CCToken.getToken()` 获取当前登录身份；setup 地址来自经确认的配置或 `window.Glod['ccex-setup']`。
2. 携带 accessToken 请求 `GET /api/agentcici/ai-applications/runtime?appCode=<固定应用代码>`，验证 HTTP 状态和响应 success/result，读取 data.apiBase、apiKey、user、agentId、keyType。appCode 由菜单固定，org 由服务端登录身份决定。未安装或缺字段时显示错误，不回退到开发者 Key。
3. 创建站点 iframe，挂载到经核实的 CRM 内容容器；保留原有 DOM 和生命周期。初始化监听器必须先于 iframe 加载注册。
4. 子页面发送 `{type:"agentcici:ready", protocolVersion:1, requestId}`。宿主核对 event.source===iframe.contentWindow、event.origin===站点URL.origin 及消息结构后，以精确 targetOrigin 返回 `{type:"agentcici:init", protocolVersion:1, requestId, context}`。
5. context 白名单为 appCode、apiBase、apiKey、user、agentId、keyType；仅业务调用确需 CRM 上下文时附加短期 cloudccContext。连接应用 Secret 留在宿主，仅用于 CCDK 换取连接应用 Token，不传给 iframe；开发者管理凭据绝不传入。
6. 子页面引入同一公共 SDK，用 `AgentCiCiApp.createClient(...)` 完成父窗口、精确 Origin、requestId 和协议版本校验。SDK 设置 `window.AgentCiCiContext` 并通过 `ready` 返回上下文。实际部署域名由宿主创建 iframe 时动态写入，子应用不预置域名白名单。

在 SDK `ready` 完成前禁用生成按钮。不要直接假设 window 属性已经存在。iframe 模式只能等待宿主消息，有超时、错误及销毁清理；不能加载测试凭据兜底。账号切换时宿主重新获取配置、重建初始化，子页面取消请求并清空旧会话。两边不使用 `*` 发送凭据，凭据不写日志、localStorage 或构建产物。

### Web 应用子页 SDK

普通 iframe 应用先加载经确认的官方 `agentcici-app@1.1.0.js`，再调用 createClient；可由 index.html 先引入，或在启动时动态加载并等待成功。动态加载仍追加运行时时间戳。业务代码只创建一个 client：

```js
(async function bootstrap() {
  const client = window.AgentCiCiApp.createClient({
    localContext: window.__AGENTCICI_LOCAL_CONTEXT__
  });

  const context = await client.ready;
  // context 也同步保存在 window.AgentCiCiContext。
  startApplication(context);

  const unsubscribe = client.subscribe(nextContext => {
    updatePageContext(nextContext.pageContext);
  });

  window.addEventListener('pagehide', () => {
    unsubscribe();
    client.destroy();
  }, { once: true });
})().catch(showInitializationError);
```

- 发布嵌入模式：SDK 从宿主添加的 `agentciciParentOrigin` 读取当前宿主 Origin，仅向该精确 Origin 发起握手，并且只接受 `event.source === window.parent` 且 `event.origin` 精确相同的回复。不得使用 `*`。
- 上下文更新：SDK 自动处理 `agentcici:context`，更新 `getContext()` / `window.AgentCiCiContext` 并调用 `subscribe()` 监听器。需要宿主重新换取 runtime 时调用 `client.refresh()`；请求宿主关闭容器时调用 `client.close()`。
- 本地模式：仅当页面为顶层且 hostname 为 `localhost`、`127.0.0.1` 或 `[::1]` 时，SDK 才接受显式 `localContext`。它应由未提交的本地文件或开发服务器运行时注入；不得把真实 Key 写入源码、`.env` 的前端变量或构建产物。
- 顶层非 localhost 页面、缺失宿主 Origin、消息来源不匹配或超时都必须显示明确错误，不得回退到测试 context。

独立本地测试：仅在顶层页面且显式 development 模式下读取测试用 `window.AgentCiCiContext`；从不提交 Git 的本地配置或交互输入提供运行 Key。生产顶层打开而无可信上下文时提示从 CloudCC 菜单进入。URL 可携带 appCode、locale 等普通参数，不能携带 API Key、Token、Secret（query 和 hash 均禁止）。动态传入运行 Key 意味着该应用脚本可读取它，不得宣称此模式把 Key 隐藏在服务端。

验收：默认菜单已打包；跨域 iframe 正常初始化并使用当前客户配置；本地测试正常；无身份/未安装/错误来源/超时有明确反馈；切换客户不复用旧 Key 或会话；源码、菜单和应用 ZIP 不含真实凭据。自动资源安装未完成时，明确说明 runtime 配置仍需安装流程生成，不能把前端初始化成功当成安装成功。

## 发布站点到 Nginx

平台发布版本时将 Web ZIP 解压到共享 aiapp 目录，访问路径为 `/aiapp/{appCode}/{version}/{sha256}/index.html`。多 Web 包分别生成路径；安装清单 webApps 保存站点路径，setup 安装记录保存后，runtime 返回 webApps 和默认 webUrl（第一项）。旧安装需升级/重装，不能猜测地址代替 runtime 配置。

打包工具为脚本菜单生成启动器，加载公共 SDK 后执行 `AgentCiCiApp.mount({appCode, launcherId})`。SDK 负责 CCDK 登录身份、runtime、连接应用换票、iframe 与初始化消息。自定义 functioncode 仍可覆盖，但必须遵守相同初始化要求。四层清单按入口读取 renderConfig.entryUrl 或安装站点地址；子页面统一使用 SDK `createClient()`，不复制协议实现。

站点发布与 org 资源安装是不同阶段；静态文件就绪不代表智能体/技能已经安装。共享目录和 /aiapp/ 路由由平台运维提供，应用开发不创建平台部署工程或自行修改Nginx。平台上架权限保持管理员专有。


## 公共SDK负责的CRM嵌入行为（应用验收边界）

以下是公共SDK的职责，用于应用验收；应用不复制这些DOM、消息和生命周期实现。默认菜单由打包器生成SDK启动脚本，旧menu清单才使用 `assets/application-menu.js` 兼容模板。SDK嵌入 `.console-right-content`，使用 prepend 添加自身 section，不覆盖 CRM 节点，不创建全屏遮罩或额外关闭按钮。iframe 允许 clipboard-write，宽度100%，高度依据容器高度与视口剩余空间取较小值。

- 使用 `window.AgentCiCiAppEmbed.destroy()` 销毁上一个实例，再创建本次实例，所有应用采用同一宿主实例入口。
- 先获取 runtime 配置，再创建 iframe；postMessage 继续校验来源窗口、精确 origin、协议版本和 requestId，凭据不进入 URL。
- 监听 resize/ResizeObserver；监听 hashchange、popstate、pagehide，并每200ms比较入口URL，以覆盖 SPA 路由变化。
- MutationObserver 等待内容区出现；目标被移除、宿主被移走，或目标出现其他直接子节点时销毁实例。10秒仍找不到内容区时清理并提示重新打开应用。
- destroy 必须中止请求、断开观察器、清理定时器和事件监听、移除自身节点；异步返回后检查 destroyed，避免切换页面后旧实例重新挂载或弹错。
- 验证重复点击、切换菜单、容器延迟出现、窗口缩放及请求中切换页面。模板中的 appCode 由打包工具替换，禁止硬编码为邮件助手。

## 统一宿主 SDK

公共 SDK 是目标 AgentCiCi 服务提供的已发布资源 `sdk/agentcici-app@1.1.0.js`；应用开发不要求平台源码仓库或 frontend/public 目录。若应用需要随站点携带子页SDK，使用经确认的官方分发文件，记录来源/摘要和兼容验证，避免不同副本无记录漂移。菜单和脚本按钮调用 `AgentCiCiApp.mount({appCode, launcherId})`，全局悬浮入口调用 `AgentCiCiApp.start({appCode, launcherId})`。位置和 iframe/Shadow DOM 渲染方式由安装快照中对应入口的 renderConfig 决定；旧清单回退应用级 renderConfig。入口不再内联 runtime 请求、CCDK 换票或 iframe DOM。

普通页面继续使用上述协议，context 额外提供 display、pageContext；存在连接应用时附加 cloudccContext。业务关闭方式、宿主层级和 CloudCC SSO 票据参数必须由各应用的 host 清单声明，公共 SDK 只执行通用协议，不识别具体 appCode、业务路由或票据前缀。Shadow DOM 应用通过 register 挂载，原生 Web 页面可使用 iframe，无需增加嵌入构建。SDK 已实现不代表目标环境已部署；不得在菜单里嵌入真实密钥。

应用版本「安装内容」的四层入口配置按 CRM 资源、触发入口、展示位置、渲染方式填写。每个入口保存自己的 renderConfig：renderer 为 iframe 或 shadow-dom，entryUrl/entryPath 为入口地址，positions 为有序多选（第一项默认），并包含 closeBehavior 与 hostLayer。setup-svc 保存快照，按 steps 创建对应 CRM 资源并保留资源 ID；思思快捷菜单从已安装菜单的真实 ID 生成。CRM 启动脚本加载固定 agentcici-app@1.1.0.js 后传 appCode 和 launcherId。

### CRM 租户归属验收

标准 SDK 的 Agent API Key 决定正式租户，CRM userId 仅区分当前用户及业务上下文，不作为计费租户。第三方应用无需自行查询或维护 CRM 租户映射。官方 CRM 专用会话由平台验证开户映射；新消费归正式组织，旧业务隔离身份及历史账单保留。验收覆盖模型、实时/文件语音及异步任务，并核对正式组织的计费流水；缺少绑定不得静默继续使用独立赠送额度。
