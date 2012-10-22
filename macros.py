
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
\usepackage{caption}
\usepackage{natbib}

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

class Macros(object):
	def __init__(self, texdown):
		self.texdown = texdown
		self.end_document = END_DOCUMENT_NIL

	def macro_sigplanpaper(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		return SIGPLANPAPER % self.texdown.anypaper(block_lines, author = self.texdown.make_author)

	def macro_techreport(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		return TECHREPORT % self.texdown.anypaper(block_lines, author = self.texdown.make_author_joined)

	def macro_acceptancetestingreport(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		return ACCEPTANCE_TESTING_REPORT % self.texdown.anypaper(block_lines, author = self.texdown.make_author_plain)

	def macro_nictatr(self, block_lines):
		self.end_document = END_DOCUMENT_PLAIN
		return NICTATR % self.texdown.anypaper(block_lines, author = self.texdown.make_author_plain)

	def macro_end_document(self, args):
		return self.end_document


