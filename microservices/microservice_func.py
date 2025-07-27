from collections import defaultdict
from datetime import datetime

from data.config import DB, ADMIN, STATUS_TRANSACTIONS, STATUS_QUEUE
from loader import bot, logger

def calculate_queue_statistics(queue_data, statuses):
    stats = {
        "total_entries": len(queue_data),
        "status_counts": defaultdict(int),
        "user_stats": defaultdict(lambda: {"count": 0, "statuses": defaultdict(int)}),
        "worker_stats": defaultdict(lambda: {"count": 0, "statuses": defaultdict(int)}),
    }
    for entry in queue_data:
        status = entry["status"]
        user_id = entry["user_id"]
        buyer_id = entry["buyer_id"]
        stats["status_counts"][status] += 1
        stats["user_stats"][user_id]["count"] += 1
        stats["user_stats"][user_id]["statuses"][status] += 1
        if buyer_id:
            stats["worker_stats"][buyer_id]["count"] += 1
            stats["worker_stats"][buyer_id]["statuses"][status] += 1
    for status, data in statuses.items():
        if status in stats["status_counts"]:
            stats["status_counts"][f"{data['symbol']} {data['name']}"] = stats["status_counts"].pop(status)
    return stats

def calculate_statistics(transactions, statuses, date_str=None):
    stats = {
        "total_transactions": 0,
        "total_amount": 0,
        "status_counts": defaultdict(int),
        "user_stats": defaultdict(lambda: {"count": 0, "amount": 0}),
    }

    target_date = None
    if date_str:
        target_date = datetime.strptime(date_str, "%d.%m.%Y").date()

    for transaction in transactions:
        transaction_date: datetime = transaction["created_at"]
        transaction_date = transaction_date.date()
        if target_date and transaction_date != target_date:
            continue

        status = transaction["status"]
        amount = transaction["amount"] if status in ['replenishment', 'refferal', 'wait_withdraft'] else 0
        user_id = transaction["user_id"]

        stats["total_transactions"] += 1
        stats["total_amount"] += amount
        stats["status_counts"][status] += 1
        stats["user_stats"][user_id]["count"] += 1
        stats["user_stats"][user_id]["amount"] += amount

    for status, data in statuses.items():
        if status in stats["status_counts"]:
            stats["status_counts"][f"{data['symbol']} {data['name']}"] = stats["status_counts"].pop(status)

    return stats

async def send_user_notification(db: DB, text: str):
    users = await db.get_all_users()
    for user in users:
        try:
            await bot.send_message(chat_id=user['_id'], text=text)
        except Exception as e:
            logger.error(e)
    try:
        transactions_list = await db.get_all_transactions()
        hold = await db.get_all_hold()
        sum_hold = sum(row["amount"] for row in hold)
        queue_list = await db.get_all_queue()
        users = await db.get_all_users()
        statistic_text = (
            f"<b>👤 О пользователях:</b>\n"
            f"Всего юзеров: <code>{len(users)} чел.</code>\n"
            f"Сумма всех балансов: <code>{round(float(sum(item['balance'] for item in users)), 2)}$</code>\n"
            f"Всего на выводе: <code>{sum_hold}$</code>\n"
        )
        statistics = calculate_statistics(transactions_list, STATUS_TRANSACTIONS)
        queue_statistics = calculate_queue_statistics(queue_list, STATUS_QUEUE)
        statistic_text += (
            f"\n<b>💱 О транзакциях:</b>\n"
            f"Сумма на выплаты за сегодня: {statistics['total_amount']}\n"
            f"Всего транзакций: {statistics['total_transactions']}\n\n"
            "<b>По статусам:</b>"
        )
        for status, count in statistics["status_counts"].items():
            statistic_text += f"\n{status}: {count}"
        statistic_text += f"\n\n<b>📄 Номера:</b>\nВсего записей: {queue_statistics['total_entries']}\n\n<b>По статусам:</b>"
        for status, count in queue_statistics["status_counts"].items():
            statistic_text += f"\n{status}: {count}"

        settings = await db.get_settings()
        if settings.get('chat_id') is None:
            admin_ids_db = await db.get_admins_role()
            admin_ids_dirty = [_id['_id'] for _id in admin_ids_db]
            admin_list = list(set(admin_ids_dirty) | set(ADMIN))

            for _id in admin_list:
                admin_text = f"🕔 Время <b>20:00</b>, работа закончена\n{statistic_text}"
                try:
                    await bot.send_message(chat_id=_id, text=admin_text)
                except Exception as e:
                    logger.error(e)
        else:
            try:
                await bot.send_message(
                    chat_id=settings['chat_id'],
                    text=statistic_text,
                    message_thread_id=settings['notification_thread_id']
                )
            except Exception as e:
                logger.error(e)
    except Exception as e:
        logger.exception(e)