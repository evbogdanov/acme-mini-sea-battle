#!/usr/bin/env python3

import subprocess
import re

# TODO: don't use `os`
import os

## ACME EVENT
## -----------------------------------------------------------------------------

class Event:
	def __init__(self, event_bytes):
		valid, orig, etype, beg, end, text = self.parse_event(event_bytes)
		self.valid = valid
		self.orig = orig
		self.etype = etype
		self.beg = beg
		self.end = end
		self.text = text

	@classmethod
	def parse_event(cls, event_bytes):
		"""
		Parse window event.
		
		Valid event looks like:
		"event M L 1 1 0 3 2 4 Text '' ''"
		
		See `acmeevent(1)` for details
		"""

		valid = False
		orig = ''
		etype = ''
		beg = ''
		end = ''
		text = ''

		event_str = event_bytes.decode().rstrip()		
		match = re.match(
			r"^event (\w+) (\w+) (\d+) (\d+) \d+ \d+ \d+ \d+ (.+) '' ''$",
			event_str)

		if match:
			valid = True
			orig = match.group(1)
			etype = match.group(2)
			beg = match.group(3)
			end = match.group(4)
			text = match.group(5) 

		return valid, orig, etype, beg, end, text

## ACME WINDOW
## -----------------------------------------------------------------------------

class Window:
	def __init__(self):
		id = self._create_window()
		self._id = id
		self.name = '/mini-sea-battle/'

	@classmethod
	def _create_window(cls):
		"""
		Create new window and return its ID
		"""
		result = subprocess.run(
			['9p', 'read', 'acme/new/ctl'],
			stdout=subprocess.PIPE)
		return int(result.stdout.decode().split()[0])

	@property
	def id(self):
		return self._id

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, name):
		self._name = name
		self._send('name', name)

	def _send(self, *messages):
		"""
		Affect the window by sending messages to its controller
		"""
		message = ' '.join(messages)
		proc1 = subprocess.Popen(['echo', message], stdout=subprocess.PIPE)
		proc2 = subprocess.Popen(
			['9p', 'write', f'acme/{self.id}/ctl'],
			stdin=proc1.stdout, stdout=subprocess.PIPE)
		proc2.communicate()

	def clean(self):
		"""
		Mark window as clean
		"""
		self._send('clean')

	def append(self, text):
		"""
		Append text to the window's body
		"""
		proc1 = subprocess.Popen(['echo', text], stdout=subprocess.PIPE)
		proc2 = subprocess.Popen(
			['9p', 'write', f'acme/{self.id}/body'],
			stdin=proc1.stdout, stdout=subprocess.PIPE)
		proc2.communicate()

	def clear(self):
		"""
		Clear window's body
		"""
		os.system(f"echo '' | tr '\n' ',' | 9p write acme/{self.id}/addr")
		os.system(f"9p write acme/{self.id}/data </dev/null")

	def listen(self, handler):
		"""
		Start listening for events
		"""
		pipe = subprocess.Popen(
			f'9p read acme/{self.id}/event 2>/dev/null | acmeevent',
			shell=True, stdout=subprocess.PIPE).stdout
		for event_bytes in pipe:
			event = Event(event_bytes)
			handler(event)

## GAMEPLAY
## -----------------------------------------------------------------------------

def play():
	def event_handler(event):
		if event.valid:
			print(f"Valid event: {event.orig} {event.etype} '{event.text}'")
		else:
			print('Invalid event')

	w = Window()
	print(w.id)
	w.append('One\nTwo')
	w.clean()
	w.listen(event_handler)

if __name__ == '__main__':
	play()
