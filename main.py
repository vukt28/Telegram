import MetaTrader5 as mt5
import threading
import os
import json
import requests
import time
 
update_id = None
user_state = {}
 
os.system('cls')
 
 
# Load settings
def load_settings(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' is not a valid JSON.")
        return {}
 
 
def update_settings(file_path, chat_id, key, value):
    """
    Cập nhật thông tin trong file cấu hình JSON cho một người dùng cụ thể.
 
    :param file_path: Đường dẫn đến file JSON cần cập nhật.
    :param chat_id: ID của người dùng cần cập nhật thông tin.
    :param key: Khóa thông tin cần cập nhật (ví dụ: 'notify_threshold' hoặc 'accounts').
    :param value: Giá trị mới cho khóa thông tin.
    """
    data = load_settings(file_path)
    if str(chat_id) in data['users']:
        data['users'][str(chat_id)][key] = value
        save_settings(file_path, data)
 
 
# Save settings into JSON file
def save_settings(file_path, data):
    """
    Lưu dữ liệu cấu hình vào file JSON. Kiểm tra tính hợp lệ trước khi ghi.
 
    :param file_path: Đường dẫn đến file JSON cần lưu.
    :param data: Dữ liệu cấu hình cần lưu.
    """
    try:
        # Kiểm tra tính hợp lệ của JSON trước khi ghi
        json_data = json.dumps(data, indent=4)
        with open(file_path, 'w') as file:
            file.write(json_data)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error writing to file '{file_path}': {e}")
 
 
# Notify via Telegram
def telegram_send_message(bot_api, chat_id, message):
    url = f'https://api.telegram.org/bot{bot_api}/sendMessage'
    payload = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message via Telegram. Error: {e}")
 
 
# Get updates from Telegram
def telegram_get_updates(bot_api):
    global update_id
    url = f'https://api.telegram.org/bot{bot_api}/getUpdates'
    params = {'timeout': 100, 'offset': update_id}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting updates: {e}")
        return None
 
 
# Check if user is registered
def is_registered_user(chat_id, data):
    return str(chat_id) in data.get('users', {})
 
 
# Handle user state
def handle_user_state(bot_api, chat_id, message, data):
    state = user_state.get(chat_id, None)
 
    if message.startswith('/'):
        user_state.pop(chat_id, None)
        telegram_handle_command(bot_api, chat_id, message, data)
        return
 
    if state is None:
        return
 
    user_data = data['users'].get(str(chat_id), {})
    if not user_data:
        telegram_send_message(bot_api, chat_id, "Không thể tìm thấy dữ liệu người dùng. Vui lòng thử lại.")
        return
 
    user_accounts = user_data.get('accounts', [])
 
    # Xử lý thêm tài khoản
    if state.get('action') == 'add':
        if 'username' not in state:
            state['username'] = message
            telegram_send_message(bot_api, chat_id, "Nhập mật khẩu:")
        elif 'password' not in state:
            state['password'] = message
            telegram_send_message(bot_api, chat_id, "Nhập tên server:")
        elif 'server' not in state:
            state['server'] = message
            telegram_send_message(bot_api, chat_id, "Chọn loại tài khoản: 1 - USD, 2 - Cent:")
        elif 'account_type' not in state:
            if message == '1':
                state['account_type'] = 'USD'
            elif message == '2':
                state['account_type'] = 'Cent'
            else:
                telegram_send_message(bot_api, chat_id, "Lựa chọn không hợp lệ. Vui lòng nhập 1 (USD) hoặc 2 (Cent):")
                return
            telegram_send_message(bot_api, chat_id, "Nhập nickname cho tài khoản (Lưu ý: không dấu):")
        elif 'nickname' not in state:
            state['nickname'] = message
            # Sau khi đã có đầy đủ thông tin, lưu tài khoản vào danh sách
            user_accounts.append({
                "username": state['username'],
                "password": state['password'],
                "server": state['server'],
                "account_type": state['account_type'],
                "nickname": state['nickname']
            })
            update_settings("settings.json", chat_id, 'accounts', user_accounts)
            telegram_send_message(bot_api, chat_id, "Đã thêm thành công tài khoản vào danh sách quản lý.")
            user_state.pop(chat_id)
 
    # Xử lý chỉnh sửa tài khoản
    elif state.get('action') == 'edit':
        if 'account_index' not in state:
            try:
                account_index = int(message) - 1
                if 0 <= account_index < len(user_accounts):
                    state['account_index'] = account_index
                    telegram_send_message(bot_api, chat_id, f"Bạn đang thay đổi tài khoản trading {user_accounts[account_index].get('nickname', user_accounts[account_index]['username'])}.\nNhập số tài khoản mới:")
                else:
                    telegram_send_message(bot_api, chat_id, "Số tài khoản không hợp lệ. Vui lòng thử lại.")
            except ValueError:
                telegram_send_message(bot_api, chat_id, "Hãy nhập một số thứ tự tài khoản hợp lệ.")
        elif 'username' not in state:
            state['username'] = message
            telegram_send_message(bot_api, chat_id, "Nhập mật khẩu mới:")
        elif 'password' not in state:
            state['password'] = message
            telegram_send_message(bot_api, chat_id, "Nhập tên server mới:")
        elif 'server' not in state:
            state['server'] = message
            telegram_send_message(bot_api, chat_id, "Chọn loại tài khoản: 1 - USD, 2 - Cent:")
        elif 'account_type' not in state:
            if message == '1':
                state['account_type'] = 'USD'
            elif message == '2':
                state['account_type'] = 'Cent'
            else:
                telegram_send_message(bot_api, chat_id, "Lựa chọn không hợp lệ. Vui lòng nhập 1 (USD) hoặc 2 (Cent):")
                return
            telegram_send_message(bot_api, chat_id, "Nhập biệt danh cho tài khoản (nickname):")
        elif 'nickname' not in state:
            state['nickname'] = message
            # Sau khi cập nhật thông tin tài khoản
            account = user_accounts[state['account_index']]
            account['username'] = state['username']
            account['password'] = state['password']
            account['server'] = state['server']
            account['account_type'] = state['account_type']
            account['nickname'] = state['nickname']
            update_settings("settings.json", chat_id, 'accounts', user_accounts)
            telegram_send_message(bot_api, chat_id, "Tài khoản trading đã được cập nhật thành công.")
            user_state.pop(chat_id)
 
    # Xử lý xóa tài khoản
    elif state.get('action') == 'delete':
        try:
            account_index = int(message) - 1
            if 0 <= account_index < len(user_accounts):
                deleted_account = user_accounts.pop(account_index)
                update_settings("settings.json", chat_id, 'accounts', user_accounts)
                telegram_send_message(bot_api, chat_id, f"Tài khoản trading {deleted_account['username']} đã được xóa thành công.")
            else:
                telegram_send_message(bot_api, chat_id, "Số tài khoản không hợp lệ. Vui lòng thử lại.")
        except ValueError:
            telegram_send_message(bot_api, chat_id, "Hãy nhập một số thứ tự tài khoản hợp lệ.")
        user_state.pop(chat_id)
 
    # Xử lý cập nhật settings
    elif state.get('action') == 'settings':
        try:
            new_threshold = int(message)
            data['users'][str(chat_id)]['notify_threshold'] = new_threshold
            update_settings("settings.json", chat_id, 'notify_threshold', new_threshold)
            telegram_send_message(bot_api, chat_id, f"Ngưỡng cảnh báo mới đã được cập nhật: {new_threshold}.")
            user_state.pop(chat_id)
        except ValueError:
            telegram_send_message(bot_api, chat_id, "Hãy nhập một số hợp lệ.")
 
 
def telegram_handle_command(bot_api, chat_id, command, data):
    if not is_registered_user(chat_id, data):
        telegram_send_message(bot_api, chat_id, f"Tài khoản {chat_id} của bạn chưa được đăng ký. Liên hệ với quản trị viên.")
        return
 
    user_state.pop(chat_id, None)  # Clear current state
 
    user_accounts = data['users'][str(chat_id)]['accounts']
 
    if command == '/update':
        if not user_accounts:
            telegram_send_message(bot_api, chat_id, "Không có tài khoản trading trong danh sách quản lý.")
            return
        monitor_all_accounts(user_accounts, bot_api, chat_id, data, send_summary=True)
 
    elif command == '/add':
        telegram_send_message(bot_api, chat_id, "Nhập số tài khoản trading bạn muốn quản lý:")
        user_state[chat_id] = {'action': 'add'}
 
    elif command == '/edit':
        if not user_accounts:
            telegram_send_message(bot_api, chat_id, "Không có tài khoản nào để chỉnh sửa.")
            return
        accounts_list = "\n".join([f"{i + 1}: {acc.get('nickname', acc['username'])}" for i, acc in enumerate(user_accounts)])
        telegram_send_message(bot_api, chat_id, f"Chọn tài khoản cần chỉnh sửa (Nhập số thứ tự):\n{accounts_list}")
        user_state[chat_id] = {'action': 'edit'}
 
    elif command == '/delete':
        if not user_accounts:
            telegram_send_message(bot_api, chat_id, "Không có tài khoản nào để xóa.")
            return
        accounts_list = "\n".join([f"{i + 1}: {acc.get('nickname', acc['username'])}" for i, acc in enumerate(user_accounts)])
        telegram_send_message(bot_api, chat_id, f"Chọn tài khoản cần xóa (Nhập số thứ tự):\n{accounts_list}")
        user_state[chat_id] = {'action': 'delete'}
 
    elif command == '/settings':
        notify_threshold = data['users'][str(chat_id)].get('notify_threshold', 0)
        telegram_send_message(bot_api, chat_id, f"Bot sẽ gửi thông báo khi tài khoản trading có số lệnh Buy hoặc Sell lớn hơn {notify_threshold}. \nNhập số mới để thay đổi:")
        user_state[chat_id] = {'action': 'settings'}
 
    else:
        telegram_send_message(bot_api, chat_id, f"Lệnh không hợp lệ: {command}")
 
 
# Process updates from Telegram
def telegram_process_updates(bot_api, data):
    global update_id
    updates = telegram_get_updates(bot_api)
    if updates and "result" in updates:
        for update in updates['result']:
            update_id = update['update_id'] + 1
            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                command = update['message']['text']
                handle_user_state(bot_api, chat_id, command, data)
 
 
# Login to MetaTrader 5 account
def login_to_mt5_account(account, bot_api, chat_id, data):
    username = int(account['username'])
    password = account['password']
    server = account['server']
    path = data["settings"]['mt5_path']
 
    try:
        # Initialize MetaTrader 5
        mt5_init = mt5.initialize(login=username, password=password, server=server, path=path)
        if not mt5_init:
            telegram_send_message(bot_api, chat_id, f"Failed to initialize MT5 for account {username}.")
            return False
 
        # Login to the account
        mt5_login = mt5.login(login=username, password=password, server=server)
        if not mt5_login:
            telegram_send_message(bot_api, chat_id, f"Login failed for account {username}.")
            return False
 
        return True
 
    except Exception as e:
        telegram_send_message(bot_api, chat_id, f"Error logging into MetaTrader 5: {e}")
        return False
 
 
def monitor_all_accounts(user_data, bot_api, chat_id, data, send_summary=False):
    if not isinstance(user_data, list):
        telegram_send_message(bot_api, chat_id, "Lỗi: Dữ liệu người dùng không hợp lệ.")
        return
 
    total_balance = 0
    total_equity = 0
    account_summaries = []
    alert_messages = []
    notify_threshold = data['users'][str(chat_id)].get('notify_threshold', 0)
 
    for account in user_data:
        if not login_to_mt5_account(account, bot_api, chat_id, data):
            continue
 
        account_info = mt5.account_info()
        if account_info is None:
            telegram_send_message(bot_api, chat_id, f"Could not retrieve account info for {account.get('nickname', account['username'])}")
            mt5.shutdown()  # Đảm bảo tắt kết nối trước khi tiếp tục vòng lặp
            continue
 
        # Kiểm tra loại tài khoản và chuyển đổi nếu cần
        account_type = account.get('account_type', 'USD').lower()
 
        account_balance = account_info.balance
        account_equity = account_info.equity
        positions = mt5.positions_get()
        current_profit = sum(pos.profit for pos in positions )
 
        total_balance += account_balance if account_type != 'cent' else account_info.balance / 100
        total_equity += account_equity if account_type != 'cent' else account_info.equity / 100
 
        # Lấy thông tin về các lệnh
        total_buy_positions = sum(1 for pos in positions if pos.type == mt5.ORDER_TYPE_BUY)
        total_sell_positions = sum(1 for pos in positions if pos.type == mt5.ORDER_TYPE_SELL)
 
        # Tạo bản tóm tắt tài khoản, mỗi thông tin một dòng
 
        account_summaries.append(
            f"{account.get('nickname', account['username'])}:\n"
            f"Balance: {account_balance:.2f}\n"
            f"Equity: {account_equity:.2f}\n"
            f"Buy: {total_buy_positions}\n"
            f"Sell: {total_sell_positions}\n"
            f"P/L: {current_profit:.2f}"
        )
 
        # Nếu số lượng Buy hoặc Sell lệnh vượt quá notify_threshold, thêm thông báo cảnh báo
        if not send_summary and (total_buy_positions > notify_threshold or total_sell_positions > notify_threshold):
            alert_messages.append(
                f"Cảnh báo: Tài khoản {account.get('nickname', account['username'])} có số lượng lệnh mở vượt quá ngưỡng {notify_threshold}:\n"
                f"Balance: {account_balance:.2f}\n"
                f"Equity: {account_equity:.2f}\n"
                f"Buy: {total_buy_positions}\n"
                f"Sell: {total_sell_positions}\n"
                f"P/L: {current_profit:.2f}"
            )
        mt5.shutdown()  # Đảm bảo tắt kết nối MT5 sau khi xử lý xong mỗi tài khoản
 
    # Chỉ gửi bản tóm tắt khi được yêu cầu
    if send_summary:
        summary_message = (
                f"Total Balance: {total_balance:.2f} \nTotal Equity: {total_equity:.2f}\n\n" +
                "\n\n".join(account_summaries)
        )
        telegram_send_message(bot_api, chat_id, summary_message)
 
    # Gửi các cảnh báo nếu có trong khoảng thời gian check_interval
    if alert_messages:
        for alert in alert_messages:
            telegram_send_message(bot_api, chat_id, alert)
 
 
def periodic_check(bot_api, data):
    while True:
        for chat_id, user_data in data.get("users", {}).items():
            # Kiểm tra định kỳ và gửi thông báo khi cần
            monitor_all_accounts(user_data.get("accounts", []), bot_api, chat_id, data, send_summary=False)
 
        check_interval = data["settings"].get("check_interval", 600)
        time.sleep(check_interval)
 
 
# Main function
if __name__ == '__main__':
    data = load_settings("settings.json")
    bot_api = data.get("settings", {}).get("bot_api")
 
    if not bot_api:
        print("Error: Bot API key is missing.")
    else:
        # Chạy hàm kiểm tra định kỳ trên một luồng riêng
        check_thread = threading.Thread(target=periodic_check, args=(bot_api, data))
        check_thread.start() 
 
        while True:
            telegram_process_updates(bot_api, data)
