#!/usr/bin/env python3
"""Base64 login and project-local multi-environment credentials."""
import argparse
import base64
import binascii
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
from urllib.parse import urlsplit

NAMES = ('AGENTCICI_BASE_URL', 'AGENTCICI_CLIENT_ID', 'AGENTCICI_CLIENT_SECRET')
CONFIG_NAME = 'cloudcc-agentcici.config.json'


def config_path():
    explicit = os.environ.get('AGENTCICI_CONFIG_PATH')
    if explicit:
        return Path(explicit).expanduser().resolve()
    current = Path.cwd()
    ancestry = (current, *current.parents)
    for directory in ancestry:
        if directory.parent.name == 'applications' and re.fullmatch(r'[a-z][a-z0-9-]{0,63}', directory.name):
            root = directory.parent.parent
            for child in ancestry:
                if child == root:
                    break
                if (child / CONFIG_NAME).exists() or (child / CONFIG_NAME).is_symlink():
                    raise RuntimeError('发现应用内旧登录配置，请先核对归并到项目根；独立身份须显式指定AGENTCICI_CONFIG_PATH')
            return root / CONFIG_NAME
    for directory in ancestry:
        path = directory / CONFIG_NAME
        if path.is_file():
            return path
    return current / CONFIG_NAME


def selected_env(root, env=None):
    name = env or os.environ.get('AGENTCICI_LOGIN_PROFILE') or root.get('use')
    if not name and not root:
        name = 'dev'
    if not isinstance(name, str) or name == 'use' or not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise RuntimeError('配置 use 或环境名称无效；仅允许字母、数字、下划线和连字符，不能使用 use')
    return name


def decode_login(encoded):
    try:
        text = base64.b64decode(''.join(encoded.split()), validate=True).decode('utf-8')
        tokens = shlex.split(text, comments=False, posix=True)
        values = {}
        if len(tokens) != 6:
            raise ValueError()
        for i in range(0, len(tokens), 2):
            name, separator, value = tokens[i + 1].partition('=')
            if tokens[i] != 'export' or not separator or name not in NAMES or name in values or not value or '\x00' in value:
                raise ValueError()
            values[name] = value
        return validate_values(values)
    except (ValueError, KeyError, UnicodeError, binascii.Error):
        raise RuntimeError('登录信息无效，请复制完整 Base64 信息；地址必须为 HTTPS 或本机开发地址') from None


def validate_values(values):
    try:
        url = urlsplit(values[NAMES[0]])
        if (not all(isinstance(values[key], str) and values[key].strip() and '\x00' not in values[key] for key in NAMES)
                or not url.hostname or url.username or url.password or url.query or url.fragment
                or url.path not in ('', '/') or (url.scheme != 'https' and not
                    (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1', '::1')))):
            raise ValueError()
        return {**values, NAMES[0]: values[NAMES[0]].rstrip('/')}
    except (ValueError, KeyError, TypeError):
        raise RuntimeError('登录信息无效，地址必须为 HTTPS 或本机开发地址，且三项凭据不能为空') from None


def read_config():
    try:
        root = json.loads(config_path().read_text(encoding='utf-8'))
        if not isinstance(root, dict) or (root and (not isinstance(root.get('use'), str) or not isinstance(root.get(root['use']), dict))):
            raise ValueError()
        return root
    except FileNotFoundError:
        return {}
    except (ValueError, OSError):
        raise RuntimeError('本地登录配置无法读取，请检查 cloudcc-agentcici.config.json') from None


def saved_identity(root, env):
    saved = root.get(env)
    if not isinstance(saved, dict) or not all(isinstance(saved.get(k), str) and saved[k].strip()
                                             for k in ('baseUrl', 'clientId', 'clientSecret')):
        raise RuntimeError('指定环境不存在或凭据不完整，请先 login --env 环境名')
    return validate_values(dict(zip(NAMES, (saved[field] for field in ('baseUrl', 'clientId', 'clientSecret')))))


def write_config(root):
    path = config_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ignore = path.parent / '.gitignore'
        existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
        rules = ['/' + path.name, '.cloudcc-agentcici-*.tmp']
        missing = [rule for rule in rules if rule not in existing.splitlines()]
        if missing:
            with ignore.open('a', encoding='utf-8') as stream:
                stream.write(('\n' if existing and not existing.endswith('\n') else '') + '\n'.join(missing) + '\n')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.cloudcc-agentcici-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(root, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    except OSError:
        raise RuntimeError('无法保存登录配置') from None
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def credentials():
    if any(os.environ.get(name) for name in NAMES):
        if not all(os.environ.get(name) for name in NAMES):
            raise RuntimeError('环境变量登录必须同时提供地址、Client ID 和 Client Secret；不与已保存身份混用')
        return {name: os.environ[name] for name in NAMES}
    root = read_config()
    if not root:
        raise RuntimeError('尚未登录，请运行 agentcici_auth.py login 并输入 Base64 登录信息')
    return saved_identity(root, selected_env(root))


def login(encoded, env=None):
    from agentcici_manage import Client
    values = decode_login(encoded)
    root = read_config()
    name = selected_env(root, env)
    try:
        Client(values).exchange()
    except Exception:
        raise RuntimeError('登录验证失败；请检查地址、凭据状态与网络，原登录配置保持不变') from None
    root[name] = dict(zip(('baseUrl', 'clientId', 'clientSecret'), (values[key] for key in NAMES)))
    root['use'] = name
    write_config(root)
    return {'status': 'logged_in', 'env': name, 'configPath': str(config_path()),
            'baseUrl': values[NAMES[0]], 'clientId': values[NAMES[1]]}


def local_command(command, env=None):
    root = read_config()
    name = selected_env(root, env)
    if not root:
        if command == 'use':
            raise RuntimeError('指定环境不存在，请先 login --env 环境名')
        return {'status': 'not_logged_in', 'env': name, 'configPath': str(config_path())}
    saved_identity(root, name)
    if command == 'logout':
        del root[name]
        if root['use'] == name:
            remaining = [key for key in root if key != 'use']
            if remaining:
                root['use'] = remaining[0]
            else:
                config_path().unlink()
                return {'status': 'not_logged_in', 'env': name, 'configPath': str(config_path())}
        write_config(root)
        return {'status': 'not_logged_in', 'env': name, 'configPath': str(config_path())}
    if command == 'use':
        root['use'] = name
        write_config(root)
    saved = root[name]
    return {'status': 'saved', 'env': name, 'configPath': str(config_path()),
            'baseUrl': saved['baseUrl'], 'clientId': saved['clientId']}


def main():
    parser = argparse.ArgumentParser(description='将解码后的开发者凭据保存到多环境项目配置')
    parser.add_argument('command', choices=['login', 'status', 'logout', 'use'])
    parser.add_argument('environment', nargs='?', help='use 命令的目标环境')
    parser.add_argument('--env', help='本次认证命令使用的环境')
    args = parser.parse_args()
    if args.environment and (args.command != 'use' or args.env):
        parser.error('只有 use 支持位置环境参数，且不能与 --env 同时使用')
    if args.command == 'use' and not (args.environment or args.env):
        parser.error('use 必须指定目标环境')
    try:
        env = args.env or args.environment
        if args.command == 'login':
            encoded = getpass.getpass('Base64 登录信息（输入不回显）：') if sys.stdin.isatty() else sys.stdin.read()
            result = login(encoded, env)
        else:
            result = local_command(args.command, env)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (RuntimeError, OSError) as error:
        print(str(error) if isinstance(error, RuntimeError) else '本地登录配置操作失败', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
