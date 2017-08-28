#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :
"""
Convert Texdown syntax to HTML.
"""

import texdown
import re

# Basic HTML-specific conversions
CONVERSIONS_TXT = r"""
#mathmode:
#	repl	$\1$
chapterstar:
	repl	<h1>\1</h1>
chapter:
	repl	<h1>\1</h1>
section:
	repl	<h2>\1</h2>
usenixabstract:
	repl	<h3>\1</h3>
subsection:
	repl	<h3>\1</h3>
subsubsection:
	repl	<h4>\1</h4>
label:
	repl	\\label{\1}
caption:
	repl	\\caption{\1}
url:
	repl	<a href="\1">\1</a>
cite:
	repl	~\\citep{\1}
cite_fixme:
	repl	~\\cite{FIXME}
teletype:
	repl	\\texttt{\1}
ref:
	repl	\\ref{\1}
italics:
	repl	\1<i>\2</i>\3
bold:
	repl	<b>\1</b>
subscript:
	repl	<sub>\1</sub>
quotes:
	repl	"\1"
escape_underscores:
	repl	_
escape_percents:
	repl	%
escape_ampersands:
	repl	&
escape_leftbracket
	match	<
	repl	&lt;
"""

# Large LaTeX macros
AFFILIATIONS = {
	'NICTAUNSWThanks': r"""NICTA\thanks{
      NICTA is funded by the Australian Government as represented by the
      Department of Broadband, Communications and the Digital Economy
      and the Australian Research Council through the ICT Centre of
      Excellence program.
    } and The University of New South Wales\\
    Sydney, Australia""",
	'GEN_AFFIL': r"""Insert Affiliation Here\\
		City, Country""",
}

TECHREPORT = r"""
<html>
<head>
<title>%(title0)s</title>
<body>

<h1>%(title0)s</h1>
%(AUTHORS)s

"""

END_DOCUMENT=r"""
</body>
</html>
"""

END_DOCUMENT_NIL = ''

class Macros(object):
	def __init__(self, texdown):
		self.texdown = texdown
		self.end_document = END_DOCUMENT_NIL

	def macro_techreport(self, block_lines):
		self.end_document = END_DOCUMENT
		return TECHREPORT % self.anypaper(block_lines, author = self.make_author_joined)

	def macro_end_document(self, args):
		return self.end_document

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

	def separate_tabs(self, line):
		return re.split(r'\t+', line)

	def make_author_joined(self, authorlist):
		name_template = '<b>%(name)s</b>'
		email_template = '<a href="mailto:%(email)s">%(email)s</a>'
		affiliation_template = '%(affiliation)s'

		authors = []
		for name, email, affiliation in authorlist:
			all_info = [name_template % {'name': name}]

			if affiliation:
				all_info.append(affiliation_template % {'affiliation': affiliation})

			if email:
				all_info.append(email_template % {'email': email})

			authors.append(', '.join(all_info))
		return '<br>'.join(authors)

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
						# FIXME: This has to move somewhere else.
						author_affil = AFFILIATIONS[line[2]]
				else:
					author_affil = None
				authors.append((author_name, author_email, author_affil))
			else:
				for idx in range(len(line)):
					info[key + str(idx)] = line[idx]

		if authors:
			info['AUTHORS'] = author(authors)
		else:
			info['AUTHORS'] = ''
		return info

	

if __name__ == '__main__':
	texdown.run_specialised_converter('latex', CONVERSIONS_TXT, Macros)

