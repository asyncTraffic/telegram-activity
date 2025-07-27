import re
from pathlib import Path
import json
from aiogram import F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from utils.misc_func.bot_models import FSM
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from loader import adminRouter, db, account_manager, bot
from keyboards.inline.adminkeyinline import *
from states.admin_state import AdminAccountStates, AdminUpdateTextMedia
from io import BytesIO
from utils.misc_func.otherfunc import filter_by_add_id, createMediaGroupByPath

@adminRouter.message(F.text == '👤 Аккаунты')
async def accounts_handler(msg: Message, state: FSM):
    await state.clear()
    accounts = await db.get_all_telegram_accounts()
    keyboard = view_accounts_key(accounts[:5], start_index=0, page_size=5, total=len(accounts))
    text = (
        "<b>👤 Аккаунты</b>\n\n"
        f"Всего аккаунтов: {len(accounts)}\n"
        "Выберите аккаунт или добавьте новый:"
    )
    await msg.answer(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'accounts_all')
async def accounts_all_handler(call: CallbackQuery, state: FSM):
    await state.clear()
    accounts = await db.get_all_telegram_accounts()
    keyboard = view_accounts_key(accounts[:5], start_index=0, page_size=5, total=len(accounts))
    text = (
        "<b>👤 Аккаунты</b>\n\n"
        f"Всего аккаунтов: {len(accounts)}\n"
        "Выберите аккаунт или добавьте новый:"
    )
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('list_acc_next_'))
async def list_accounts_next(call: CallbackQuery, state: FSM):
    start_index = int(call.data.split('_')[-1])
    accounts = await db.get_all_telegram_accounts()
    if start_index >= len(accounts):
        await call.answer("Это последняя страница", show_alert=True)
        return
    keyboard = view_accounts_key(accounts[start_index:start_index+5], start_index=start_index, page_size=5, total=len(accounts))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('list_acc_back_'))
async def list_accounts_back(call: CallbackQuery, state: FSM):
    start_index = int(call.data.split('_')[-1])
    prev_index = max(0, start_index - 5)
    accounts = await db.get_all_telegram_accounts()
    keyboard = view_accounts_key(accounts[prev_index:prev_index+5], start_index=prev_index, page_size=5, total=len(accounts))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('getacc_'))
async def get_account(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split('_')[-1])
    account = await db.get_telegram_account_by_id(account_id)
    if not account:
        await call.answer("Аккаунт не найден", show_alert=True)
        return
    proxy = (
        f"{account['proxy']['type']}://{account['proxy']['username']}:{account['proxy']['password']}@"
        f"{account['proxy']['host']}:{account['proxy']['port']}" if account['proxy'] else 'нет'
    )
    text = (
        f"<b>Аккаунт: {account['name'] or account['session_name']}</b>\n\n"
        f"Имя сессии: <code>{account['session_name']}</code>\n"
        f"ID аккаунта: <code>{account['account_id']}</code>\n"
        f"Номер телефона: <code>{account['phone_number'] or 'не указан'}</code>\n"
        f"Прокси: <code>{proxy}</code>\n"
        f"Статус: <code>{'✅ активен' if account['is_active'] else '❌ не активен'}</code>"
    )
    keyboard = account_detail_key(account)
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'add_account')
async def add_account_start(call: CallbackQuery, state: FSM):
    await state.set_state(AdminAccountStates.waiting_for_account_name)
    keyboard = back_fun_key('accounts_all')
    await call.message.edit_text("🆕 Введите метку/имя для нового аккаунта:", reply_markup=keyboard)

@adminRouter.message(AdminAccountStates.waiting_for_account_name)
async def process_account_name(msg: Message, state: FSM):
    name = msg.text.strip()
    if not name:
        await msg.answer("❌ Имя не должно быть пустым, попробуйте ещё раз:")
        return
    await state.update_data(account_label=name)
    keyboard = back_fun_key('accounts_all')
    await state.set_state(AdminAccountStates.waiting_for_session_str)
    await msg.answer(
        "📄 Загрузите ваш <code>.session</code>-файл "
        "(отправьте как документ, файл с расширением <code>.session</code>).",
        reply_markup=keyboard
    )

@adminRouter.message(AdminAccountStates.waiting_for_session_str)
async def process_session_file(msg: Message, state: FSM):
    document = msg.document
    if not document or not document.file_name.endswith('.session'):
        await msg.answer("❌ Пожалуйста, загрузите файл с расширением <code>.session</code>:")
        return
    file_info = await msg.bot.get_file(document.file_id)
    raw = await msg.bot.download_file(file_info.file_path)
    tmp_dir = Path("sessions_tmp")
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / document.file_name
    tmp_path.write_bytes(raw.read())
    keyboard = back_fun_key('accounts_all')
    await state.update_data(session_path=str(tmp_path))
    await msg.answer(
        "🌐 Укажите прокси в формате строки:\n"
        "<code>protocol://[user:pass@]host:port</code>\n"
        "Например: <code>socks5://login:pass@127.0.0.1:9050</code>\n"
        "Или отправьте <code>-</code>, если прокси не нужен.",
        reply_markup=keyboard
    )
    await state.set_state(AdminAccountStates.waiting_for_proxy)

@adminRouter.message(AdminAccountStates.waiting_for_proxy)
async def process_proxy_and_add(msg: Message, state: FSM):
    text = msg.text.strip()
    proxy = None
    if text.lower() != '-':
        pattern = re.compile(
            r'^(?P<proto>\w+)://'
            r'(?:(?P<username>[^:]+):(?P<password>[^@]+)@)?'
            r'(?P<host>[^:]+):(?P<port>\d+)$'
        )
        match = pattern.match(text)
        if not match:
            await msg.answer(
                "❌ Неправильный формат прокси.\n"
                "Формат: <code>protocol://login:pass@host:port</code> или <code>protocol://host:port</code>.\n"
                "Например: <code>socks5://127.0.0.1:9050</code>"
            )
            return
        proxy = {
            "type": match.group("proto").lower(),
            "host": match.group("host"),
            "port": int(match.group("port")),
            "username": match.group("username"),
            "password": match.group("password"),
        }
    data = await state.get_data()
    label = data['account_label']
    session_tmp = data['session_path']
    new_name = await account_manager.add_account(
        session_file=session_tmp,
        proxy=json.dumps(proxy, ensure_ascii=False) if proxy else None
    )
    try:
        Path(session_tmp).unlink()
    except Exception:
        pass
    if not new_name:
        await msg.answer("❌ Не удалось добавить аккаунт. Проверьте сессию и повторите.")
        await state.clear()
        return
    await msg.answer(f"✅ Аккаунт «{label}» сохранён под именем <code>{new_name}</code>.")
    await state.clear()
    accounts = await db.get_all_telegram_accounts()
    keyboard = view_accounts_key(accounts[:5], start_index=0, page_size=5, total=len(accounts))
    await msg.answer("👤 Текущий список аккаунтов:", reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("acc_edit_proxy_"))
async def edit_account_proxy(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    await state.update_data(edit_acc_id=account_id)
    await state.set_state(AdminAccountStates.waiting_for_proxy_edit)
    keyboard = back_fun_key(f"getacc_{account_id}")
    await call.message.edit_text(
        "✏️ Введите новый прокси в формате:\n"
        "<code>protocol://[user:pass@]host:port</code>\n"
        "Или отправьте <code>-</code>, чтобы удалить текущий прокси.",
        reply_markup=keyboard
    )

@adminRouter.message(AdminAccountStates.waiting_for_proxy_edit)
async def process_proxy_edit(msg: Message, state: FSM):
    data = await state.get_data()
    account_id = data['edit_acc_id']
    text = msg.text.strip()
    if text == "-":
        await db.update_account_proxy(account_id, None)
    else:
        pattern = re.compile(
            r'^(?P<proto>\w+)://'
            r'(?:(?P<username>[^:]+):(?P<password>[^@]+)@)?'
            r'(?P<host>[^:]+):(?P<port>\d+)$'
        )
        match = pattern.match(text)
        if not match:
            await msg.answer("❌ Неверный формат, попробуйте ещё раз или '-' для удаления:")
            return
        proxy = {
            "type": match.group("proto"),
            "username": match.group("username"),
            "password": match.group("password"),
            "host": match.group("host"),
            "port": int(match.group("port"))
        }
        await db.update_account_proxy(account_id, json.dumps(proxy, ensure_ascii=False))
    await msg.answer("✅ Прокси обновлён.", reply_markup=back_fun_key(f'getacc_{account_id}'))
    await state.clear()

@adminRouter.callback_query(F.data.startswith("acc_remove_proxy_"))
async def remove_account_proxy(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    await db.update_account_proxy(account_id, None)
    await call.message.edit_text("✅ Прокси удалён", reply_markup=back_fun_key(f'getacc_{account_id}'))

@adminRouter.callback_query(F.data.startswith("acc_toggle_active_"))
async def toggle_account_active(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    account = await db.get_telegram_account_by_id(account_id)
    new_status = not account['is_active']
    await db.update_account_active(account_id, new_status)
    proxy = (
        f"{account['proxy']['type']}://{account['proxy']['username']}:{account['proxy']['password']}@"
        f"{account['proxy']['host']}:{account['proxy']['port']}" if account['proxy'] else 'нет'
    )
    account = await db.get_telegram_account_by_id(account_id)
    text = (
        f"<b>Аккаунт: {account['name'] or account['session_name']}</b>\n\n"
        f"Имя сессии: <code>{account['session_name']}</code>\n"
        f"ID аккаунта: <code>{account['account_id']}</code>\n"
        f"Номер телефона: <code>{account['phone_number'] or 'не указан'}</code>\n"
        f"Прокси: <code>{proxy}</code>\n"
        f"Статус: <code>{'✅ активен' if account['is_active'] else '❌ не активен'}</code>"
    )
    keyboard = account_detail_key(account)
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("acc_delete_"))
async def delete_account_request(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    keyboard = acc_delete_confirm_key(account_id)
    await call.message.edit_text("🚫 Подтвердите удаление аккаунта:", reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("acc_confirm_delete_"))
async def confirm_account_delete(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    account = await db.get_account_by_uniq_id(account_id)
    await db.delete_account(account['session_name'])
    await account_manager.stop_account(account['session_name'])
    await call.answer("✅ Аккаунт удалён", show_alert=True)
    accounts = await db.get_all_telegram_accounts()
    keyboard = view_accounts_key(accounts[:5], start_index=0, page_size=5, total=len(accounts))
    await call.message.edit_text(
        f"Всего аккаунтов: {len(accounts)}\nВыберите аккаунт или добавьте новый:",
        reply_markup=keyboard
    )

@adminRouter.callback_query(F.data.startswith("upacc_name_"))
async def update_account_name_start(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    await state.update_data(edit_acc_id=account_id)
    await state.set_state(AdminAccountStates.waiting_for_name_update)
    keyboard = back_fun_key(f"getacc_{account_id}")
    await call.message.edit_text(
        "♻️ Введите новое имя профиля (First Last):",
        reply_markup=keyboard
    )
    await call.answer()

@adminRouter.message(AdminAccountStates.waiting_for_name_update)
async def process_account_name_update(msg: Message, state: FSM):
    data = await state.get_data()
    account_id = data["edit_acc_id"]
    new_name = msg.text.strip()
    if not new_name:
        await msg.answer("❌ Имя не должно быть пустым:")
        return
    record = await db.get_telegram_account_by_id(account_id)
    await account_manager.update_account_name(record["session_name"], new_name)
    keyboard = back_fun_key(f"getacc_{account_id}")
    await msg.answer("✅ Имя обновлено.", reply_markup=keyboard)
    await state.clear()

@adminRouter.callback_query(F.data.startswith("upacc_about_"))
async def update_account_about_start(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    await state.update_data(edit_acc_id=account_id)
    await state.set_state(AdminAccountStates.waiting_for_about_update)
    keyboard = back_fun_key(f"getacc_{account_id}")
    await call.message.edit_text(
        "♻️ Введите новый текст «О себе»:",
        reply_markup=keyboard
    )
    await call.answer()

@adminRouter.message(AdminAccountStates.waiting_for_about_update)
async def process_account_about_update(msg: Message, state: FSM):
    data = await state.get_data()
    account_id = data["edit_acc_id"]
    new_about = msg.text.strip()
    record = await db.get_telegram_account_by_id(account_id)
    await account_manager.update_account_about(record["session_name"], new_about)
    keyboard = back_fun_key(f"getacc_{account_id}")
    await msg.answer("✅ Описание обновлено.", reply_markup=keyboard)
    await state.clear()

@adminRouter.callback_query(F.data.startswith("upacc_photo_"))
async def update_account_photo_start(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split("_")[-1])
    await state.update_data(edit_acc_id=account_id)
    await state.set_state(AdminAccountStates.waiting_for_photo_update)
    keyboard = back_fun_key(f"getacc_{account_id}")
    await call.message.edit_text(
        "♻️ Пришлите новое фото профиля (как фото, не документ):",
        reply_markup=keyboard
    )
    await call.answer()

@adminRouter.message(AdminAccountStates.waiting_for_photo_update, F.photo)
async def process_account_photo_update(msg: Message, state: FSM):
    data = await state.get_data()
    account_id = data["edit_acc_id"]
    photo = msg.photo[-1]
    file = await msg.bot.get_file(photo.file_id)
    buf_io = await msg.bot.download_file(file.file_path)
    photo_bytes = buf_io.read()
    record = await db.get_telegram_account_by_id(account_id)
    session_name = record["session_name"]
    success = await account_manager.update_account_photo(session_name, photo_bytes)
    keyboard = back_fun_key(f"getacc_{account_id}")
    if success:
        await msg.answer("✅ Фото профиля обновлено.", reply_markup=keyboard)
    else:
        await msg.answer("❌ Не удалось обновить фото.", reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('acc_media_'))
async def account_media_handler(call: CallbackQuery, state: FSM):
    account_id = int(call.data.split('_')[-1])
    account_media = await db.get_all_media_account(account_id=int(account_id))
    clear_dict = filter_by_add_id(account_media)
    text = (
        "Здесь вы можете посмотреть медиафайлы, воспользуйтесь кнопками ниже для взаимодействия:"
    )
    await call.message.edit_text(text, reply_markup=view_media_key(account_id, clear_dict, start=0, total=len(clear_dict)))

@adminRouter.callback_query(F.data.startswith('vmdeia_back_'))
async def media_back_handler(call: CallbackQuery, state: FSM):
    start = int(call.data.split("_")[-2])
    account_id = int(call.data.split("_")[-1])
    account_media = await db.get_all_media_account(account_id=int(account_id))
    clear_dict = filter_by_add_id(account_media)
    await call.message.edit_reply_markup(reply_markup=view_media_key(account_id, clear_dict, start=start, total=len(clear_dict)))

@adminRouter.callback_query(F.data.startswith('vmdeia_next_'))
async def media_next_handler(call: CallbackQuery, state: FSM):
    start = int(call.data.split("_")[-2])
    account_id = int(call.data.split("_")[-1])
    account_media = await db.get_all_media_account(account_id=int(account_id))
    clear_dict = filter_by_add_id(account_media)
    await call.message.edit_reply_markup(reply_markup=view_media_key(account_id, clear_dict, start=start, total=len(clear_dict)))

@adminRouter.callback_query(F.data.startswith('viewmedia_'))
async def view_media_handler(call: CallbackQuery, state: FSM):
    add_id = int(call.data.split('_')[1])
    account_id = int(call.data.split('_')[2])
    media_list = await db.get_all_media_by_add_id(add_id)
    one_ex = len(media_list) == 1 and media_list[0]['media_type'] in ['video_note', 'voice_note']
    if not one_ex:
        media = await createMediaGroupByPath(media_list)
        media = media.build()
        try:
            await bot.send_media_group(chat_id=call.from_user.id, media=media)
        except Exception as e:
            logger.exception(e)
            await call.answer('Не удалось выдать медиагруппу', show_alert=True)
            return
    else:
        media_dict = media_list[0]
        media = FSInputFile(media_dict['media_path'])
        try:
            if media_dict['media_type'] == 'video_note':
                await bot.send_video_note(chat_id=call.from_user.id, video_note=media)
            elif media_dict['media_type'] == 'voice_note':
                await bot.send_voice(chat_id=call.from_user.id, voice=media)
        except Exception as e:
            logger.exception(e)
            await call.answer(f'Не удалось выдать {"видеосообщение" if media_dict["media_type"] == "video_note" else "голосовое сообщение"}', show_alert=True)
            return
    text = "Воспользуйтесь клавиатурой ниже 👇"
    await call.message.answer(text, reply_markup=func_media_key(account_id, add_id, one_ex, media_list[0]['is_active']))

@adminRouter.callback_query(F.data.startswith('mediaedittext_'))
async def media_edit_text_handler(call: CallbackQuery, state: FSM):
    add_id = int(call.data.split('_')[1])
    account_id = int(call.data.split('_')[2])
    await state.set_state(AdminUpdateTextMedia.add_id)
    await state.update_data(add_id=add_id)
    await state.set_state(AdminUpdateTextMedia.acc_id)
    await state.update_data(acc_id=account_id)
    await state.set_state(AdminUpdateTextMedia.text)
    keyboard = back_fun_key(f'viewmedia_{add_id}_{account_id}')
    await call.message.edit_text('Введите новый текст:', reply_markup=keyboard)

@adminRouter.message(AdminUpdateTextMedia.text)
async def update_text_media_handler(msg: Message, state: FSM):
    data = await state.get_data()
    add_id = data.get('add_id')
    account_id = data.get('acc_id')
    new_text = msg.text
    await db.update_text_media(add_id, new_text)
    await state.clear()
    keyboard = back_fun_key(f'viewmedia_{add_id}_{account_id}')
    await msg.answer('✅ Текст успешно изменён', reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('media_trash_'))
async def media_trash_handler(call: CallbackQuery, state: FSM):
    add_id = int(call.data.split('_')[2])
    account_id = int(call.data.split('_')[3])
    text = "Вы точно хотите удалить медиафайлы?"
    await call.message.edit_text(text, reply_markup=two_factor_delete_media(account_id, add_id))

@adminRouter.callback_query(F.data.startswith('sucdelmedia_'))
async def confirm_media_delete_handler(call: CallbackQuery, state: FSM):
    add_id = int(call.data.split('_')[1])
    account_id = int(call.data.split('_')[2])
    await db.delete_media(add_id)
    text = "✅ Медиафайлы были удалены"
    keyboard = back_fun_key(f'acc_media_{account_id}')
    await call.message.edit_text(text, reply_markup=keyboard)