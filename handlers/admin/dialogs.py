from aiogram import F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loader import adminRouter, db
from utils.misc_func.bot_models import FSM
from keyboards.inline.adminkeyinline import view_dialogs_key, back_fun_key, save_dialog_key
from states.admin_state import *
import re
import random
import json
from utils.misc_func.generator_dialogs import ai_generate_dialog

@adminRouter.message(F.text == '📜 Диалоги')
async def dialogs_handler(msg: Message, state: FSM):
    await state.clear()
    dialogs = await db.get_all_dialogs()
    dialogs.reverse()
    keyboard = view_dialogs_key(dialogs[:5], start_index=0, page_size=5, total=len(dialogs))
    text = (
        f"<b>📜 Диалоги</b>\n\n"
        f"Всего диалогов: {len(dialogs)}\n"
        "Выберите диалог из списка:"
    )
    await msg.answer(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'dialogs')
async def dialogs_callback_handler(call: CallbackQuery, state: FSM):
    await state.clear()
    dialogs = await db.get_all_dialogs()
    dialogs.reverse()
    keyboard = view_dialogs_key(dialogs[:5], start_index=0, page_size=5, total=len(dialogs))
    text = (
        f"<b>📜 Диалоги</b>\n\n"
        f"Всего диалогов: {len(dialogs)}\n"
        "Выберите диалог из списка:"
    )
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('list_dlg_next_'))
async def list_dialogs_next(call: CallbackQuery, state: FSM):
    start_index = int(call.data.split('_')[-1])
    dialogs = await db.get_all_dialogs()
    dialogs.reverse()
    if start_index >= len(dialogs):
        await call.answer("Это последняя страница", show_alert=True)
        return
    keyboard = view_dialogs_key(dialogs[start_index:start_index+5], start_index=start_index, page_size=5, total=len(dialogs))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('list_dlg_back_'))
async def list_dialogs_back(call: CallbackQuery, state: FSM):
    start_index = int(call.data.split('_')[-1])
    prev_index = max(0, start_index - 5)
    dialogs = await db.get_all_dialogs()
    dialogs.reverse()
    keyboard = view_dialogs_key(dialogs[prev_index:prev_index+5], start_index=prev_index, page_size=5, total=len(dialogs))
    await call.message.edit_reply_markup(reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith('getdlg_'))
async def get_dialog(call: CallbackQuery, state: FSM):
    dialog_id = int(call.data.split('_')[-1])
    dialog = await db.get_dialog_by_id(dialog_id)
    if not dialog:
        await call.answer("Диалог не найден", show_alert=True)
        return
    messages = dialog['messages']
    text = f"<b>Диалог: {dialog['name']}</b>\n\n"
    for message in messages:
        text += f"[{message['role']}] {message['text']}\n"
    text += f"\n<em>Требуется аккаунтов: {dialog['num_accounts']}</em>"
    keyboard = back_fun_key('dialogs')
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'add_dialog')
async def add_dialog_start(call: CallbackQuery, state: FSM):
    await state.set_state(AdminDialogStates.waiting_for_dialog_name)
    await call.message.edit_text("🆕 Введите название нового диалога:", reply_markup=back_fun_key('dialogs'))

@adminRouter.message(AdminDialogStates.waiting_for_dialog_name)
async def process_dialog_name(msg: Message, state: FSM):
    name = msg.text.strip()
    if not name:
        await msg.answer("❌ Название не может быть пустым. Попробуйте ещё раз:")
        return
    await state.update_data(name=name)
    keyboard = back_fun_key('dialogs')
    await msg.answer(
        "📝 Введите сообщения диалога построчно в формате:\n"
        "[Role] Текст сообщения\n\n"
        "Пример:\n"
        "[User1] Привет\n"
        "[User2] Как дела?",
        reply_markup=keyboard
    )
    await state.set_state(AdminDialogStates.waiting_for_dialog_messages)

@adminRouter.message(AdminDialogStates.waiting_for_dialog_messages)
async def process_dialog_messages(msg: Message, state: FSM):
    lines = msg.text.strip().splitlines()
    pattern = re.compile(r"^\[(?P<role>[^\]]+)\]\s*(?P<text>.+)$")
    messages = []
    keyboard = back_fun_key('dialogs')
    for idx, line in enumerate(lines, start=1):
        match = pattern.match(line)
        if not match:
            await msg.answer(
                f"❌ Ошибка формата в строке {idx}: «{line}»\n"
                "Каждая строка должна быть в формате [Role] Текст."
            )
            return
        messages.append({
            "role": match.group("role"),
            "text": match.group("text")
        })
    await state.update_data(messages=messages)
    await msg.answer("🔢 Сколько аккаунтов нужно для этого диалога? Введите целое число > 0:", reply_markup=keyboard)
    await state.set_state(AdminDialogStates.waiting_for_num_accounts)

@adminRouter.message(AdminDialogStates.waiting_for_num_accounts)
async def process_num_accounts(msg: Message, state: FSM):
    text = msg.text.strip()
    if not text.isdigit() or int(text) < 1:
        await msg.answer("❌ Введите целое число больше нуля:")
        return
    num_accounts = int(text)
    data = await state.get_data()
    name = data['name']
    messages = data['messages']
    new_id = await db.add_dialog(name=name, messages=messages, num_accounts=num_accounts)
    await msg.answer(f"✅ Диалог «{name}» (ID {new_id}) успешно добавлен!")
    await state.clear()
    dialogs = await db.get_all_dialogs()
    keyboard = view_dialogs_key(dialogs[:5], start_index=0, page_size=5, total=len(dialogs))
    await msg.answer("📜 Текущий список диалогов:", reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'generate_dialog')
async def generate_dialog_start(call: CallbackQuery, state: FSM):
    await call.answer()
    await state.set_state(AdminAIGenerateStates.waiting_for_num_roles)
    await call.message.edit_text(
        "<b>🔀 AI-Генерация диалога</b>\n\n"
        "Введите количество участников (целое число > 0):"
    )

@adminRouter.message(AdminAIGenerateStates.waiting_for_num_roles)
async def generate_dialog_process(msg: Message, state: FSM):
    text = msg.text.strip()
    if not text.isdigit() or int(text) < 1:
        await msg.answer("❌ Введите корректное целое число больше нуля:")
        return
    num_roles = int(text)
    await msg.answer("<i>Генерирую диалог через AI, подождите...</i>")
    try:
        result = await ai_generate_dialog(num_roles)
    except Exception as e:
        await msg.answer(f"❌ Ошибка генерации: {e}")
        await state.clear()
        return
    out = [f"<b>🔀 {result['name']}</b>\n"]
    for message in result['messages']:
        out.append(f"[{message['role']}] {message['text']}")
    text_out = "\n".join(out)
    await msg.answer(text_out)
    keyboard = save_dialog_key(result)
    await state.update_data(ai_dialog=result)
    await msg.answer("Что делаем дальше?", reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("save_ai_dialog_"))
async def save_ai_dialog(call: CallbackQuery, state: FSM):
    name = call.data.replace("save_ai_dialog_", "")
    data = await state.get_data()
    ai_dialog = data.get("ai_dialog", {})
    await state.clear()
    if not ai_dialog or ai_dialog.get("name") != name:
        await call.answer("❌ Нечего сохранять", show_alert=True)
        return
    try:
        dialog_id = await db.add_dialog(
            name=ai_dialog["name"],
            messages=ai_dialog["messages"],
            num_accounts=ai_dialog["num_accounts"]
        )
        await call.answer(f"✅ Диалог сохранён под ID={dialog_id}", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка при сохранении abilities: {e}", show_alert=True)
    dialogs = await db.get_all_dialogs()
    dialogs.reverse()
    keyboard = view_dialogs_key(dialogs[:5], start_index=0, page_size=5, total=len(dialogs))
    await call.message.edit_text("📜 Список диалогов:", reply_markup=keyboard)