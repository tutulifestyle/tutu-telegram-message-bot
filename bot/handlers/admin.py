from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from bot.config import config
from bot.database import db

# 会话状态
WAITING_REPLY = 1


def is_admin(user_id: int) -> bool:
    """检查是否是管理员"""
    return user_id == config.ADMIN_ID


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理内联按钮回调"""
    query = update.callback_query
    user = update.effective_user

    if not is_admin(user.id):
        await query.answer("⚠️ 无权限", show_alert=True)
        return

    await query.answer()

    data = query.data
    parts = data.split("_", 1)
    action = parts[0]
    target_user_id = int(parts[1]) if len(parts) > 1 else None

    if action == "reply":
        await handle_reply_button(query, context, target_user_id)
    elif action == "ban":
        await handle_ban_button(query, context, target_user_id)
    elif action == "unban":
        await handle_unban_button(query, context, target_user_id)
    elif action == "info":
        await handle_info_button(query, context, target_user_id)
    elif action == "cancelreply":
        await handle_cancel_reply(query, context)


async def handle_reply_button(query, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    """处理回复按钮"""
    # 保存目标用户 ID 到 context
    context.user_data["reply_to_user"] = target_user_id
    context.user_data["reply_info_msg_id"] = query.message.message_id

    # 获取用户信息
    user_info = await db.get_user(target_user_id)
    if user_info:
        name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "未知"
    else:
        name = "未知用户"

    keyboard = [[InlineKeyboardButton("❌ 取消回复", callback_data="cancelreply_0")]]

    await query.message.reply_text(
        f"💬 正在回复用户 <b>{name}</b>\n\n"
        f"请发送您的回复内容：",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_ban_button(query, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    """处理拉黑按钮"""
    user_info = await db.get_user(target_user_id)

    if not user_info:
        await query.message.reply_text("❌ 用户不存在")
        return

    if user_info.get("is_banned"):
        await query.message.reply_text("⚠️ 该用户已被拉黑")
        return

    # 拉黑用户
    await db.ban_user(target_user_id, "管理员手动拉黑")

    name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "未知"

    keyboard = [[InlineKeyboardButton("✅ 解除拉黑", callback_data=f"unban_{target_user_id}")]]

    await query.message.reply_text(
        f"🚫 已拉黑用户 <b>{name}</b> (ID: <code>{target_user_id}</code>)",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_unban_button(query, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    """处理解除拉黑按钮"""
    user_info = await db.get_user(target_user_id)

    if not user_info:
        await query.message.reply_text("❌ 用户不存在")
        return

    if not user_info.get("is_banned"):
        await query.message.reply_text("⚠️ 该用户未被拉黑")
        return

    await db.unban_user(target_user_id)

    name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "未知"

    await query.message.reply_text(
        f"✅ 已解除拉黑用户 <b>{name}</b> (ID: <code>{target_user_id}</code>)",
        parse_mode=ParseMode.HTML
    )


async def handle_info_button(query, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    """处理用户信息按钮"""
    user_info = await db.get_user(target_user_id)

    if not user_info:
        await query.message.reply_text("❌ 用户不存在")
        return

    msg_count = await db.get_user_message_count(target_user_id)
    today_count = await db.get_today_msg_count(target_user_id)

    name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "未知"
    username = user_info.get('username')
    username_display = f"@{username}" if username else "无"
    banned_status = "🚫 已拉黑" if user_info.get("is_banned") else "✅ 正常"
    ban_reason = user_info.get("ban_reason") or "无"
    created_at = user_info.get("created_at", "未知")

    # 生成私聊链接
    if username:
        chat_link = f"https://t.me/{username}"
    else:
        chat_link = f"tg://user?id={target_user_id}"

    info_text = f"""👤 <b>用户详情</b>
━━━━━━━━━━━━━━
📛 昵称: {name}
🆔 ID: <code>{target_user_id}</code>
📛 用户名: {username_display}
🔗 私聊: <a href="{chat_link}">点击打开</a>
━━━━━━━━━━━━━━
📊 总留言数: {msg_count} 条
📅 今日留言: {today_count} 条
📆 首次使用: {created_at}
━━━━━━━━━━━━━━
📌 状态: {banned_status}"""

    if user_info.get("is_banned"):
        info_text += f"\n📝 拉黑原因: {ban_reason}"

    # 根据状态显示不同按钮
    if user_info.get("is_banned"):
        keyboard = [[InlineKeyboardButton("✅ 解除拉黑", callback_data=f"unban_{target_user_id}")]]
    else:
        keyboard = [
            [
                InlineKeyboardButton("💬 回复", callback_data=f"reply_{target_user_id}"),
                InlineKeyboardButton("🚫 拉黑", callback_data=f"ban_{target_user_id}"),
            ]
        ]

    await query.message.reply_text(
        info_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_cancel_reply(query, context: ContextTypes.DEFAULT_TYPE):
    """取消回复"""
    context.user_data.pop("reply_to_user", None)
    context.user_data.pop("reply_info_msg_id", None)

    await query.message.edit_text("❌ 已取消回复")


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理管理员发送的消息（用于回复用户）"""
    message = update.message
    user = update.effective_user

    if not is_admin(user.id):
        return

    # 检查是否在回复模式
    reply_to_user = context.user_data.get("reply_to_user")

    if reply_to_user:
        # 发送回复给用户
        try:
            if message.text:
                await context.bot.send_message(
                    chat_id=reply_to_user,
                    text=f"📩 收到回复：\n\n{message.text}"
                )
            elif message.photo:
                await context.bot.send_photo(
                    chat_id=reply_to_user,
                    photo=message.photo[-1].file_id,
                    caption=f"📩 收到回复：\n\n{message.caption or ''}"
                )
            elif message.video:
                await context.bot.send_video(
                    chat_id=reply_to_user,
                    video=message.video.file_id,
                    caption=f"📩 收到回复：\n\n{message.caption or ''}"
                )
            else:
                await message.reply_text("❌ 暂不支持此类型的回复，请发送文字或图片")
                return

            # 清除回复状态
            context.user_data.pop("reply_to_user", None)
            context.user_data.pop("reply_info_msg_id", None)

            await message.reply_text("✅ 回复已发送")

        except Exception as e:
            await message.reply_text(f"❌ 发送失败：{e}")

    # 如果是回复转发的消息
    elif message.reply_to_message:
        # 尝试通过回复的消息找到原用户
        reply_msg_id = message.reply_to_message.message_id

        # 查找消息映射
        msg_record = await db.get_message_by_forward_id(reply_msg_id)

        if msg_record:
            target_user_id = msg_record["user_id"]
            try:
                if message.text:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"📩 收到回复：\n\n{message.text}"
                    )
                elif message.photo:
                    await context.bot.send_photo(
                        chat_id=target_user_id,
                        photo=message.photo[-1].file_id,
                        caption=f"📩 收到回复：\n\n{message.caption or ''}"
                    )
                else:
                    await message.reply_text("❌ 暂不支持此类型的回复")
                    return

                await message.reply_text("✅ 回复已发送")

            except Exception as e:
                await message.reply_text(f"❌ 发送失败：{e}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看统计信息"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    stats = await db.get_stats()

    text = f"""📊 <b>统计信息</b>
━━━━━━━━━━━━━━
👥 总用户数: {stats['total_users']}
💬 总留言数: {stats['total_messages']}
📅 今日留言: {stats['today_messages']}
🚫 已拉黑用户: {stats['banned_users']}
━━━━━━━━━━━━━━
⏰ 统计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """拉黑用户命令"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text("用法: /ban <用户ID> [原因]")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ 无效的用户 ID")
        return

    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "管理员手动拉黑"

    user_info = await db.get_user(target_user_id)
    if not user_info:
        await update.message.reply_text("❌ 用户不存在")
        return

    await db.ban_user(target_user_id, reason)

    name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "未知"

    keyboard = [[InlineKeyboardButton("✅ 解除拉黑", callback_data=f"unban_{target_user_id}")]]

    await update.message.reply_text(
        f"🚫 已拉黑用户 <b>{name}</b> (ID: <code>{target_user_id}</code>)\n原因: {reason}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """解除拉黑命令"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text("用法: /unban <用户ID>")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ 无效的用户 ID")
        return

    user_info = await db.get_user(target_user_id)
    if not user_info:
        await update.message.reply_text("❌ 用户不存在")
        return

    await db.unban_user(target_user_id)

    name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "未知"

    await update.message.reply_text(
        f"✅ 已解除拉黑用户 <b>{name}</b> (ID: <code>{target_user_id}</code>)",
        parse_mode=ParseMode.HTML
    )
