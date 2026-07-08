import time
import telebot
from deltax import getKey  # Gọi trực tiếp các hàm từ file deltax.py kế bên

# Đã điền sẵn Token Bot của bạn vào đây
BOT_TOKEN = "8962766272:AAGxjnwxK7x3tRJ3_EnxmDVTWZ6HsgZG5tw"  
bot = telebot.TeleBot(BOT_TOKEN)

# Hàng đợi chống spam (Mỗi tài khoản gửi lệnh cách nhau ít nhất 15 giây)
user_cooldowns = {}
COOLDOWN_TIME = 15 

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    guide = (
        "🤖 **Bypass Helper Bot**\n\n"
        "📌 **Cách sử dụng:**\n"
        "Gửi lệnh theo cú pháp: `/bypass [LINK_CỦA_BẠN]`\n"
        "Ví dụ: `/bypass https://gateway.platoboost.com/a/8?id=...`\n\n"
        "⚠️ *Lưu ý:* Vui lòng không gửi liên tục để tránh hệ thống kích hoạt cơ chế bảo vệ."
    )
    bot.reply_to(message, guide, parse_mode="Markdown")

@bot.message_handler(commands=['bypass'])
def handle_bypass(message):
    user_id = message.from_user.id
    current_time = time.time()

    # Kiểm tra cooldown ngăn chặn spam lệnh làm nghẽn tiến trình
    if user_id in user_cooldowns:
        elapsed = current_time - user_cooldowns[user_id]
        if elapsed < COOLDOWN_TIME:
            remaining = int(COOLDOWN_TIME - elapsed)
            bot.reply_to(message, f"⏳ Vui lòng đợi thêm {remaining} giây để thực hiện yêu cầu tiếp theo.")
            return

    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "❌ Định dạng sai! Vui lòng dùng: `/bypass [ĐƯỜNG_LINK]`")
            return
        
        url = args[1].strip()
        status_msg = bot.reply_to(message, "🔄 Hệ thống đang ghi nhận thông tin và xử lý...", parse_mode="Markdown")
        user_cooldowns[user_id] = current_time
        
        # Hàm callback cập nhật trạng thái xử lý trực tiếp lên màn hình chat
        def update_status(msg):
            try:
                bot.edit_message_text(f"🔄 Trạng thái: _{msg}_", 
                                      chat_id=message.chat.id, 
                                      message_id=status_msg.message_id, 
                                      parse_mode="Markdown")
            except Exception:
                pass

        # Thực thi tiến trình lấy key
        result = getKey(url, verbose_cb=update_status)
        
        # Gửi trả kết quả cuối cùng cho người dùng
        if result and not result.startswith("bypass fail"):
            success_msg = (
                "✅ **Xử lý thành công!**\n\n"
                f"🔑 **Key nhận được:**\n`{result}`\n\n"
                "_*Nhấp vào chuỗi kí tự trên để tự động sao chép._"
            )
            bot.edit_message_text(success_msg, 
                                  chat_id=message.chat.id, 
                                  message_id=status_msg.message_id, 
                                  parse_mode="Markdown")
        else:
            bot.edit_message_text(f"❌ **Xử lý thất bại!** Đường dẫn không hợp lệ hoặc máy chủ bận.\nChi tiết: `{result}`", 
                                  chat_id=message.chat.id, 
                                  message_id=status_msg.message_id, 
                                  parse_mode="Markdown")
            
    except Exception as e:
        bot.reply_to(message, f"⚠️ Đã xảy ra lỗi không mong muốn: {str(e)}")

if __name__ == "__main__":
    print("Bot đang chạy công khai...")
    bot.infinity_polling()
