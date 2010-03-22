syn match texdowncomment "^%.*" contains=texdownfixme
syn match texdownchapter /^##.*##/
syn match texdownsection /^==.*==/ contains=texdownlabel
syn match texdownsubsection /^=[^=].*[^=]=/ contains=texdownlabel
syn match texdownsubsubsection /^-[^-].*-/ contains=texdownlabel
syn match texdowncaption /\~\~ [^\~]* \~\~/ contains=texdownlabel
syn match texdownlabel /<<[^<]*>>/
syn match texdownfixme /FIXME:.*$/ contained
syn match texdowncite /\[\[[^\[]*\]\]/
syn match texdowncitefixme /\[\[FIXME\]\]/
syn match texdownref /\[[^\[]*\]/
syn match texdownitalics /\/[^ ][^\/]*[^ ]\//
syn match texdownbold /\*[^\*]*\*/
syn match texdowntt /''[^']*''/
syn match texdownargs /[^^]!!.*/
syn match texdowncommand /^!!.*/
syn match texdowndefinition /^ [^:]*:/
syn match texdownbullet /^ \+\*/
syn match texdownenum /^ \+[0-9]\+\./
syn region texdownquote matchgroup=Normal start="^\"\"\"" end = "^\"\"\"" 
syn region texdowntable start="^!! table" end = "^!!"

hi link texdowncomment Comment
hi link texdownquote Comment
hi texdownbullet guibg=gray
hi texdownenum guibg=gray
hi TexdownHeading guifg=SlateBlue gui=bold
hi TexdownMildHeading guifg=SlateBlue
hi TexdownMilderHeading guifg=DarkBlue
hi texdowncaption guifg=orange
hi texdownfixme guifg=red guibg=yellow
hi texdowncite guifg=darkorange
hi texdowncitefixme guifg=red guibg=yellow
hi texdownref guifg=darkgreen
hi texdownitalics gui=italic
hi texdownbold gui=bold
hi texdowntt guibg=grey guifg=darkgreen
hi texdownlabel guifg=magenta
hi texdownargs guifg=grey
hi texdowncommand guifg=brown
hi texdowndefinition guifg=cyan guibg=blue
hi link texdownchapter TexdownHeading
hi link texdownsection TexdownHeading
hi link texdownsubsection TexdownMildHeading
hi link texdownsubsubsection TexdownMilderHeading

