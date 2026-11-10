#!/usr/bin/env python3
"""AgentCiCi platform management CLI with automatic developer-token exchange."""

from __future__ import annotations

import argparse
import io
import mimetypes
import os
import re
import zipfile
import uuid
import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, values=None) -> None:
        from agentcici_auth import credentials, NAMES
        values = credentials() if values is None else values
        self.base_url = values[NAMES[0]].rstrip("/")
        self.client_id = values[NAMES[1]]
        self.client_secret = values[NAMES[2]]
        self.token = ""

    def exchange(self) -> str:
        if not self.token:
            result = self._request("POST", "/openapi/v1/developer/token", {
                "clientId": self.client_id,
                "clientSecret": self.client_secret,
            }, authenticated=False)
            self.token = result["accessToken"]
        return self.token

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        return self._request(method, path, body, authenticated=True)

    def download(self, method, path, body=None):
        headers = {"Authorization": "Bearer " + self.exchange(), "Accept": "application/zip"}
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=180) as response:
                result = response.read(100 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"原生包导出失败 HTTP {error.code}；检查服务端部署、读取权限及资源发布状态") from None
        except urllib.error.URLError:
            raise RuntimeError("原生包导出连接失败") from None
        if len(result) > 100 * 1024 * 1024 or not zipfile.is_zipfile(io.BytesIO(result)):
            raise RuntimeError("服务端未返回有效 ZIP 或包超过 100 MiB")
        return result

    def upload_document(self, path, filename):
        file = pathlib.Path(filename)
        if not file.is_file() or not 0 < file.stat().st_size <= 100 * 1024 * 1024:
            raise RuntimeError("资料必须为非空且不超过100 MiB的文件；服务端仍校验上传策略")
        boundary = 'cici-document-' + uuid.uuid4().hex
        name = re.sub(r'[\r\n"\\]', '_', file.name)
        content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n').encode() + file.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        request = urllib.request.Request(self.base_url + path, data=body, method='POST', headers={
            'Authorization': 'Bearer ' + self.exchange(), 'Content-Type': 'multipart/form-data; boundary=' + boundary,
            'Accept': 'application/json'})
        try:
            with urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=120) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('文档上传失败或结果未知；先查询文档列表核实，不自动重复上传') from None
        if not result.get('success'):
            raise RuntimeError('文档上传未成功，请核对上传策略和知识库权限')
        return result.get('data')

    def _request(self, method: str, path: str, body: dict[str, Any] | None, authenticated: bool) -> Any:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + self.exchange()
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=30) as response:
                envelope = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                message = json.loads(error.read().decode("utf-8")).get("message")
            except Exception:
                message = None
            raise RuntimeError(message or f"AgentCiCi 返回 HTTP {error.code}") from None
        except urllib.error.URLError as error:
            raise RuntimeError(f"无法连接 AgentCiCi：{error.reason}") from None
        if not envelope.get("success"):
            raise RuntimeError(envelope.get("message") or "AgentCiCi 请求失败")
        return envelope.get("data")


def read_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.json_value:
        value = json.loads(args.json_value)
    elif args.file:
        value = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
    else:
        raise RuntimeError("必须提供 --json 或 --file")
    if not isinstance(value, dict):
        raise RuntimeError("请求数据必须是 JSON 对象")
    return value


def add_payload_arguments(command: argparse.ArgumentParser) -> None:
    inputs = command.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--json", dest="json_value")
    inputs.add_argument("--file")


def add_resource_commands(module: argparse.ArgumentParser, id_name: str) -> None:
    commands = module.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="列出资源")
    get = commands.add_parser("get", help="读取资源详情")
    get.add_argument(id_name)
    create = commands.add_parser("create", help="创建资源")
    add_payload_arguments(create)
    update = commands.add_parser("update", help="更新资源")
    update.add_argument(id_name)
    add_payload_arguments(update)
    delete = commands.add_parser("delete", help="删除资源")
    delete.add_argument(id_name)
    delete.add_argument("--confirm-id", required=True)
    if module.prog.endswith(("agents", "skills")):
        export = commands.add_parser("export", help="下载原生包到本地，不覆盖已有文件")
        export.add_argument(id_name)
        export.add_argument("--output", required=True)
        if module.prog.endswith("skills"):
            export.add_argument("--allow-draft", action="store_true")
        compile_command = commands.add_parser("compile", help="编译当前草稿")
        compile_command.add_argument(id_name)
        publish = commands.add_parser("publish", help="发布技能或指定智能体版本")
        publish.add_argument(id_name)
        if module.prog.endswith("agents"):
            publish.add_argument("--version-no", type=int, required=True)
        else:
            publish.add_argument("--change-log", default="")
    if module.prog.endswith("agents"):
        create_key = commands.add_parser("create-api-key", help="创建运行密钥，仅写入指定的私密 JSON 文件")
        create_key.add_argument(id_name)
        add_payload_arguments(create_key)
        create_key.add_argument("--output", required=True)
        revoke_key = commands.add_parser("revoke-api-key", help="撤销指定运行密钥")
        revoke_key.add_argument(id_name)
        revoke_key.add_argument("credential_id", type=int)
        revoke_key.add_argument("--confirm-id", required=True)
        bindings = commands.add_parser("skills", help="读取技能关联")
        bindings.add_argument(id_name)
        for name in ("bind-skills", "bind-knowledge", "bind-tools"):
            binding = commands.add_parser(name, help="替换完整关联列表；空列表清空")
            binding.add_argument(id_name)
            add_payload_arguments(binding)
    if module.prog.endswith("mcp"):
        for name in ("tools", "discover"):
            command = commands.add_parser(name, help="读取已有工具" if name == "tools" else "从 MCP 服务重新发现工具")
            command.add_argument(id_name)

    return commands


def add_knowledge_commands(module):
    commands = add_resource_commands(module, 'resource_id')
    get_access = commands.add_parser('get-access', help='读取知识库访问模式、角色和版本')
    get_access.add_argument('resource_id')
    set_access = commands.add_parser('set-access', help='按已读取的版本替换知识库访问策略')
    set_access.add_argument('resource_id')
    add_payload_arguments(set_access)
    documents = commands.add_parser('documents', help='读取知识库文档与索引状态')
    documents.add_argument('resource_id')
    upload = commands.add_parser('upload', help='上传授权测试资料，需另外发布索引')
    upload.add_argument('resource_id')
    upload.add_argument('--file', required=True)
    retrieve = commands.add_parser('retrieve', help='检索测试')
    retrieve.add_argument('resource_id')
    add_payload_arguments(retrieve)
    for action in ('publish-document', 'reindex-document', 'delete-document'):
        command = commands.add_parser(action)
        command.add_argument('resource_id', help='文档ID')
        if action == 'delete-document':
            command.add_argument('--confirm-id', required=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="使用开发者密钥管理 AgentCiCi 智能体、技能和 MCP 服务")
    modules = root.add_subparsers(dest="module", required=True)
    add_resource_commands(modules.add_parser("agents", help="管理智能体"), "resource_id")
    add_resource_commands(modules.add_parser("skills", help="管理技能"), "resource_id")
    add_resource_commands(modules.add_parser("mcp", help="管理 MCP 服务"), "resource_id")
    add_knowledge_commands(modules.add_parser("knowledge", help="管理知识库、文档与检索"))
    modules.add_parser("tools", help="读取组织现有工具，不创建工具").add_subparsers(dest="command", required=True).add_parser("list")
    return root


def resource_path(module: str) -> str:
    suffix = {"agents": "agents", "skills": "skills", "mcp": "mcp-servers", "knowledge": "knowledge-bases"}[module]
    return "/openapi/v1/management/" + suffix


SKILL_FIELDS = "skillCode name description enabled promptFragment draftSpecText toolWhitelist kbWhitelist handoffRule outputContract runtimeApis riskLevel changeLog".split()
MCP_FIELDS = "name description transportType url headers timeoutSeconds enabled authType tokenUrl clientId clientSecret tokenAudience tokenScopes".split()


def execute(client, args):
    if args.module == "tools":
        return client.request("GET", "/openapi/v1/management/tools")
    base = resource_path(args.module)
    path = base + "/" + urllib.parse.quote(getattr(args, "resource_id", ""), safe="")
    if args.module == "agents" and args.command == "create-api-key":
        body = read_payload(args)
        body.setdefault("maxPromptChars", 64000)
        body.setdefault("maxResponseChars", 128000)
        output = pathlib.Path(args.output).expanduser().resolve()
        # Reserve a private destination before creating a remote credential.
        try:
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise RuntimeError("输出文件已存在，请选择新路径") from None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                result = client.request("POST", path + "/api-keys", body)
                json.dump(result, file, ensure_ascii=False, indent=2)
        except Exception:
            # A timeout may leave a remote key; never automatically retry creation.
            raise RuntimeError("密钥创建或保存失败，结果可能未知；请核对后台密钥列表，不自动重试。输出路径：" + str(output)) from None
        return {"file": str(output), "credentialId": result["credential"]["id"]}
    if args.module == "agents" and args.command == "revoke-api-key":
        if args.credential_id <= 0 or str(args.credential_id) != args.confirm_id:
            raise RuntimeError("--confirm-id 必须与待撤销的正整数 credential ID 完全一致")
        return client.request("POST", path + "/api-keys/" + str(args.credential_id) + "/revoke", {})
    if args.command == "list":
        return client.request("GET", base)
    if args.command == "get":
        return client.request("GET", path)
    if args.command == "tools":
        return client.request("GET", path + "/tools")
    if args.command == "discover":
        return client.request("POST", path + "/discover")
    if args.module == 'knowledge':
        if args.command == 'get-access':
            return client.request('GET', path + '/access')
        if args.command == 'set-access':
            return client.request('PUT', path + '/access', read_payload(args))
        if args.command == 'documents':
            return client.request('GET', path + '/documents')
        if args.command == 'upload':
            return client.upload_document(path + '/documents', args.file)
        if args.command == 'retrieve':
            return client.request('POST', path + '/retrieval/test', read_payload(args))
        if args.command in ('publish-document', 'reindex-document', 'delete-document'):
            document_path = base + '/documents/' + urllib.parse.quote(args.resource_id, safe='')
            if args.command == 'delete-document':
                if args.resource_id != args.confirm_id:
                    raise RuntimeError('--confirm-id 必须与待删除文档 ID 完全一致')
                return client.request('DELETE', document_path)
            return client.request('POST', document_path + ('/publish' if args.command == 'publish-document' else '/reindex'), {})
    if args.command == "create":
        return client.request("POST", base, read_payload(args))
    if args.command == "update":
        body = read_payload(args)
        if args.module in ("skills", "mcp", "knowledge"):
            current = client.request("GET", path)
            fields = SKILL_FIELDS if args.module == "skills" else MCP_FIELDS if args.module == "mcp" else ["name", "description"]
            body = {**{k: v for k, v in current.items() if k in fields}, **body}
        return client.request("PATCH" if args.module == "agents" else "PUT", path, body)
    if args.command == "export":
        output = pathlib.Path(args.output).expanduser().resolve()
        if output.exists():
            raise RuntimeError("输出文件已存在，请选择新路径")
        if not output.parent.is_dir():
            raise RuntimeError("输出目录不存在，请先创建")
        body = {"allowDraft": args.allow_draft} if args.module == "skills" else None
        data = client.download("POST" if args.module == "skills" else "GET", path + "/package", body)
        with output.open("xb") as file:
            file.write(data)
        return {"file": str(output), "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if args.command == "compile":
        return client.request("POST", path + "/compile", {})
    if args.command == "publish":
        if args.module == "agents":
            if args.version_no <= 0:
                raise RuntimeError("--version-no 必须是正整数")
            body = {"versionNo": args.version_no}
        else:
            body = {"changeLog": args.change_log}
        return client.request("POST", path + "/publish", body)
    if args.command == "skills":
        return client.request("GET", path + "/skills")
    if args.command.startswith("bind-"):
        field = {"bind-skills": "bindings", "bind-knowledge": "knowledgeBaseIds", "bind-tools": "toolIds"}[args.command]
        body = read_payload(args)
        allowed = {field, "toolLoadingModes", "toolRuntimePolicies"} if args.command == "bind-tools" else {field}
        if field not in body or not isinstance(body[field], list) or not set(body).issubset(allowed):
            raise RuntimeError("请求必须包含列表字段 " + field + "，且只能使用该绑定支持的配置字段")
        if args.command == "bind-tools":
            if "toolLoadingModes" in body and not isinstance(body["toolLoadingModes"], dict):
                raise RuntimeError("toolLoadingModes 必须是对象")
            if "toolRuntimePolicies" in body and not isinstance(body["toolRuntimePolicies"], dict):
                raise RuntimeError("toolRuntimePolicies 必须是对象")
        return client.request("PUT" if field == "bindings" else "PATCH",
                              path + ("/skills" if field == "bindings" else ""), body)
    if args.resource_id != args.confirm_id:
        raise RuntimeError("--confirm-id 必须与待删除资源 ID 完全一致")
    return client.request("DELETE", path)


def main() -> int:
    args = parser().parse_args()
    try:
        result = execute(Client(), args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, json.JSONDecodeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
