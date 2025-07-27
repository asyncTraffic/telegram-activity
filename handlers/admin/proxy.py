import re
import socks
from aiogram import F
from aiogram.types import Message, CallbackQuery
from loader import adminRouter, db, FSM
from states.admin_state import AdminProxyStates
from keyboards.inline.adminkeyinline import (
    view_proxy_main_key,
    view_proxy_delete_key,
    view_proxy_confirm_key,
    back_fun_key
)
from keyboards.reply.adminkey import kbMainAdmin
from loguru import logger

PAGE_SIZE = 5

@adminRouter.message(F.text == '🌐 Прокси')
async def proxy_menu_handler(msg: Message, state: FSM):
    await state.clear()
    proxies = await db.get_all_proxies()
    text = (
        "<b>🌐 Управление прокси</b>\n\n"
        "📋 Список прокси:\n"
    )
    keyboard = view_proxy_main_key(proxies, start=0, total=len(proxies))
    await msg.answer(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'proxys')
async def proxy_menu_callback_handler(call: CallbackQuery, state: FSM):
    await state.clear()
    proxies = await db.get_all_proxies()
    text = (
        "<b>🌐 Управление прокси</b>\n\n"
        "📋 Список прокси:\n"
    )
    keyboard = view_proxy_main_key(proxies, start=0, total=len(proxies))
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("proxy_next_"))
async def proxy_next_handler(call: CallbackQuery, state: FSM):
    start = int(call.data.split("_")[-1])
    proxies = await db.get_all_proxies()
    text = (
        "<b>🌐 Управление прокси</b>\n\n"
        "📋 Список прокси:\n"
        "\n".join(f"• {p}" for p in proxies[start:start+PAGE_SIZE]) or "— пусто"
    )
    keyboard = view_proxy_main_key(proxies, start=start, total=len(proxies))
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("proxy_back_"))
async def proxy_back_handler(call: CallbackQuery, state: FSM):
    start = int(call.data.split("_")[-1])
    proxies = await db.get_all_proxies()
    text = (
        "<b>🌐 Управление прокси</b>\n\n"
        "📋 Список прокси:\n"
        "\n".join(f"• {p}" for p in proxies[start:start+PAGE_SIZE]) or "— пусто"
    )
    keyboard = view_proxy_main_key(proxies, start=start, total=len(proxies))
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data == 'proxy_add')
async def proxy_add_start(call: CallbackQuery, state: FSM):
    await state.set_state(AdminProxyStates.waiting_for_proxy_add)
    await call.message.edit_text(
        "➕ Введите новый прокси:\n"
        "<code>protocol://[user:pass@]host:port</code>\n",
        reply_markup=back_fun_key('proxys')
    )

@adminRouter.message(AdminProxyStates.waiting_for_proxy_add)
async def proxy_add_process(msg: Message, state: FSM):
    proxy_str = msg.text.strip()
    match = re.match(
        r'^(?P<proto>\w+)://(?:(?P<user>[^:]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$',
        proxy_str
    )
    if not match:
        await msg.answer("❌ Неверный формат. Попробуйте `socks5://login:pass@127.0.0.1:9050`")
        return
    proto, host, port, user, password = (
        match.group("proto").lower(),
        match.group("host"),
        int(match.group("port")),
        match.group("user"),
        match.group("pass")
    )
    if proto not in ("socks5", "socks4", "http", "https"):
        await msg.answer(f"❌ Протокол `{proto}` не поддерживается.", reply_markup=back_fun_key('proxys'))
        return
    try:
        sock = socks.socksocket()
        sock.set_proxy(
            socks.PROXY_TYPE_SOCKS5 if proto == "socks5" else
            socks.PROXY_TYPE_SOCKS4 if proto == "socks4" else
            socks.PROXY_TYPE_HTTP,
            host, port, True, user, password
        )
        sock.settimeout(5)
        sock.connect((host, port))
        sock.close()
    except Exception as e:
        await msg.answer(f"❌ Не удалось подключиться: {e}")
        return
    success = await db.add_proxy(proxy_str)
    await msg.answer(
        "✅ Прокси добавлен." if success else "⚠️ Такой прокси уже есть.",
        reply_markup=back_fun_key('proxys')
    )
    await state.clear()

@adminRouter.callback_query(F.data == 'proxy_del')
async def proxy_delete_start(call: CallbackQuery, state: FSM):
    proxies = await db.get_all_proxies()
    text = "<b>🗑 Удаление прокси</b>\n\nВыберите, какой удалить:"
    keyboard = view_proxy_delete_key(proxies, start=0, total=len(proxies))
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("proxy_del_next_"))
async def proxy_delete_next(call: CallbackQuery, state: FSM):
    start = int(call.data.split("_")[-1])
    proxies = await db.get_all_proxies()
    text = "<b>🗑 Удаление прокси</b>\n\nВыберите, какой удалить:"
    keyboard = view_proxy_delete_key(proxies, start=start, total=len(proxies))
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("proxy_del_back_"))
async def proxy_delete_back(call: CallbackQuery, state: FSM):
    start = int(call.data.split("_")[-1])
    proxies = await db.get_all_proxies()
    text = "<b>🗑 Удаление прокси</b>\n\nВыберите, какой удалить:"
    keyboard = view_proxy_delete_key(proxies, start=start, total=len(proxies))
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("proxy_delete_sel_"))
async def proxy_delete_select(call: CallbackQuery, state: FSM):
    proxy_id = int(call.data.split("_")[-1])
    proxy = await db.get_proxy_by_id(proxy_id)
    text = f"🗑 Вы уверены, что хотите удалить прокси?\n\n{proxy['proxy']}"
    keyboard = view_proxy_confirm_key(proxy_id)
    await call.message.edit_text(text, reply_markup=keyboard)

@adminRouter.callback_query(F.data.startswith("proxy_confirm_delete_"))
async def proxy_confirm_delete(call: CallbackQuery, state: FSM):
    proxy_id = int(call.data.replace("proxy_confirm_delete_", ""))
    proxy = await db.get_proxy_by_id(proxy_id)
    success = await db.remove_proxy(proxy['proxy'])
    text = "✅ Прокси удалён." if success else "⚠️ Прокси не найден."
    await call.message.edit_text(text, reply_markup=back_fun_key('proxys'))