# member-activity

查询团队成员活动历史，生成贡献报告。

## 使用场景

- 查询某个成员最近做了什么
- 了解团队成员的技术栈和贡献领域
- 在接手新任务时了解前人的实现

## 命令

### 查询成员活动

查询指定成员最近的活动记录：

```
/member-activity --member <成员ID> --limit 20
```

**示例**：
```
/member-activity --member xiaozhi --limit 10
```

**输出示例**：
```
# xiaozhi 的最近活动
[2026-04-22T10:00:00+08:00] 会话开始 (任务: TASK-STORY-001-01)
[2026-04-22T10:30:00+08:00] 修改文件: src/UserService.java
[2026-04-22T11:00:00+08:00] 修改文件: src/UserController.java
[2026-04-22T11:30:00+08:00] 会话结束 (时长: 5400s, 文件: 5)
```

### 查询成员贡献报告

生成详细的成员贡献报告：

```
/member-activity --report --member <成员ID>
```

**输出示例**：
```
# 成员贡献报告: xiaozhi

## 统计数据
- 活跃会话数: 12
- 完成任务数: 5
- 完成 Story 数: 2

## 最近活动
[2026-04-22T10:00:00+08:00] 会话开始
[2026-04-22T11:30:00+08:00] 会话结束
...
```

### 搜索特定任务/Story 的活动

```
/member-activity --task-id <task_id>
/member-activity --story-id <story_id>
/member-activity --type <event_type>
```

**支持的 event_type**：
- `session-start` - 会话开始
- `session-end` - 会话结束
- `file-changed` - 文件修改
- `task-done` - 任务完成
- `story-done` - Story 完成
- `blocker-identified` - 阻塞点识别

## 数据来源

活动数据来自 `.chatlabs/reports/members/{member_id}/activity.log`，由以下 Hook 自动写入：

- `session-start.py` - 会话开始时记录
- `session-end.py` - 会话结束时记录
- `file-tracker.py` - 文件修改时记录

## 与 AI 的协作

当 AI 在规划新任务时，会自动参考当前成员的最近活动，以：
- 避免重复实现已有功能
- 了解前人的代码结构和设计决策
- 识别成员的技术栈和擅长领域