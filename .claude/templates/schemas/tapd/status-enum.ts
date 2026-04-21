/**
 * TAPD 状态枚举定义
 *
 * 设计原则：
 * - 英文大写下划线风格（IN_DEVELOPMENT）
 * - 与 TAPD v_status 中文别名配对使用
 * - 通过 tapd-config.json 的 v_status_aliases 字段维护映射
 */

/** Story 状态枚举 */
export const STORY_STATUS = {
  BACKLOG: 'BACKLOG',           // 待办/ backlog
  DESIGN: 'DESIGN',             // 设计中
  IN_DEVELOPMENT: 'IN_DEVELOPMENT', // 开发中
  PENDING_REVIEW: 'PENDING_REVIEW', // 待评审
  IN_REVIEW: 'IN_REVIEW',       // 评审中
  PENDING_TEST: 'PENDING_TEST', // 待测试
  IN_TEST: 'IN_TEST',           // 测试中
  COMPLETED: 'COMPLETED',       // 已完成
  DEPLOYED: 'DEPLOYED',         // 已上线
} as const;

export type StoryStatus = typeof STORY_STATUS[keyof typeof STORY_STATUS];

/** Task 状态枚举 */
export const TASK_STATUS = {
  OPEN: 'OPEN',                 // 打开
  IN_DEVELOPMENT: 'IN_DEVELOPMENT', // 开发中
  PENDING_TEST: 'PENDING_TEST', // 待测试
  DONE: 'DONE',                 // 完成
} as const;

export type TaskStatus = typeof TASK_STATUS[keyof typeof TASK_STATUS];

/** 本地语义状态键 */
export const LOCAL_PHASE = {
  PENDING: 'pending',
  IN_PROGRESS: 'in_progress',
  WAITING_CONSENSUS: 'waiting-consensus',
  DONE: 'done',
} as const;

export type LocalPhase = typeof LOCAL_PHASE[keyof typeof LOCAL_PHASE];

/** 语义键 → 状态枚举的默认映射 */
export const STATUS_MAP_KEYS = {
  story: {
    to_dev: 'IN_DEVELOPMENT',
    to_review: 'IN_REVIEW',
    to_test: 'PENDING_TEST',
    done: 'COMPLETED',
  } as const,
  task: {
    to_dev: 'IN_DEVELOPMENT',
    to_test: 'PENDING_TEST',
    done: 'DONE',
  } as const,
} as const;

/** 中文 v_status 别名（用于 TAPD API 调用）*/
export const V_STATUS_ALIASES: Record<string, string> = {
  BACKLOG: '待办',
  DESIGN: '设计中',
  IN_DEVELOPMENT: '开发中',
  PENDING_REVIEW: '待评审',
  IN_REVIEW: '评审中',
  PENDING_TEST: '待测试',
  IN_TEST: '测试中',
  COMPLETED: '已完成',
  DEPLOYED: '已上线',
  OPEN: '打开',
  DONE: '完成',
};

/** 关键词匹配规则（用于 tapd-init 智能推荐）*/
export const KEYWORD_MATCH_RULES: Array<{
  pattern: RegExp;
  status: string;
  confidence: number;
}> = [
  // IN_DEVELOPMENT
  { pattern: /dev|develop|开发|进行中|工作中/i, status: 'IN_DEVELOPMENT', confidence: 1.0 },
  { pattern: /progress|进行/i, status: 'IN_DEVELOPMENT', confidence: 0.9 },

  // IN_REVIEW
  { pattern: /review|评审/i, status: 'IN_REVIEW', confidence: 1.0 },

  // PENDING_TEST
  { pattern: /test|测试|qa|待测/i, status: 'PENDING_TEST', confidence: 1.0 },

  // COMPLETED
  { pattern: /done|完成|resolved|已实现/i, status: 'COMPLETED', confidence: 1.0 },

  // DEPLOYED
  { pattern: /deploy|上线|release|发布/i, status: 'DEPLOYED', confidence: 1.0 },

  // BACKLOG
  { pattern: /backlog|待办|todo|新建/i, status: 'BACKLOG', confidence: 0.8 },

  // DESIGN
  { pattern: /design|设计/i, status: 'DESIGN', confidence: 1.0 },

  // IN_TEST
  { pattern: /testing|测试中/i, status: 'IN_TEST', confidence: 1.0 },

  // PENDING_REVIEW
  { pattern: /pending.*review|待评审/i, status: 'PENDING_REVIEW', confidence: 1.0 },
];

/**
 * 根据关键词匹配状态枚举
 * @param statusName TAPD 返回的状态名称（可能中文或英文）
 * @returns 匹配到的枚举状态，未匹配返回 null
 */
export function matchStatusByKeyword(statusName: string): { status: string; confidence: number } | null {
  for (const rule of KEYWORD_MATCH_RULES) {
    if (rule.pattern.test(statusName)) {
      return { status: rule.status, confidence: rule.confidence };
    }
  }
  return null;
}

/**
 * 获取状态的中文别名
 * @param status 英文枚举状态
 * @returns 中文别名，未找到返回原值
 */
export function getVStatusAlias(status: string): string {
  return V_STATUS_ALIASES[status] || status;
}
