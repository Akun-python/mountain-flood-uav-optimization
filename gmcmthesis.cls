\NeedsTeXFormat{LaTeX2e}[1995/12/01]
\ProvidesClass{gmcmthesis}
              [2026/09/22 MathModel Huawei Cup 2026]
%% Inital Code
\newif\if@gmcm@bwprint\@gmcm@bwprintfalse
\newif\if@gmcm@preface\@gmcm@prefacetrue
% tokens definition
%%%% 承诺书
\newcommand\gmcm@tokens@keywords{}
\newcommand*\gmcm@tokens@tihao{}
\newcommand*\gmcm@tokens@baominghao{}
\newcommand*\gmcm@tokens@schoolname{}
\newcommand*\gmcm@tokens@membera{}
\newcommand*\gmcm@tokens@memberb{}
\newcommand*\gmcm@tokens@memberc{}
\newcommand*\gmcm@tokens@supervisor{}
\newcommand*\gmcm@tokens@yearinput{}
\newcommand*\gmcm@tokens@monthinput{}
\newcommand*\gmcm@tokens@dayinput{}
%%%% 编号专用页
% 没有
%% Declaration of Options
\DeclareOption{colorprint}{\@gmcm@bwprintfalse}
\DeclareOption{bwprint}{\@gmcm@bwprinttrue}
\DeclareOption{withoutpreface}{\@gmcm@prefacefalse}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{ctexart}}
%% Executing of Options
\ExecuteOptions{colorprint}
\ProcessOptions\relax
%% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%Loading Class
\LoadClass[a4paper,zihao=-4]{ctexart}
%% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%Loading Package
\RequirePackage{ifxetex}
\RequireXeTeX
\ifxetex\else
\ClassError{mcmthesis}{You must use the `xelatex' driver\MessageBreak Please choose `xelatex'}{%
Just choose `xelatex', no `pdflatex' or `latex' and so on.}
\fi
% 页面布局
\RequirePackage{geometry}
% 数学宏包
\RequirePackage{amsmath}
\RequirePackage{amsfonts}
\RequirePackage{amssymb}
\RequirePackage{bm}
% 设置颜色
\RequirePackage{color,xcolor}
% 插入图片
\RequirePackage{graphicx}
% 表格
\RequirePackage{tabularx,array}
% 调整单元格格式
\RequirePackage{makecell}
%% 长表格
\RequirePackage{longtable}
%% booktabs 提供了\toprule 等命令.
\RequirePackage{booktabs}
%% multirow 支持在表格中跨行
\RequirePackage{multirow}
%% 调整间隔, 让表格更好看些
\RequirePackage{bigstrut}
%% 在跨行表格中输入定界符
\RequirePackage{bigdelim}
% 保护脆落命令
\RequirePackage{cprotect}
% 设置代码环境
\RequirePackage{listings}

% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 一 设置附录代码
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\usepackage{listings,color}

% Matlab highlight color settings
%\definecolor{mBasic}{RGB}{248,248,242}       % default
\definecolor{mKeyword}{RGB}{0,0,255}          % bule
\definecolor{mString}{RGB}{160,32,240}        % purple
\definecolor{mComment}{RGB}{34,139,34}        % green
\definecolor{mBackground}{RGB}{245,245,245}   % lightgrey
\definecolor{mNumber}{RGB}{128,128,128}       % gray

% Python highlight color settings
%\definecolor{pBasic}{RGB}{248, 248, 242}     % default
\definecolor{pKeyword}{RGB}{228,0,128}        % magenta
\definecolor{pString}{RGB}{148,0,209}         % purple
\definecolor{pComment}{RGB}{117,113,94}       % gray
\definecolor{pIdentifier}{RGB}{166, 226, 46}  %
\definecolor{pBackground}{RGB}{245,245,245}   % lightgrey
\definecolor{pNumber}{RGB}{128,128,128}       % gray

\lstnewenvironment{Matlab}[1]{
\lstset{language=matlab,               % choose the language of the code
  xleftmargin=10pt,
  xrightmargin=10pt,
  frame=tlbr,framesep=4pt,framerule=0.5pt, % sets the frame style
  %frame=shadowbox,rulesepcolor=\color{red!20!green!20!blue!20},
  basicstyle=\small\ttfamily\linespread{1}\selectfont,
  keywordstyle={\color{mKeyword}},     % sets color for keywords
  stringstyle={\color{mString}},       % sets color for strings
  commentstyle={\color{mComment}},     % sets color for comments
  backgroundcolor=\color{gray!5},%\color{pBackground}, % choose the background color
  rulecolor=\color{gray!50},
  title=#1,                            % \lstname show the filename of files
  keywords={break,case,catch,classdef,continue,else,elseif,end,for,
  function,global,if,otherwise,parfor,persistent,return,spmd,switch,try,while},
  showspaces=false,                    % show spaces adding particular underscores
  showstringspaces=false,              % underline spaces within strings
  showtabs=false,                      % show tabs within strings adding particular underscores
  tabsize=4,                           % sets default tabsize to 2 spaces
  captionpos=t,                        % sets the caption-position to bottom
  breaklines=true,                     % sets automatic line breaking
}}{}

\lstnewenvironment{Python}[1]{
\lstset{language=python,               % choose the language of the code
  xleftmargin=10pt,
  xrightmargin=10pt,
  frame=single,framesep=4pt,framerule=0.5pt, % sets the frame style
  %frame=shadowbox,rulesepcolor=\color{red!20!green!20!blue!20},
  basicstyle=\small\gmcm@pythonfont\linespread{1}\selectfont,
  keywordstyle=\color{pKeyword},       % sets color for keywords
  stringstyle=\color{pString},         % sets color for strings
  commentstyle=\color{pComment},       % sets color for comments
  backgroundcolor=\color{gray!5},%\color{pBackground}, % choose the background color
  rulecolor=\color{gray!50},
  title=#1,                            % \lstnames how the filename of files
  emph={format_string,eff_ana_bf,permute,eff_ana_btr},
  emphstyle=\color{pIdentifier},
  showspaces=false,                    % show spaces adding particular underscores
  showstringspaces=false,              % underline spaces within strings
  showtabs=false,                      % show tabs within strings adding particular underscores
  tabsize=4,                           % sets default tabsize to 2 spaces
  captionpos=t,                        % sets the caption-position to bottom
  breaklines=true,                     % sets automatic line breaking
}}{}


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 二 设置页面
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 首行缩进
\RequirePackage{indentfirst}
% 设置浮动体的标题
\RequirePackage{caption}
% 定制列表环境
\RequirePackage{enumitem}
% 下划线
\RequirePackage{ulem}
% 尺寸计算
\RequirePackage{calc}
\RequirePackage{titletoc,url}
%参考文献
\RequirePackage[numbers]{natbib}
\setlength{\bibsep}{0pt plus 0.3ex}

\RequirePackage{etoolbox}
\AtBeginEnvironment{thebibliography}{%
    \phantomsection
    \addcontentsline{toc}{section}{\refname}
    }
% 超链接 hyperref 的设置
\RequirePackage{hyperref}
%% Document Layout
% 页面布局
\geometry{top=30.0mm,bottom=25.0mm,left=22.5mm,right=22.5mm,headsep=8mm}
% \geometry{top=30.0mm,bottom=25.0mm,left=31.7mm,right=31.7mm,headsep=8mm}
\renewcommand*{\baselinestretch}{1}
% 每行缩进两个汉字
\setlength\parindent{2em}

% ----------
% 删减一小段数学环境
% -----------

% 浮动环境设置
% 默认情况下, \LaTeX{} 要求每页的文字至少占据 20%,否则该页就只单独放置一个浮动环境,
% 而这通常不是我们想要的, 我们将这个要求降低到 5%.
 \renewcommand*{\textfraction}{0.05}
% 有时如果多个浮动环境连续放在一起, \LaTeX{}
% 会将它们分在几个不同页，即使它们可在同一页放
% 得下. 我们可以通过修改 |\topfraction| 和 |\bottomfraction| 分别设置顶端和底端的浮
% 动环境的最大比例.
 \renewcommand*{\topfraction}{0.9}
 \renewcommand*{\bottomfraction}{0.8}
% 有时\LaTeX{}会把一个浮动环境单独放在一页,
% 我们要求这个环境至少要占据 85% 才能单独放在一页.
% 注意:  |\floatpagefraction| 的数值必须小于 |\topfraction|.
 \renewcommand*{\floatpagefraction}{0.85}
% 关于图片 graphicx
 % 如果图片没有指定后缀, 依次按下列顺序搜索
\DeclareGraphicsExtensions{.pdf,.eps,.jpg,.png}
 % 设置图表搜索路径, 可以给图表文件夹取如下名字
\graphicspath{{figures/}{figure/}{pictures/}%
  {picture/}{pic/}{pics/}{image/}{images/}}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 三 设置字体
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{\setmainfont{TeX Gyre Termes}}
\IfFontExistsTF{Courier New}{\setmonofont{Courier New}}{\setmonofont{Latin Modern Mono}}
\IfFontExistsTF{Arial}{\setsansfont{Arial}}{\setsansfont{TeX Gyre Heros}}
\IfFontExistsTF{Consolas}{\newfontfamily\gmcm@pythonfont{Consolas}}{%
  \newcommand\gmcm@pythonfont{\ttfamily}}

% 中文正文、粗体与宋楷黑字体族由 ctex 按平台选择，勿覆盖为 macOS 专用字体。
% 摘要页的固定标签使用隶书；模板随附字体，避免依赖系统安装。
\setCJKfamilyfont{gmcm-cover-label}[Path=./]{LiSu.ttf}
\newcommand\gmcm@coverfont{\CJKfamily{gmcm-cover-label}}


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 四 设置图表
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 图表标题
\DeclareCaptionFont{song}{\songti}
\DeclareCaptionFont{minusfour}{\zihao{-4}}
\captionsetup[figure]{%
	format=hang,   % 标题从第二行开始都有缩进, 应该和 justification=raggedright 的效果一样.
	labelsep=quad, % 分隔符是一个空格
	font={song,minusfour}, % 图的字体, 宋体小四
	position=bottom % position=bottom, 不代表标题放在下面, 标题仍放在你放\caption的位置.
}
\captionsetup[table]{%
	format=hang,   % 标题从第二行开始都有缩进, 应该和 justification=raggedright 的效果一样.
	labelsep=quad, % 分隔符是一个空格
	font={song,minusfour}, % 表的字体, 宋体小四
	position=top % position=bottom, 不代表标题放在下面, 标题仍放在你放\caption的位置.
}
% 列表环境设置
\setlist{%
	topsep=0.3em, % 列表顶端的垂直空白
	partopsep=0pt, % 列表环境前面紧接着一个空白行时其顶端的额外垂直空白
	itemsep=0ex plus 0.1ex, % 列表项之间的额外垂直空白
	parsep=0pt, % 列表项内的段落之间的垂直空白
	leftmargin=1.5em, % 环境的左边界和列表之间的水平距离
	rightmargin=0em, % 环境的右边界和列表之间的水平距离
	labelsep=0.5em, % 包含标签的盒子与列表项的第一行文本之间的间隔
	labelwidth=2em % 包含标签的盒子的正常宽度；若实际宽度更宽，则使用实际宽度。
}

% 超链接
% \AtBeginDocument{%
	 \hypersetup{%
		% % unicode=false, % hyperref 和 xetex 同时使用时不能开启 Unicode 选项.
		 colorlinks=true,
		 bookmarksnumbered=true,
		 bookmarksopen=true,
 		 bookmarksopenlevel=0,
		 allcolors=black,
		 breaklinks=true}%
% }
% \if@gmcm@bwprint
% \AtBeginDocument{\hypersetup{hidelinks}}
% \else\relax\fi
\def\UrlAlphabet{%
      \do\a\do\b\do\c\do\d\do\e\do\f\do\g\do\h\do\i\do\j%
      \do\k\do\l\do\m\do\n\do\o\do\p\do\q\do\r\do\s\do\t%
      \do\u\do\v\do\w\do\x\do\y\do\z\do\A\do\B\do\C\do\D%
      \do\E\do\F\do\G\do\H\do\I\do\J\do\K\do\L\do\M\do\N%
      \do\O\do\P\do\Q\do\R\do\S\do\T\do\U\do\V\do\W\do\X%
      \do\Y\do\Z}
\def\UrlDigits{\do\1\do\2\do\3\do\4\do\5\do\6\do\7\do\8\do\9\do\0}
\g@addto@macro{\UrlBreaks}{\UrlOrds}
\g@addto@macro{\UrlBreaks}{\UrlAlphabet}
\g@addto@macro{\UrlBreaks}{\UrlDigits}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 四 设置封面 摘要 目录
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%
% 封面
%%%%%%%%%%%%%%%%%%%%%%%%
% 生成封面, 使用\maketitle
\renewcommand{\maketitle}{\par
	\begingroup
      \newpage
      \global\@topnum\z@ % Prevents figures from going at top of page.
      \ge@maketitle      %
    \endgroup
  \global\let\thanks\relax
  \global\let\maketitle\relax
  \global\let\@maketitle\relax
  \global\let\@thanks\@empty
  \global\let\@author\@empty
  \global\let\@date\@empty
  \global\let\@title\@empty
  \global\let\title\relax
  \global\let\author\relax
  \global\let\date\relax
  \global\let\and\relax
}
\def\ge@maketitle{%
  \clearpage
  \if@gmcm@preface
  \thispagestyle{empty}%
  \setcounter{page}{0}% 封面不显示页码，并避免与摘要 page.1 的 PDF 锚点重复。
  \pdfbookmark[1]{封~面}{cover}

 \begin{center}
 {\includegraphics[width=\textwidth]{logo}}

  \vskip1.5cm
 {\zihao{2} \gmcm@ges@string@contents \par}
 \end{center}

 \vskip4em

 % \thispagestyle{gmcmheadings}
 \renewcommand\arraystretch{1.5}
 %\noindent 
 \begin{tabularx}{\textwidth-40pt}{lX}
  \zihao{-2}\bfseries 学\qquad 校&\zihao{-2}\bfseries\gmcm@tokens@schoolname\\
  \Xhline{1.2pt}\\
  \zihao{-2}\bfseries 参赛队号&\zihao{-2}\bfseries\gmcm@tokens@baominghao\\
  \Xhline{1.2pt}\\[-15pt]
   \multirow{3}{*}{\zihao{-2}\bfseries 队员姓名}&\zihao{-2}\bfseries   1. \gmcm@tokens@membera\hfill\null\\
   \cline{2-2}\\[-15pt]
                               &\zihao{-2}\bfseries 2. \gmcm@tokens@memberb\hfill\null\\
   \cline{2-2}\\[-15pt]
                        &\zihao{-2}\bfseries 3.  \gmcm@tokens@memberc\hfill\null\\
   \Xhline{1.2pt}
  \end{tabularx}
  \clearpage
  \fi

	\makenametitle
	}

\def\makenametitle{
\clearpage
\thispagestyle{plain}%
\pdfbookmark[1]{标~题}{title}
\pagenumbering{arabic}
\begin{center}
%{\includegraphics[width=4cm]{logo}}
{\zihao{2} \gmcm@ges@string@contents \par}
\end{center}

\vskip0.6cm%

\begin{center}\begin{tabularx}{.95\textwidth}{@{}lX@{}}
{\zihao{-2}\gmcm@coverfont 题\quad 目：} &\centering\arraybackslash\zihao{3}\heiti \@title\\
\cline{2-2}
\end{tabularx}
\end{center}
}


% 中文标题格式设置
% 目录深度
\setcounter{secnumdepth}{3}
\def\@seccntformat#1{\csname the#1\endcsname\ \ }
% 节标题格式, 居中, 使用\chinese命令修改计数器, \kern 使得数字和内容不至于太远
\newcommand{\thinskip}{\hskip 0.05em\relax}
\renewcommand\thesection{\arabic{section}}
\renewcommand\thesubsection{\thesection.\arabic{subsection}}
\renewcommand\thesubsubsection{\thesubsection.\arabic{subsubsection}}
\renewcommand\section{\@startsection{section}{1}{\z@}%
 	{2.5ex \@plus -1ex \@minus -.2ex}%
	{2.3ex \@plus.2ex}%
	{\centering\zihao{4}\heiti}}
\renewcommand\subsection{\@startsection{subsection}{2}{\z@}%
	{1.25ex\@plus -1ex \@minus -.2ex}%
	{1.25ex \@plus .2ex}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
	{1.25ex\@plus -1ex \@minus -.2ex}%
	{1.2ex \@plus .2ex}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\paragraph{\@startsection{paragraph}{4}{\z@}%
	{3.25ex \@plus1ex \@minus.2ex}%
	{-1em}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\subparagraph{\@startsection{subparagraph}{5}{\parindent}%
	 {3.25ex \@plus1ex \@minus .2ex}%
	 {-1em}%
	 {\normalfont\normalsize\bfseries}}
%%%%%%%%%%%%%%%%%%%%%%%%
% 摘要
%%%%%%%%%%%%%%%%%%%%%%%%
%% 摘要页的固定标签使用隶书小二号.
%% 定义摘要环境
\renewenvironment{abstract}{%
\if@twocolumn
		\section*{\gmcm@cap@abstractname}%
	\else
	 \begin{center}%
	{\zihao{-2}\gmcm@coverfont\gmcm@cap@abstractname\vspace{\z@}}%
	 \end{center}%
 	 \quotation
	\fi}
	{\if@twocolumn\else\endquotation\fi\clearpage}
\renewenvironment{quotation}
	{\list{}{\listparindent 2em%
	 \itemindent \listparindent
	 \rightmargin\z@
	 \leftmargin\z@
	 \parsep \z@ \@plus\p@}%
	\item\relax}
	{\endlist}

\newcommand\keywords[1]{%
	\renewcommand{\gmcm@tokens@keywords}{#1}
	\par
	\vskip1ex
	{\noindent\zihao{-2}\gmcm@coverfont\gmcm@cap@keywordsname：}~{\gmcm@tokens@keywords}
	}


\newcommand*\baominghao[1]{%
	\renewcommand{\gmcm@tokens@baominghao}{#1}}
\newcommand*\schoolname[1]{%
	\renewcommand{\gmcm@tokens@schoolname}{#1}}
\newcommand*\membera[1]{%
	\renewcommand{\gmcm@tokens@membera}{#1}}
\newcommand*\memberb[1]{%
	\renewcommand{\gmcm@tokens@memberb}{#1}}
\newcommand*\memberc[1]{%
	\renewcommand{\gmcm@tokens@memberc}{#1}}
%%%%%%%%%%%%%%%%%%%%%%%%
% 其他
%%%%%%%%%%%%%%%%%%%%%%%%

% ----------
% 删减一小段定理
% -----------

  %%%  中文标题名称
 \newcommand*{\gmcm@cap@abstractname}{摘\quad 要：}
  %%%  中文关键字
 \newcommand*{\gmcm@cap@keywordsname}{关键词}
 
  %%%常量
 \newcommand\gmcm@ges@string@contents{\includegraphics{title}}
 %\newcommand\gmcm@ges@string@contents{\includegraphics[width=11cm]{title}}++++++++++++++++++
 \renewcommand{\thetable}{\arabic{section}.\arabic{table}}
 \renewcommand{\theequation}{\arabic{section}.\arabic{equation}}
 \renewcommand{\thefigure}{\arabic{section}.\arabic{figure}}
 
 % %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% 字图与子标题
 % \RequirePackage{subcaption}
 \RequirePackage[titles]{tocloft}
 %\renewcommand{\cftdot}{$\cdot$}
 %\renewcommand{\cftsecdotsep}{1.5}
 \renewcommand{\cftsecdotsep}{4.5}
 \setlength{\cftbeforesecskip}{7pt}
 \setlength{\cftbeforesubsecskip}{3pt}
 %\setlength{\cftbeforesubsecskip}{5pt}
 \renewcommand{\cftsecfont}{\zihao{-4}\heiti}
 \renewcommand{\cftsecleader}{\cftdotfill{\cftsecdotsep}}
 \renewcommand{\cftsecaftersnumb}{\hskip.4em}
%%%%%%%%%%%%%%%%%%%%%%%%
% 目录
%%%%%%%%%%%%%%%%%%%%%%%%
% ----------- 设置新的生成目录命令 -------------
\newcommand{\maketoc}{
  \phantomsection
  \pdfbookmark[1]{目~录}{contents}
  \tableofcontents
}

\RequirePackage{titletoc}
\RequirePackage[title,titletoc]{appendix}

\newcommand*{\gmcm@cap@appendixname}{附录}
\renewcommand*\appendixname{\gmcm@cap@appendixname}

% 定义附录  
% \let\oldappendix\appendix
\renewcommand\appendix{\par
  \setcounter{section}{0}%
   \setcounter{subsection}{0}%
  \gdef\thesection{\appendixname\@Alph\c@section}
  %\gdef\thesubsection{\@Alph\c@section\thinskip.\thinskip\c@subsection}
}

%%设置目录格式
% 节的目录格式
\titlecontents{section}[0pt]{\vspace{2mm}\heiti}
{\thecontentslabel\hskip.5em}{}{\titlerule*[0.5pc]{.}\contentspage}
% 小节的目录格式
\titlecontents{subsection}[30pt]{\songti}
{\thecontentslabel\hskip.5em}{}{\titlerule*[0.5pc]{.}\contentspage}
% 小小节的目录格式
\titlecontents{subsubsection}[55pt]{\songti}
{\thecontentslabel\hskip.5em}{}{\titlerule*[0.5pc]{.}\contentspage}

\pagestyle{plain}

\endinput
