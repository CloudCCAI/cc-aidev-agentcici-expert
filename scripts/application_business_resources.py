"""AI 应用对象、字段、自定义类交付校验；契约对应平台安装器。"""
import json
import re

FIELDS = {
    'object': {'apiName', 'label', 'nameLabel', 'dataType', 'showFormat', 'beginIndex', 'remark', 'accessable', 'quickCreate', 'locationEnabled', 'reportable'},
    'field': {'apiName', 'objectApiName', 'label', 'fieldType', 'length', 'decimalPlaces', 'lookupObjectApiName', 'childrelationName', 'remark', 'maxFiles', 'imageInputMode', 'required', 'allowDuplicates', 'caseSensitive', 'defaultValue', 'helpText', 'placeholder', 'options', 'defaultFirstOption'},
    'class': {'apiName', 'label', 'source', 'remark'},
    'timer': {'apiName', 'label', 'source', 'remark'},
    'trigger': {'apiName', 'label', 'source', 'remark', 'targetObjectApiName', 'triggerTime'},
    'validationRule': {'apiName', 'objectApiName', 'label', 'formulaText', 'errorMessage', 'remark'},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def api(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', value)


def validate_resources(resources, files, installation):
    require(isinstance(resources, list), '业务资源声明必须为数组')
    steps = installation.get('steps', [])
    keys = {step['key'] for step in steps}
    require(len(keys) == len(steps), '安装步骤 key 重复')
    graph = {step['key']: step.get('dependsOn', []) for step in steps}
    expected, identities = set(), set()
    for resource in resources:
        require(isinstance(resource, dict), '业务资源必须为对象')
        require(set(resource) <= {'key', 'kind', 'file', 'apiName', 'label', 'remark', 'dependsOn', 'targetObjectApiName', 'triggerTime'}, '业务资源包含不支持的声明字段')
        key, kind, path = (resource.get(k, '') for k in ('key', 'kind', 'file'))
        require(isinstance(key, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', key) and key not in keys, '业务资源 key 非法或重复')
        require(kind in FIELDS, '不支持的业务资源类型')
        pattern = r'cloudcc/metadata/[A-Za-z0-9_/-]+\.json' if kind in ('object', 'field', 'validationRule') else r'cloudcc/backend/' + {'class': 'classes', 'trigger': 'triggers', 'timer': 'timers'}[kind] + r'/[A-Za-z0-9_/-]+\.java'
        require(isinstance(path, str) and re.fullmatch(pattern, path) and path in files and path not in expected, '业务资源文件路径无效或重复')
        if kind in ('class', 'trigger', 'timer'):
            payload = {k: resource[k] for k in ('apiName', 'label', 'remark', 'targetObjectApiName', 'triggerTime') if k in resource}
            payload['source'] = files[path].decode('utf-8')
            require(isinstance(payload.get('source'), str) and 0 < len(payload['source']) <= 200000, '类源码为空或过大')
            require(api(payload.get('apiName')) and (kind != 'class' or re.search(r'\bpublic\s+class\s+' + re.escape(payload['apiName']) + r'\b', payload['source'])), '类名称与源码不一致')
        else:
            payload = json.loads(files[path])
        require(isinstance(payload, dict) and set(payload) <= FIELDS[kind], '业务资源包含源组织ID、凭据或不支持的属性')
        require(api(payload.get('apiName')) and isinstance(payload.get('label'), str) and payload['label'].strip(), '业务资源缺少 API Name 或标签')
        identity = (kind, payload.get('objectApiName', ''), payload['apiName'])
        require(identity not in identities, '业务资源 API Name 重复')
        identities.add(identity)
        if kind in ('object', 'field'): validate_configuration(payload, kind)
        if kind == 'trigger':
            require(api(payload.get('targetObjectApiName')) and isinstance(payload.get('triggerTime'), str) and payload['triggerTime'].strip(), '触发器缺少对象或时机')
        if kind == 'validationRule':
            require(api(payload.get('objectApiName')) and all(isinstance(payload.get(k), str) and payload[k].strip() for k in ('formulaText', 'errorMessage')), '验证规则缺少公式或错误提示')
        if kind == 'object':
            require(payload.get('dataType', 'S') in ('S', 'V'), '对象名称字段类型无效')
        if kind == 'field':
            require(api(payload.get('objectApiName')), '字段缺少所属对象 API Name')
            field_type = payload.get('fieldType')
            require(field_type in {'S', 'N', 'P', 'c', 'L', 'Q', 'D', 'T', 'B', 'E', 'U', 'Y', 'M', 'F', 'X', 'J', 'A', 'H', 'IMG', 'FL'}, '安装器不支持该字段类型')
            numeric = field_type in ('N', 'P', 'c')
            long_text = field_type in ('J', 'A')
            default_length = 32000 if long_text else 4000 if field_type == 'X' else 18 if numeric else 80
            length, decimals = payload.get('length', default_length), payload.get('decimalPlaces', 0)
            require(type(length) is int and type(decimals) is int and 1 <= length <= (32000 if long_text else 4000) and 0 <= decimals <= 18 and (not numeric or length + decimals <= 18), '字段长度或精度无效')
            if 'maxFiles' in payload:
                require(field_type in ('IMG', 'FL') and type(payload['maxFiles']) is int and 1 <= payload['maxFiles'] <= 10, '上传数量必须为1至10的整数且仅适用于图片/文件')
            if 'imageInputMode' in payload:
                require(field_type == 'IMG' and payload['imageInputMode'] in ('input', 'url'), '图片录入方式无效')
            if field_type in ('Y', 'M'):
                require(api(payload.get('lookupObjectApiName')) and isinstance(payload.get('childrelationName'), str) and payload['childrelationName'].strip(), '关系字段缺少目标对象或反向关系名称')
        keys.add(key)
        graph[key] = resource.get('dependsOn', [])
        expected.add(path)
    for dependencies in graph.values():
        require(isinstance(dependencies, list) and all(isinstance(d, str) and d in keys for d in dependencies), '业务资源依赖不存在或格式无效')
    done = set()
    while len(done) < len(keys):
        ready = {key for key, dependencies in graph.items() if key not in done and set(dependencies) <= done}
        require(ready, '业务资源依赖存在循环')
        done |= ready
    return expected


def validate_configuration(p, kind):
    names = ('quickCreate', 'locationEnabled', 'reportable') if kind == 'object' else ('required', 'allowDuplicates', 'caseSensitive', 'defaultFirstOption')
    for name in names:
        require(name not in p or type(p[name]) is bool, '配置布尔值无效: ' + name)
    if kind == 'object':
        require('accessable' not in p or type(p['accessable']) is str and p['accessable'] in ('0', '1', '2'), '对象访问范围无效')
        return
    field_type = p.get('fieldType')
    require('allowDuplicates' not in p or field_type in ('S', 'N', 'E'), '字段不支持重复配置')
    require('caseSensitive' not in p or field_type == 'S' and p.get('allowDuplicates') is False, '大小写配置须用于禁止重复文本')
    for name in ('defaultValue', 'helpText', 'placeholder'):
        require(name not in p or type(p[name]) is str, '配置字符串无效: ' + name)
    require('placeholder' not in p or field_type == 'S', '占位文案仅用于文本字段')
    if field_type in ('L', 'Q'):
        options = p.get('options')
        require(isinstance(options, list) and options and all(type(v) is str and v.strip() and v == v.strip() and len(v.encode('utf-16-le')) // 2 <= 255 and '\n' not in v and '\r' not in v for v in options), '本地选项不能为空或含非法值')
        require(len(set(options)) == len(options), '本地选项重复')
    else:
        require('options' not in p and 'defaultFirstOption' not in p, '非选项字段不能配置选项')
    if 'defaultValue' in p:
        require(field_type in ('S', 'N', 'P', 'c', 'D', 'F', 'T', 'B', 'E', 'U', 'X', 'J', 'A', 'H'), '字段不支持默认值')
        if field_type == 'B': require(p['defaultValue'] in ('0', '1'), '复选框默认值须为0或1')
        if field_type in ('N', 'P', 'c') and p['defaultValue']:
            import decimal
            try:
                require(re.fullmatch(r'[-+]?[0-9]+(?:\.[0-9]+)?', p['defaultValue']) is not None, '数值默认值无效')
                value = decimal.Decimal(p['defaultValue'])
                require(value.is_finite(), '数值默认值无效')
            except decimal.InvalidOperation:
                raise ValueError('数值默认值无效') from None
