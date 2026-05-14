---
name: remote-log-fetch
description: |
  远程日志获取工具。通过 SSH 访问远程服务器查询日志。
  当用户说：查询日志、获取日志、查看日志、远程日志、日志追踪、traceId 查日志、
  "帮我看看某台机器的日志"、"log" + traceId、"日志文件" + 服务器 等关键词时使用。
  也适用于：诊断问题、排查 bug、分析日志、需要从服务器获取日志内容的场景。
---

# Remote Log Fetch

通过 SSH 连接远程服务器，根据 traceId 或关键字查询日志。

## 配置结构

在 `.chatlabs/project-config.json` 中定义：

```json
{
  "ssh_servers": [
    {
      "env": "dev",
      "name": "开发环境",
      "host": "192.168.1.100",
      "port": 22,
      "user": "deploy",
      "password_env": "SSH_DEV_PASSWORD"
    },
    {
      "env": "staging",
      "name": "预发环境",
      "host": "192.168.1.101",
      "port": 22,
      "user": "deploy",
      "password_env": "SSH_STAGING_PASSWORD"
    }
  ],
  "log_paths": [
    {
      "env": "dev",
      "log_dir": "/var/log/myapp",
      "log_pattern": "log_debug_{date}.{seq}.log"
    },
    {
      "env": "staging",
      "log_dir": "/home/deploy/logs",
      "log_pattern": "debug-{date}.{seq}.log"
    }
  ],
  "output_dir": "./logs_query"
}
```

### 字段说明

**ssh_servers:**
- `env`: 环境标识（dev/staging/prod），用于匹配 log_paths
- `name`: 服务器名称描述
- `host`: 服务器 IP 或域名
- `port`: SSH 端口，默认 22
- `user`: SSH 用户名
- `password_env`: 环境变量名，存储 SSH 密码（使用 `os.getenv()` 获取）

**log_paths:**
- `env`: 必须与 ssh_servers 中的 env 对应
- `log_dir`: 日志文件所在目录
- `log_pattern`: 日志文件名模式
  - `{date}` 替换为 YYYY-MM-DD 格式
  - `{seq}` 匹配序号（0, 1, 2...）

**output_dir:** 查询结果输出目录（相对于项目根目录）

## 使用方式

### 1. 选择服务器

从 `.chatlabs/project-config.json` 的 ssh_servers 中选择一个服务器：

```
可用服务器：
- dev: 开发环境 (192.168.1.100)
- staging: 预发环境 (192.168.1.101)
- prod: 生产环境 (192.168.1.102)

请告诉我您要查询哪个环境的日志？
```

如果用户指定了环境，直接使用对应的服务器。

### 2. 执行 SSH 命令

使用 `sshpass` 进行密码认证。根据条件构建 SSH 命令：

**使用 grep 搜索：**
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no deploy@192.168.1.100 \
  "grep -n 'traceId123456' /var/log/myapp/log_debug_*.log"
```

**使用 tail 查看最后 N 行：**
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no deploy@192.168.1.100 \
  "tail -n 200 /var/log/myapp/log_debug_$(date +%Y-%m-%d).*.log"
```

**使用 ls 查看日志文件列表：**
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no deploy@192.168.1.100 \
  "ls -la /var/log/myapp/"
```

### 3. 保存结果

将查询结果写入 `output_dir` 下的文件，命名格式：
```
{环境名}-{日志日期}-{traceId/关键字}.log
```

例如：`dev-2026-05-08-383986f9757948e7963dc7e587cc96bf1778229222587.log`

**保存前处理：**
1. 移除远程日志路径前缀（使用 `sed 's|.*/log_debug_{date}.*\.log:||'`）
2. 移除行号前缀（使用 `sed 's/^[0-9]*://'`）
3. 移除警告信息（如 locale 警告）

## 日志文件名模式

日志文件命名遵循 `{日志名-日期-序号.log}` 格式：

| 示例 | 模式 |
|-----|------|
| log_debug_2026-05-02.0.log | log_debug_{date}.{seq}.log |
| debug-2026-05-03.0.log | debug-{date}.{seq}.log |
| error-2026-05-11.1.log | error-{date}.{seq}.log |

使用 glob 模式匹配：`{日志名}*{date}.*.log`

## 执行流程

```
┌─────────────────────────────────────────────────────────────┐
│                    远程日志查询流程                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 读取 .chatlabs/project-config.json                         │
│     └── 获取 ssh_servers、log_paths、output_dir              │
│                                                             │
│  2. 确认服务器环境                                            │
│     └── 用户指定 env → 使用对应配置                           │
│     └── 用户未指定 → 列出选项让用户选择                        │
│                                                             │
│  3. 读取密码                                                 │
│     └── 从 password_env 环境变量获取密码                      │
│                                                             │
│  4. 构建 SSH 命令                                            │
│     ├── 有 traceId → grep 搜索                               │
│     ├── 关键字搜索 → grep 搜索                                │
│     └── 仅查看最新日志 → tail 查看                            │
│                                                             │
│  5. 执行 SSH 并获取输出                                      │
│     └── 使用 sshpass + Bash tool 执行命令                     │
│                                                             │
│  6. 保存到 output_dir                                         │
│     └── 写入 {环境名}-{日志日期}-{traceId/关键字}.log        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## SSH 命令示例

**根据 traceId 搜索：**
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no user@host \
  "grep -n 'abc123' /path/to/logs/*.log"
```

**搜索多个关键字：**

```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no user@host \
  "grep -E 'traceId|error|timeout' /path/to/logs/log_debug_2026-05-11.*.log"
```

**列出日志目录：**
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no user@host \
  "ls -lht /path/to/logs/ | head -20"
```

**查看指定日期的日志：**
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no user@host \
  "cat /path/to/logs/debug-2026-05-11.*.log | head -100"
```

## 注意事项

1. **环境变量**：密码通过 `password_env` 字段指定的环境变量获取，使用 `os.getenv()` 读取
2. **sshpass**：使用 `sshpass` 工具传递密码，避免交互式输入
3. **StrictHostKeyChecking**：使用 `-o StrictHostKeyChecking=no` 跳过首次连接的主机密钥确认
4. **通配符**：在 SSH 命令中使用 glob 时，确保引号正确防止本地 shell 展开
5. **编码**：如果日志是 GBK 编码，需要添加 `-C` 参数或使用 `iconv` 转换
6. **结果合并**：多文件搜索结果按文件分组，便于查看