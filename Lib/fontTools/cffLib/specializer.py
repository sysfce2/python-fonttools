# -*- coding: utf-8 -*-

"""T2CharString operator specializer and generalizer."""

from __future__ import print_function, division, absolute_import
from fontTools.misc.py23 import *

def programToCommands(program):
	"""Takes a T2CharString program list and returns list of commands.
	Each command is a two-tuple of commandname,arg-list.  The commandname might
	be None if no commandname shall be emitted (used for glyph width (TODO),
	hintmask/cntrmask argument, as well as stray arguments at the end of the
	program (¯\_(ツ)_/¯)."""

	commands = []
	stack = []
	it = iter(program)
	for token in it:
		if not isinstance(token, basestring):
			stack.append(token)
			continue
		if token in {'hintmask', 'cntrmask'}:
			if stack:
				commands.append((None, stack))
			commands.append((token, []))
			commands.append((None, [next(it)]))
		else:
			commands.append((token,stack))
		stack = []
	if stack:
		commands.append((None, stack))
	return commands

def commandsToProgram(commands):
	"""Takes a commands list as returned by programToCommands() and converts
	it back to a T2CharString program list."""
	program = []
	for op,args in commands:
		program.extend(args)
		if op:
			program.append(op)
	return program



def _everyN(el, n):
	"""Group the list el into groups of size n"""
	if len(el) % n != 0: raise ValueError(args)
	for i in range(0, len(el), n):
		yield el[i:i+n]


class _GeneralizerDecombinerCommandsMap(object):

	@staticmethod
	def rmoveto(args):
		if len(args) != 2: raise ValueError(args)
		yield ('rmoveto', args)
	@staticmethod
	def hmoveto(args):
		if len(args) != 1: raise ValueError(args)
		yield ('rmoveto', [args[0], 0])
	@staticmethod
	def vmoveto(args):
		if len(args) != 1: raise ValueError(args)
		yield ('rmoveto', [0, args[0]])

	@staticmethod
	def rlineto(args):
		for args in _everyN(args, 2):
			yield ('rlineto', args)
	@staticmethod
	def hlineto(args):
		it = iter(args)
		while True:
			yield ('rlineto', [next(it), 0])
			yield ('rlineto', [0, next(it)])
	@staticmethod
	def vlineto(args):
		it = iter(args)
		while True:
			yield ('rlineto', [0, next(it)])
			yield ('rlineto', [next(it), 0])

	@staticmethod
	def rrcurveto(args):
		for args in _everyN(args, 6):
			yield ('rrcurveto', args)
	@staticmethod
	def hhcurveto(args):
		if len(args) < 4 or len(args) % 4 > 1: raise ValueError(args)
		if len(args) % 2 == 1:
			yield ('rrcurveto', [args[1], args[0], args[2], args[3], args[4], 0])
			args = args[5:]
		for args in _everyN(args, 4):
			yield ('rrcurveto', [args[0], 0, args[1], args[2], args[3], 0])
	@staticmethod
	def vvcurveto(args):
		if len(args) < 4 or len(args) % 4 > 1: raise ValueError(args)
		if len(args) % 2 == 1:
			yield ('rrcurveto', [args[0], args[1], args[2], args[3], 0, args[4]])
			args = args[5:]
		for args in _everyN(args, 4):
			yield ('rrcurveto', [0, args[0], args[1], args[2], 0, args[3]])
	@staticmethod
	def hvcurveto(args):
		if len(args) < 4 or len(args) % 8 not in {0,1,4,5}: raise ValueError(args)
		last_args = None
		if len(args) % 2 == 1:
			lastStraight = len(args) % 8 == 5
			args, last_args = args[:-5], args[-5:]
		it = _everyN(args, 4)
		try:
			while True:
				args = next(it)
				yield ('rrcurveto', [args[0], 0, args[1], args[2], 0, args[3]])
				args = next(it)
				yield ('rrcurveto', [0, args[0], args[1], args[2], args[3], 0])
		except StopIteration:
			pass
		if last_args:
			args = last_args
			if lastStraight:
				yield ('rrcurveto', [args[0], 0, args[1], args[2], args[4], args[3]])
			else:
				yield ('rrcurveto', [0, args[0], args[1], args[2], args[3], args[4]])
	@staticmethod
	def vhcurveto(args):
		if len(args) < 4 or len(args) % 8 not in {0,1,4,5}: raise ValueError(args)
		last_args = None
		if len(args) % 2 == 1:
			lastStraight = len(args) % 8 == 5
			args, last_args = args[:-5], args[-5:]
		it = _everyN(args, 4)
		try:
			while True:
				args = next(it)
				yield ('rrcurveto', [0, args[0], args[1], args[2], args[3], 0])
				args = next(it)
				yield ('rrcurveto', [args[0], 0, args[1], args[2], 0, args[3]])
		except StopIteration:
			pass
		if last_args:
			args = last_args
			if lastStraight:
				yield ('rrcurveto', [0, args[0], args[1], args[2], args[3], args[4]])
			else:
				yield ('rrcurveto', [args[0], 0, args[1], args[2], args[4], args[3]])

	@staticmethod
	def rcurveline(args):
		if len(args) < 8 or len(args) % 6 != 2: raise ValueError(args)
		args, last_args = args[:-2], args[-2:]
		for args in _everyN(args, 6):
			yield ('rrcurveto', args)
		yield ('rlineto', last_args)
	@staticmethod
	def rlinecurve(args):
		if len(args) < 8 or len(args) % 2 != 0: raise ValueError(args)
		args, last_args = args[:-6], args[-6:]
		for args in _everyN(args, 2):
			yield ('rlineto', args)
		yield ('rrcurveto', last_args)


def generalizeCommands(commands, ignoreErrors=True):
	result = []
	mapping = _GeneralizerDecombinerCommandsMap
	for op,args in commands:
		func = getattr(mapping, op if op else '', None)
		if not func:
			result.append((op,args))
			continue
		try:
			for command in func(args):
				result.append(command)
		except ValueError:
			if ignoreErrors:
				# Store op as data, such that consumers of commands do not have to
				# deal with incorrect number of arguments.
				result.append((None,args))
				result.append((None, [op]))
			else:
				raise
	return result

def generalizeProgram(program, **kwargs):
	return commandsToProgram(generalizeCommands(programToCommands(program), **kwargs))


def _categorizeVector(v):
	"""
	Takes X,Y vector v and returns one of r, h, v, or 0 depending on which
	of X and/or Y are zero.

	>>> _categorizeVector((0,0))
	'0'
	>>> _categorizeVector((1,0))
	'h'
	>>> _categorizeVector((0,2))
	'v'
	>>> _categorizeVector((1,2))
	'r'
	"""
	return "rvh0"[(v[1]==0) * 2 + (v[0]==0)]

def specializeCommands(commands,
		       ignoreErrors=False,
		       generalizeFirst=True,
		       preserveTopology=False,
		       maxstack=48):

	# We perform several rounds of optimizations.  They are carefully ordered and are:
	#
	# 0. Generalize commands.
	#    This ensures that they are in our expected simple form, with each line/curve only
	#    having arguments for one segment, and using the generic form (rlineto/rrcurveto).
	#    If caller is sure the input is in this form, they can turn off generalization to
	#    save time.
	#
	# 1. Combine successive rmoveto operations.
	#
	# 2. Specialize rmoveto/rlineto/rrcurveto operators into horizontal/vertical variants.
	#    We specialize into some, made-up, varianats as well, which simplifies following
	#    passes.
	#
	# 3. Merge or delete redundant operations, if changing topology is allowed.  OpenType
	#    spec declares point numbers in CFF undefined, so by default we happily change
	#    topology.  If client relies on point numbers (in GPOS anchors, or for hinting
	#    purposes(what?)) they can turn this off.
	#
	# 4. Peephole optimization to revert back some of the h/v variants back into their
	#    original "relative" operator (rline/rrcurveto) if that saves a byte.
	#
	# 5. Resolve choices, ie. when same curve can be encoded in multiple ways using the
	#    same number of bytes, to maximize combining.
	#
	# 6. Combine adjacent operators when possible, minding not to go over max stack
	#    size.
	#
	# 7. Resolve any remaining made-up operators into real operators.
	#
	# I have convinced myself that this produces optimal bytecode (except for, possibly
	# one byte each time maxstack size prohibits combining.)  YMMV, but you'd be wrong. :-)

	# 0. Generalize commands.
	if generalizeFirst:
		commands = generalizeCommands(commands, ignoreErrors=ignoreErrors)
	else:
		commands = commands[:] # Make copy since we modify in-place later.

	# 1. Combine successive rmoveto operations.
	for i in range(len(commands)-1, 0, -1):
		if 'rmoveto' == commands[i][0] == commands[i-1][0]:
			v1, v2 = commands[i-1][1], commands[i][1]
			commands[i-1] = ('rmoveto', [v1[0]+v2[0], v1[1]+v2[1]])
			del commands[i]

	# 2. Specialize rmoveto/rlineto/rrcurveto operators into horizontal/vertical variants.
	#
	#    We, in fact, specialize into more, made-up, variants that special-case when both
	#    X and Y components are zero.  This simplifies the following optimization passes.
	#    This case is rare, but OCD does not let me skip it.
	#
	#    After this round, we will have four variants that use the following mnemonics:
	#
	#    - 'r' for relative,   ie. non-zero X and non-zero Y,
	#    - 'h' for horizontal, ie. zero X and non-zero Y,
	#    - 'v' for vertical,   ie. non-zero X and zero Y,
	#    - '0' for zeros,      ie. zero X and zero Y.
	#
	#    The zero pseudo-operators are not part of the spec, but help simplify the following
	#    optimization rounds.  We resolve them at the end.  So, after this, we will have four
	#    moveto and four lineto variants, and sixteen curveto variants.  For example, a
	#    '0hcurveto' operator means a curve dx0,dy0,dx1,dy1,dx2,dy2,dx3,dy3 where dx0, dx1,
	#    and dy3 are zero but not dx3.  An 'rvcurveto' means dx3 is zero but not dx0,dy0,dy3.
	for i in range(len(commands)):
		op,args = commands[i]
		if op not in {'rmoveto', 'rlineto'}:
			#c = _categorizeVector(args)
			continue
		if op != 'rrcurveto':
			continue

		# rrcurveto is the fun!

	#new_commands, commands = commands[:1], commands[1:]
	#for command in commands:
	#	new_commands.append(command)
	#commands, new_commands = new_commands, None

	return commands

def specializeProgram(program, **kwargs):
	return commandsToProgram(specializeCommands(programToCommands(program), **kwargs))


if __name__ == '__main__':
	import sys
	if len(sys.argv) == 1:
		import doctest
		sys.exit(doctest.testmod().failed)
	program = []
	for token in sys.argv[1:]:
		try:
			token = int(token)
		except ValueError:
			try:
				token = float(token)
			except ValueError:
				pass
		program.append(token)
	print("Program:"); print(program)
	commands = programToCommands(program)
	print("Commands:"); print(commands)
	program2 = commandsToProgram(commands)
	print("Program from commands:"); print(program2)
	assert program == program2
	print("Generalized program:"); print(generalizeProgram(program))
	print("Specialized program:"); print(specializeProgram(program))

