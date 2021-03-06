import json
import random
import re
import threading
import time
from enum import Enum
from collections import namedtuple

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType, DotDict, VkBotMessageEvent

import vk as vk_database

class VkApi(vk_database.API):
	def __init__(this, token):
		session = vk_database.Session(token)
		vk_database.API.__init__(this, session=session, v="5.95", lang="ru", timeout=10)

class KeyboardColor(Enum):
	"""
	Возможные цвета кнопок
	"""
	PRIMARY = "primary" # синяя
	DEFAULT = "default" # белая
	NEGATIVE = "negative" # красная
	POSITIVE = "positive" # зелёная

	BLUE = "primary" # синяя
	WHITE = "default" # белая
	RED = "negative" # красная
	GREEN = "positive" # зелёная

class VkBot:

	def __setattr__(self, name, value):
		self.__dict__[name] = value

	priveleged_types = {
		"text": r"\w+"
	}

	def __init__(self, token, group_id=None, tokens=None):

		self.loading_payload = False

		self.before_function = None
		self.after_function = None
		self.default_function = None

		self.decorated = list()
		self.next_steps = list()

		self.vk_session = vk_api.VkApi(token=token)
		self.vk = self.vk_session.get_api()
		if group_id != None:
			self.long_poll = VkBotLongPoll(self.vk_session, group_id)
		else:
			raise Exception("Укажите ID группы")

		if tokens != None:
			for arg in tokens:
				self.__dict__[arg['name']] = self.new_vk_session(arg['token'])

	def to_event_object(self, raw):
		return VkBotMessageEvent(raw)

	def new_vk_session(self, token):
		return VkApi(token=token)

	def register_next_step(self, function, event):
		for i, info in enumerate(self.next_steps):
			if info.get("id") == event.from_id:
				del self.next_steps[i]
				break
		self.next_steps.append({"id":event.from_id, "function":function})

	def unset_next_step(self, event):
		for i, info in enumerate(self.next_steps):
			if info.get("id") == event.from_id:
				del self.next_steps[i]
				return

	def get_next_step(self, event):
		for info in self.next_steps:
			if info.get("id") == event.from_id:
				return info.get("function")

		return None

	def message_handler(self, **kwargs):
		def decorate(function):
			def wrapper(e):
				function(e)
			self.decorated.append(dict(function=wrapper, options=kwargs))
			return wrapper
		return decorate

	def add_handler(self, function, **kwargs):
		self.decorated.append(dict(function=function, options=kwargs))

	def process_new_update(self, update):
		function = None

		if "payload" not in update:
			update.update(dict(payload=dict()))
		else:
			if self.loading_payload == True:
				update.update(dict(payload=json.loads(update.payload)))

		try: update.update(dict(splitted=update.text.split(" ")))
		except Exception as e: print(e)

		next_step = self.get_next_step(update)
		if next_step == None:
			for executable in self.decorated:
				if function == None:

					if executable['options'].get('commands') != None:
						if function == None:
							for command in executable['options'].get("commands"):
								if command == update.text.split(" ")[0].lower():
									function = executable['function']
									break
						else:
							break

					if executable['options'].get('func') != None:
						if function == None:
							if executable['options']['func'](update) == True:
								function = executable['function']
								break
						else:
							break

					if executable['options'].get('texts') != None:
						if function == None:
							for text in executable['options'].get("texts"):
								if text == update.text:
									function = executable['function']
									break
						else:
							break

					if executable['options'].get('texts_lower') != None:
						if function == None:
							for text in executable['options'].get("texts_lower"):
								if text == update.text.lower():
									function = executable['function']
									break
						else:
							break

					if executable['options'].get('priveleged_type') != None:
						if function == None:
							for _type, regexp in self.priveleged_types.items():
								if len(re.findall(regexp, update.text)) > 0:
									function = executable['function']
									break
						else:
							break

					if len(update.attachments) != 0:
						if function == None:
							for attachment in update.attachments:
								if 'type' in attachment:
									if update.attachments[attachment] == executable['options'].get('content_type'):
										function = executable['function']
										break
						else:
							break

					for key, option in executable['options'].items():
						if function == None:
							for key1, option1 in update.items():
								if key1 == key and option1 == option:
									function = executable['function']
									break
						else:
							break
				else:
					break
		else:
			function = next_step

		if self.before_function != None:
			try:
				self.before_function(update)
			except Exception as e:
				print(f"Остановлена работа скрипта. {e}")
				return

		if function != None:
			function(update)
		else:
			if self.default_function != None:
				self.default_function(update)

		if self.after_function != None:
			self.after_function(update)

	def polling(self):
		for event in self.long_poll.listen():
			if event.type == VkBotEventType.MESSAGE_NEW:
				self.process_new_update(event.object)

	def send_message(self, text, peer_id, attachment=None, keyboard=None):
		return self.vk.messages.send(
			random_id=time.time() + random.randint(0, 12000000),
			peer_id=peer_id,
			attachment=attachment,
			message=text,
			keyboard=keyboard
		)

	def get_keys(self, one_time=False, buttons=[]):
		return json.dumps(dict(
			one_time=one_time,
			buttons=buttons
		), ensure_ascii=False)

	def get_btn(self, text, color, payload=None):
		payload = json.dumps(payload) if payload != None else "{\"none\":\"none\"}"
		return dict(
			action=dict(
				type="text", payload=payload, label=text
			),
			color=color.value
		)
