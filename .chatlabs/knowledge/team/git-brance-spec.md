# 核心分支命名规范
没有前缀的分支是核心分支，主要用于开发环境、用户测试环境部署的。
例如：dev、uat、staging 这几个是我们项目常用的分支命名。

| 分支类型 | 前缀 | 创建来源 | 合并目标 | 使用场景 |
| :--- | :--- | :--- | :--- | :--- |
| 主分支 | `main` 或 `master` | - | - | 存储稳定的、已发布的代码，是项目的基石。 |
| 功能分支 | `feature/` | `master` | `dev/staging` | 开发一个新功能。 |
| 修复分支 | `bugfix/` | `feature` | `feature` | 修复测试环境或开发过程中发现的 Bug。 |
| 紧急修复分支 | `hotfix/` | `master` | `dev/staging` 和 `uat` | 紧急修复生产环境的问题，需要快速上线。 |
| 发布分支 | `release/` | `develop` | `main` 和 `develop` | 准备一个新版本的发布，进行最后的测试和修修补补。 |

命名示例
功能分支：feature/user-login、feature/add-dark-mode
修复分支：bugfix/login-error、bugfix/payment-timeout
紧急修复分支：hotfix/critical-security-patch
发布分支：release/v1.2.0、release/v2.0.0-rc.1

# 最佳实践
- 小写字母 + 连字符：全部使用小写字母，单词之间用连字符（-）分隔。避免使用大写、下划线或空格。
✅ feature/user-login
❌ feature/UserLogin、feature/user_login、feature/user login
- 描述要清晰简洁：分支名要能准确描述其工作内容，长度控制在 30-50 个字符内。
✅ bugfix/login-500-error
❌ bugfix/fix、bugfix/update
- 结合任务编号（可选但推荐）：有使用 Jira、GitHub Issues、tapd 等工具，可以把任务编号加进去，方便追溯。
feature/{id}-user-authentication
bugfix/{id}-login-validation-error
用完即删：功能或修复完成后，合并回 develop 分支，然后立即删除这个功能/修复分支。保持仓库整洁。
备注: {id} 表示的是对应的任务管理平台的 id，根据当前所在平台灵活变更


# 开发流程
新功能开发/bug修复根据上述的规范创建分支，开发修复完成后合并到 dev、再将 dev 合并到 uat，再切换到开始分支
