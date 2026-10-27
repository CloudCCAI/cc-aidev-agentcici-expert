#!/usr/bin/env python3
"""在应用 cloudcc 工程内调用 CLI，临时链接根目录共享配置与缓存。"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


@contextmanager
def project_lock(config):
    # 独立锁避免Windows字节锁阻止CLI读取配置；锁内不保存任何凭据。
    lock = Path(tempfile.gettempdir()) / ('agentcici-cloudcc-' + sha256(str(config).encode()).hexdigest() + '.lock')
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(descriptor, 'r+b') as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('共用CRM配置正在使用或无法加锁，请稍后重试') from error
        yield


def remove_link(path, target):
    if path.is_symlink() and path.resolve() == target:
        path.unlink()
    elif path.exists() or path.is_symlink():
        raise RuntimeError('临时配置链接被替换，已保留现场，请核对应用cloudcc目录')


@contextmanager
def shared_config(root, project):
    config = root / 'cloudcc-cli.config.json'
    cache = root / '.cloudcc-cache.json'
    config_link = project / config.name
    cache_link = project / cache.name
    with project_lock(config):
        for path in (config_link, cache_link):
            if path.exists() or path.is_symlink():
                raise RuntimeError('应用cloudcc内已有配置或缓存，请先核对归并；不覆盖现有文件或链接')
        if cache.is_symlink() or (cache.exists() and not cache.is_file()):
            raise RuntimeError('根目录CRM缓存必须是普通文件或尚未生成')
        config_linked = cache_linked = False
        try:
            config_link.symlink_to(config)
            config_linked = True
            # 缓存缺失时链接允许暂时悬空，由CLI首次写入根路径。
            cache_link.symlink_to(cache)
            cache_linked = True
            yield
        finally:
            try:
                if cache_linked:
                    if cache_link.is_symlink():
                        remove_link(cache_link, cache)
                    elif cache_link.is_file():
                        # CLI失效处理可能先删除链接、再生成新缓存；移动回唯一源。
                        cache_link.replace(cache)
                        cache.chmod(0o600)
                    elif not cache_link.exists():
                        # CLI明确删除而没有重建缓存，不保留根目录旧Token。
                        cache.unlink(missing_ok=True)
                    else:
                        raise RuntimeError('CLI缓存路径异常，已保留现场，请核对应用cloudcc目录')
                    if cache.is_file():
                        cache.chmod(0o600)
            finally:
                if config_linked:
                    remove_link(config_link, config)


def run_class(cli, root, app_code, action, name, format_flag=None):
    root = Path(root).expanduser().resolve()
    cli = Path(cli).expanduser().resolve()
    if not cli.is_file():
        raise RuntimeError('请指定已安装CloudCC技能的tools/bin/cloudcc绝对路径')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', app_code) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', name):
        raise RuntimeError('应用标识或类名无效')
    app = root / 'applications' / app_code
    if not app.is_dir() or app.is_symlink() or not app.resolve().is_relative_to(root / 'applications'):
        raise RuntimeError('应用目录不存在或位于项目范围外')
    config = root / 'cloudcc-cli.config.json'
    if config.is_symlink() or not config.is_file():
        raise RuntimeError('请先在项目根目录配置普通文件cloudcc-cli.config.json')
    if action not in ('create', 'format', 'validate', 'publish'):
        raise RuntimeError('不支持的类操作')
    if format_flag not in (None, '--write', '--check') or (format_flag and action != 'format'):
        raise RuntimeError('格式参数仅用于format操作')
    project = app / 'cloudcc'
    source = project / 'backend' / 'classes' / name
    for path in (project, project / 'backend', source.parent, source):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise RuntimeError('CloudCC资源目录必须位于应用cloudcc内且不能使用目录链接')
    if action == 'create':
        if source.exists():
            raise RuntimeError('类目录已存在，不覆盖现有源码')
        if (app / 'backend' / 'classes' / name).exists():
            raise RuntimeError('发现旧布局backend/classes，请先核对已有类；不会重复创建或自动搬迁')
        project.mkdir(exist_ok=True)
    elif not source.is_dir():
        raise RuntimeError('应用cloudcc/backend/classes内类目录不存在；旧布局需显式确认迁移，不自动搬迁')
    else:
        java_file = source / (name + '.java')
        if java_file.is_symlink() or not java_file.is_file() or (source / 'config.json').is_symlink():
            raise RuntimeError('应用内缺少类源码或类文件使用了不受支持的链接')
    with shared_config(root, project):
        command = [str(cli), action, 'classes', name]
        if action != 'create':
            command.append(str(project))
        if action == 'format':
            command.append(format_flag or '--check')
        return subprocess.run(command, cwd=project).returncode


def main():
    parser = argparse.ArgumentParser(description='在applications/<app>/cloudcc内操作类，共享根配置和缓存')
    parser.add_argument('--cli', required=True, help='已安装CloudCC技能的tools/bin/cloudcc绝对路径')
    parser.add_argument('--root', required=True, help='共用配置所在的项目根目录')
    parser.add_argument('--app', required=True, help='applications下的应用标识')
    parser.add_argument('action', choices=['create', 'format', 'validate', 'publish'])
    parser.add_argument('name')
    formatting = parser.add_mutually_exclusive_group()
    formatting.add_argument('--write', action='store_true')
    formatting.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        return run_class(args.cli, args.root, args.app, args.action, args.name,
                         '--write' if args.write else '--check' if args.check else None)
    except (RuntimeError, OSError) as error:
        print(str(error) if isinstance(error, RuntimeError) else 'CloudCC类操作失败，请检查目录、符号链接权限及执行权限', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
