from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config import config
from bot.database import db


# 允许的消息类型
ALLOWED_TYPES = {"text", "photo", "animation", "voice", "video_note", "sticker"}
# 禁止的类型（文件、视频）
BLOCKED_TYPES = {"document", "video"}


def get_user_display_name(user) -> str:
    """获取用户显示名"""
    parts = []
    if user.first_name:
        parts.append(user.first_name)
    if user.last_name:
        parts.append(user.last_name)
    return " ".join(parts) if parts else "未知用户"


def get_username_display(user) -> str:
    """获取用户名显示"""
    if user.username:
        return f"@{user.username}"
    return "无"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    await db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    welcome_text = """👋 欢迎使用留言机器人！

📝 **使用方法**
直接发送消息给我，管理员会收到你的留言并回复你。

⚠️ **注意事项**
• 请勿发送垃圾信息

发消息开始留言吧！"""

    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    help_text = """📖 **帮助信息**

**如何留言？**
直接给我发送消息即可，支持文字、图片、链接、语音等。

**为什么不能发送文件？**
为了安全考虑，暂不支持发送文件。

**消息限制**
• 每分钟最多 3 条
• 每天最多 30 条
• 发送过快会触发冷却

如有问题请稍后再试。"""

    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户发来的消息"""
    message = update.message
    user = update.effective_user

    # 忽略管理员的消息（在这个 handler 中）
    if user.id == config.ADMIN_ID:
        return

    # 获取或创建用户
    await db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # 检查是否被拉黑
    if await db.is_user_banned(user.id):
        await message.reply_text("⚠️ 您已被限制发送消息。")
        return

    # 检查消息类型
    content_type = get_content_type(message)
    if content_type in BLOCKED_TYPES:
        await message.reply_text("❌ 暂不支持发送文件或视频。")
        return

    if content_type not in ALLOWED_TYPES:
        await message.reply_text("❌ 不支持的消息类型。")
        return

    # 检查频率限制
    allowed, reason = await db.check_rate_limit(user.id)
    if not allowed:
        await message.reply_text(f"⚠️ {reason}")
        return

    # 转发消息给管理员
    try:
        # 构建用户信息
        msg_count = await db.get_user_message_count(user.id)
        user_info = build_user_info_text(user, msg_count + 1, message.text or message.caption)

        # 根据消息类型发送（合并为一条消息）
        if content_type == "text":
            # 纯文字消息
            sent_msg = await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=user_info,
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )
        elif content_type == "photo":
            # 图片消息
            sent_msg = await context.bot.send_photo(
                chat_id=config.ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=user_info,
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )
        elif content_type == "voice":
            # 语音消息
            sent_msg = await context.bot.send_voice(
                chat_id=config.ADMIN_ID,
                voice=message.voice.file_id,
                caption=user_info,
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )
        elif content_type == "sticker":
            # 贴纸：先发信息卡片，再发贴纸
            sent_msg = await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=user_info + "\n\n⬇️ 贴纸如下：",
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )
            await context.bot.send_sticker(
                chat_id=config.ADMIN_ID,
                sticker=message.sticker.file_id
            )
        elif content_type == "animation":
            # GIF 动图
            sent_msg = await context.bot.send_animation(
                chat_id=config.ADMIN_ID,
                animation=message.animation.file_id,
                caption=user_info,
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )
        elif content_type == "video_note":
            # 视频圈：先发信息卡片，再发视频圈
            sent_msg = await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=user_info + "\n\n⬇️ 视频圈如下：",
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )
            await context.bot.send_video_note(
                chat_id=config.ADMIN_ID,
                video_note=message.video_note.file_id
            )
        else:
            sent_msg = await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=user_info,
                parse_mode=ParseMode.HTML,
                reply_markup=build_action_keyboard(user.id)
            )

        # 保存消息映射
        await db.save_message(
            user_id=user.id,
            user_msg_id=message.message_id,
            forward_msg_id=sent_msg.message_id,
            content_type=content_type
        )

        # 更新消息计数
        await db.increment_msg_count(user.id)

        # 通知用户
        await message.reply_text("✅ 消息已送达，请耐心等待回复。")

    except Exception as e:
        await message.reply_text("❌ 消息发送失败，请稍后再试。")
        print(f"Error forwarding message: {e}")


def get_content_type(message) -> str:
    """获取消息内容类型"""
    if message.text:
        return "text"
    elif message.photo:
        return "photo"
    elif message.video:
        return "video"
    elif message.animation:
        return "animation"
    elif message.voice:
        return "voice"
    elif message.video_note:
        return "video_note"
    elif message.sticker:
        return "sticker"
    elif message.document:
        return "document"
    elif message.audio:
        return "audio"
    else:
        return "unknown"


def build_user_info_text(user, msg_count: int, text_content: str = None) -> str:
    """构建用户信息文本"""
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    name = get_user_display_name(user)
    username = get_username_display(user)

    info = f"""📨 <b>新留言</b>
━━━━━━━━━━━━━━"""

    if text_content:
        info += f"\n\n💬「{text_content}」\n\n━━━━━━━━━━━━━━"

    info += f"""
👤 用户: {name}
📛 用户名: {username}
📊 第 {msg_count} 条留言
⏰ 时间: {now}（北京时间）
━━━━━━━━━━━━━━"""

    return info


def build_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """构建操作按钮"""
    keyboard = [
        [InlineKeyboardButton("💬 回复", callback_data=f"reply_{user_id}")],
        [
            InlineKeyboardButton("👤 用户信息", callback_data=f"info_{user_id}"),
            InlineKeyboardButton("🚫 拉黑", callback_data=f"ban_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
