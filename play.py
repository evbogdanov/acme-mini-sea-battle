#!/usr/bin/env python3

import subprocess
import re
import random
import sys

# TODO: get rid of all `os.system`, use `subprocess` instead 
import os

## ACME EVENT
## -----------------------------------------------------------------------------

class Event:
	ORIG_MOUSE = 'M'
	ETYPE_MIDDLE_CLICKS = ['x', 'X']
	ETYPE_RIGHT_CLICKS = ['l', 'L']

	def __init__(self, event_bytes):
		is_valid, orig, etype, beg, end, text = self.parse_event(event_bytes)
		self.is_valid = is_valid
		self.orig = orig
		self.etype = etype
		self.beg = beg
		self.end = end
		self.text = text

	@property
	def is_middle_click(self):
		return (
			self.orig == self.ORIG_MOUSE and 
			self.etype in self.ETYPE_MIDDLE_CLICKS)

	@property
	def is_right_click(self):
		return (
			self.orig == self.ORIG_MOUSE and 
			self.etype in self.ETYPE_RIGHT_CLICKS)

	@classmethod
	def parse_event(cls, event_bytes):
		"""
		Parse window event.
		
		Valid event looks like:
		"event M L 1 1 0 3 2 4 Text '' ''"
		
		See `acmeevent(1)` for details
		"""

		is_valid = False
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
			is_valid = True
			orig = match.group(1)
			etype = match.group(2)
			beg = match.group(3)
			end = match.group(4)
			text = match.group(5) 

		return is_valid, orig, etype, beg, end, text

	def stringify(self):
		"""
		Convert event to the format understood by Acme
		"""
		return f'{self.orig}{self.etype}{self.beg} {self.end}'

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
		self.send_message('name', name)

	def send_message(self, *messages):
		"""
		Affect the window by sending messages to its controller
		"""
		message = ' '.join(messages)
		proc1 = subprocess.Popen(['echo', message], stdout=subprocess.PIPE)
		proc2 = subprocess.Popen(
			['9p', 'write', f'acme/{self.id}/ctl'],
			stdin=proc1.stdout, stdout=subprocess.PIPE)
		proc2.communicate()

	def send_event(self, event):
		"""
		Send stringified event to window
		"""
		os.system(f"echo '{event.stringify()}' | 9p write acme/{self.id}/event")

	def clean(self):
		"""
		Mark window as clean
		"""
		self.send_message('clean')

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

## GRID
## -----------------------------------------------------------------------------

class Grid:
	LETTERS = 'ABCD'
	NUMBERS = '1234'

	SQUARE_EMPTY = ' '
	SQUARE_SHIP = 'x'
	SQUARE_MISS = '-'
	SQUARE_HIT = '+'

	def __init__(self):
		squares = {}
		for coord in Grid.coordinates():
			squares[coord] = self.SQUARE_EMPTY
		self.squares = squares

	@staticmethod
	def coordinates():
		"""
		Gimme all possible coordinates on the grid
		"""
		return [f'{let}{num}'
			for let in Grid.LETTERS
			for num in Grid.NUMBERS]

	@staticmethod
	def is_valid_coordinate(coord):
		"""
		Game class will thank me for this method
		"""
		return (
			len(coord) == 2 and
			coord[0] in Grid.LETTERS and
			coord[1] in Grid.NUMBERS)

	def squares_at_line(self, num, hide_ships=False):
		"""
		Make printing line by line easy peasy
		"""
		squares_list = []
		for let in self.LETTERS:
			square = self.squares[f'{let}{num}']
			if hide_ships and square == self.SQUARE_SHIP:
				square = self.SQUARE_EMPTY
			squares_list.append(square)
		return squares_list

## GAME
## -----------------------------------------------------------------------------

class Game:
	NUMBER_OF_SHIPS = 4
	NUMBER_OF_CLICKS_TO_KEEP = 2
	
	STATUS_SHIPS_PLACEMENT = 1
	STATUS_SHOOTING = 2

	def __init__(self):
		self.window = Window()
		self.grid_player = Grid()
		self.grid_bot = Grid()
		self.player_clicks = ''
		self.status = self.STATUS_SHIPS_PLACEMENT

	def append_player_click(self, text):
		"""
		Append right click made by player. Return True on success.
		"""
		if len(text) == 1:
			self.player_clicks += text
			self.player_clicks = self.player_clicks[
				-self.NUMBER_OF_CLICKS_TO_KEEP:]
			return True
		return False

	def handle_player_coordinate(self, coord):
		"""
		This method fires up when the player enters a new (valid!) coordinate
		"""
		if self.status == self.STATUS_SHIPS_PLACEMENT:
			self.place_player_ship(coord)
			if not self.can_player_place_ships():
				self.status = self.STATUS_SHOOTING
		elif self.status == self.STATUS_SHOOTING:
			player_hit = self.do_player_shooting(coord)
			if player_hit:
				self.maybe_the_end()
			else:
				while True:
					bot_hit = self.do_bot_shooting()
					if bot_hit:
						self.maybe_the_end()
					else:
						break
		self.print()

	def handle_event(self, event):
		"""
		Handle a window's event
		"""
		if not event.is_valid:
			return

		if event.is_middle_click:
			# Middle click executes normal Acme commands
			self.window.send_event(event)
			return

		if not event.is_right_click:
			return

		# I only interested in right clicks
		appended = self.append_player_click(event.text)

		if not appended:
			return

		coord = self.player_clicks
		if not Grid.is_valid_coordinate(coord):
			return

		self.handle_player_coordinate(coord)

	def play(self):
		"""
		Start playing
		"""
		self.place_bot_ships()
		self.print()
		self.window.listen(self.handle_event)

	def print(self, hide_bot_ships=True):
		"""
		Print the state of the game to the window
		"""
		self.window.clear()
		squares = (
			self.grid_bot.squares_at_line(1, hide_ships=hide_bot_ships) +
			self.grid_player.squares_at_line(1) +
			self.grid_bot.squares_at_line(2, hide_ships=hide_bot_ships) +
			self.grid_player.squares_at_line(2) +
			self.grid_bot.squares_at_line(3, hide_ships=hide_bot_ships) +
			self.grid_player.squares_at_line(3) +
			self.grid_bot.squares_at_line(4, hide_ships=hide_bot_ships) +
			self.grid_player.squares_at_line(4))
		self.window.append("""
    A   B   C   D            A   B   C   D
  +---+---+---+---+        +---+---+---+---+
1 | {} | {} | {} | {} |      1 | {} | {} | {} | {} |
  +---+---+---+---+        +---+---+---+---+
2 | {} | {} | {} | {} |      2 | {} | {} | {} | {} |
  +---+---+---+---+        +---+---+---+---+
3 | {} | {} | {} | {} |      3 | {} | {} | {} | {} |
  +---+---+---+---+        +---+---+---+---+
4 | {} | {} | {} | {} |      4 | {} | {} | {} | {} |
  +---+---+---+---+        +---+---+---+---+""".format(*squares))
		self.window.clean()

	def can_player_place_ships(self):
		"""
		Can he?
		"""
		placed_ships = 0
		for square in self.grid_player.squares.values():
			if square == Grid.SQUARE_SHIP:
				placed_ships += 1
		return placed_ships < self.NUMBER_OF_SHIPS

	def place_player_ship(self, coord):
		"""
		Player places his ship on the given coordinate
		"""
		self.grid_player.squares[coord] = Grid.SQUARE_SHIP

	def place_bot_ships(self):
		"""
		Randomly place bot ships on the grid
		"""
		coords = Grid.coordinates()
		random.shuffle(coords)
		for coord in coords[:self.NUMBER_OF_SHIPS]:
			self.grid_bot.squares[coord] = Grid.SQUARE_SHIP

	def do_player_shooting(self, coord):
		"""
		Player shoots. If it's a hit, then return True.
		"""
		square = self.grid_bot.squares[coord]
		if square == Grid.SQUARE_SHIP:
			self.grid_bot.squares[coord] = Grid.SQUARE_HIT
			return True
		if square == Grid.SQUARE_EMPTY:
			self.grid_bot.squares[coord] = Grid.SQUARE_MISS
		return False

	def do_bot_shooting(self):
		"""
		Bot shoots
		"""
		coords = list(filter(lambda c:
			Grid.SQUARE_MISS != self.grid_player.squares[c] != Grid.SQUARE_HIT,
			Grid.coordinates()))
		if not coords:
			return False
		coord = random.choice(coords)
		square = self.grid_player.squares[coord]
		if square == Grid.SQUARE_SHIP:
			self.grid_player.squares[coord] = Grid.SQUARE_HIT
			return True
		self.grid_player.squares[coord] = Grid.SQUARE_MISS
		return False

	def maybe_the_end(self):
		"""
		Call me when somebody hits someone. The game might be over.
		"""
		def all_hit(grid):
			score = 0
			for square in grid.squares.values():
				if square == Grid.SQUARE_HIT:
					score += 1
			return score == self.NUMBER_OF_SHIPS

		if all_hit(self.grid_bot):
			self.exit('You won!')
		elif all_hit(self.grid_player):
			self.exit('You lost the game!')

	def exit(self, message):
		"""
		Print the final message and quit
		"""
		self.print(hide_bot_ships=False)
		self.window.append(message)
		self.window.clean()
		sys.exit()

## MAIN
## -----------------------------------------------------------------------------

def main():
	game = Game()
	game.play()

if __name__ == '__main__':
	main()
