import asyncio
import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot.config import config
from bot.database import db
from bot.handlers.user import start_command, help_command, handle_user_message
from bot.handlers.admin import (
    handle_callback,
    handle_admin_message,
    stats_command,
    ban_command,
    unban_command,
)

# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """应用初始化后执行"""
    # 确保数据目录存在
    db_dir = Path(config.DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    # 连接数据库
    await db.connect()
    logger.info("数据库已连接")


async def post_shutdown(application: Application):
    """应用关闭时执行"""
    await db.close()
    logger.info("数据库已关闭")


def main():
    """主函数"""
    # 验证配置
    config.validate()

    # 创建应用
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # 注册命令处理器
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))

    # 注册回调处理器（内联按钮）
    application.add_handler(CallbackQueryHandler(handle_callback))

    # 管理员消息处理器（优先级高）
    application.add_handler(
        MessageHandler(
            filters.Chat(config.ADMIN_ID) & ~filters.COMMAND,
            handle_admin_message
        )
    )

    # 用户消息处理器
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_user_message
        )
    )

    # 启动机器人
    logger.info("机器人启动中...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
