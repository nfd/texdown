#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
import codecs

"""
Convert Texdown syntax to LaTeX.

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
import re
import sys
# Attempt to import 'localmacros' from cwd preferentially.
sys.path.insert(0, '.')
import localmacros

# Conversions consisting of the regular expression to match, and
# the replacement text. The replacement may also be a function.
# Order is important: replacements are performed in the order
# listed.
CONVERSIONS_TXT = r"""
block_cmd:
	match	^\t(.*)$
	func	block_cmd
	incl	caption
startline:
	match	^!!([^ ]*?)(?: (.*?))?$
	func	startline_cmd
bullets:
	match	^( +)\*(.*?)\n
	func	bullets
	incl	escape_percents teletype quotes bold italics cite ref escape_underscores
numbers:
	match	^( +)[0-9]+\.(.*?)\n
	func	numbers
	incl	escape_percents teletype quotes bold italics cite ref escape_underscores
description:
	match	^ (.+?):(.*)\n
	func	description
	incl	italics bold
mathmode:
	match	\$(.*?)\$
	repl	$\1$
chapterstar:
	match	^##\*(.*)##
	repl	\\chapter*{\1}
	incl	label
chapter:
	match	^##(.*)##
	repl	\\chapter{\1}
	incl	label
section:
	match	^==(.*)==
	repl	\\section{\1}
	incl	label escape_underscores escape_percents teletype
subsection:
	match	^=(.*)=
	repl	\\subsection{\1}
	incl	label escape_underscores escape_percents teletype
subsubsection:
	match	^-(.*)-
	repl	\\subsubsection{\1}
	incl	label escape_underscores escape_percents teletype
label:
	match	<<([^<]*)>>
	repl	\\label{\1}
caption:
	match	\~\~ ([^\~]*) \~\~
	repl	\\caption{\1}
	incl	label cite
url:
	match	\(\((.*?)\)\)
	repl	\\url{\1}
cite:
	match	 *\[\[([^\[]*)\]\]
	repl	~\\citep{\1}
cite_fixme:
	match	\[\[FIXME\]\]
	repl	~\\cite{FIXME}
teletype:
	match	''(.+?)''
	repl	\\texttt{\1}
	incl	escape_underscores
ref:
	match	\[([^\[]*)\]
	repl	\\ref{\1}
italics:
	match	([^A-Za-z]|^)/([^ ].+?[^ ])/([^A-Za-z]|$)
	repl	\1\\textit{\2}\3
bold:
	match	\*([^\*]+)\*
	repl	\\textbf{\1}
subscript:
	match	__(.*?)__
	repl	\\subscript{\1}
quotes:
	match	"(.+?)"
	repl	``\1''
	incl	escape_underscores escape_percents escape_ampersands
escape_underscores:
	match	_
	repl	\_
escape_percents:
	match	(?!^)%
	repl	\%
escape_ampersands:
	match	&
	repl	\&
"""
CONVERSIONS = {}
CONVERSIONS_ORDER = []
hlname = None
for line in CONVERSIONS_TXT.split('\n'):
	if not line.strip():
		continue

	if line.startswith('\t'):
		key, value = line[1:].split('\t', 1)
		if key == 'match':
			value = re.compile(value, re.MULTILINE)
		elif key == 'incl':
			value = value.split(' ')
		CONVERSIONS[hlname][key] = value
	else:
		hlname = line[:-1]
		CONVERSIONS[hlname] = {}
		CONVERSIONS_ORDER.append(hlname)

class ConversionError(Exception):
	pass

class Converter(object):
	def __init__(self, texdown):
		self.block_cmd = None
		self.block_accum = []
		self.macros = {}

		self.register_macros(self)
		self.register_macros(localmacros.Macros(self.convert))

		self.latex = self.convert(texdown, magic = True)
	
	def register_macros(self, obj):
		for key in dir(obj):
			if key.startswith('macro_'):
				self.macros[key[6:]] = getattr(obj, key)

	def convert(self, texdown, magic = False):
		"""
		Conversion:
			Text is list of (chunk, names of conversions for this chunk),
			conceptually. Do a depth-first conversion and join up a
			complete text block in reality.
		"""
		texdown = self.do_convert(texdown, CONVERSIONS_ORDER)
		#for match, replacement in CONVERSIONS:
		#	texdown = self.convert_one(texdown, match, replacement)

		if magic:
			# Hack: add document ending here.
			texdown += self.macros['end_document'](None)

			# Hack: magical abstract conversion.
			abstract_start = texdown.find('\section{ Abstract }')
			if abstract_start != -1:
				abstract_end = texdown.find('\section', abstract_start + 1)
				texdown = texdown[:abstract_start] \
					+ '\\begin{abstract}\n' \
					+ texdown[abstract_start + 20: abstract_end] \
					+ '\\end{abstract}\n' \
					+ texdown[abstract_end:]

		return texdown
	
	def do_convert(self, text, match_names):
		"""
		Walk down the list of names in match_names.
		"""
		result = []

		match_name = match_names[0]
		children = match_names[1:]
		conv = CONVERSIONS[match_name]

		for pre_match, match in self.convert_one(text, conv):
			if children:
				pre_match = self.do_convert(pre_match, children)
			if 'incl' in conv:
				match = self.do_convert(match, conv['incl'])
			result.append(pre_match)
			result.append(match)

		return ''.join(result)
			

	def convert_one(self, texdown, conv):
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

			yield before_match, result

		if matches:
			# Store everything after the last match
			#result.append(texdown[matches[-1].end():])
			yield texdown[matches[-1].end():], ''
	
	def macro_bullets(self, match, open_start, open_end):
		result = []

		if open_start:
			result.append('\\begin{itemize}\n')
		result.append('\t\\item %s\n' % match.group(2))
		if open_end:
			result.append('\\end{itemize}\n')

		return ''.join(result)
	
	def macro_numbers(self, match, open_start, open_end):
		result = []

		if open_start:
			result.append('\\begin{enumerate}\n')
		result.append('\t\\item %s\n' % match.group(2))
		if open_end:
			result.append('\\end{enumerate}\n')

		return ''.join(result)

	
	def macro_description(self, match, open_start, open_end):
		result = []

		if open_start:
			result.append('\\begin{description}\n')
		key, value = self.convert(match.group(1)), self.convert(match.group(2))
		result.append('\t\\item[%s:] %s\n' % (key, value))
		if open_end:
			result.append('\\end{description}\n')

		return ''.join(result)
	
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
	
if __name__ == '__main__':
	handle = codecs.open(sys.argv[1], 'r', encoding = 'utf-8')
	data = handle.read()
	handle.close()

	try:
		c = Converter(data)
	except ConversionError, e:
		print "Error: %s" % (str(e))
		sys.exit(1)

	if len(sys.argv) == 3:
		handle = codecs.open(sys.argv[2], 'w', encoding = 'utf-8')
		handle.write(c.latex)
		handle.close()
	else:
		sys.stdout.write(c.latex)

