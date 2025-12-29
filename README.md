# Telegram Message Bot

A simple Telegram private message forwarding bot. Users send messages to the bot, and the admin receives notifications and can reply directly.

一个简洁的 Telegram 私信留言转发机器人，用户给 Bot 发消息，管理员收到通知并可直接回复。

## Features / 功能特性

- **Message Forwarding / 消息转发**: User messages are forwarded to admin with complete user info
- **Inline Buttons / 内联按钮**: Reply or block users with one click
- **Rate Limiting / 频率限制**: Prevent spam (per-minute and daily limits)
- **Blacklist / 黑名单**: Block/unblock malicious users
- **Message Filtering / 消息过滤**: Support text, images, voice; block files (security)

## Message Preview / 消息预览

```
📨 新留言
━━━━━━━━━━━━━━

💬「Hello, this is a test message」

━━━━━━━━━━━━━━
👤 用户: John
📛 用户名: @john_doe
📊 第 1 条留言
⏰ 时间: 2025-01-01 12:00:00（北京时间）
━━━━━━━━━━━━━━

┌─────────────────────────┐
│        💬 回复           │
├────────────┬────────────┤
│ 👤 用户信息 │  🚫 拉黑    │
└────────────┴────────────┘
```

## Quick Start / 快速开始

### 1. Create Bot / 创建 Bot

1. Find [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` to create a bot
3. Save the Token

### 2. Get Your Telegram ID / 获取你的 Telegram ID

1. Find [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send any message to get your numeric ID

### 3. Configure / 配置

```bash
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_telegram_id

# Optional / 可选
RATE_LIMIT_PER_MINUTE=3
RATE_LIMIT_PER_DAY=20
COOLDOWN_MINUTES=5
```

### 4. Deploy with Docker / Docker 部署

```bash
# Build and start / 构建并启动
docker-compose up -d

# View logs / 查看日志
docker-compose logs -f

# Stop / 停止
docker-compose down
```

### 5. Run Locally / 本地运行

```bash
pip install -r requirements.txt
python -m bot.main
```

## Usage / 使用方法

### For Users / 用户端

- `/start` - Start using the bot
- `/help` - Help information
- Send any message to leave a message

### For Admin / 管理员端

**Button Operations / 按钮操作:**
- Click `💬 回复` - Enter reply mode
- Click `🚫 拉黑` - Block the user
- Click `👤 用户信息` - View user details

**Commands / 命令:**
- `/stats` - View statistics
- `/ban <user_id> [reason]` - Block user
- `/unban <user_id>` - Unblock user

## Configuration / 配置项

| Config | Required | Default | Description |
|--------|----------|---------|-------------|
| BOT_TOKEN | Yes | - | Bot Token from @BotFather |
| ADMIN_ID | Yes | - | Admin's Telegram ID |
| RATE_LIMIT_PER_MINUTE | No | 3 | Max messages per minute |
| RATE_LIMIT_PER_DAY | No | 20 | Max messages per day |
| COOLDOWN_MINUTES | No | 5 | Cooldown time in minutes |

## Project Structure / 项目结构

```
telegram-message-bot/
├── bot/
│   ├── main.py           # Entry point
│   ├── config.py         # Configuration
│   ├── database.py       # SQLite database
│   └── handlers/
│       ├── user.py       # User message handling
│       └── admin.py      # Admin operations
├── data/                 # Data directory
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## License

MIT License
