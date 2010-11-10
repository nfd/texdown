import re

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

SIGPLANPAPER = r"""\documentclass[preprint,natbib,10pt]{sigplanconf}

\usepackage{graphicx}
\setkeys{Gin}{keepaspectratio=true,clip=true,draft=false,width=\linewidth}
\usepackage{url}
\usepackage{amsmath}
\usepackage[pdfborder={0 0 0}]{hyperref}

\makeatletter 
\g@addto@macro\@verbatim\small 
\makeatother 

\begin{document}
  \conferenceinfo{%(conference0)s}{%(conference1)s}
  \copyrightyear{%(copyrightyear0)s}
  \title{%(title0)s}

  %(AUTHORS)s
  \maketitle
"""

TECHREPORT = r"""\documentclass[preprint,natbib,10pt]{article}

\usepackage{graphicx}
\setkeys{Gin}{keepaspectratio=true,clip=true,draft=false,width=\linewidth}
\usepackage{url}
\usepackage{amsmath}
\usepackage[pdfborder={0 0 0}]{hyperref}

\makeatletter 
\g@addto@macro\@verbatim\small 
\makeatother 

\begin{document}
  \title{%(title0)s}

  %(AUTHORS)s
  \maketitle
"""

NICTATR = r"""\documentclass[preprint,natbib,10pt]{article}

\usepackage{graphicx}
\setkeys{Gin}{keepaspectratio=true,clip=true,draft=false,width=\linewidth}
\usepackage{url}
\usepackage{amsmath}
\usepackage[pdfborder={0 0 0}]{hyperref}

\makeatletter 
\g@addto@macro\@verbatim\small 
\makeatother 

\begin{document}
  \title{%(title0)s}

	%(AUTHORS)s
  \maketitle
"""

END_DOCUMENT=r"""
	\bibliographystyle{plainnat}
	\bibliography{papers}
	\end{document}
"""

END_DOCUMENT_PLAIN=r"""
	\bibliographystyle{plain}
	\bibliography{papers}
	\end{document}
"""

END_DOCUMENT_NIL = ''


def separate_tabs(line):
	return re.split(r'\t+', line)

def make_author(name, email, affiliation):
	all_info = [name]
	if email:
		all_info.append(r"\\" + "\n\t\t%s" % (email))
	if affiliation:
		all_info.append(r"\\" + "\n\t\t%s" % (affiliation))
	return r"	\authorinfo{%s}" % (''.join(all_info))+ "\n" 

def make_author_plain(name, email, affiliation):
	all_info = [name]
	if email:
		all_info.append(r"\\" + "\n\t\t%s" % (email))
	if affiliation:
		all_info.append(r"\\" + "\n\t\t%s" % (affiliation))
	return r"	\author{%s}" % (''.join(all_info))+ "\n" 

class Macros(object):
	def __init__(self, convert_cmd = None):
		self.end_document = END_DOCUMENT_NIL
		self.convert_cmd = convert_cmd
		self.page_width_mm = 210 - 89 # subtract margins

	def macro_sigplanpaper(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		self.author = make_author
		return SIGPLANPAPER % self.anypaper(block_lines)

	def macro_techreport(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		self.author = make_author_plain
		return TECHREPORT % self.anypaper(block_lines)

	def macro_nictatr(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		self.author = make_author_plain
		return NICTATR % self.anypaper(block_lines)
	
	def anypaper(self, block_lines):
		info = {'AUTHORS': '?authors',
			'conference': ('?conf', '?conf'), 
			'copyrightyear': '?year',
			'title': '?title'}

		authors = []

		for line in block_lines:
			line = separate_tabs(line)
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
				authors.append(self.author(author_name, author_email, author_affil))
			else:
				for idx in range(len(line)):
					info[key + str(idx)] = line[idx]

		if authors:
			info['AUTHORS'] = '\n'.join(authors)
		return info
	
	def fancy_table(self, block_lines, check_for_sizes = False,
				make_float = True):
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

		block_lines = [separate_tabs(line) for line in block_lines]
		cols = len(block_lines[0])

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

		latex_sizecmd = ''.join(latex_sizes)
		result.append('	\\begin{tabular}{%s}\n' % latex_sizecmd)

		count = 0
		for line in block_lines:
			elements = [self.convert_cmd(element) for element in line]
			result.append('\t' + ' & '.join(elements) + r'\\' + '\n')
			count += 1

		result.append('	\\end{tabular}\n')
		if caption:
			result.append(caption)
		if make_float:
			result.append('\\end{table}\n')
		return ''.join(result)

	def macro_numericresults(self, block_lines):
		return self.fancy_table(block_lines)
	
	def macro_floatgraphic(self, args):
		"""
		Includes a graphic, places it in a figure, and gives it a label. Usage:
		!!floatgraphic filename, Caption goes here
		"""
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

		result = [
			'\\begin{figure}[htb]',
			'	\\begin{center}',
			'		\\includegraphics{figures/%s}' % (filename),
			'	\\end{center}',
			'	\\caption{\\label{figure.%s}%s}' % (label, caption),
			'\\end{figure}',
		]

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
				self.convert_cmd(block_lines[-1][2:]) +\
				r'\end{flushright}'
		result = [r'\begin{quote}'] + block_lines + [r'\end{quote}']
		return '\n'.join(result) + '\n'

	def macro_end_document(self, args):
		return self.end_document

