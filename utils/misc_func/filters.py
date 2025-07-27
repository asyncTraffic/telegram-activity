
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from data.config import ADMIN, db
from aiogram import Bot, Dispatcher, F, Router
from loguru import logger
from utils.misc_func.bot_models import *
from typing import *


class ForumTopicEditedFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.forum_topic_edited is not None


class ForumTopicCreatedFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.forum_topic_created is not None






class IsCallCenterChat(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:    
        upd = message if type(message) == Message else message.message

        if str(upd.chat.type) != 'private':
            try:
                chat = await db.get_chat_cc_by_id(upd.chat.id)
            except:
                chat = None

            if chat is None:
                return False
            else:
                return True
        else:
            return False

        
        
class IsMoveInThread(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        upd = message if type(message) == Message else message.message
        chat_id = upd.chat.id

        if upd.chat.is_forum:
            uniq_id = int(str(chat_id) + str(upd.message_thread_id))
            data = await db.get_chat_center_by_uniq_id(uniq_id)

            if data is None:
                return False
            
            if data['free']:
                return True
            
            else:
                if int(data['buyer']) == message.from_user.id:
                    return True
                else:
                    return False
        else:
            return False



class IsAdmin(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        try:
            user = await db.get_user_info(message.from_user.id)
        except:
            user = None

        if user is None:
            return True

        if (message.from_user.id in ADMIN) or (user.get('role') != None and user.get('role') in ['admin', 'owner']):
            return True
        else:
            return False


class IsNotAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user.id in ADMIN:
            return False
        else:
            return True
        

class IsPrivate(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        try:
            if message.chat.type == 'private':
                return True
            else:
                return False
            
        except:
            if message.message.chat.type == 'private':
                return True
            else:
                return False
      

class IsBan(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        user = await db.get_user_info_dict(message.from_user.id)

        if user is None:
            return True

        if message.from_user.id in ADMIN or user['role'] != 'ban':
            return True
        else:
            return False
        
class IsBuyer(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        user = await db.get_user_info_dict(message.from_user.id)
        if user is None:
            return False

        if message.from_user.id in ADMIN or user['role'] == 'buyer':
            return True
        else:
            return False
        
class IsChat(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        try:
            type_ = message.chat.type
        except:
            type_ = message.message.chat.type

        if str(type_) != 'private':
            return True
        else:
            return False


class IsWorkTime(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        upd = message if type(message) == Message else message.message
        settings = await db.get_settings()
        if settings.get('work') == False:
            
            users = await db.get_admins_role()

            if (message.from_user.id in [_id['_id'] for _id in users]) or (message.from_user.id in ADMIN):

                return True
            else:
                if type(message) == Message:
                    await message.answer('⏳ Сейчас бот не работает, загляните позже')
                else:
                    await message.answer('⏳ Сейчас бот не работает, загляните позже', True)

                return False
        else:
            return True


class IsNullThread(BaseFilter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        upd = message if type(message) == Message else message.message

        if upd.message_thread_id == 1:
            return False

        else:
            return True
