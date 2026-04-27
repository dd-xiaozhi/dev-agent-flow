# 编码规范

## 命名规范

### 文件命名
- **Python 脚本**: `snake_case.py`
- **Markdown 文档**: `kebab-case.md`
- **Hook 脚本**: `snake_case.py`
- **Skill 文档**: `kebab-case.md`

### 变量命名
- **Python**: `snake_case`（下划线命名）
  ```python
  story_id = "STORY-001"
  workflow_state = {}
  ```
- **JSON 字段**: `snake_case` 或 `camelCase`（根据上下文）

### 函数/方法命名
```python
def load_workflow_state(story_id):
def create_story(name, options):
def emit_event(event_type, payload):
```

## Import 顺序

```python
# 1. 标准库
import json
import os
from datetime import datetime

# 2. 第三方库
from anthropic import Anthropic

# 3. 本地模块（按相对路径）
from ..scripts.workflow_state import WorkflowState
```

## Docstring 风格

使用 Google 风格：

```python
def load_state(story_id: str) -> dict:
    """加载 story 工作状态。

    Args:
        story_id: Story 标识符

    Returns:
        包含 phase、verdicts 等字段的状态字典

    Raises:
        FileNotFoundError: 状态文件不存在时
    """
    pass
```

## 错误处理

### 异常类型
```python
# 自定义异常
class FlowError(Exception):
    """Flow 执行异常基类"""
    pass

class StateError(FlowError):
    """状态管理异常"""
    pass

class TAPDSyncError(FlowError):
    """TAPD 同步异常"""
    pass
```

### 错误返回值约定
```python
# 返回 None 表示失败
result = load_state(story_id)
if result is None:
    logger.warning("状态文件不存在")

# 返回元组表示成功/失败
success, message = sync_to_tapd(payload)
if not success:
    raise TAPDSyncError(message)
```

## 测试组织

### 测试目录
- `tests/` - 单元测试
- `.claude/skills/contract-test/` - 契约测试适配器

### 测试文件命名
```
test_workflow_state.py
test_tapd_sync.py
test_fitness_runner.py
```

### 断言风格
```python
import pytest

def test_workflow_state_load():
    state = WorkflowState.load("STORY-001")
    assert state.phase == "doc-librarian"
    assert state.story_id == "STORY-001"
```

## 注释规范

### TODO/FIXME 标记
```python
# TODO(agent): 补充错误处理
# FIXME(generator): 边界条件未覆盖
```

### 复杂逻辑注释
```python
# 使用时间戳避免并发冲突（格式: YYYYMMDD-HHMMSS）
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
```

## Shell 脚本约定

**全部使用 Python 替代 shell**（遵循 memory 规则）：
- 路径操作 → `os.path`
- 文件读写 → `open()` / `pathlib`
- 进程调用 → `subprocess`