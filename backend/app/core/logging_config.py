"""
Centralized Logging Configuration for Cupid Agent System.

Provides structured logging with:
- Colored console output for development
- JSON formatting for production
- Request ID tracking
- Performance metrics
- Agent-specific loggers

Inspired by production logging from OpenAI, Anthropic, and Perplexity.
"""
import logging
import sys
from typing import Any

# ANSI Color Codes for Terminal Output

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Standard colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

# Custom Formatter with Colors

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and structured output."""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.BRIGHT_BLACK,
        logging.INFO: Colors.BRIGHT_CYAN,
        logging.WARNING: Colors.BRIGHT_YELLOW,
        logging.ERROR: Colors.BRIGHT_RED,
        logging.CRITICAL: Colors.BRIGHT_MAGENTA,
    }
    
    AGENT_COLORS = {
        "supervisor": Colors.BRIGHT_YELLOW,
        "personalization": Colors.BRIGHT_BLUE,
        "research": Colors.BRIGHT_GREEN,
        "composer": Colors.BRIGHT_MAGENTA,
        "orchestrator": Colors.BRIGHT_CYAN,
        "router": Colors.BRIGHT_YELLOW,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and structure."""
        # Get level color
        level_color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
        
        # Get agent color if present
        agent_name = getattr(record, "agent", None)
        agent_color = self.AGENT_COLORS.get(agent_name, Colors.WHITE) if agent_name else Colors.WHITE
        
        # Format timestamp
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        
        # Format level name
        level_name = f"{level_color}{record.levelname:8s}{Colors.RESET}"
        
        # Format logger name (agent)
        if agent_name:
            logger_name = f"{agent_color}[{agent_name}]{Colors.RESET}"
        else:
            logger_name = f"{Colors.DIM}[{record.name}]{Colors.RESET}"
        
        # Format message
        message = record.getMessage()
        
        # Add run_id if present
        run_id = getattr(record, "run_id", None)
        run_id_str = f" {Colors.DIM}(run:{run_id[:8]}){Colors.RESET}" if run_id else ""
        
        # Combine all parts
        formatted = f"{Colors.DIM}{timestamp}{Colors.RESET} {level_name} {logger_name}{run_id_str} {message}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        
        return formatted

# LOGER SETUP
def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the entire application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(ColoredFormatter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langchain_core").setLevel(logging.WARNING)
    logging.getLogger("langchain_groq").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    
    # Silence SQLAlchemy verbose logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
    
    # Silence uvicorn access logs (keep errors)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# Agent Logger Factory

class AgentLogger:
    """
    Structured logger for agent operations.
    
    Provides convenience methods for logging agent lifecycle events,
    inputs, outputs, and performance metrics.
    """
    
    def __init__(self, agent_name: str):
        """
        Initialize agent logger.
        
        Args:
            agent_name: Name of the agent (personalization, research, composer)
        """
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"app.agents.{agent_name}")
    
    def _log(self, level: int, message: str, run_id: str | None = None, **kwargs: Any) -> None:
        """Internal logging method with agent context."""
        extra = {"agent": self.agent_name}
        if run_id:
            extra["run_id"] = run_id
        self.logger.log(level, message, extra=extra, **kwargs)
    
    def debug(self, message: str, run_id: str | None = None, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, run_id, **kwargs)
    
    def info(self, message: str, run_id: str | None = None, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, message, run_id, **kwargs)
    
    def warning(self, message: str, run_id: str | None = None, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, run_id, **kwargs)
    
    def error(self, message: str, run_id: str | None = None, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, run_id, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, run_id: str | None = None, exc_info: bool = False, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, run_id, exc_info=exc_info, **kwargs)
    
    # ── Agent Lifecycle Events ──────────────────────────────────────────
    
    def agent_start(self, run_id: str, **context: Any) -> None:
        """Log agent start with context."""
        self.info("=" * 10, run_id)
        self.info(f"𖠌 {self.agent_name.upper()} AGENT START", run_id)
        self.info("=" * 10, run_id)
        for key, value in context.items():
            if value is not None:
                self.info(f"  {key}: {value}", run_id)
    
    def agent_complete(self, run_id: str, **metrics: Any) -> None:
        """Log agent completion with metrics."""
        self.info("─" * 10, run_id)
        self.info(f"(✓) {self.agent_name.upper()} AGENT COMPLETE", run_id)
        for key, value in metrics.items():
            if value is not None:
                self.info(f"  {key}: {value}", run_id)
        self.info("=" * 10, run_id)
    
    def agent_error(self, run_id: str, error: Exception) -> None:
        """Log agent error."""
        self.error("─" * 10, run_id)
        self.error(f"(✗) {self.agent_name.upper()} AGENT FAILED", run_id, exc_info=True)
        self.error(f"  Error: {str(error)}", run_id)
        self.error("=" * 10, run_id)
    
    # ── Input/Output Logging ─────────────────────────────────────────────
    
    def log_input(self, run_id: str, label: str, content: str, max_length: int = 200) -> None:
        """Log input data with truncation."""
        truncated = content[:max_length] + "..." if len(content) > max_length else content
        self.info(f"🖂 INPUT [{label}]: {truncated}", run_id)
    
    def log_output(self, run_id: str, label: str, content: str | list | dict, max_length: int = 200) -> None:
        """Log output data with truncation."""
        if isinstance(content, (list, dict)):
            content_str = str(content)
        else:
            content_str = str(content)
        truncated = content_str[:max_length] + "..." if len(content_str) > max_length else content_str
        self.info(f"📤 OUTPUT [{label}]: {truncated}", run_id)
    
    def log_metric(self, run_id: str, metric_name: str, value: Any) -> None:
        """Log a performance metric."""
        self.info(f"📊 METRIC [{metric_name}]: {value}", run_id)
    
    def log_step(self, run_id: str, step_name: str, details: str = "") -> None:
        """Log a processing step."""
        msg = f"⚙️  STEP: {step_name}"
        if details:
            msg += f" - {details}"
        self.info(msg, run_id)

# Convenience Functions

def get_agent_logger(agent_name: str) -> AgentLogger:
    """
    Get a logger for a specific agent.
    
    Args:
        agent_name: Name of the agent (personalization, research, composer)
    
    Returns:
        AgentLogger instance
    """
    return AgentLogger(agent_name)


def log_api_call(
    logger: AgentLogger,
    run_id: str,
    provider: str,
    model: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    latency_ms: int | None = None,
) -> None:
    """
    Log an LLM API call with metrics.
    
    Args:
        logger: Agent logger instance
        run_id: Run ID for tracking
        provider: LLM provider (groq, openai, anthropic, etc.)
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        latency_ms: API call latency in milliseconds
    """
    logger.info(f"🤖 LLM CALL: {provider}/{model}", run_id)
    if prompt_tokens:
        logger.info(f"  Prompt tokens: {prompt_tokens}", run_id)
    if completion_tokens:
        logger.info(f"  Completion tokens: {completion_tokens}", run_id)
    if latency_ms:
        logger.info(f"  Latency: {latency_ms}ms", run_id)


def log_search_call(
    logger: AgentLogger,
    run_id: str,
    query: str,
    results_count: int,
    latency_ms: int | None = None,
) -> None:
    """
    Log a search API call.
    
    Args:
        logger: Agent logger instance
        run_id: Run ID for tracking
        query: Search query
        results_count: Number of results returned
        latency_ms: API call latency in milliseconds
    """
    logger.info(f"🔍 SEARCH: {query[:100]}", run_id)
    logger.info(f"  Results: {results_count}", run_id)
    if latency_ms:
        logger.info(f"  Latency: {latency_ms}ms", run_id)
