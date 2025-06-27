import os
import json
import gspread
import discord
from discord.ext import commands
from discord.ui import View, Button
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from discord.ext import tasks

json_str = os.getenv('GOOGLE_CREDENTIALS')
if not json_str:
    raise ValueError("❌ GOOGLE_CREDENTIALS 環境變數未設定")

json_data = json.loads(json_str)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json_data, scope)
client = gspread.authorize(creds)
member_sheet = client.open("虧虧135私車班表").worksheet("member")

def get_sheet_safe(date: str):
    try:
        return client.open("虧虧135私車班表").worksheet(date)
    except Exception as e:
        print(f"❌ 找不到工作表 {date}：{e}")
        return None

sheet_map = {}
start_date = datetime.strptime("6/30", "%m/%d")
for i in range(8):
    date = start_date + timedelta(days=i)
    date_str = f"{date.month}/{date.day}"
    sheet = get_sheet_safe(date_str)
    if sheet:
        sheet_map[date_str] = sheet

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="-", intents=intents)

def get_user_row_by_id(user_id):
    id_list = member_sheet.col_values(1)
    print(f"正在查找用戶 ID {user_id}，ID 列表：{id_list}")

    if str(user_id) in id_list:
        return id_list.index(str(user_id)) + 1
    return None

@bot.event
async def on_ready():
    print("✅ Bot 已上線")
    if not check_and_remind.is_running():
        check_and_remind.start()
    if not stay_awake.is_running():
        stay_awake.start()

@bot.command()
async def ref(ctx, 暱稱: str, 倍率: str, s6: str = None):
    user_id = str(ctx.author.id)

    try:
        float_倍率 = float(倍率)
    except ValueError:
        await ctx.send(f"{ctx.author.mention}，倍率為無效數字。")
        return

    if s6:
        try:
            float_s6 = float(s6)
        except ValueError:
            await ctx.send(f"{ctx.author.mention}，S6為無效數字。")
            return

    id_list = member_sheet.col_values(1)
    row = None
    for idx, uid in enumerate(id_list[1:], start=2):
        if uid == user_id:
            row = idx
            break

    if not row:
        row = len(id_list) + 1

    member_sheet.update_cell(row, 1, user_id)
    member_sheet.update_cell(row, 2, 暱稱)
    member_sheet.update_cell(row, 3, 倍率)
    if s6:
        member_sheet.update_cell(row, 4, s6)

    回覆訊息 = f"{ctx.author.mention} 已登記暱稱：{暱稱}，倍率：{倍率}"
    if s6:
        回覆訊息 += f"，S6：{s6}"
    await ctx.send(回覆訊息)

@bot.command()
async def add(ctx, 日期: str, 時段: str):
    if 日期 not in sheet_map:
        await ctx.reply("無效的日期。", mention_author=False)
        return

    try:
        start_hour, end_hour = map(int, 時段.split('-'))
        if not (0 <= start_hour < end_hour <= 24):
            raise ValueError
    except ValueError:
        await ctx.reply("請輸入有效的時間範圍。", mention_author=False)
        return

    day_sheet = sheet_map[日期]
    sheet = sheet_map.get(日期)
    user_id = str(ctx.author.id)

    row = get_user_row_by_id(user_id)
    if not row:
        await ctx.reply("請先登記倍率。", mention_author=False)
        return

    nickname = member_sheet.cell(row, 2).value
    倍率 = member_sheet.cell(row, 3).value

    if not nickname or not 倍率:
        await ctx.reply("未讀取到暱稱或倍率。", mention_author=False)
        return

    member_tag = f"{nickname}({倍率})"

    header = day_sheet.row_values(1)

    start_column = 8

    member_col = None
    for idx, val in enumerate(header[start_column-1:], start=start_column):
        if val == member_tag:
            member_col = idx
            break

    if not member_col:
        member_col = start_column
        if len(header) < member_col:
            header.extend([''] * (member_col - len(header)))
        if member_col > 26:
            member_col = 26
        
        day_sheet.update_cell(1, member_col, member_tag)

    for hour in range(start_hour, end_hour):
        label = f"{hour:02d}-{(hour+1):02d}"

        try:
            cell = day_sheet.find(label)
            row = cell.row
        except:
            await ctx.reply(f"找不到時間段 {label}，請確認工作表是否有該時間。", mention_author=False)
            return

        day_sheet.update_cell(row, member_col, nickname)

    await ctx.message.add_reaction("✅")

@bot.command()
async def dele(ctx, 日期: str, 時段: str):
    if 日期 not in sheet_map:
        await ctx.reply("無效的日期。", mention_author=False)
        return

    try:
        start_hour, end_hour = map(int, 時段.split('-'))
        if not (0 <= start_hour < end_hour <= 24):
            raise ValueError
    except ValueError:
        await ctx.reply("請輸入有效的時間範圍。", mention_author=False)
        return

    day_sheet = sheet_map[日期]
    sheet = sheet_map.get(日期)
    user_id = str(ctx.author.id)

    row = get_user_row_by_id(user_id)
    if not row:
        await ctx.reply("請先登記倍率。", mention_author=False)
        return

    nickname = member_sheet.cell(row, 2).value
    倍率 = member_sheet.cell(row, 3).value

    if not nickname or not 倍率:
        await ctx.reply("未讀取到暱稱或倍率。", mention_author=False)
        return

    member_tag = f"{nickname}({倍率})"

    header = day_sheet.row_values(1)

    start_column = 8

    member_col = None
    for idx, val in enumerate(header[start_column-1:], start=start_column):
        if val == member_tag:
            member_col = idx
            break

    if not member_col:
        await ctx.message.add_reaction("✅")
        return

    for hour in range(start_hour, end_hour):
        label = f"{hour:02d}-{(hour+1):02d}"

        try:
            cell = day_sheet.find(label)
            row = cell.row
        except:
            await ctx.reply(f"找不到時間段 {label}，請確認工作表是否有該時間。", mention_author=False)
            return

        day_sheet.update_cell(row, member_col, '')

    await ctx.message.add_reaction("✅")

@bot.command()
async def q(ctx, 日期: str, 時段: str):
    if 日期 not in sheet_map:
        await ctx.reply("無效的日期。", mention_author=False)
        return

    try:
        start_hour, end_hour = map(int, 時段.split('-'))
        if not (0 <= start_hour < end_hour <= 24):
            raise ValueError
    except ValueError:
        await ctx.reply("請輸入有效的時間範圍。", mention_author=False)
        return

    day_sheet = sheet_map[日期]
    time_label = f"{start_hour:02d}-{(start_hour + 1) % 24:02d}"

    try:
        cell = day_sheet.find(time_label)
        row = cell.row
    except:
        await ctx.reply(f"找不到時間段 {time_label}，請確認工作表是否有該時間。", mention_author=False)
        return

    members_data = day_sheet.get(f'C{row}:F{row}')
    row_data = members_data[0] if members_data else []

    message = f"{日期} {time_label}\n"
    message += "p1: 跑者虧虧\n"

    for idx in range(4):
        col_data = row_data[idx] if idx < len(row_data) else ''
        mentions = []

        if col_data.strip():
            names = col_data.strip().split()
            for name in names:
                try:
                    member_ids = member_sheet.col_values(2)
                    for i, n in enumerate(member_ids[1:], start=2):
                        if n == name:
                            user_id = member_sheet.cell(i, 1).value
                            mentions.append(f"<@{user_id}>")
                            break
                except:
                    continue

        message += f"p{idx + 2}: {' '.join(mentions)}\n"

    bot_msg = await ctx.send(message)
    await bot_msg.add_reaction("✅")

A_CHANNEL_ID = 1309944755886620702
B_CHANNEL_ID = 1309944822060023919

class ConfirmButton(View):
    def __init__(self, room_number):
        super().__init__(timeout=60)
        self.room_number = room_number

    @discord.ui.button(label="✅ 確認更新", style=discord.ButtonStyle.success)
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        b_channel = interaction.client.get_channel(B_CHANNEL_ID)
        if not b_channel:
            await interaction.response.send_message("❌ 找不到目標頻道 B。", ephemeral=True)
            return

        try:
            # 確保頻道名稱合法（只能有小寫字母、數字、-）
            safe_name = self.room_number.lower()
            await b_channel.edit(name=safe_name)
            await interaction.response.send_message(f"✅ 已將頻道名稱改為 `{safe_name}`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 更改頻道名稱失敗：{e}", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id == A_CHANNEL_ID:
        content = message.content.strip()
        if content.isdigit() and len(content) == 5:
            room_number = content
            view = ConfirmButton(room_number)
            await message.channel.send(
                f"💬 偵測到房號：`{room_number}`，請點擊下方按鈕以確認更改頻道名稱：",
                view=view
            )

    await bot.process_commands(message)

reminder_channel_id = 1309945039090225245

@tasks.loop(minutes=1)
async def check_and_remind():
    now = datetime.now()
    if now.minute != 50:
        return

    next_hour_time = now + timedelta(hours=1)
    hour = next_hour_time.hour
    time_label = f"{hour:02d}-{24 if hour == 23 else (hour + 1):02d}"

    if hour == 0:
        target_date = now + timedelta(days=1)
    else:
        target_date = now
    date_str = f"{target_date.month}/{target_date.day}"

    work_sheet = sheet_map.get(date_str)
    if not work_sheet:
        print(f"⚠️ 無法找到日期工作表 {date_str}")
        return

    try:
        time_column = work_sheet.col_values(1)
        row_index = next((i + 1 for i, val in enumerate(time_column) if val.strip() == time_label), None)
        if row_index is None:
            print(f"❌ 無法找到時間段 {time_label} 在工作表 {date_str}")
            return
        row_data = work_sheet.row_values(row_index)[2:6]
    except Exception as e:
        print(f"⚠️ 讀取工作表資料時錯誤: {e}")
        return

    message = f"{date_str} {time_label}\n"
    message += "p1: 跑者虧虧\n"

    for idx in range(4):
        col_data = row_data[idx] if idx < len(row_data) else ''
        mentions = []

        if col_data.strip():
            names = col_data.strip().split()
            for name in names:
                try:
                    name_col = member_sheet.col_values(2)[1:]
                    for i, n in enumerate(name_col, start=2):
                        if n == name:
                            user_id = member_sheet.cell(i, 1).value
                            mentions.append(f"<@{user_id}>")
                            break
                except Exception as e:
                    print(f"⚠️ 匹配 {name} 時發生錯誤: {e}")
                    continue

        message += f"p{idx + 2}: {' '.join(mentions) if mentions else '無'}\n"

    channel = bot.get_channel(reminder_channel_id)
    if channel:
        try:
            await channel.send(f"{message}")
        except Exception as e:
            print(f"⚠️ 發送提醒失敗: {e}")
    else:
        print("❌ 找不到提醒頻道，請確認 reminder_channel_id 是否正確")

@check_and_remind.before_loop
async def before_loop():
    await bot.wait_until_ready()

from discord.ext import tasks

keep_alive_channel_id = 1213889966204125194

@tasks.loop(minutes=15)
async def stay_awake():
    channel = bot.get_channel(keep_alive_channel_id)
    if channel:
        try:
            await channel.send("check")
        except Exception as e:
            print(f"⚠️ 發送保持活躍訊息時出錯: {e}")
    else:
        print("❌ 找不到保持活躍的頻道")

@stay_awake.before_loop
async def before_stay_awake():
    await bot.wait_until_ready()

bot.run(os.getenv("DISCORD_TOKEN"))
