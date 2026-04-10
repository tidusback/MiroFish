"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # 新闻数据源配置（可选）
    # NewsAPI.org key – leave blank to use only RSS/URL scraping
    NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '')

    # -----------------------------------------------------------------------
    # Uncensored Meta-Search Engine – Provider API Keys (all optional)
    # -----------------------------------------------------------------------
    # Brave Search API key (free tier: 2,000 req/month)
    # Get one at: https://api.search.brave.com/
    BRAVE_SEARCH_API_KEY = os.environ.get('BRAVE_SEARCH_API_KEY', '')

    # Semantic Scholar API key (optional – increases rate limits)
    # Get one at: https://www.semanticscholar.org/product/api
    SEMANTIC_SCHOLAR_API_KEY = os.environ.get('SEMANTIC_SCHOLAR_API_KEY', '')

    # GitHub Personal Access Token (optional – increases rate limits to 5,000/hr)
    # Create at: https://github.com/settings/tokens
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

    # Marginalia API key (optional – enables full result set)
    # Get one at: https://marginalia-search.com/
    MARGINALIA_API_KEY = os.environ.get('MARGINALIA_API_KEY', '')
    
    # Sentinel value written to .env when keys are not yet configured.
    # Allows the server to start in search-only mode without crashing.
    _PLACEHOLDER = "not-configured"

    @classmethod
    def validate(cls):
        """验证必要配置 (returns hard errors only; placeholder values are warnings)"""
        errors = []
        if not cls.LLM_API_KEY or cls.LLM_API_KEY == cls._PLACEHOLDER:
            pass  # warn-only; simulation/graph features will fail but search works
        if not cls.ZEP_API_KEY or cls.ZEP_API_KEY == cls._PLACEHOLDER:
            pass  # warn-only; same reason
        return errors

    @classmethod
    def search_only_mode(cls) -> bool:
        """True when LLM/Zep keys are absent – only the search engine is functional."""
        return (
            not cls.LLM_API_KEY
            or cls.LLM_API_KEY == cls._PLACEHOLDER
            or not cls.ZEP_API_KEY
            or cls.ZEP_API_KEY == cls._PLACEHOLDER
        )

