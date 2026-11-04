# AI 应用实时语音输入

应用需要“麦克风 → 文字草稿”时读取本指南；不要求所有应用增加语音。沿用[宿主 SDK](web-app-development.md#web-应用子页-sdk)和[运行 OpenAPI](agent-runtime-openapi.md)，不创建新智能体、技能或自定义类来完成语音识别，也不复制官方 CRM 应用的私有认证流程。

## 身份与授权

1. 使用已有 `AgentCiCiApp.createClient()` 实例，等待 `client.ready`；开始一次新录音前调用 `client.refresh()`，通过 `client.subscribe()` 等待新上下文。当前 SDK 的 refresh 仅发送刷新请求，不返回 Promise 或 runtime，不能写成 `await client.refresh()`。本地顶层 localhost 显式测试模式使用已配置的上下文，不请求宿主刷新。不要为语音另建客户端或缓存旧 Key。
2. 使用 runtime 的 `apiBase`、`apiKey`，Key 需有 `audio` 或 `*` scope，智能体已发布且启用 API 渠道。开发者管理 Token 不能用于此接口。
3. 当 `keyType === 'cloudcc'`，从同一 runtime 的 `cloudccContext.accessToken/baseUrl` 取当前 CRM 用户身份，放入 `X-Cloudcc-Access-Token`、`X-Cloudcc-Base-Url` 请求头；缺失时提示从 CRM 重开，不能借用管理员身份。standard Key 不因增加语音而改成 cloudcc Key。
4. 授权归属 API Key 的组织；CRM 身份须有效且组织匹配，已验证的 CRM 用户不要求额外创建正式成员。接口仍可能因限流或组织服务不可用拒绝启动，按实际错误提示处理。

## 申请凭证

```http
POST {apiBase}/voice-sessions?scene=voice-asr
Authorization: Bearer {runtime.apiKey}
```

无需请求体。语音输入显式使用 `voice-asr`；仅支持该场景和 `meeting-realtime-asr`，省略参数默认会议场景。不要靠 `provider` 参数选择厂商，后端按凭证签名场景路由。

成功响应无外层 data 包装，且禁止缓存：

```json
{
  "sceneCode": "voice-asr",
  "token": "{短期语音凭证}",
  "expiresIn": 60,
  "websocketPath": "/ws/asr",
  "maxSeconds": 300
}
```

`expiresIn` 为凭证有效秒数，不是录音时长。凭证只保存在内存，通过 WebSocket 消息认证，不放 URL、持久存储或日志。HTTP 失败读取 `code/message`：401 表示身份问题；403 / `agent_api_scope_denied` 表示权限不足；400 / `voice_scene_invalid` 表示场景非法；限流、订阅或余额拒绝按实际响应处理，不盲目重试。

## WebSocket 协议

HTTP 请求继续只拼接 `apiBase` 的相对端点。WebSocket 使用服务端返回的根路径 `websocketPath`，以 `apiBase` 解析同源 URL，将 https 改为 wss（本地 http 改为 ws）；它不位于 `/openapi/v1/ws/asr` 下。

| 顺序 | 客户端行为 | 等待的服务端事件 |
|---|---|---|
| 1 | 连接 `/ws/asr`，open 后发送 `{"type":"authenticate","token":"…"}` | `{"type":"status","message":"authenticated"}` |
| 2 | 发送 `{"type":"start","sampleRate":16000,"speakerDiarization":false}` | `{"type":"status","message":"started"}` |
| 3 | started 后发送二进制 PCM 分片 | `{"type":"partial","text":"临时段"}` / `{"type":"final","text":"确认段"}` |
| 4 | 停止采集，再发送 `{"type":"stop"}` | 接收尾部 partial/final，直到 `{"type":"finished"}` |
| 5 | finished 后关闭连接，释放音频资源 | 连接关闭 |

- `partial` 替换当前临时段；`final` 追加确认段并清空临时段。显示内容为原草稿 + 已确认段 + 临时段，不能反复把 partial 累加。
- `error` 含 `message`；认证失败、上游启动失败、超限和意外断线都不算成功。保留已识别文字，释放资源，重试申请新凭证和连接。
- 每个语音连接只允许一次 start，限定 16kHz，最多 300 秒音频且不启用说话人分离。思思的 60 秒自动停止、初始 5 秒无识别和已有文字 2 秒无新增停止是应用策略，其他应用按需求决定，不当成平台规则。

## 最小协议接入示例

先在应用初始化时等待 `client.ready`。嵌入模式通过下面的适配函数等待刷新后的上下文；subscribe 会立即回调现有上下文，因此须跳过第一次通知。

```js
function refreshVoiceRuntime(client, signal) {
  signal?.throwIfAborted();
  return new Promise((resolve, reject) => {
    let initial = true, unsubscribe;
    const timer = setTimeout(() => done(new Error('运行身份刷新超时')), 20000);
    function done(error, runtime) {
      clearTimeout(timer); unsubscribe?.();
      signal?.removeEventListener('abort', cancel);
      if (error) reject(error); else resolve(runtime);
    }
    function cancel() { done(new Error('语音已取消')); }
    unsubscribe = client.subscribe(runtime => {
      if (initial) { initial = false; return; }
      done(null, runtime);
    });
    signal?.addEventListener('abort', cancel, { once: true });
    try { client.refresh(); } catch (error) { done(error); }
  });
}
```

嵌入模式以 `await refreshVoiceRuntime(client, signal)` 的结果作为下例 runtime；本地显式测试模式用 `client.getContext()`。凭证 fetch 在下例中单独设置 20 秒超时；传入的 signal 只管理本轮生命周期取消，避免请求超时计时器误终止后续录音。

以下示例负责凭证、握手和文字事件；麦克风采集由应用接入 `sendPcm`，不是 SDK 内置录音 API。`onText` 接收本轮识别文字，原草稿由调用方保留；`onEnd` 负责同步 UI 状态和停止采集。示例依赖浏览器 `WebSocket`、`fetch` 和宿主提供的 runtime，不引入开发者密钥。

```js
async function openVoiceInput(runtime, { onText, onEnd, signal }) {
  signal?.throwIfAborted();
  if (!runtime.apiBase || !runtime.apiKey) throw new Error('应用运行身份不可用');
  const headers = { Authorization: `Bearer ${runtime.apiKey}` };
  if (runtime.keyType === 'cloudcc') {
    const crm = runtime.cloudccContext;
    if (!crm?.accessToken || !crm?.baseUrl) throw new Error('请从 CRM 重开应用');
    headers['X-Cloudcc-Access-Token'] = crm.accessToken;
    headers['X-Cloudcc-Base-Url'] = crm.baseUrl;
  }
  const response = await fetch(`${runtime.apiBase.replace(/\/$/, '')}/voice-sessions?scene=voice-asr`, {
    method: 'POST', headers, cache: 'no-store',
    signal: AbortSignal.any([signal || new AbortController().signal, AbortSignal.timeout(20000)])
  });
  const ticket = await response.json();
  if (!response.ok) throw new Error(ticket.message || `语音授权失败：${response.status}`);
  if (!ticket.token || ticket.sceneCode !== 'voice-asr' || ticket.websocketPath !== '/ws/asr') {
    throw new Error('语音接口不兼容，请联系平台管理员');
  }
  signal?.throwIfAborted();
  const url = new URL(ticket.websocketPath, runtime.apiBase);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(url.href);
  let phase = 'auth', confirmed = '', ended = false;
  let resolveReady, rejectReady, timer;
  const ready = new Promise((resolve, reject) => { resolveReady = resolve; rejectReady = reject; });
  function finish(error) {
    if (ended) return;
    ended = true;
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
    ws.close();
    if (phase === 'auth' || phase === 'start') rejectReady(error || new Error('语音已结束'));
    onEnd(error);
  }
  function cancel() { finish(new Error('语音已取消')); }
  function deadline() {
    clearTimeout(timer);
    timer = setTimeout(() => finish(new Error('语音服务响应超时')), 8000);
  }
  ws.onopen = () => {
    if (!ended) ws.send(JSON.stringify({ type: 'authenticate', token: ticket.token }));
    ticket.token = null;
  };
  ws.onmessage = event => {
    if (ended) return;
    let data;
    try { data = JSON.parse(event.data); } catch (_) { finish(new Error('语音响应格式错误')); return; }
    if (phase === 'auth' && data.type === 'status' && data.message === 'authenticated') {
      phase = 'start'; deadline();
      ws.send(JSON.stringify({ type: 'start', sampleRate: 16000, speakerDiarization: false }));
    } else if (phase === 'start' && data.type === 'status' && data.message === 'started') {
      phase = 'recording'; clearTimeout(timer); resolveReady();
    } else if (data.type === 'partial' || data.type === 'final') {
      const text = typeof data.text === 'string' ? data.text : '';
      if (data.type === 'final') confirmed += text;
      onText(confirmed + (data.type === 'partial' ? text : ''));
    } else if (data.type === 'finished') finish();
    else if (data.type === 'error') finish(new Error(data.message || '语音识别失败'));
  };
  ws.onerror = () => finish(new Error('语音连接异常'));
  ws.onclose = () => { if (!ended) finish(new Error('语音连接已中断')); };
  signal?.addEventListener('abort', cancel, { once: true });
  deadline();
  await ready;
  return {
    sendPcm(buffer) {
      if (!ended && phase === 'recording' && ws.readyState === WebSocket.OPEN) ws.send(buffer);
    },
    stop() {
      if (!ended && phase === 'recording') {
        phase = 'stopping'; deadline(); ws.send(JSON.stringify({ type: 'stop' }));
      }
    },
    cancel
  };
}
```

调用方用 AbortController 管理启动取消、身份切换和宿主销毁。为身份刷新和凭证 fetch 也设置有界等待（见上例）；超时后忽略迟到的 runtime，不继续启动录音。正常停止先停止音频分片再调用 `stop()`；等待 finished 的阶段不要提前 cancel，否则可能丢失尾部结果。识别结束只回填输入框，未经业务明确要求不自动发送聊天。

## 麦克风与生命周期

- 浏览器需安全上下文、用户授权和实际可用的麦克风。iframe 由宿主允许 `microphone` 权限，Shadow DOM 使用宿主页权限。权限失败给出明确提示，不替换为浏览器厂商自带的另一套语音服务。
- 通过 `getUserMedia({audio:true})` 和 Web Audio 采集；必要时在用户手势内恢复 AudioContext。源采样率可能是 44.1/48kHz，必须重采样成 16000Hz、单声道、16位有符号小端 PCM，发送原始二进制分片，不带 WAV 头。不能把 MediaRecorder 默认输出的 WebM/Opus 直接发给接口。
- 音频权限和设备启动也须可取消、可超时；迟到的 MediaStream 必须停止 tracks。started 前不发送音频，结束后断开音频节点、停止全部 tracks、关闭 AudioContext 并清理计时器和 WebSocket。
- 控制单次音频长度不超过返回的 `maxSeconds`，检查 `ws.bufferedAmount` 限制积压；应用自行确定更短上限、静音停止及 UI 动画。结束、重试、切换会话、关闭容器和销毁都须释放资源，错误时保留草稿。

## 验收

交付前至少核对：

- 当前安装身份、audio scope、CRM组织归属与签名scene均正确；缺凭证/错误组织/旧服务/额度不足须明确失败，不自动改走会议场景。
- partial替换、final追加、尾部结果、手动停止、权限拒绝、启动取消、断线重试和宿主销毁，16kHz PCM及音频上限与积压控制。
- 桌面实际宿主中的麦克风权限与一次真实识别；模拟音频/ASR测试单列，不能替代真实识别质量验收。仅按用户需求增加移动端测试。

目标环境没有语音接口、签名场景或可用路由时，报告具体缺失并交接平台维护；不在普通 AI 应用开发中擅自修改或部署平台后端。
