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
import os
import re
import sys
import macros as builtinmacros
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
startline:
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
	repl	$\1$
chapterstar:
	match	^##\*(.*)##
	repl	\\chapter*{\1}
	incl	label
chapter:
	match	^## *(.*) *##
	repl	\\chapter{\1}
	incl	label
section:
	match	^== *(.*) *==
	repl	\\section{\1}
	incl	label escape_underscores escape_percents teletype
usenixabstract:
	match	^\^ *(.*) *\^
	repl	\\subsection*{\1}
	incl	label escape_underscores escape_percents teletype
subsection:
	match	^= *(.*) *=
	repl	\\subsection{\1}
	incl	label escape_underscores escape_percents teletype
subsubsection:
	match	^- *(.*) *-
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
	def __init__(self, texdown, macro_classes):
		self.block_cmd = None
		self.block_accum = []
		self.macros = {}

		self.register_macros(self)
		self.register_macros(builtinmacros.Macros(self))
		if localmacros is not None:
			self.register_macros(localmacros.Macros(self))

		for cls in macro_classes:
			self.register_macros(cls(self))

		self.enum_depth = 0 # Keep track, so we can set the counter in \enumerate

		self.latex = self.convert(texdown, magic = True)
	
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

		enum_number = int(match.group(2))
		if open_start:
			result.append('\\begin{enumerate}\n')
			self.enum_depth += 1
			if enum_number != 1:
				varname = 'enum' + 'i' * self.enum_depth
				result.append('\\setcounter{%s}{%d}\n' % (varname, enum_number - 1))
		result.append('\t\\item %s\n' % match.group(3))
		if open_end:
			result.append('\\end{enumerate}\n')
			self.enum_depth -= 1

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

	# Functions to make available to macros.py and localmacros.py.
	def separate_tabs(self, line):
		return re.split(r'\t+', line)

	def make_author(self, name, email, affiliation):
		all_info = [name]
		if email:
			all_info.append(r"\\" + "\n\t\t%s" % (email))
		if affiliation:
			all_info.append(r"\\" + "\n\t\t%s" % (affiliation))
		return r"	\authorinfo{%s}" % (''.join(all_info))+ "\n" 

	def make_author_plain(self, name, email, affiliation):
		all_info = [name]
		if email:
			all_info.append(r"\\" + "\n\t\t%s" % (email))
		if affiliation:
			all_info.append(r"\\" + "\n\t\t%s" % (affiliation))
		return r"	\author{%s}" % (''.join(all_info))+ "\n" 

	def anypaper(self, block_lines, author = None):
		info = {'AUTHORS': '?authors',
			'conference': ('?conf', '?conf'), 
			'copyrightyear': '?year',
			'title': '?title'}

		authors = []

		for line in block_lines:
			line = self.separate_tabs(line)
			key = line.pop(0)

			if key == 'author':
				author_name = line[0]
				if len(line) >= 2:
					author_email = line[1]
				else:
					author_email = None
				if len(line) >= 3:
					if line[2].startswith('"'):
						# Directly-written affiliation
						assert line[2].endswith('"')
						author_affil = line[2][1:-1]
					else:
						author_affil = AFFILIATIONS[line[2]]
				else:
					author_affil = None
				authors.append(author(author_name, author_email, author_affil))
			else:
				for idx in range(len(line)):
					info[key + str(idx)] = line[idx]

		if authors:
			info['AUTHORS'] = '\n'.join(authors)
		else:
			info['AUTHORS'] = ''
		return info

	# Popular stuff from localmacros.py
	def fancy_table(self, block_lines, check_for_sizes = False, make_float = True, cell_func = None, horizborders = None, vertborders = None):
		"""
		Produces a table containing data. Numbers must be tab separated. EG:
			X	Y	!!numericresults
			37	1
			38	2
		"""

		if block_lines[-1].startswith('~~'):
			caption = block_lines.pop()
		else:
			caption = None
		result = []
		if make_float:
			result.append('\\begin{table}\n')

		block_lines = [self.separate_tabs(line) for line in block_lines]
		cols = len(block_lines[0])

		if cell_func:
			for rownum in range(len(block_lines)):
				line = block_lines[rownum]
				for colnum in range(len(line)):
					line[colnum] = cell_func(rownum, colnum, line[colnum])
				block_lines[rownum] = line


		latex_sizes = ['l'] * cols # The default

		if check_for_sizes:
			# The first row may contain size information of the form !\d+%. If
			# it does, use 'p' rather than 'l' to lay out the table, and base
			# the overall size on the known page width.
			all_sizes_percent = [-1] * cols
			found_one = False
			for col_num, element in enumerate(block_lines[0]):
				matcher = re.match(r'.*!([0-9]+)%$', element)
				if matcher:
					found_one = True
					all_sizes_percent[col_num] = int(matcher.group(1))
					block_lines[0][col_num] = element[:element.rfind('!')]

			if found_one:
				# Assign any missing numbers
				perc_left = 100
				for col_num in range(cols):
					if all_sizes_percent[col_num] == -1:
						all_sizes_percent[col_num] = perc_left
					else:
						perc_left -= all_sizes_percent[col_num]

				# Convert to mm
				all_sizes_mm = [(self.page_width_mm * col_size) / 100 \
						for col_size \
						in all_sizes_percent]
				latex_sizes = ['p{%dmm}' % (size_mm) for size_mm in all_sizes_mm]

		# Check for magical alignment of columns.
		# Left-alignment (the default): cells neither start nor end with a space.
		# Right-alignment: At least one cell starts with a space; no cell ends with one.
		# Centered alignment: At least one cell both starts and ends with a space.
		# at least one entry with a space.
		for col_num in range(cols):
			align = latex_sizes[col_num]
			if len(align) == 1 and align in 'lcr':
				for line in block_lines:
					cell = line[col_num]
					if cell.startswith(' ') and align == 'l':
						align = 'r'
					if cell.endswith(' '):
						align = 'c'
				latex_sizes[col_num] = align


		# Borders
		if horizborders:
			if horizborders[1] == '|':
				latex_sizes = [item for sublist in zip(latex_sizes, ['|'] * len(latex_sizes))
						for item in sublist][:-1]
			if horizborders[0] == '|':
				latex_sizes.insert(0, '|')
			if horizborders[2] == '|':
				latex_sizes.append('|')

		# Start output
		latex_sizecmd = ''.join(latex_sizes)
		result.append('	\\begin{tabular}{%s}\n' % latex_sizecmd)


		if vertborders and vertborders[0] == '-':
			result.append('\\hline\n')

		count = 0
		for line in block_lines:
			if vertborders and vertborders[1] == '-' and count > 0:
				result.append('\\hline\n')
			if vertborders and vertborders[1] == 't' and count == 1:
				result.append('\\hline\n')
			elements = [self.convert(element) for element in line]

			result.append('\t')

			result.append(' & '.join(elements))

			result.append(r'\\' + '\n')
			count += 1

		if vertborders and vertborders[2] == '-':
			result.append('\\hline\n')

		result.append('	\\end{tabular}\n')
		if caption:
			result.append(caption)
		if make_float:
			result.append('\\end{table}\n')
		return ''.join(result)

	def macro_floatgraphic(self, args):
		"""
		Includes a graphic, places it in a figure, and gives it a label. Usage:
		!!floatgraphic filename, Caption goes here
		"""
		return self.macro_anygraphic(args, floating = True)

	def macro_inlinegraphic(self, args):
		return self.macro_anygraphic(args, floating = False)

	def macro_anygraphic(self, args, floating = True, centered = False, floatspec = None, extra = ""):
		if ',' in args:
			filename, caption = args.split(',', 1)
			caption = caption.strip()
		else:
			filename = args
			caption = None

		label = filename
		if '/' in label:
			label = label.split('/')[-1]
		if '#' in label:
			filename = filename.split('#')[0]
			label = label.replace('#', '.')
		label = label.replace('-', '.')

		if floatspec is None:
			floatspec = '[htb]'

		result = []

		if floating:
			result.append('\\begin{figure}%s' % (floatspec))

		if centered:
			result.append('\\begin{center}')

		result.append('\\includegraphics%s{figures/%s}' % (extra, filename))
	
		if centered:
			result.append('		\\end{center}')

		if floating:
			result.append('	\\caption{\\label{figure.%s}%s}' % (label, caption))
			result.append('\\end{figure}')

		else:
			result.append('\\captionof{figure}{%s}' % (caption))
		return '\n'.join(result)

	def macro_floatgraphic_wholepage(self, args):
		result = [self.macro_floatgraphic(args),
				'\\afterpage{\\clearpage}']
		return '\n'.join(result)
	

	def macro_absolutegraphic(self, args):
		"""
		Includes an absolutely-positioned graphic without label.
		"""
		filename, left, top, height= \
			[arg.strip() for arg in args.split(',')]
		result = [
			r'\begin{picture}(0.0, 0.0)',
			r'	\put(%s,%s) {' % (left, top),
			r'		\includegraphics[height=%s]{figures/%s}' % (height, filename),
			r'	}',
			r'\end{picture}',
		]
		return '\n'.join(result)
	
	def macro_floatcode(self, block_lines, placement_spec = None):
		"""
		Code inside a figure. If the final line is a caption, does the right
		thing. Usage:
			code line 1	!!floatcode
			final code line
			~~ <<label.if.wanted>> Caption if wanted ~~
		"""
		if placement_spec is None:
			placement_spec = 'htb'

		caption = None
		if block_lines[-1].startswith('~~'):
			caption = block_lines.pop()
		block_lines = [line.replace('\t', '  ') for line in block_lines]
		result = ['\\begin{figure}[%s]' % (placement_spec)]
		result.append('\\begin{verbatim}')
		result.extend(block_lines)
		result.append('\\end{verbatim}')
		if caption:
			result.append(caption)
		result.append('\\end{figure}')
		return '\n'.join(result)
	
	def macro_exactfloatcode(self, block_lines):
		return self.macro_floatcode(block_lines, 'h!')
	
	def macro_floattable(self, block_lines):
		return self.fancy_table(block_lines, check_for_sizes = True)
	
	def macro_inlinetable(self, block_lines):
		return self.fancy_table(block_lines, check_for_sizes = True, make_float = False)
	
	def macro_blockquote(self, block_lines):
		# Special-case attribution line.
		if block_lines[-1].startswith('--'):
			block_lines[-1] = r'\begin{flushright} --' +\
				self.convert(block_lines[-1][2:]) +\
				r'\end{flushright}'
		result = [r'\begin{quote}'] + block_lines + [r'\end{quote}']
		return '\n'.join(result) + '\n'

	
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

	print clses
	return clses

if __name__ == '__main__':
	opts, args = parse_args()

	local_macro_clses = import_local_macros(opts.localmacros)

	texdownfile = args[0]
	
	handle = codecs.open(texdownfile, 'r', encoding = 'utf-8')
	data = handle.read()
	handle.close()

	try:
		c = Converter(data, local_macro_clses)

	except ConversionError, e:
		print "Error: %s" % (str(e))
		sys.exit(1)

	if len(args) == 2:
		outputfile = args[1]
		handle = codecs.open(outputfile, 'w', encoding = 'utf-8')
		handle.write(c.latex)
		handle.close()
	else:
		sys.stdout.write(c.latex)

