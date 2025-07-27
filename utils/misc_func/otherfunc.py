

import uuid, base64, re, pytz

from aiogram.types import *
from aiogram.utils.media_group import MediaGroupBuilder

from data.config import BOT_TIMEZONE
from datetime import datetime
from data.config import BOT_TIMEZONE
from aiogram import Dispatcher, Bot
from loguru import logger
from typing import *
from data.config import DB
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State



def filter_by_add_id(records):
    # Создаем пустой словарь для хранения записей по add_id
    filtered_dict = {}
    
    # Проходим по всем записям в списке
    for record in records:
        add_id = record['add_id']
        
        # Если add_id еще не в словаре, добавляем его с пустым списком
        if add_id not in filtered_dict:
            filtered_dict[add_id] = []
        
        # Добавляем текущую запись в список соответствующего add_id
        filtered_dict[add_id].append(record)
    
    return filtered_dict


async def send_notif_chat_admin(bot: Bot, db: DB, text: str):
	settings = await db.get_settings()
	text = (
		f"🔔 <b>Уведомление</b>"
	)



async def clear_user_state(bot: Bot, dp: Dispatcher, user_id: int, chat_id: int = None, thread_id: int = None):
	
	try:
		if chat_id is None:
			chat_id = user_id
		state = dp.fsm.get_context(bot=bot, user_id=user_id, chat_id=chat_id, thread_id=thread_id)
		await state.clear()

	except Exception as e:
		logger.exception(f"Ошибка при очистке состояния для пользователя {user_id}: {e}")


def format_phone_number(phone_number):
	
	digits = ''.join(filter(str.isdigit, phone_number))
	
	if digits.startswith('8'):
		digits = '7' + digits[1:]

	if digits.startswith('9'):
		digits = '7' + digits
	
	if len(digits) < 11:    
		return False
		
	elif len(digits) > 11:
		return False
	
	return digits


def check_positive_number(text):
	processed_text = text.replace(" ", "")  
	try:
		number = float(processed_text) 
		return number > 0  
	except ValueError:
		return False  


def generate_short_uuid():
	short_uuid = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8').rstrip('=')
	return short_uuid


def round_to_ten(number):
  return (number // 10 + (number % 10 >= 5)) * 10


def format_number(number):
	formatted_number = "{:.8f}".format(number)  

	
	if "." in formatted_number:
		integer_part, fractional_part = formatted_number.split(".")
		fractional_part = fractional_part.rstrip("0")  
		if fractional_part:  
			formatted_number = integer_part + "." + fractional_part
		else:
			formatted_number = integer_part  

	return formatted_number


def is_non_negative(x):
	try:
		x = float(x)
	except:
		return False

	if isinstance(x, int) or isinstance(x, float):
		return x >= 0
	else:
		return False


async def createMediaGroup(album: List[Message]) -> MediaGroupBuilder:
	mediaGroup = MediaGroupBuilder()

	for m in album:
		match m.content_type:
			case ContentType.PHOTO:
				mediaGroup.add_photo(
					media=m.photo[-1].file_id,
					caption=m.caption,
					caption_entities=m.caption_entities,
				)
				
			case ContentType.VIDEO:
				mediaGroup.add_video(
					media=m.video.file_id,
					caption=m.caption,
					caption_entities=m.caption_entities,
				)
			
			case ContentType.DOCUMENT:
				mediaGroup.add_document(
					media=m.document.file_id,
					caption=m.caption,
					caption_entities=m.caption_entities,
				)
		
	return mediaGroup


async def createMediaGroupByPath(media_list: List[dict], text_media: Union[str, None]) -> MediaGroupBuilder:
	mediaGroup = MediaGroupBuilder()
	n = 0
	for m in media_list:

		if n == 0 and text_media != None:
			caption = text_media
		else:
			caption = None

		n+=1

		match m['media_type']:
			case 'photo':
				mediaGroup.add_photo(
					media=FSInputFile(m['media_path']),
					caption=caption,
				)
				
			case 'video':
				mediaGroup.add_video(
					media=FSInputFile(m['media_path']),
					caption=caption,
				)
			
			case 'document':
				mediaGroup.add_document(
					media=FSInputFile(m['media_path']),
					caption=caption,

				)
	return mediaGroup

		
def validate_date(date_str: str) -> bool:
	"""
	Проверяет валидность введенной даты в формате "день.месяц.год часы:минуты"
	"""
	pattern = r'^(\d{1,2})\.(\d{1,2})\.(\d{4}) (\d{1,2})\:(\d{2})$'
	match = re.match(pattern, date_str)

	if match:
		day, month, year, hour, minute = match.groups()

		
		if int(day) < 1 or int(day) > 31:
			return False
		if int(month) < 1 or int(month) > 12:
			return False

		
		if int(year) < 1:
			return False

		
		if int(hour) < 0 or int(hour) > 23:
			return False
		if int(minute) < 0 or int(minute) > 59:
			return False

		return True
	else:
		return False


def check_format_keys(text):
	
	pattern = r'.*https?://[^ ]+' 

	if re.match(pattern, text):
		return True
	else:
		return False


def find_link(text):
	
	link = re.search(r'http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
	if link:
		return link.group()
	return None


	
def get_date(full: bool = True) -> str:
	
	if full:
		return datetime.now(pytz.timezone(BOT_TIMEZONE)).strftime("%d.%m.%Y %H:%M")
	else:
		return datetime.now(pytz.timezone(BOT_TIMEZONE)).strftime("%d.%m.%Y")


def convert_date(from_time, full=True, second=True) -> Union[str, int]:
	
	if "-" in str(from_time):
		from_time = from_time.replace("-", ".")

	if str(from_time).isdigit():
		if full:
			to_time = datetime.fromtimestamp(from_time, pytz.timezone(BOT_TIMEZONE)).strftime("%d.%m.%Y %H:%M:%S")
		elif second:
			to_time = datetime.fromtimestamp(from_time, pytz.timezone(BOT_TIMEZONE)).strftime("%d.%m.%Y %H:%M")
		else:
			to_time = datetime.fromtimestamp(from_time, pytz.timezone(BOT_TIMEZONE)).strftime("%d.%m.%Y")
	else:
		if " " in str(from_time):
			cache_time = from_time.split(" ")

			if ":" in cache_time[0]:
				cache_date = cache_time[1].split(".")
				cache_time = cache_time[0].split(":")
			else:
				cache_date = cache_time[0].split(".")
				cache_time = cache_time[1].split(":")

			if len(cache_date[0]) == 4:
				x_year, x_month, x_day = cache_date[0], cache_date[1], cache_date[2]
			else:
				x_year, x_month, x_day = cache_date[2], cache_date[1], cache_date[0]

			x_hour, x_minute, x_second = cache_time[0], cache_time[2], cache_time[2]

			from_time = f"{x_day}.{x_month}.{x_year} {x_hour}:{x_minute}:{x_second}"
		else:
			cache_date = from_time.split(".")

			if len(cache_date[0]) == 4:
				x_year, x_month, x_day = cache_date[0], cache_date[1], cache_date[2]
			else:
				x_year, x_month, x_day = cache_date[2], cache_date[1], cache_date[0]

			from_time = f"{x_day}.{x_month}.{x_year}"

		if " " in str(from_time):
			to_time = int(datetime.strptime(from_time, "%d.%m.%Y %H:%M:%S").timestamp())
		else:
			to_time = int(datetime.strptime(from_time, "%d.%m.%Y").timestamp())

	return to_time


def clear_html(get_text: str) -> str:
	if get_text is not None:
		if "<" in get_text: get_text = get_text.replace("<", "*")
		if ">" in get_text: get_text = get_text.replace(">", "*")
	else:
		get_text = ""

	return get_text


def snum(amount: Union[int, float], remains: int = 2) -> str:
	
	format_str = "{:." + str(remains) + "f}"
	str_amount = format_str.format(float(amount))

	if remains != 0:
		if "." in str_amount:
			remains_find = str_amount.find(".")
			remains_save = remains_find + 8 - (8 - remains) + 1

			str_amount = str_amount[:remains_save]

	if "." in str(str_amount):
		while str(str_amount).endswith('0'): str_amount = str(str_amount)[:-1]

	if str(str_amount).endswith('.'): str_amount = str(str_amount)[:-1]

	return str(str_amount)
