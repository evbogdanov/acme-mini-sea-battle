#!/usr/bin/env python3

import subprocess
import os

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
		proc2 = subprocess.Popen(['9p', 'write', f'acme/{self.id}/ctl'], stdin=proc1.stdout, stdout=subprocess.PIPE)
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
		proc2 = subprocess.Popen(['9p', 'write', f'acme/{self.id}/body'], stdin=proc1.stdout, stdout=subprocess.PIPE)
		proc2.communicate()

	def clear(self):
		"""
		Clear window's body
		"""
		os.system(f"echo '' | tr '\n' ',' | 9p write acme/{self.id}/addr")
		os.system(f"9p write acme/{self.id}/data </dev/null")

## PLAY
## -----------------------------------------------------------------------------

def play():
	w = Window()
	print(w.id)
	w.append('One\nTwo')
#	w.clear()
	w.clean()

if __name__ == '__main__':
	play()
