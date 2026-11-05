# AI应用持续语音通话

应用需要持续聆听、自动分轮、智能体回答播报、插话、静音与挂断时，优先复用平台通用SDK。仅“麦克风→文字草稿”仍读[实时语音输入](voice-input.md)，不因本指南把所有语音输入改为自动发送。

## 能力与前置条件

- 普通脚本：`/sdk/agentcici-voice@1.0.0.js`；无凭据的PC/移动自适应示例：`/sdk/examples/voice-call.html`。两者以目标平台服务的origin解析，不硬编码UAT/生产地址。加载前核对目标服务实际存在相同版本，不用SPA HTML的200冒充SDK成功。
- SDK组合已有`POST voice-sessions?scene=voice-asr`、凭证返回的`/ws/asr`、`POST chat-messages`、`POST voice-speech`。它是浏览器端编排，不是新的统一服务端双向语音Socket；Node/原生客户端可按协议自行接入。
- 使用应用已安装/获准的智能体运行Key，需`chat`和`audio`或`*`权限，智能体已发布并开放API；不要使用开发者管理Token、厂商密钥或另建智能体。普通应用沿用standard Key，官方CRM应用才沿用其既有cloudcc身份。
- `apiBase`必须是宿主返回的完整`/openapi/v1`地址；HTTP只拼接相对端点，WebSocket按返回根路径解析。SDK脚本属于静态资源，用`new URL('/sdk/...', runtime.apiBase)`定位，不把它追加到`/openapi/v1/sdk`。
- 浏览器需HTTPS/安全上下文、WebSocket、Web Audio、麦克风权限；iframe由宿主允许microphone。`start()`须在用户点击内直接调用，不在点击前先等待额外网络请求后才恢复音频。

## 身份刷新与脚本加载

运行身份只保存在内存。长期通用Key/管理凭据留在后端，客户端使用已授权的受限运行身份；不要写入URL、日志、localStorage或发布包。cloudcc身份须来自同一runtime的`cloudccContext.accessToken/baseUrl`，由SDK传CRM请求头并由平台校验组织，不借用管理员身份。

- Shadow DOM应用的`mount(container, context, bridge)`使用`getRuntime: () => bridge.refreshRuntime()`；此bridge方法返回刷新后的runtime Promise。
- iframe应用继续复用已有`AgentCiCiApp.createClient()`，先等`client.ready`。宿主client的`refresh()`只发送消息、不返回runtime；按[语音输入指南的refreshVoiceRuntime适配](voice-input.md#最小协议接入示例)，通过subscribe跳过初次旧值、等待下一次上下文，并设置超时与取消，不能写`await client.refresh()`当作身份。
- 显式localhost测试可返回未提交的本地runtime配置，不把它变成正式环境的身份兜底。

## 统一在线加载与运行时时间戳

语音SDK统一从目标平台在线加载，不下载后内联/合并进应用JS，不在发布包中携带SDK实现或设备语音回退副本。应用只保留加载器、界面和业务适配；SDK地址仍使用固定版本，当前为agentcici-voice@1.0.0.js。

每次实际创建script请求时，在加载当刻执行`url.searchParams.set('_t', String(Date.now()))`。不在构建时生成时间戳，不把Key/Token拼进URL；用URL处理已有查询参数和hash，不直接拼第二个问号。时间戳请求目标地址的最新响应，不能保证绕过自定义Service Worker/CDN策略，也不自动切换SDK版本或热替换正在通话的实例。

同一页面以不含时间戳的规范SDK URL（含origin和版本）缓存加载Promise，成功后复用；不同origin/版本不能共用缓存。为与其他应用共用，可采用`Symbol.for('agentcici.voice.sdk.loads')`作为页面共享Map。失败或超时清除对应Promise和script，允许用户显式重试；不能将失败Promise永久缓存，也不能无限自动重试。新页面/刷新页面会创建新请求和新时间戳，不要求每轮问答重新下载SDK。

应用聊天界面与注册不能等待语音脚本完成；在语音分支后台初始化。组件就绪前禁用语音启动按钮，失败提供明确重试，普通聊天保持可用。异步重试成功后提示用户再次点击，不能在网络回调中直接启动录音/播放而丢失移动端用户手势。SDK加载完成后仍检查宿主是否已销毁或signal已abort，迟到结果不能创建/启动已结束实例。

```js
function loadOnlineVoiceSdk(runtime) {
  const key = Symbol.for('agentcici.voice.sdk.loads');
  const loads = window[key] || (window[key] = new Map());
  const url = new URL('/sdk/agentcici-voice@1.0.0.js', runtime.apiBase);
  const source = url.href;
  if (loads.has(source)) return loads.get(source);
  const pending = new Promise((resolve, reject) => {
    const script = document.createElement('script'); let settled = false;
    function finish(error) {
      if (settled) return;
      settled = true; clearTimeout(timer); script.onload = script.onerror = null; script.remove();
      if (error) reject(error); else resolve(window.AgentCiCiVoice);
    }
    const timer = setTimeout(() => finish(new Error('语音SDK加载超时')), 10000);
    script.onload = () => finish(window.AgentCiCiVoice?.version === '1.0.0'
      && typeof window.AgentCiCiVoice.createClient === 'function'
      ? null : new Error('语音SDK内容或版本不正确'));
    script.onerror = () => finish(new Error('语音SDK加载失败'));
    url.searchParams.set('_t', String(Date.now())); // 每次新请求在此生成，不在构建时写死
    script.src = url.href; // 普通script，不设置type=module
    document.head.append(script);
  });
  loads.set(source, pending);
  pending.catch(() => { if (loads.get(source) === pending) loads.delete(source); });
  return pending;
}

// 语音分支的后台初始化；不要用它阻塞应用mount或普通聊天。
const initial = await getRuntime();
const sdk = await loadOnlineVoiceSdk(initial);
lifecycle.signal.throwIfAborted(); // 宿主销毁后不创建迟到实例
const voiceClient = sdk.createClient({
  getRuntime,
  user: runtime => runtime.user || runtime.currentUser?.userId,
  signal: lifecycle.signal
});
const call = voiceClient.createVoiceCall({
  onTranscript: row => updateTranscriptById(row),
  onStateChange: state => showState(state),
  onLevel: level => drawWaveform(level),
  onError: error => showError(error.message),
  onDraft: text => preserveDraft(text)
});
// 初始化成功后启用按钮；由之后的用户点击直接触发start。
startButton.onclick = () => call.start().catch(error => showError(error.message));
muteButton.onclick = () => call.setMuted(true);
unmuteButton.onclick = () => call.setMuted(false);
hangupButton.onclick = () => call.hangup().catch(error => showError(error.message));
// 宿主销毁：lifecycle.abort(); call.destroy();
```

给后台初始化捕获异常并显示语音分支的加载状态、失败和重试，不使整个聊天应用失败。loader超时后，即使迟到脚本仍在浏览器执行，也不能自动开始媒体。多个应用共用加载结果，但各自维护通话实例与销毁状态，不能删除公共SDK全局变量来强制更新其他应用正在使用的实例。

`user`是调用方已有的稳定终端用户ID，也可直接传字符串；不能用每轮随机ID或伪造CRM用户来绕过隔离。`getRuntime`每次返回`apiBase/apiKey`及可选`keyType/cloudccContext/user/currentUser/agentId/companyId`；SDK在每个受保护请求前刷新，身份变化须结束当前通话、重新建立，单纯Key续期不等于换用户。标准Key不用传CRM请求头。

## 方法与事件

| 接口 | 语义 |
|---|---|
| `await call.start()` | 用户手势下启动；已启动不重复录音，启动失败抛错并触发onError；错误后先挂断再重试 |
| `call.setMuted(boolean)` | 只静音麦克风；恢复后继续聆听，不用它代替挂断或中止播报 |
| `await call.hangup()` | 立即停止本地录音/播报，等待当前任务停止确认；失败处理Promise，不吞掉错误 |
| `call.destroy()` | 释放媒体、事件监听等资源；销毁实例不能再启动 |
| `active/state/conversationId` | 只读当前通话、状态及会话；同实例多轮复用同一会话 |

`onTranscript`收到`{id, role, text, partial?, removed?, speaking?, interrupted?, done?}`。以`id`创建/替换同一条记录，`removed=true`删除临时条目，不能把每次partial或快照追加成新发言；`role`为user/assistant，使用textContent渲染。`done`表示回答完成，`speaking`表示播报中，不能把partial或断流当成完成。

`onStateChange`为`idle/starting/listening/thinking/speaking/muted/error`字符串，`onLevel`为0–1数值，`onError`为Error，`onDraft`返回未发送文字。界面可保留双方文字、音量波形和静音/挂断按钮；人物形象和动画属于应用，不加入SDK。

SDK不读取CRM页面；默认cloudcc聊天设置readPageInfo=false。确需业务页面上下文时，`createClient`显式提供`getContext(runtime)`返回`{readPageInfo, pageContext}`，仍受运行Key的maxPromptChars限制。应控制字段与长文本总量，不能通过通话绕过页面开关、权限或长度限制。

已有聊天框需要保留自己的文件、历史和SSE流程时，可提供`createVoiceCall({transport,...callbacks})`：transport实现`busy()`、`send(text, updateAnswer)`、`cancel()`；send覆盖整个请求生命周期，按顺序调用updateAnswer(累计文字, 是否完成)，失败必须reject；cancel须等待平台停止确认并在失败时reject。`call.updateAnswer(text, done)`和`call.fail(error)`只用于现有流程桥接，不要求普通SDK调用方使用。不要同时启用默认传输和另一套chat-messages自动发送。

## 自动分轮、插话与停止

SDK在一个ASR连接内按识别结果与音频停顿分轮，静默不发送；到250秒或平台更短上限时续接。保持partial/final的区别，不能把每个final当作独立问题。

回答期间插话结合持续声音和有效文字，匹配播报原文的回声会忽略。音频持续时长必须依据真实样本数/采样率，不能假定4096样本一定约85ms：16kHz时是256ms；设备帧长差异不能导致插话判定永久重置。SDK保留320ms确认及噪声/回声过滤，实际阈值效果和外放回声仍需目标设备验收，不宣称完整声纹识别。

确认插话先停止本机播报、使旧PCM失效，再停止旧任务，最后发送新问题；task_id尚未返回时等待事件，不猜测ID。停止失败暂停通话，不并发发送覆盖旧会话。SSE必须收到成功message_end，断流/错误不能按完成处理。挂断、后台、退出、身份变化和宿主abort停止媒体；迟到的麦克风授权或上游结果不能重启已结束通话。停止请求不能撤销已经执行的业务写操作。

## 语音合成接口

```http
POST {apiBase}/voice-speech
Authorization: Bearer {runtime.apiKey}
Content-Type: application/json

{"text":"你好，很高兴和你通话。"}
```

- 每段1–500个Unicode字符，需audio权限；cloudcc另带前述两个CRM身份请求头。
- 返回no-store的audio/pcm：24000Hz、单声道、16位有符号小端，X-Audio-Sample-Rate为24000；无WAV头。逐片播放须处理16位样本跨网络分片的奇数字节，不能把原始PCM直接当MP3交给audio标签。
- 模型与统一音色由平台voice-tts场景配置，不在前端传厂商Key或任意音色。SDK按句分段、顺序播放、限制积压，错误时不擅自降级到设备自带语音。
- 400 voice_text_invalid为文本错误；401为运行/CRM身份问题；403 agent_api_scope_denied为权限不足；503 voice_synthesis_unavailable为平台路由/音色尚未就绪；限流、订阅/资源拒绝及音频中断按实际message处理。
- ASR、聊天/模型与语音合成用量分别记录。合成按上游已生成PCM计量，后来被打断的已生成音频仍可能计入；具体资源规则以目标平台实时文档为准，不在应用或技能复制固定单价。

## 交付验收

先检查应用发布JS不含SDK实现、SDK网络请求来自runtime平台origin且带当次时间戳，同页去重、失败/超时重试、正常聊天不阻塞和销毁后迟到加载保护；再测试SDK不加载应用人物/界面也能两轮问答并验应用适配：稳定user与conversationId、识别替换、回答顺序、短促噪声不打断、真实插话、16k/44.1k/48k源采样率、静音恢复、停止失败、启动取消、身份更新、后台和销毁资源释放。复用平台服务前读真实返回与版本，不仅检查SDK全局变量存在。

模拟ASR/PCM回归、注入合成测试语音的真实平台联调和人类麦克风实机分别记录；PC/移动端外放、权限和回声由实际目标设备验证，不能用模拟视口代替。目标环境缺少SDK/ASR/合成路由时报告具体缺失，不在普通应用开发任务中擅自部署平台；部署须在用户授权的范围内。
