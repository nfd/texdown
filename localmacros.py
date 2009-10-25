import re

AFFILIATIONS = {
	'GEN_AFFIL': r"""Insert Affiliation Here\\
		City, Country""",
}

AUTHOR = r"""
  \authorinfo{%(author0)s}
		{%(author2)s}
		{%(author1)s}
"""

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

TECHREPORT = r"""\documentclass[preprint,natbib,10pt]{sigplanconf}

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


def separate_tabs(line):
	return re.split(r'\t+', line)

class Macros(object):
	def macro_sigplanpaper(self, block_lines):
		return SIGPLANPAPER % self.anypaper(block_lines)

	def macro_techreport(self, block_lines):
		return TECHREPORT % self.anypaper(block_lines)
	
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
				subst = {'author0': line[0], 'author1': line[1],
					'author2': AFFILIATIONS[line[2]]}
				authors.append(AUTHOR % subst)
			else:
				for idx in range(len(line)):
					info[key + str(idx)] = line[idx]

		if authors:
			info['AUTHORS'] = '\n'.join(authors)
		return info
	
	def macro_numericresults(self, block_lines):
		result = ['\\begin{figure}\n']
		cols = len(separate_tabs(block_lines[0]))
		result.append('	\\begin{tabular}{%s}\n' % ('l' * cols))

		for line in block_lines:
			result.append('\t' + ' & '.join(separate_tabs(line)) + r'\\' + '\n')

		result.append('	\\end{tabular}\n')
		result.append('\\end{figure}\n')
		return ''.join(result)
	
	def macro_floatgraphic(self, args):
		if ',' in args:
			filename, caption = args.split(',', 1)
			caption = caption.strip()
		else:
			filename = args
			caption = None

		result = [
			'\\begin{figure}[htb]',
			'	\\begin{center}',
			'		\\includegraphics{figures/%s}' % (filename),
			'	\\end{center}',
			'	\\caption{\\label{figure.%s}%s}' % (filename, caption),
			'\\end{figure}',
		]

		return '\n'.join(result)
	
	def macro_floatcode(self, block_lines):
		"""
		Includes magical final-line caption support.
		"""
		if block_lines[-1].startswith('~~'):
			caption = block_lines.pop()
		block_lines = [line.replace('\t', '  ') for line in block_lines]
		result = ['\\begin{figure}[htb]']
		result.append('\\begin{verbatim}')
		result.extend(block_lines)
		result.append('\\end{verbatim}')
		if caption:
			result.append(caption)
		result.append('\\end{figure}')
		return '\n'.join(result)
	
	def macro_floattable(self, block_lines):
		if block_lines[-1].startswith('~~'):
			caption = block_lines.pop()
		numcols = block_lines[0].count('\t') + 1
		block_lines = [line.replace('\t', ' & ') for line in block_lines]
		result = ['\\begin{figure}',
			'\\begin{tabular}{%s}' % ('l' * numcols),
		]
		for line in block_lines:
			result.append(line + r' \\')
		result.append('\\end{tabular}')
		if caption:
			result.append(caption)
		result.append('\\end{figure}')
		return '\n'.join(result)

	def macro_end_document(self, args):
		return END_DOCUMENT
