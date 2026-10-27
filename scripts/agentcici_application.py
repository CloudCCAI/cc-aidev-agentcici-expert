#!/usr/bin/env python3
"""Build and validate application request archives; never execute archived code."""
import argparse
import hashlib
import io
from application_manifest import compile_manifest, missing
import json
import pathlib
import re
import stat
import sys
import zipfile
import urllib.request
from urllib.parse import urlsplit
import urllib.error
import uuid
from agentcici_manage import Client, NoCredentialRedirect

LIMIT = 100 * 1024 * 1024
FORMAT = 'agentcici-application-request'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_zip(data):
    require(len(data) <= LIMIT, 'ZIP 超过 100 MiB')
    result = {}
    names = set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        require(len(entries) <= 10000, 'ZIP 条目过多')
        require(sum(i.file_size for i in entries) <= LIMIT, 'ZIP 解压大小超过 100 MiB')
        for item in entries:
            name = item.filename
            path = pathlib.PurePosixPath(name)
            require(not name.startswith('/') and '\\' not in name and ':' not in name
                    and '..' not in path.parts and name not in names, 'ZIP 路径非法或重复')
            names.add(name)
            require(not stat.S_ISLNK(item.external_attr >> 16), '不支持符号链接')
            if not item.is_dir():
                result[name] = archive.read(item)
    return result


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode()


def refs(items):
    require(isinstance(items, list), '资源必须为数组')
    result = {}
    for item in items:
        ref = item.get('ref', '')
        require(re.fullmatch(r'[a-z][a-z0-9-]{0,63}', ref), '资源 ref 非法')
        require(ref not in result, '资源 ref 重复')
        result[ref] = item
    return result


def validate(files):
    manifest = json.loads(files['application.json'])
    if manifest.get('formatVersion') == 2:
        from application_business_resources import validate_resources
        installation = manifest.get('installationManifest', {})
        require(installation.get('schemaVersion') == 2, '业务资源安装清单需要schemaVersion=2')
        require(set(manifest.get('sha256', {})) == set(files) - {'application.json'}
                and all(digest(files[k]) == v for k, v in manifest['sha256'].items()), '文件摘要不匹配')
        paths = validate_resources(manifest.get('cloudccResources'), files, installation)
        baseline = json.loads(json.dumps(manifest))
        baseline['formatVersion'] = baseline['installationManifest']['schemaVersion'] = 1
        baseline.pop('cloudccResources')
        remaining = {name: value for name, value in files.items() if name not in paths}
        baseline['sha256'] = {name: digest(value) for name, value in remaining.items() if name != 'application.json'}
        remaining['application.json'] = encode(baseline)
        validate(remaining)
        return manifest
    require(manifest.get('format') == FORMAT and manifest.get('formatVersion') == 1, '应用包格式不支持')
    require(re.fullmatch(r'[a-z][a-z0-9-]{1,63}', manifest.get('appCode', '')), '应用代码非法')
    require(re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', manifest.get('version', '')), '版本非法')
    require(isinstance(manifest.get('name'), str) and bool(manifest['name'].strip()), '缺少应用名称')
    if 'installationManifest' in manifest:
        installation = manifest['installationManifest']
        require(isinstance(installation, dict) and installation.get('schemaVersion') == 1 and isinstance(installation.get('steps'), list) and 1 <= len(installation['steps']) <= 30, '安装清单需要 schemaVersion=1 和 1 至 30 个步骤')
        render = installation.get('renderConfig')
        require(isinstance(render, dict) and render.get('renderer') in ['iframe', 'shadow-dom'], '渲染方式无效')
        positions = render.get('positions', [])
        require(isinstance(positions, list) and 1 <= len(positions) <= 7 and all(isinstance(p, str) and p in ['float', 'right', 'fullscreen', 'detail-right', 'list-right', 'dialog', 'home'] for p in positions) and len(set(positions)) == len(positions), '展示位置无效或重复')
        from urllib.parse import urlsplit
        entry = render.get('entryUrl', '')
        require(isinstance(entry, str), '加载地址必须是字符串')
        if entry.strip():
            url = urlsplit(entry.strip())
            require(url.scheme in ['http', 'https'] and url.hostname and not url.username and not url.password, '加载地址必须为 HTTP(S)')
        else:
            require(render['renderer'] == 'iframe' or render.get('entryPath'), 'Shadow DOM 必须提供 JS 地址或包内入口')
        require(render.get('closeBehavior') in ['hide', 'confirm-destroy'], '关闭方式无效')
        require(render.get('hostLayer') in ['content', 'assistant'], '宿主层级无效')
        authentication = render.get('authentication')
        if authentication is not None:
            require(isinstance(authentication, dict), '宿主认证配置无效')
            query = authentication.get('query')
            require(authentication.get('type') == 'cloudcc-sso-ticket'
                    and isinstance(query, dict) and 1 <= len(query) <= 8
                    and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', key) and isinstance(value, str) and len(value) <= 256 for key, value in query.items())
                    and isinstance(authentication.get('targetPath'), str) and authentication['targetPath'].startswith('/') and not authentication['targetPath'].startswith('//')
                    and re.fullmatch(r'[a-z][a-z0-9_]{1,31}', authentication.get('ticketPrefix', ''))
                    and (not authentication.get('localeParam') or re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', authentication['localeParam'])), '宿主认证配置无效')
        servers = installation.get('mcpServers', [])
        tools = installation.get('tools', [])
        require(isinstance(servers, list) and len(servers) <= 30 and isinstance(tools, list) and len(tools) <= 100, 'MCP或工具声明无效')
        mcp_refs, names, tool_refs = set(), set(), set()
        for server in servers:
            require(isinstance(server, dict) and set(server) == {'ref', 'name', 'description', 'transportType', 'url'}, 'MCP发布声明不能包含凭据或额外字段')
            url = urlsplit(server['url'])
            require(re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', server['ref'])
                    and server['ref'] not in mcp_refs and isinstance(server['name'], str) and server['name'].strip()
                    and server['name'] not in names and len(server['name']) <= 120
                    and isinstance(server['description'], str) and len(server['description']) <= 2000
                    and server['transportType'] == 'streamableHttp' and url.scheme == 'https'
                    and url.hostname and not url.username and not url.password and not url.fragment
                    and not url.query and len(server['url']) <= 512, 'MCP发布声明无效或地址携带凭据')
            mcp_refs.add(server['ref']); names.add(server['name'])
        for tool in tools:
            require(isinstance(tool, dict) and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', tool.get('ref', ''))
                    and tool['ref'] not in tool_refs and isinstance(tool.get('name'), str)
                    and 0 < len(tool['name'].strip()) <= 160, '工具名称或ref无效')
            expected = {'ref', 'name', 'source', 'mcpRef'} if tool.get('source') == 'mcp' else {'ref', 'name', 'source'}
            require(set(tool) == expected and (tool.get('source') == 'builtin'
                    or tool.get('source') == 'mcp' and tool.get('mcpRef') in mcp_refs), '工具来源或MCP关联无效')
            tool_refs.add(tool['ref'])
        agent_runtime = installation.get('agentRuntime')
        if agent_runtime is not None:
            require(isinstance(agent_runtime, dict)
                    and re.fullmatch(r'[a-z][a-z0-9-]{0,63}', agent_runtime.get('agentId', ''))
                    and agent_runtime.get('keyType') in ['cloudcc', 'standard'], '智能体运行配置无效')
    checksums = manifest['sha256']
    require(set(checksums) == set(files) - {'application.json'}, '文件清单不匹配')
    require(all(digest(files[k]) == v for k, v in checksums.items()), '文件摘要不匹配')
    require(manifest['web'] == {'file': 'site.zip', 'entry': 'index.html'}, '站点入口非法')
    site = read_zip(files['site.zip'])
    require('index.html' in site, '站点缺少根层 index.html')
    for name in site:
        path = pathlib.PurePosixPath(name)
        require(not any(p.startswith('.') or p == 'node_modules' for p in path.parts)
                and path.suffix not in {'.map', '.pem', '.key'}
                and path.name not in {'cloudcc-agentcici.config.json', 'cloudcc-cli.config.json'}, '站点包含禁止发布的文件')
    skills = refs(manifest['skills'])
    agents = refs(manifest['agents'])
    knowledge = refs(manifest.get('knowledgeBases', []))
    require(len(agents) + int('platformAgent' in manifest) <= 1, '应用包只能包含一个智能体')
    if 'platformAgent' in manifest:
        require(re.fullmatch(r'[a-z][a-z0-9-]{0,63}', manifest['platformAgent'].get('ref', '')), '平台智能体引用无效')
        require(not skills and not knowledge, '平台智能体复用已有组织依赖')
        require(manifest.get('installationManifest', {}).get('agentRuntime', {}).get('agentId') == manifest['platformAgent']['ref'], '平台智能体运行引用不一致')
    elif agents and 'agentRuntime' in manifest.get('installationManifest', {}):
        require(manifest.get('installationManifest', {}).get('agentRuntime', {}).get('agentId') == next(iter(agents)), '自定义智能体运行引用不一致')
    render = manifest.get('installationManifest', {}).get('renderConfig', {})
    if 'entryPath' in render:
        require(re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*(?:\.[A-Za-z0-9_-]+)+', render['entryPath']) and render['entryPath'] in site, '包内入口不存在或路径无效')
        require(not render.get('entryUrl'), '包内入口与外部地址不能同时配置')
    expected = {'application.json', 'site.zip'}
    if 'cloudcc/menu.json' in files: expected.add('cloudcc/menu.json')
    else: require(bool(manifest.get('installationManifest', {}).get('steps')), '需要安装入口')
    for ref, skill in skills.items():
        require(skill['file'] == f'skills/{ref}.zip', '技能文件路径非法')
        expected.add(skill['file'])
        package = read_zip(files[skill['file']])
        sm = json.loads(package['manifest.json'])
        require(sm.get('format') == 'universal-skill-package' and sm.get('formatVersion') == '1.0'
                and 'SKILL.md' in package, '技能需为平台标准导出包')
    for ref, agent in agents.items():
        require(agent['file'] == f'agents/{ref}.ciciagent', '智能体文件路径非法')
        expected.add(agent['file'])
        require(len(files[agent['file']]) <= 5 * 1024 * 1024, '智能体包超过 5 MiB')
        package = read_zip(files[agent['file']])
        require(set(package) == {'manifest.json', 'agent.json'}, '智能体包文件不匹配')
        am = json.loads(package['manifest.json'])
        require(am.get('format') == 'agentcici-agent-package' and am.get('formatVersion') == 1
                and am.get('snapshot') == 'SAVED_DRAFT', '智能体需为原生导出包')
        require(am.get('sha256') == digest(package['agent.json']), '智能体包摘要错误')
        payload = json.loads(package['agent.json'])
        tool_targets = {item['ref']: item for item in manifest.get('installationManifest', {}).get('tools', [])}
        custom_skills = [d for d in payload.get('skills', []) if d.get('kind', 'CUSTOM') == 'CUSTOM']
        managed_skills = [d for d in payload.get('skills', []) if d.get('kind') == 'MANAGED']
        require(set(agent.get('skillBindings', {})) == {d['ref'] for d in custom_skills}, '自定义技能未完整映射')
        require(all(v in skills for v in agent.get('skillBindings', {}).values()), '自定义技能目标不存在')
        require(set(agent.get('managedSkillBindings', {})) == {d['ref'] for d in managed_skills}, '受管技能未完整映射')
        require(all(agent['managedSkillBindings'][d['ref']] == d['sourceCode'] for d in managed_skills), '受管技能代码不匹配')
        for field, dependencies, targets in [('knowledgeBindings', 'knowledge', knowledge), ('toolBindings', 'tools', tool_targets)]:
            bindings = agent.get(field, {})
            require(set(bindings) == {d['ref'] for d in payload.get(dependencies, [])}, f'{field} 未完整映射')
            require(all(v in targets for v in bindings.values()), f'{field} 目标不存在')
            if field == 'toolBindings':
                require(all(tool_targets[bindings[d['ref']]]['name'] == d['name'] for d in payload.get('tools', [])), '工具名称与依赖不一致')
    require(set(files) == expected, '包含未声明文件')
    if 'cloudcc/menu.json' in files:
        menu = json.loads(files['cloudcc/menu.json'])
        require(menu.get('type') == 'script' and menu.get('tabName') and menu.get('pname'), '需要脚本菜单')
        require('__AGENTCICI_SITE_URL__' in menu.get('functioncode', ''), '菜单缺少安装时站点地址占位符')
    return manifest


def package(source, output):
    source = pathlib.Path(source).resolve()
    config = json.loads(source.read_text())
    root = source.parent
    if config.get("schemaVersion") == 2:
        config = compile_manifest(config, root)
    def local(name):
        candidate = root / name
        require(not candidate.is_symlink(), '不支持符号链接')
        resolved = candidate.resolve()
        require(resolved.is_relative_to(root), '输入路径必须位于项目目录内')
        return resolved
    directory = local(config['web']['directory'])
    require(directory.is_dir(), '构建目录不存在')
    site = {}
    size = 0
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), '构建目录不能包含符号链接')
        if path.is_file():
            relative = path.relative_to(directory)
            require(not any(p.startswith('.') or p == 'node_modules' for p in relative.parts)
                    and path.suffix not in {'.map', '.pem', '.key'}
                    and path.name not in {'cloudcc-agentcici.config.json', 'cloudcc-cli.config.json'}, '构建目录包含禁止发布的文件')
            size += path.stat().st_size
            require(size <= LIMIT, '站点产物超过 100 MiB')
            site[relative.as_posix()] = path.read_bytes()
    files = {'site.zip': zip_bytes(site)}
    manifest = {k: config[k] for k in ['appCode', 'name', 'version']}
    manifest.update(format=FORMAT, formatVersion=1, summary=config.get('summary', ''),
                    web={'file': 'site.zip', 'entry': 'index.html'}, knowledgeBases=config.get('knowledgeBases', []))
    if 'appType' in config: manifest['appType'] = config['appType']
    if 'platformAgent' in config: manifest['platformAgent'] = config['platformAgent']
    if 'installationManifest' in config:
        manifest['installationManifest'] = config['installationManifest']
    for kind, extension in [('agents', 'ciciagent'), ('skills', 'zip')]:
        manifest[kind] = []
        for ref, item in refs(config.get(kind, [])).items():
            path = local(item['file'])
            require(path.stat().st_size <= LIMIT, '资源包过大')
            name = f'{kind}/{ref}.{extension}'
            files[name] = path.read_bytes()
            entry = {'ref': ref, 'file': name}
            if kind == 'agents':
                entry.update(skillBindings=item.get('skillBindings', {}), managedSkillBindings=item.get('managedSkillBindings', {}), knowledgeBindings=item.get('knowledgeBindings', {}), toolBindings=item.get('toolBindings', {}))
            manifest[kind].append(entry)
    if 'menu' in config:
        menu = config['menu']
        require(menu.get('type') == 'script', '菜单必须为 script')
        script = menu.get('functioncode')
        if not script:
            sdk_url = menu.get('sdkUrl', '')
            require(isinstance(sdk_url, str) and sdk_url, '旧menu清单需要显式sdkUrl或functioncode；新应用请使用schemaVersion=2')
            url = urlsplit(sdk_url)
            require((url.scheme == 'https' or url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1', '::1'))
                    and url.hostname and not url.username and not url.password and not url.query and not url.fragment, 'SDK地址必须是明确的无凭据HTTPS或本机HTTP地址')
            script = (pathlib.Path(__file__).resolve().parent.parent / 'assets/application-menu.js').read_text(encoding='utf-8').replace('__APP_CODE__', json.dumps(config['appCode'])).replace('__SDK_URL__', json.dumps(sdk_url))
        files['cloudcc/menu.json'] = encode({'tabName': menu['tabName'], 'pname': menu['pname'], 'type': 'script', 'functioncode': script})
    manifest['sha256'] = {name: digest(data) for name, data in files.items()}
    if config.get('cloudccResources') or config.get('formatVersion') == 2:
        manifest['formatVersion'] = 2
        manifest['cloudccResources'] = config.get('cloudccResources', [])
        require('installationManifest' in manifest, '业务资源需要安装清单')
        manifest['installationManifest']['schemaVersion'] = 2
        for resource in manifest['cloudccResources']:
            path = local(resource['file'])
            require(path.is_file() and path.stat().st_size <= LIMIT, '业务资源文件不存在或过大')
            require(resource['file'] not in files, '业务资源文件重复')
            files[resource['file']] = path.read_bytes()
        manifest['sha256'] = {name: digest(value) for name, value in files.items()}
    files['application.json'] = encode(manifest)
    validate(files)
    data = zip_bytes(files)
    read_zip(data)
    output = pathlib.Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(data)
    return {'status': 'prepared', 'path': str(output.resolve()), 'sha256': digest(data)}


def main():
    parser = argparse.ArgumentParser(description='AI 应用发布申请包：准备、校验、提交与查询')
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('package')
    build.add_argument('--manifest', required=True)
    build.add_argument('--output', required=True)
    release = commands.add_parser('release', help='打包、上传、创建草稿并发布为本组织可安装版本')
    release.add_argument('--manifest', required=True)
    release.add_argument('--output', required=True)
    commands.add_parser('list', help='列出本组织开发的应用')
    owned = commands.add_parser('get', help='查询本组织应用和版本状态')
    owned.add_argument('app_code')
    publish = commands.add_parser('publish', help='发布已上传的本组织版本')
    publish.add_argument('app_code')
    publish.add_argument('--version', required=True)
    deletion = commands.add_parser('delete', help='删除本组织应用及全部版本包，有安装或市场引用时拒绝')
    deletion.add_argument('app_code')
    deletion.add_argument('--confirm-id', required=True)
    preflight = commands.add_parser('check', help='列出源清单缺失必填项，供发布前问答')
    preflight.add_argument('--manifest', required=True)
    submit = commands.add_parser('submit', help='提交待审核申请，不直接发布')
    submit.add_argument('file')
    draft = commands.add_parser('draft', help='从本组织上传申请创建市场草稿，不上架')
    draft.add_argument('request_id')
    status = commands.add_parser('status')
    status.add_argument('request_id')
    check = commands.add_parser('validate')
    check.add_argument('file')
    args = parser.parse_args()
    try:
        if args.command in ('list', 'get', 'publish', 'delete'):
            if args.command == 'list':
                result = Client().request('GET', '/openapi/v1/management/ai-applications/owned')
            else:
                require(re.fullmatch(r'[a-z][a-z0-9-]{1,63}', args.app_code), '应用代码非法')
                path = '/openapi/v1/management/ai-applications/' + args.app_code
                if args.command == 'delete':
                    require(args.confirm_id == args.app_code, '--confirm-id必须与应用代码相同')
                    result = Client().request('DELETE', path)
                elif args.command == 'get':
                    result = Client().request('GET', path)
                else:
                    require(re.fullmatch(r'[0-9]\.[0-9]\.[0-9]', args.version), '版本非法')
                    result = Client().request('POST', path + '/versions/' + args.version + '/publish', {})
        elif args.command == 'check':
            source = pathlib.Path(args.manifest).resolve()
            config = json.loads(source.read_text())
            absent = missing(config)
            result = {'status': 'incomplete' if absent else 'complete', 'missing': absent}
            if not absent: compile_manifest(config, source.parent)
        elif args.command == 'draft':
            uuid.UUID(args.request_id)
            result = Client().request('POST', '/openapi/v1/management/application-requests/' + args.request_id + '/draft', {})
        elif args.command == 'status':
            uuid.UUID(args.request_id)
            result = Client().request('GET', '/openapi/v1/management/application-requests/' + args.request_id)
        elif args.command == 'package':
            result = package(args.manifest, args.output)
        else:
            if args.command == 'release':
                package(args.manifest, args.output)
            path = pathlib.Path(args.output if args.command == 'release' else args.file)
            require(path.stat().st_size <= LIMIT, '包过大')
            data = path.read_bytes()
            manifest = validate(read_zip(data))
            result = {'status': 'valid', 'appCode': manifest['appCode'], 'sha256': digest(data)}
            if args.command in ('submit', 'release'):
                client = Client()
                boundary = 'cici-' + uuid.uuid4().hex
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="application.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode()
                        + data + f'\r\n--{boundary}--\r\n'.encode())
                request = urllib.request.Request(client.base_url + '/openapi/v1/management/application-requests',
                    data=body, method='POST', headers={'Authorization': 'Bearer ' + client.exchange(),
                    'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Accept': 'application/json'})
                try:
                    with urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=120) as response:
                        envelope = json.load(response)
                except urllib.error.HTTPError as error:
                    raise RuntimeError(f'申请提交返回 HTTP {error.code}；核对服务端版本与 application.submit 权限') from None
                except (urllib.error.URLError, TimeoutError):
                    raise RuntimeError('申请提交结果未知；可重交同一原包，服务端按 org + SHA-256 去重') from None
                require(envelope.get('success'), '申请接收失败')
                result = envelope['data']
                request_id = result['id']
                try:
                    result['draft'] = client.request('POST', '/openapi/v1/management/application-requests/' + request_id + '/draft', {})
                except (RuntimeError, OSError) as error:
                    raise RuntimeError(f'上传已成功，申请 ID={request_id}；草稿未确认创建：{error}。可用 draft {request_id} 重试') from None
                if args.command == 'release':
                    try:
                        result['publication'] = client.request('POST', '/openapi/v1/management/ai-applications/'
                            + manifest['appCode'] + '/versions/' + manifest['version'] + '/publish', {})
                    except (RuntimeError, OSError):
                        raise RuntimeError('上传及草稿创建已成功，组织发布未确认；请先 get ' + manifest['appCode']
                            + ' 核实版本状态，再使用 publish 重试，不重新打包覆盖同版本') from None
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, zipfile.BadZipFile, RuntimeError) as error:
        print(f'申请包处理失败：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
