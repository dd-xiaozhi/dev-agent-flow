"""路径常量"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# .chatlabs 目录
CHATLABS_DIR = PROJECT_ROOT / ".chatlabs"

# 状态目录
STATE_DIR = CHATLABS_DIR / "state"

# Stories 目录
STORIES_DIR = CHATLABS_DIR / "stories"

# Consensus 目录（用于本地适配器）
CONSENSUS_DIR = CHATLABS_DIR / "consensus"
