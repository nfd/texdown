#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import os
import re
import sys
import codecs

"""
Convert Texdown syntax to iother formats.

Very idiosyncratic. Not very generic.

The idea is to take a file in Texdown format and walk down a list of "conversions".
Each conversion is a regular expression. For each match of the regular expression,
a replacement is made. The replacement is either straight text, or a function.
If the replacer is a function, its return value is a string of replaced text.

Replacements often have a block structure. For example, a bulleted list is simply
a set of lines beginning with ' *'. Replacement functions need to know when to
start and end this list. The framework lets them know by passing in flags indicating
whether the block is "open at the start" and "open at the end" -- i.e. if it is
immediately preceded or succeeded by another match of the same type.
"""
# Attempt to import 'localmacros' from cwd preferentially.
sys.path.insert(0, '.')
try:
	import localmacros
except ImportError:
	localmacros = None

from optparse import OptionParser

# Conversions consisting of the regular expression to match, and
# the replacement text. The replacement may also be a function.
# Order is important: replacements are performed in the order
# listed.
CONVERSIONS_TXT = r"""
block_cmd:
	match	^\t(.*)$
	func	block_cmd
	incl	caption
startline_cmd:
	match	^!!([^ ]*?)(?: (.*?))?$
	func	startline_cmd
bullets:
	match	^( +)\*(.*?)\n
	func	bullets
	incl	escape_percents teletype quotes bold italics cite ref escape_underscores
numbers:
	match	^( +)([0-9]+)\.(.*?)\n
	func	numbers
	incl	escape_percents teletype quotes bold italics cite ref escape_underscores
description:
	match	^ (.+?):(.*)\n
	func	description
	incl	italics bold
mathmode:
	match	\$(.*?)\$
chapterstar:
	match	^##\*(.*)##
	incl	label
chapter:
	match	^## *(.*) *##
	incl	label
section:
	match	^== *(.*) *==
	incl	label escape_underscores escape_percents teletype
usenixabstract:
	match	^\^ *(.*) *\^
	incl	label escape_underscores escape_percents teletype
subsection:
	match	^= *(.*) *=
	incl	label escape_underscores escape_percents teletype
subsubsection:
	match	^- *(.*) *-
	incl	label escape_underscores escape_percents teletype
label:
	match	<<([^<]*)>>
caption:
	match	\~\~ ([^\~]*) \~\~
	incl	label cite
url:
	match	\(\((.*?)\)\)
cite:
	match	 *\[\[([^\[]*)\]\]
cite_fixme:
	match	\[\[FIXME\]\]
teletype:
	match	''(.+?)''
	incl	escape_underscores
ref:
	match	\[([^\[]*)\]
italics:
	match	([^A-Za-z]|^)/([^ ].+?[^ ])/([^A-Za-z]|$)
bold:
	match	\*([^\*]+)\*
subscript:
	match	__(.*?)__
quotes:
	match	"(.+?)"
	incl	escape_underscores escape_percents escape_ampersands
escape_underscores:
	match	_
escape_percents:
	match	(?!^)%
escape_ampersands:
	match	&
"""
def extract_conversions(conversions_txt):
	conversions = {}
	conversions_order = []

	hlname = None
	for line in conversions_txt.split('\n'):
		if not line.strip():
			continue

		if line.startswith('\t'):
			key, value = line[1:].split('\t', 1)
			if key == 'match':
				value = re.compile(value, re.MULTILINE)
			elif key == 'incl':
				value = value.split(' ')
			conversions[hlname][key] = value
		else:
			hlname = line[:-1]
			conversions[hlname] = {}
			conversions_order.append(hlname)
	
	return conversions, conversions_order

CONVERSIONS, CONVERSIONS_ORDER = extract_conversions(CONVERSIONS_TXT)

def update_conversions(conversions, more_conversions_txt):
	" Update conversions dict with values from matching keys in more_conversions_txt. "

	extra, more_conversions_order = extract_conversions(more_conversions_txt)

	for extra_name, extra_dict in extra.items():
		if extra_name in conversions:
			conversions[extra_name].update(extra_dict)

class ConversionError(Exception):
	pass

class Converter(object):
	def __init__(self, macro_classes):
		self.block_cmd = None
		self.block_accum = []
		self.macros = {}

		self.register_macros(self)
		if localmacros is not None:
			self.register_macros(localmacros.Macros(self))

		for cls in macro_classes:
			self.register_macros(cls(self))

	def __call__(self, texdown):
		self.reset()
		self.output = self.convert(texdown, magic = True)
		return self.output

	def reset(self):
		self.enum_depth = 0 # Keep track, so we can set the counter in \enumerate
	
	def register_macros(self, obj):
		for key in dir(obj):
			if key.startswith('macro_'):
				self.macros[key[6:]] = getattr(obj, key)

	def convert(self, texdown, magic = False, fragment = False):
		"""
		Conversion:
			Text is list of (chunk, names of conversions for this chunk),
			conceptually. Do a depth-first conversion and join up a
			complete text block in reality.
		"""
		if fragment:
			# Hack to ensure that ^ and $ don't match anything important.
			texdown = ' ' + texdown + ' '

		texdown = self.do_convert(texdown, CONVERSIONS_ORDER)
		#for match, replacement in CONVERSIONS:
		#	texdown = self.convert_one(texdown, match, replacement)

		if magic:
			# Hack: add document ending here.
			texdown += self.macros['end_document'](None)

			# Hack: magical abstract conversion.
			if 0:
				abstract_start = texdown.find('\section{ Abstract }')
				if abstract_start != -1:
					abstract_end = texdown.find('\section', abstract_start + 1)
					texdown = texdown[:abstract_start] \
						+ '\\begin{abstract}\n' \
						+ texdown[abstract_start + 20: abstract_end] \
						+ '\\end{abstract}\n' \
						+ texdown[abstract_end:]

		if fragment:
			texdown = texdown[1:-1]

		return texdown
	
	def do_convert(self, text, match_names):
		"""
		Walk down the list of names in match_names.
		"""
		result = []

		match_name = match_names[0]
		children = match_names[1:]
		conv = CONVERSIONS[match_name]

		for pre_match, match in self.convert_one(text, match_name, conv):
			if children:
				pre_match = self.do_convert(pre_match, children)
			if 'incl' in conv:
				match = self.do_convert(match, conv['incl'])
			result.append(pre_match)
			result.append(match)

		return ''.join(result)
			

	def convert_one(self, texdown, match_name, conv):
		match = conv['match']

		matches = list(match.finditer(texdown))
		if not matches:
			yield texdown, ''

		for idx in range(len(matches)):
			match = matches[idx]

			# Does this match start right after the previous one ends?
			if idx > 0:
				prev_end = matches[idx - 1].end()
				open_start = (match.start() - 1 > prev_end)
				#print("mid idx open start", open_start)
				# Store everything between the last result and this one.
				#result.append(texdown[prev_end:match.start()])
				before_match = texdown[prev_end:match.start()]
			else:
				# At beginning of file: start the block.
				open_start = True
				#print("beginning open start", open_start)
				#print("text", texdown)
				# Also store everything up to the first match in result.
				#result.append(texdown[:match.start()])
				before_match = texdown[:match.start()]

			# Work out if there is a newline after this match and before
			# the next one.
			if idx < (len(matches) - 1):
				next_start = matches[idx + 1].start()
				open_end = (match.end() +1 < next_start)
			else:
				# At end of file: end the block.
				open_end = True

			#print(match, newline_before, newline_after)

			if 'func' in conv:
				handler = self.macros[conv['func']]
				try:
					co = handler.__code__ # python 3
				except AttributeError:
					co = handler.func_code # python 2
				try:
					if co.co_argcount == 2:
						#result.append(handler(match))
						result = handler(match)
					else:
						#result.append(handler(match, open_start, open_end))
						result = handler(match, open_start, open_end)
				except:
					nl_count = texdown[:match.start()].count('\n')
					print("*** Error while converting line %d:" % (nl_count + 1))
					raise
			elif 'repl' in conv:
				result = match.expand(conv['repl'])
			else:
				raise NotImplementedError()

			# If there is a post-processing handler, call it here.
			postprocess_handler = self.macros.get('postproc_%s' % (match_name))
			if postprocess_handler:
				result = postprocess_handler(result)

			yield before_match, result

		if matches:
			# Store everything after the last match
			#result.append(texdown[matches[-1].end():])
			yield texdown[matches[-1].end():], ''
	
	def macro_block_cmd(self, match, open_start, open_end):
		# A block command ends with \t!!(.*) on its first line. This 
		# determines the real block handler.
		line = match.group(1)
		if open_start:
			# Expect a block command.
			if '\t!!' not in line:
				raise ConversionError("Block does not end with \\t!!macroname")
			line, self.block_cmd = line.rsplit('\t!!', 1)
		if line.strip():
			self.block_accum.append(line)
		if open_end:
			handler = self.macros[self.block_cmd]
			result = handler(self.block_accum)
			self.block_accum = []
			self.block_cmd = None
			return result
		else:
			return ''

	def macro_startline_cmd(self, match):
		command = match.group(1)
		args = match.group(2)

		try:
			handler = self.macros[command]
		except KeyError:
			raise ConversionError("Macro '%s' not found." % (command))
		return handler(args)

def parse_args():
	parser = OptionParser()
	parser.add_option('-m', dest = 'localmacros', default = [], action = 'append')
	return parser.parse_args() # returns (opts, args)

def import_local_macros(filenames):
	# Read "filenames", return list of Macros classes.

	clses = []

	for filename in filenames:
		# Convert the filename to a module name by removing path components and
		# stripping the extension if present.
		modulename = filename
		modulename = os.path.split(modulename)[1]
		modulename = os.path.splitext(modulename)[0]

		if modulename not in sys.modules:
			__import__(modulename)

		clses.append(sys.modules[modulename].Macros)

	return clses

def run_specialised_converter(name, specialised_conversions_txt, specialised_macros):
	update_conversions(CONVERSIONS, specialised_conversions_txt)

	opts, args = parse_args()

	local_macro_clses = [specialised_macros] + import_local_macros(opts.localmacros)

	texdownfile = args[0]
	
	handle = codecs.open(texdownfile, 'r', encoding = 'utf-8')
	data = handle.read()
	handle.close()

	c = Converter(local_macro_clses)

	try:
		output = c(data)
	except ConversionError as e:
		print("Error: %s" % (e,))
		sys.exit(1)

	if len(args) == 2:
		outputfile = args[1]
		handle = codecs.open(outputfile, 'w', encoding = 'utf-8')
		handle.write(output)
		handle.close()
	else:
		sys.stdout.write(output)

