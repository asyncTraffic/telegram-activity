from aiogram.filters import Command, CommandObject
from keyboards.reply.adminkey import kbMainAdmin
from loader import *
from keyboards.inline.adminkeyinline import *
from utils.misc_func.bot_models import FSM
from loguru import logger
from utils.misc_func.otherfunc import is_non_negative, generate_short_uuid
from aiogram.types import ChatMemberAdministrator
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BotCommand, BotCommandScopeChat
from datetime import datetime, timedelta, timezone
import math
import random
import json
from data.config import db, COOLDOWN_MINUTES
from states.admin_state import AdminChatAccountAddStates, AdminChatAccountDeleteStates

@adminRouter.message(F.text == '🗂 Чаты')
async def chats_call_center_handler(msg: Message, state: FSM):
    await state.clear()
    chats = await db.get_all_chats()
    keyboard = view_chats_key(chats[:5], 0, len(chats[:5]), len(chats))
    text = (
        "<b>🗂 Чаты</b>\n\n"
        f"☎️ Всего чатов: {len(chats)}\n"
        "Вы можете просмотреть имеющиеся чаты или добавить новый по кнопкам ниже 👇"
    )
    await msg.answer(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'chatscc')
async def chats_callback_handler(call: CallbackQuery, state: FSM):
    await state.clear()
    chats = await db.get_all_chats()
    chats.reverse()
    keyboard = view_chats_key(chats[:5], 0, len(chats[:5]), len(chats))
    text = (
        "<b>🗂 Чаты</b>\n\n"
        f"☎️ Всего чатов: {len(chats)}\n"
        "Вы можете просмотреть имеющиеся чаты или добавить новый по кнопкам ниже 👇"
    )
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("list_cc_next_"))
async def list_chats_next_handler(call: CallbackQuery, state: FSM):
    step = int(call.data.replace("list_cc_next_", ""))
    chats = await db.get_all_chats()
    chats.reverse()
    if len(chats[step:step + 5]) == 0:
        await call.answer("Это последняя страница", show_alert=True)
        return
    keyboard = view_chats_key(chats[step:step + 5], step, len(chats[:step + 5]), len(chats))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("list_cc_back_"))
async def list_chats_back_handler(call: CallbackQuery, state: FSM):
    step = int(call.data.replace("list_cc_back_", ""))
    if step == 0:
        await call.answer("Это была последняя страница", show_alert=True)
        return
    await state.clear()
    chats = await db.get_all_chats()
    chats.reverse()
    keyboard = view_chats_key(chats[step - 5:step], step - 5, len(chats[:step]), len(chats))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'add_chat')
async def add_chat_handler(call: CallbackQuery, state: FSM):
    bot_info = await bot.get_me()
    username = bot_info.username
    url = (
        f'https://t.me/{username}?startgroup=true&admin=change_info+edit_messages+'
        'post_messages+delete_messages+restrict_members+invite_users+pin_messages+'
        'manage_topics+promote_members+anonymous+manage_chat'
    )
    text = (
        "<b>💭 Добавление чата</b>\n\n"
        "Для добавление чата выполните следующие действия:\n"
        "1. Включите темы в чате\n"
        "2. Воспользуйтесь кнопкой '🔰 Добавить в чат', добавьте бота в чат с правами администратора\n"
        f"3. Отправьте в чат команду <code>/addchat</code>\n\n"
        "<i>ℹ️ После этого чат добавится в базу и вы сможете приступить к его настройке</i>"
    )
    await call.message.edit_text(text, reply_markup=add_bot_in_chat(url))

@adminChatRouter.message(Command('addchat'))
async def add_chat_command_handler(msg: Message, command: CommandObject):
    bot_member = await bot.get_chat_member(chat_id=msg.chat.id, user_id=(await bot.get_me()).id)
    if isinstance(bot_member, ChatMemberAdministrator):
        success = await db.add_chat(msg.chat.id, msg.chat.title)
        await msg.reply('✅ Чат успешно добавлен' if success else '⚠️ Этот чат уже добавлен в базу')
    else:
        await msg.reply('⚠️ Бот должен быть администратором чата')

@adminRouter.callback_query(F.data.startswith('getcc_'))
async def get_chat_handler(call: CallbackQuery, state: FSM):
    await state.clear()
    chat_id = int(call.data.replace('getcc_', ''))
    chat_info = await db.get_chat_by_id(chat_id)
    chat_accounts_info = await db.get_all_account_chat_by_chat_id(chat_id)
    trigger_invite = '🟢 включен' if chat_info['trigger_invite'] else '🔴 выключен'
    trigger_time = '🟢 включен' if chat_info['trigger_time'] else '🔴 выключен'
    try:
        chat_bot_info = await bot.get_chat(chat_id=chat_id)
        logger.info(chat_bot_info.title)
    except Exception as e:
        logger.error(e)
    text = (
        f"💭 Чат: {chat_info['title']}\n"
        f"🗂 Аккаунтов: {len(chat_accounts_info)}\n"
        f"🔔 Триггер на вступление: {trigger_invite}\n"
        f"🔔 Триггер по времени: {trigger_time}"
    )
    await call.message.edit_text(text, reply_markup=chat_menu(str(chat_id), chat_info['trigger_invite'], chat_info['trigger_time']))

@adminRouter.callback_query(F.data.startswith("list_vacc_next_"))
async def list_accounts_next_handler(call: CallbackQuery, state: FSM):
    step, chat_id = map(int, str(call.data.replace("list_vacc_next_", "")).split('_'))
    accounts = await db.get_accounts_by_chat_id(chat_id)
    if len(accounts[step:step + 5]) == 0:
        await call.answer("Это последняя страница", show_alert=True)
        return
    keyboard = view_account_by_chat_id_key(chat_id, accounts[step:step + 5], step, len(accounts[:step + 5]), len(accounts))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("list_vacc_back_"))
async def list_accounts_back_handler(call: CallbackQuery, state: FSM):
    step, chat_id = map(int, str(call.data.replace("list_vacc_back_", "")).split('_'))
    if step == 0:
        await call.answer("Это была последняя страница", show_alert=True)
        return
    await state.clear()
    accounts = await db.get_accounts_by_chat_id(chat_id)
    keyboard = view_account_by_chat_id_key(chat_id, accounts[step - 5:step], step - 5, len(accounts[:step]), len(accounts))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('checkbuyer_'))
async def check_buyer_handler(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.replace('checkbuyer_', ''))
    chat_info = await db.get_chat_by_id(chat_id)
    accounts = await db.get_accounts_by_chat_id(chat_id)
    keyboard = view_account_by_chat_id_key(chat_id, accounts[:5], 0, len(accounts[:5]), len(accounts))
    text = f"<b>📄 Список аккаунтов в чате {chat_info['title']}</b>\n\n"
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('delacc_'))
async def delete_account_handler(call: CallbackQuery, state: FSM):
    account_id, chat_id = map(int, call.data.replace('delacc_', '').split('_'))
    account_info = await db.get_account_by_id(account_id)
    chat_info = await db.get_chat_by_id(chat_id)
    text = f"💭 Вы уверены, что хотите удалить аккаунт {account_info['name']} из чата {chat_info['title']}?"
    await call.message.edit_text(text, reply_markup=two_factor_del_chat_key(chat_id))

@adminRouter.callback_query(F.data.startswith('sucdelacc_'))
async def confirm_delete_account_handler(call: CallbackQuery, state: FSM):
    account_id, chat_id = map(int, call.data.replace('sucdelacc_', '').split('_'))
    chat_info = await db.get_chat_by_id(chat_id)
    account_info = await db.get_account_by_id(account_id)
    success = await db.delete_account_from_chat(chat_id, account_id)
    if success:
        text = f"🗑 Аккаунт {account_info['name']} удалён из чата {chat_info['title']}"
        await call.message.edit_text(text, reply_markup=back_fun_key(f'checkbuyer_{chat_id}'))
    else:
        await call.answer('⚠️ Не удалось удалить аккаунт из базы', show_alert=True)

@adminRouter.callback_query(F.data.startswith("trigger_invite_switch_"))
async def trigger_invite_switch(call: CallbackQuery):
    chat_id, new_val = map(int, call.data.split("_")[3:])
    await db.update_chat_trigger_invite(chat_id, bool(new_val))
    info = await db.get_chat_by_id(chat_id)
    chat_accounts_info = await db.get_all_account_chat_by_chat_id(chat_id)
    trigger_invite = '🟢 включен' if info['trigger_invite'] else '🔴 выключен'
    trigger_time = '🟢 включен' if info['trigger_time'] else '🔴 выключен'
    text = (
        f"💭 Чат: {info['title']}\n"
        f"🗂 Аккаунтов: {len(chat_accounts_info)}\n"
        f"🔔 Триггер на вступление: {trigger_invite}\n"
        f"🔔 Триггер по времени: {trigger_time}"
    )
    await call.message.edit_text(text, reply_markup=chat_menu(str(chat_id), info['trigger_invite'], info['trigger_time']))

@adminRouter.callback_query(F.data.startswith("trigger_time_switch_"))
async def trigger_time_switch(call: CallbackQuery):
    chat_id, new_val = map(int, call.data.split("_")[3:])
    await db.update_chat_trigger_time(chat_id, bool(new_val))
    info = await db.get_chat_by_id(chat_id)
    chat_accounts_info = await db.get_all_account_chat_by_chat_id(chat_id)
    trigger_invite = '🟢 включен' if info['trigger_invite'] else '🔴 выключен'
    trigger_time = '🟢 включен' if info['trigger_time'] else '🔴 выключен'
    text = (
        f"💭 Чат: {info['title']}\n"
        f"🗂 Аккаунтов: {len(chat_accounts_info)}\n"
        f"🔔 Триггер на вступление: {trigger_invite}\n"
        f"🔔 Триггер по времени: {trigger_time}"
    )
    await call.message.edit_text(text, reply_markup=chat_menu(str(chat_id), info['trigger_invite'], info['trigger_time']))

@adminRouter.callback_query(F.data.startswith("accounts_add_"))
async def start_add_accounts(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split("_")[-1])
    accounts = await db.get_accounts_not_in_chat(chat_id)
    await state.set_state(AdminChatAccountAddStates.selecting_accounts)
    await state.update_data(chat_id=chat_id, selected=[])
    keyboard = view_accounts_not_in_chat_key(chat_id, accounts[:5], 0, 5, len(accounts), selected=set())
    await call.message.edit_text("Выберите аккаунты для добавления:", reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("add_acc_next_"))
async def add_accounts_next(call: CallbackQuery, state: FSM):
    chat_id, start = map(int, call.data.split("_")[2:])
    data = await state.get_data()
    selected = set(data['selected'])
    accounts = await db.get_accounts_not_in_chat(chat_id)
    keyboard = view_accounts_not_in_chat_key(chat_id, accounts[start:start+5], start, 5, len(accounts), selected)
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("add_acc_back_"))
async def add_accounts_back(call: CallbackQuery, state: FSM):
    chat_id, start = map(int, call.data.split("_")[2:])
    prev = max(0, start - 5)
    data = await state.get_data()
    selected = set(data['selected'])
    accounts = await db.get_accounts_not_in_chat(chat_id)
    keyboard = view_accounts_not_in_chat_key(chat_id, accounts[prev:prev+5], prev, 5, len(accounts), selected)
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("select_acc_"))
async def select_account(call: CallbackQuery, state: FSM):
    chat_id, acc_id = map(int, call.data.split("_")[2:4])
    data = await state.get_data()
    selected = set(data['selected'])
    if acc_id in selected:
        selected.remove(acc_id)
    else:
        selected.add(acc_id)
    await state.update_data(selected=list(selected))
    start = data.get('page_start', 0)
    accounts = await db.get_accounts_not_in_chat(chat_id)
    keyboard = view_accounts_not_in_chat_key(chat_id, accounts[start:start+5], start, 5, len(accounts), selected)
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("submit_add_acc_"))
async def submit_add_accounts(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split("_")[-1])
    data = await state.get_data()
    selected_ids = data.get("selected", [])
    await state.clear()
    if not selected_ids:
        await call.answer("❌ Ничего не выбрано", show_alert=True)
        return
    invite = await bot.create_chat_invite_link(chat_id=chat_id, expire_date=None, member_limit=None)
    await db.add_accounts_to_chat(chat_id, selected_ids)
    for account_id in selected_ids:
        record = await db.get_telegram_account_by_id(account_id)
        await account_manager.join_chat_by_link(record["session_name"], invite.invite_link)

@adminRouter.callback_query(F.data.startswith("trash_accounts_"))
async def start_delete_accounts(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split("_")[-1])
    accounts = await db.get_accounts_in_chat(chat_id)
    await state.set_state(AdminChatAccountDeleteStates.deleting_accounts)
    await state.update_data(chat_id=chat_id, selected_del=[])
    keyboard = view_chat_account_delete_key(chat_id, accounts[:5], 0, 5, len(accounts), selected=set())
    await call.message.edit_text("Выберите аккаунты для удаления:", reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("complete_add_"))
async def complete_add_accounts(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split("_")[-1])
    data = await state.get_data()
    selected_ids = data.get("selected", [])
    await state.clear()
    if not selected_ids:
        await call.answer("❌ Ничего не выбрано", show_alert=True)
        return
    invite = await bot.create_chat_invite_link(chat_id=chat_id, expire_date=None, member_limit=None)
    for account_id in selected_ids:
        record = await db.get_telegram_account_by_account_id(account_id)
        success = await account_manager.join_chat_by_link(record["session_name"], invite.invite_link)
        unique_id = f'{chat_id}{account_id}'
        await db.add_accounts_to_chat(unique_id, chat_id, account_id)
        if not success:
            logger.warning(f"Не удалось войти аккаунту {record['session_name']}")
    await call.message.edit_text("✅ Аккаунты добавлены и присоединились к чату", reply_markup=back_fun_key(f'getcc_{chat_id}'))

@adminRouter.callback_query(F.data.startswith("complete_remove_"))
async def complete_remove_accounts(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split("_")[-1])
    data = await state.get_data()
    selected = data.get("selected", [])
    if not selected:
        await call.answer("❌ Ничего не выбрано", show_alert=True)
        return
    await db.remove_accounts_from_chat(chat_id, selected)
    await state.clear()
    await call.message.edit_text("✅ Аккаунты удалены из базы", reply_markup=back_fun_key(f'getcc_{chat_id}'))

@adminRouter.callback_query(F.data.startswith("remove_all_"))
async def remove_all_accounts(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split("_")[-1])
    await db.clear_accounts_from_chat(chat_id)
    await state.clear()
    await call.message.edit_text("✅ Аккаунты удалены из базы", reply_markup=back_fun_key(f'getcc_{chat_id}'))

@adminRouter.callback_query(F.data.startswith("accounts_rem_next_"))
async def remove_accounts_next(call: CallbackQuery, state: FSM):
    chat_id, start = map(int, call.data.split("_")[2:])
    data = await state.get_data()
    selected = set(data.get("selected", []))
    accounts = await db.get_accounts_in_chat(chat_id)
    keyboard = view_chat_account_delete_key(chat_id, accounts[start:start + 5], start=start, page_size=5, total=len(accounts), selected=selected)
    await state.update_data(start=start)
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("accounts_rem_back_"))
async def remove_accounts_back(call: CallbackQuery, state: FSM):
    chat_id, start = map(int, call.data.split("_")[2:])
    prev = max(0, start - 5)
    data = await state.get_data()
    selected = set(data.get("selected", []))
    accounts = await db.get_accounts_in_chat(chat_id)
    keyboard = view_chat_account_delete_key(chat_id, accounts[prev:prev + 5], start=prev, page_size=5, total=len(accounts), selected=selected)
    await state.update_data(start=prev)
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("toggle_rem_"))
async def toggle_remove_account(call: CallbackQuery, state: FSM):
    chat_id, acc_id, start = map(int, call.data.split("_")[2:5])
    data = await state.get_data()
    selected = set(data.get("selected", []))
    if acc_id in selected:
        selected.remove(acc_id)
    else:
        selected.add(acc_id)
    accounts = await db.get_accounts_in_chat(chat_id)
    keyboard = view_chat_account_delete_key(chat_id, accounts[start:start + 5], start=start, page_size=5, total=len(accounts), selected=selected)
    await state.update_data(selected=list(selected))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminChatRouter.message(F.new_chat_members)
async def on_new_members(msg: Message):
    chat_id = msg.chat.id
    info = await db.get_chat_invite_info(chat_id)
    if not info or not info['trigger_invite']:
        return
    last_trigger = info['last_invite_trigger']
    now = datetime.now()
    if last_trigger and (now - last_trigger) < timedelta(minutes=COOLDOWN_MINUTES):
        logger.info('В откате')
        return
    await db.update_chat_last_invite(chat_id)
    accounts = await db.get_accounts_in_chat(chat_id)
    if not accounts:
        return
    dialogs = await db.get_all_dialogs()
    valid_dialogs = [d for d in dialogs if d['num_accounts'] <= len(accounts)]
    if not valid_dialogs:
        return
    dialog = random.choice(valid_dialogs)
    messages = dialog["messages"]
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError:
            messages = []
    dialog_text = "\n".join(f"[{m['role']}] {m['text']}" for m in messages)
    try:
        await account_manager.play_dialog(chat_id, dialog_text, dialog['num_accounts'])
    except Exception as e:
        logger.error(f"Ошибка при проигрывании диалога в чате {chat_id}: {e}")

@adminRouter.callback_query(F.data.startswith('trash_chat_'))
async def trash_chat_handler(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split('_')[-1])
    chat_info = await db.get_chat_by_id(chat_id)
    text = f"Вы уверены, что хотите удалить чат <b>{chat_info['title']}</b>?"
    await call.message.edit_text(text, reply_markup=two_factor_key_del_chat(chat_id))

@adminRouter.callback_query(F.data.startswith('suctrash_chat_'))
async def confirm_trash_chat_handler(call: CallbackQuery, state: FSM):
    chat_id = int(call.data.split('_')[-1])
    chat_info = await db.get_chat_by_id(chat_id)
    await db.delete_chat(chat_id)
    await call.message.edit_text(
        f"Чат <b>{chat_info['title']}</b> успешно удалён из базы",
        reply_markup=back_fun_key('chatscc')
    )