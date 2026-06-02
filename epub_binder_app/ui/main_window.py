# -*- coding: utf-8 -*-
"""
Epub Binder v5.1.0  —  PyQt6 Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 디자인 : teleuserbot / tokki_organizer 동일 디자인 시스템
• v4.2.5   : 이름변경-ZIP묶기 시 '복사본으로 저장' 체크하면
             1개짜리 단일 EPUB(낱개)도 시리즈 묶음과 함께 출력 폴더에 복사
• v4.2.4   : 병합 권목차/권표지 보정, 이름변경 일괄변경 오류 수정
• 정렬   : 자동(natural_sort_key) 기본 / 수동 체크 시 드래그·▲▼ 조절
• 공백코드: 합치기 전 각 파일 개별 full 제거 (항상 강제 실행)
           U+200B~U+FFFB + U+E0001 + Tags-block + book-token 전부 제거
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pip install PyQt6
"""

import sys, os, re, io, shutil, uuid, zipfile, posixpath
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QProgressBar, QCheckBox, QFrame, QSizePolicy,
    QFileDialog, QMessageBox, QAbstractItemView,
    QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QComboBox, QRadioButton, QSpinBox, QButtonGroup,
    QStyledItemDelegate, QStyleOptionButton, QStyle,
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QRect
from PyQt6.QtGui import QFont, QColor

from epub_binder_app.settings import APP_EXPIRATION_DATE
from epub_binder_app.workers import (
    EpubTxtWorker,
    MergeWorker,
    NaverSeriesFetchThread,
    ScanWorker,
    StripOnlyWorker,
    TxtEpubWorker,
)
from epub_binder_app.ui.dialogs import CoverPickerDialog
from epub_binder_app.ui.widgets import FileListWidget
from epub_binder_core.epub_text import (
    extract_epub_text_sections,
    xml_attr as _xml_attr,
)
from epub_binder_core.txt_epub import build_txt_epub

try:
    from epub_binder_core.rename_service import build_rename_preview_rows as _core_build_rename_preview_rows
    from epub_binder_core.title_parser import (
        EpubNameMeta as _CoreEpubNameMeta,
        format_rename_name as _core_format_rename_name,
        parse_epub_name as _core_parse_epub_name,
    )
    from epub_binder_core.epub_io import extract_epub_metadata as _core_extract_epub_metadata
except Exception:
    _core_build_rename_preview_rows = None
    _CoreEpubNameMeta = None
    _core_format_rename_name = None
    _core_parse_epub_name = None
    _core_extract_epub_metadata = None

try:
    from epub_binder_core.grouping import build_series_groups as _core_build_series_groups
except Exception:
    _core_build_series_groups = None

try:
    from epub_binder_core.name_cleanup import clean_series_title_author as _core_clean_series_title_author
except Exception:
    _core_clean_series_title_author = None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎨 디자인 시스템
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
C = {
    "bg":      "#f4f6fb", "surface": "#ffffff", "surface2": "#ffffff",
    "bg2":     "#eef1f6", "bg3":     "#e4e8f0",
    "border":  "#dde2ef", "accent":  "#2272d8", "green":    "#18a870",
    "orange":  "#d4880a", "red":     "#c93535",
    "text":    "#1a2035", "text2":   "#4a5470", "text3":    "#8893b0",
}

import os as _os, sys as _sys
_check_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14">'
    '<polyline points="2,7 5.5,11 12,3" stroke="white" stroke-width="2" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
_exe_dir = _os.path.dirname(
    _sys.executable if getattr(_sys, 'frozen', False) else _os.path.abspath(__file__))
_check_svg_path = _os.path.join(_exe_dir, '_check.svg').replace('\\', '/')
try:
    with open(_check_svg_path, 'w') as _f:
        _f.write(_check_svg)
except: pass

# 아이콘 base64 (배포 시 별도 파일 불필요)
_ICO_B64 = (
    "AAABAAcAEBAAAAAAIAC7BAAAdgAAABgYAAAAACAA6AcAADEFAAAgIAAAAAAgAGELAAAZDQAAMDAAAAAA"
    "IACNEgAAehgAAEBAAAAAACAAThoAAAcrAACAgAAAAAAgAOxDAABVRQAAAAAAAAAAIACSqgAAQYkAAIlQ"
    "TkcNChoKAAAADUlIRFIAAAAQAAAAEAgGAAAAH/P/YQAAAQhpQ0NQSUNDIFByb2ZpbGUAAHicY2BgPMEA"
    "BCwGDAy5eSVFQe5OChGRUQrsDxgYgRAMEpOLCxhwA6Cqb9cgai/r4lGHC3CmpBYnA+kPQKxSBLQcaKQI"
    "kC2SDmFrgNhJELYNiF1eUlACZAeA2EUhQc5AdgqQrZGOxE5CYicXFIHU9wDZNrk5pckIdzPwpOaFBgNp"
    "DiCWYShmCGJwZ3AC+R+iJH8RA4PFVwYG5gkIsaSZDAzbWxkYJG4hxFQWMDDwtzAwbDuPEEOESUFiUSJY"
    "iAWImdLSGBg+LWdg4I1kYBC+wMDAFQ0LCBxuUwC7zZ0hHwjTGXIYUoEingx5DMkMekCWEYMBgyGDGQCm"
    "1j8/R2zgUAAAA25JREFUeJw10ctvVGUYgPHn/eabM3PmdKalpeJIQa7SgpGWAYMEOlwMSgxqFBduRIma"
    "6NqFu0kXuHdhQKKChoCYVBOILggCaZNSKBVLJAUsDRdb2qGFlnam086c73UhPn/As/lJLpczbW1tLtOw"
    "+Iudy9Z8imoS54xaC/Eo6hxiDAI4VTzf17sP83zfeW6NEekXEeGFhYs/+OTF1u9m01FSC2sw5QrW8zFB"
    "PbGYx3ShiDFC6Jwrlcrm8A/Hz3Zf79+Ty+UmAdjXsun0l/veC6fHTpVVu3R25JT2nD+go8N92tn5m47l"
    "r+vli6dVVSsDNy8p8Br/ZU1O1cyIPkxK3Fy9dpuReyPcH58kSEa5fauXodE8E4UZYoHPg8k7mh8fB1gI"
    "kM1mkSen5s83ZH9P18+rmYshEURUYMG8ajY1Z/iluwfreZTmZjVVWyfnL/dWTlzobFTVQbt689azDc3r"
    "/V/v3tF16QZT7yfUakjoHEOho/vPm/h1abARxYXSeaFrqvx48ngQBFNGRO1sYdprWuBv3LBsLSVXYfOO"
    "HdJ99gJBPE7Ui4LyRCIiE9PTYbrhbb/9m4NdxWIx35rNWgFW/nTgs7/e2ftq1I09EuPXQnINVy7/wWj+"
    "AZ7nEarDISSsuI5bD8ylqzcGTx76aqWqqgWsjRgAVYmIzk0g5TGcCOrF+fFYO9uDNKlUimODfTyz8xUQ"
    "NPNxJgKoXdac+bYjH/N6v75IuVhCyyHIFYKqepLJKkK17Nn4Eramhp8Hrus/E+Vy36kz++8M3yjLIcH6"
    "VcmZa/dnesbvDcyvXlS91H86pc6p6ORtqmZjlEpTGBFAtBKpRLrOHS2mMsG29dktL4//fX/sf8aa53Y/"
    "37WoZUlToqTOqBpVsPEEUxeH2ffsBmzM43h/N8GORnwbpayOzpMdQzanao5sbnp/RWtz04f1KypbW9da"
    "ZmbBOSQ1nzOr7zJReEwqmWJX41O88eZujcYS4cn29vBw18HXbZuIW7KlcX5YKOnazAKdtzQNhRkwBjRk"
    "z7u7gDTgAAUKQLWtra8FeCRiBD/pr2v5aFvP8ro6syKoVqNORARXCVnVsopiKc7wwAjWGhTBRKI6Ojoi"
    "R4+cOCLkMLThkrXJvcvfyuzXqElrqIKIoIoXxHCVObxyhKhYFFDnNJFMyFDv4ON/AZk2lAfJ6MmiAAAA"
    "AElFTkSuQmCCiVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAABCGlDQ1BJQ0MgUHJvZmls"
    "ZQAAeJxjYGA8wQAELAYMDLl5JUVB7k4KEZFRCuwPGBiBEAwSk4sLGHADoKpv1yBqL+viUYcLcKakFicD"
    "6Q9ArFIEtBxopAiQLZIOYWuA2EkQtg2IXV5SUAJkB4DYRSFBzkB2CpCtkY7ETkJiJxcUgdT3ANk2uTml"
    "yQh3M/Ck5oUGA2kOIJZhKGYIYnBncAL5H6IkfxEDg8VXBgbmCQixpJkMDNtbGRgkbiHEVBYwMPC3MDBs"
    "O48QQ4RJQWJRIliIBYiZ0tIYGD4tZ2DgjWRgEL7AwMAVDQsIHG5TALvNnSEfCNMZchhSgSKeDHkMyQx6"
    "QJYRgwGDIYMZAKbWPz9HbOBQAAAGm0lEQVR4nF2Va4yU1RnHf88578y7szOzN/ZS7iCIFERbbhWCYAtF"
    "K4VUDAhBUqSpQpsYoqYfeltJbalEJdGGII2aXqS12woVKGhbuoRytV2Ri+zCAsvV3e59Z3Znd+d9z9MP"
    "s0uxz6eTnJP/ef5Pfud/hFwZI+Kc6uQC339x8ZSp85J5eXHUCQBiIM9HRBgsBeS2NYpiLR9fvPCfo/V1"
    "C4zIGadqPMCoqorI5HnjJxx4ZcnK8gs3G0n392JRVJVQBVsYR/+nD4BzDmMtAoRhIIUlQ1w6na44Wl9X"
    "LiKgKl5lZSXGGB1VXPLa1kdWl//8yP7sqLnjIyOGl9CbDTHGkoz7dPUlMNF8XBhijABCfjxGqiuFc45o"
    "rMht3fGOqT5c/V1r7YEwDC0Q4hkLMOzp+xf0vvr1le7ll9c71ZOqmYOq2cOqqX/oX96uVNXLqtquqt2q"
    "2qFhzw39YM/vVTVU1S6nqrp29WPtk8rKEp5nGZygGXCbKIrlR5syHTLj7gmQTRO0d0JHF92tHZyuvYKm"
    "r/Hypi0snL+I9/fupyPVxSef1KFhB/2pdtR10tLalv00CGw2G9wapmhlpZGNG/MXTpxc/8MHFldsbqh2"
    "r/xigyn3fXCKESEezyPV3YPziukISygrLAZ1xPJ90qlugjAkGi/V5555lu3bfvUFz/NOBUFggVBEBM/z"
    "yMK3tz+6+vVxxeXunfMnrBeLgtMcHqo4heFDCvnRunV8f9uvae9J5fATg6I4xaVSKf515uzJqx1tSzOZ"
    "zFWRHHdlwGQgBH62+vP3zFk08V4XFTWhE1BFRVEsRh3WKWHE4PLzkYiHqKIixBJJCktL2XHo72z7276H"
    "rTH7Quc8GTruzsb533qqYqCboC3d5RnPIn0BQxJ5WM+S4zNH/i3+VXMztoaOxpu6+823NNPZ/jtgD/An"
    "IAvghdlsc6rp0wqMcTj1ItagCk89+zTH9u2n/lwtiMWFwW1M6MAtOYcVo8bq9oOHZfP6J6fePPrP9e3G"
    "ZJ1zBnACxEeUxGp2vf3CnYJTdc4IwuQpE7nSFqezPUUymSQvL4biUHWIyoC2gueze9d7VF9sDBauWutt"
    "eGj+tmzQt16dekDgiUh36Cdq7po0YUJiWHFIptcgFu3pZsKkMRAZyUcnDnL0yAmsNUQiPuJbsn39iDGo"
    "KivWPsHln7xoWlpbddKMGfedPHwIVQ1FBA/A87yoNYPoDsRPPAbZZogMBWMIQoeNFfLnfXvI1FzkwVmz"
    "Eec4VXeO2jO1JJMJwiDg/8tT1WQkm55ae+686unA4BSMDCSYQ6NnSZTcwZdnTyeSX8L1hlpGxUfw+IqV"
    "0NvLtfPneXDrJqYt+oa7r6zUO/vh8WPzKis9EfGArJSPGnN61iOP3i3GhhqGFisgAk4HvCjOgaeOooI4"
    "Hx0/zndG3MGah5dAEFBz9hQbao65DVtek5+uWV3XdLl+enNLS7c6h6J4XiRaVlA+FAUrRrQv3UfYnxU/"
    "6aMit5C0CoXFCRKJQgQQMaCKH/VpbmiQdXNm097S+G9gHRAFHHDUu3nx/JTf/OC5yUAfsLRodMEzM5+c"
    "pyk/agIUQ85RGDqC/GK6/OtE7FBsMg79EWLWx5aLPPb8alxWVym6SlXx8/LYVflbPBFpthGvOjmkdNTQ"
    "qcOemPfjpXLyjWoSfb1EVW89LescfUnov5Kmc0w3m978JRebG1k6ZRr9jWma/nqJbG+fw4iz1mrDleva"
    "2dS2AyCybNkyG41F3/jmnu/p1CUzs++/tVF7ru/WTP272ntpp/Ze2qk9F/6gmZYjeujAXp09/Yu6bdtL"
    "unffH3XOzBn6+qubtaezSTsb67Sn7XLY2XhBx48cfWKQokBEdOS0sZNam9t07ueGycI1i+i/eQOvwB+g"
    "CSCCug7m3H8vBw7txs+LAZYFc79ExHo4AiKRfLxYvmu/ctW0ptvrAOstX77cAGGmNZ1OFCW0/sY56EkT"
    "rSi5TXwwFkKQNvzIcMAHIJpfBjhyH6cCURk2eiTlFeVDOjpSoVdVVSVihJaG5ncz19oXBPPH9q9a8bz5"
    "yvxpYvqzOWFRBMGFSmlFAbO++hD736shCLKofKYLUDU26mtPW3qmqt4jgFRWVkpVVZV36caVXYtfevxr"
    "YTJC28UmjJFbJgRBnaOwrIhJc+7iw93HycPHl0guWHN95M4LmkzE5YMtO3tuzwcF8oAXxs2duKpwRFk5"
    "zhlEkMFtgTBwdKcyJIvieMbiS3RQ9DMXuCCgtvrjY/8F16VAiv+ssDYAAAAASUVORK5CYIKJUE5HDQoa"
    "CgAAAA1JSERSAAAAIAAAACAIBgAAAHN6evQAAAEIaUNDUElDQyBQcm9maWxlAAB4nGNgYDzBAAQsBgwM"
    "uXklRUHuTgoRkVEK7A8YGIEQDBKTiwsYcAOgqm/XIGov6+JRhwtwpqQWJwPpD0CsUgS0HGikCJAtkg5h"
    "a4DYSRC2DYhdXlJQAmQHgNhFIUHOQHYKkK2RjsROQmInFxSB1PcA2Ta5OaXJCHcz8KTmhQYDaQ4glmEo"
    "ZghicGdwAvkfoiR/EQODxVcGBuYJCLGkmQwM21sZGCRuIcRUFjAw8LcwMGw7jxBDhElBYlEiWIgFiJnS"
    "0hgYPi1nYOCNZGAQvsDAwBUNCwgcblMAu82dIR8I0xlyGFKBIp4MeQzJDHpAlhGDAYMhgxkAptY/P0ds"
    "4FAAAAoUSURBVHiclZd7lNXVdcc/+5xzX3MvM8www8NBQIRIUcQSlFhZlboIkqyFSBOoJiKtdlXQSuIj"
    "1fpoSmxWQs1iSaUsk5g2DyIRjGQpGAzRlMiIGqU18nKigsDwGGaYx53Hvff3O2f3j3vnEek/PWuddc/v"
    "/s7vnL2/57u/ex9hqAmAEaNBw3LgzobciJlVyVRaUZHKJAXEGDACWvmo8v/gIuc/a0Bp7eh4vxDHnwM+"
    "rrwKMmyebFm6VJZt3frd66ZMu33t4r9iasMYrCpmcDlQBUbWQDqFqA5+PTiUYfMqC8fBk6keGd2xcV3i"
    "P3f/erUz9sk4eAfEAwZYK+K96jdvmXXVQz+546vxhh07zHO/f8vEFgg6aIL3HptIghVUhwxDym774LHG"
    "DoNCEbGKEWluOXa8Ld+zUFUPicggAkZEgqpOuKC6prllzXp36482miPVBXn0gduoyyYq3gggjMgm6IvS"
    "+MQYfIhApeKBwRhLVTZDT08PKKgqJpHUc2e7+NyiZR2hFM0UkROqKgOn5ABjRUKsOv/Wq+am/ufIx/Hr"
    "vSfkg6ZnwBkoRkO4irD3v97mqjmfxtbPAqqHXKcXij007X2La+ZdO4AXUBd+17TTEsVNxpgTIQQHxAPA"
    "mSEMmXDp2Ebd8+F+Flx3JSGZoNDaQegr4Hv78H39RD19rPj79Rw+fJhSTwt3r1rJf3xvPXetup1ib57m"
    "jz5kxV/fTam7m1DopZjPA3165NhxguoZ7/3w/c4zoPNsvotJDaM5ePgYxiVJZ5IYA9YYrAgJa3hh86NM"
    "mTSWhHZwySUT2fzsNqZcfBHJZIKJF45n+4ubSKQSiAjWWkClflQdwGhrbYBhjK7gZ42ID6qzZo+f+M7v"
    "vvaYv/yxB+ySVQt48Ks3k1Hhj1o6AcUYfAwNU4BJZT+itnJo2iTExfLcoJBM6tlTp+WS6X92sqOz68IK"
    "3wY5IIAF7JalW/yyrcu2b/zC8oXL58zzS5563J6xfWSq0vjgy2QTJXjFWkMclMbaHFvWr+Mb33uGl994"
    "i4QT4ijGmDKwWokCY204eKjZ9PUXtgG3AV0DMVIWH2sB+Mrq1Zkn1q9/de2ipXPum/95bT3XYfr7e7Di"
    "KqelqHiCWCRAyhnG1Y8hn++iTWJsqqoiWVKmphHUB3wcUzd2dHH10xtTm/a8epc1ZqOvkFGAa4EVQBoo"
    "AuOABbUI10z+lNRlswQFH2JEQSuGgKDq6Ys9aWsw1kEigTipvAuoD1TlciRTmRDA/ObAe30fnGlZICJN"
    "qmoBL+lstnjb408mR02agEYRgmDF0B+X6IlK9HZ0UpdJU12dq0DKoMgIICJlnVAFHRIsDYHmfW+H5576"
    "rok72t4B/hk4AhxgKHZxwWvr6Y/+ML69/VzU2503YpyANxiDBb54x0robOPXP38WMZbgDYiv7GIr6wzp"
    "riAoSiqZYP7iL5i7H13jH/7STbN2/+K5K42x231FggejIAWTi7BpwTWXfmb2ldM16u83tkIi1LDy7ls4"
    "2+XYsvmXWKP4UO6iECSUY1llQBDL6mcMvYUSv9r1CrOXLGP1t9eFW66YYY4e3v/nxpjXQgiWskpBwjkS"
    "6fSXHrl/uao2R1psUg2vq4a9quEN1bYdqlGzqnpVLer/pxV6W/WixjH6nRd3Rl//8TMB+H5ZG3ADCLhS"
    "FBkR+fjtfe8T509Y392NNcKARlkraNdJSqkkNpHjzb1NPL9tB9Y51AesTVJVnaa7rw+p8ENESBrLHStX"
    "8fDD/8BPf/oT+btH1ghwqfeeQe+HWZJwCYuI0bLwDwmk94r6LjB5JFldYbgQfADnONpynJeeeIE75y8i"
    "4FGvJKuz/GzXy0yYNJFRI3LEkR/Kz59oLplMBJdKTZs7ZwY2NzbYlDM4+8ezVEmYEuCYO28Rc+ctGnzV"
    "2fkRN77bzNrV90EogvdQW48pFvng6FF+uPNVFv/TWj20700FDlpr8d7bASK6KIonQ3x702tv6iP3PGqi"
    "vgJWZEgnBwbiwWZRU0PkYxSwiSSnTp6kr1gk7jgLcYnYg/OKSaVY9/gGvnzv15i78Hp766wZAvx48+bN"
    "dtmyZYayAgeXTKd3L7rrnvG2tjb6fVevMXU29gSLImIEEcEoaLmCAgJJEdLGkM4kONcPhsM4Y8A4FMUl"
    "HfmOcyxZfS/3r/2WX33jX5ojhw4+5hLutzfdfBPGGg8QfMBZ6xrGXTyVugmTEiGOUAFjhOCVqLeAj31F"
    "eIaqN6uQMsLIEWmSNsM5flM+KaTML69kqqrYv3t3+Oy4i2zr6aP7gDfjKL6BoWxYBPa4/t6e6zfcedsK"
    "IFXZpQ9YDNQ3TKvXuomjJZQlr8xyyhlEVRmRzNDd3kOdBIIqSMAaiw8BI46zHUfNn8yfzlS96ApFt5cJ"
    "rIg19Lbn2b9rX5MDdhtjd4OCMYQ4vu/C2ZNvWbLh9pAZlTHtJzsriw/4XxkEpbG6nmMHjvLemhcx6QyU"
    "+sn39jGippFiocDUz36axV+5kY7WDmMSLqhBiT0ul6H3RKdtfm3/NQ6wIXi3dMvSeOvNzy9smNb4neXb"
    "7uedZ19n37/v4oKaamwAqQA8UB8qyrupDOc68ow1ad4/foK/3fCvtOS72PA3qxhZV0Pz1pd4fl8rxVIJ"
    "ETGqAWuddnbl9YMPP2wHHhyIJiNGAF5Z8fN7w6IfrIymjm7Qd/f+QH37TtXWnaptLw/rv1I9s0O1+J62"
    "HDusUxob9YL6UfpvGx/X1/bs0pmXTdeGbLVu2fy0qvar729RjU5r3H9CVePoX9b8owIPOOdwgIhI0KC1"
    "2dE1V4y5vFF2fvEJu/nJ+7j8M5cTnz6DsaYcAMObKD5/hgvGz2LbL5/BWce06TMB2PPbHbx34CBXz5mN"
    "ljoQEULwlTK+YN7Z998Ab0VRZB1DCSyXqclk4pLHxcLFU8YRtbchGghhWA4esgB8P3F3C5fNmAnElHra"
    "EIFcLsnVc6/G9/dWKqky9YMPhFCSQqEIUHTOeQOD94v2/KnODmeMSn2W7S+9QWLUOFy2CpPLYnJVn+gZ"
    "bK4Kl+zG93dDHEjmRpLIjoREFgCbGYGtymEzOVwmRzKXxZjaMGXqZGzSNsZxLA5QVK1Y01fsKbyy/4W3"
    "l9+47svRw9d9O1GM4Nq/mIGNAlK5GwyUkwN4GAlc9qdKvqOejz4+jsjARe6TZwbeB9K5WmpzNfiSv8E5"
    "t3VwHVXVVCo1xaTdu8u33ZvJjMzF27/+M1s42SlG/o9cUgkJax0PPX0PB944xC827iCVShN8zHlNKec5"
    "VUzCaV9Xr5z6w4lNww924Ip2faoqvWnegzfUX7LoCqxxCAEwlJXIVLwb+u31JZwY0sZS5dKMMFkMMlgr"
    "Dd8kqJJIOc4dOcW6Jd84j1lWRLyqfgp4yCbcwmxD9WhhUAQH6t1hMAze1AmqKIoVg3DeJWgQChEJUaHo"
    "823dT/0vPosCPSlm19kAAAAASUVORK5CYIKJUE5HDQoaCgAAAA1JSERSAAAAMAAAADAIBgAAAFcC+YcA"
    "AAEIaUNDUElDQyBQcm9maWxlAAB4nGNgYDzBAAQsBgwMuXklRUHuTgoRkVEK7A8YGIEQDBKTiwsYcAOg"
    "qm/XIGov6+JRhwtwpqQWJwPpD0CsUgS0HGikCJAtkg5ha4DYSRC2DYhdXlJQAmQHgNhFIUHOQHYKkK2R"
    "jsROQmInFxSB1PcA2Ta5OaXJCHcz8KTmhQYDaQ4glmEoZghicGdwAvkfoiR/EQODxVcGBuYJCLGkmQwM"
    "21sZGCRuIcRUFjAw8LcwMGw7jxBDhElBYlEiWIgFiJnS0hgYPi1nYOCNZGAQvsDAwBUNCwgcblMAu82d"
    "IR8I0xlyGFKBIp4MeQzJDHpAlhGDAYMhgxkAptY/P0ds4FAAABFASURBVHicxZl5nF1Flce/p+re9/r1"
    "mk466axkIRGIIYQJEDBjIGTYN1FQVEYFHQ04qIiQUSGYgMMkKMiuMBDGiBggyCagrA0xAUJQASEhK6HT"
    "CWTrTi9vu1Vn/rj3db90d6Kf+cxn5nw+1a/vVnW2Oud3TkH/JKU/dZWVU4BbgdVADtD/w+GAAvAgUJWw"
    "JH0Y7Yd5PfbYY4OmpmXXgrtkRG1d5fHjP87Bw0dQlU4hXvt8qIAag63M4EW6n0vZi6pli/yN+6pgrWFH"
    "W7u78anf2tZs178JskDRAIhK7wf9MC+jGZ1uamp6OLT2lKtP/BTfm3mySw8ZblAniO69YrkENoTBgyAw"
    "8XWJEymfvvyDv3HfexDrHnvjVV21ad0RYgT1e6/dW5FGwBuxd1eE5sIHLriocOoxs8IP398od6x4gZdX"
    "v0O2UEQSNWkvQVQECYR+xPu7SZOvVZX6ugHamuuU19atRZVzgKWAJXYtYG8LWMClbHpW3uUv/MmZ50Wn"
    "TpuRWtL0JBfeew8F6/iHIydTUxOC1z6ye1WsKsZU4YyFvyGGqnYroi8JYkL/h+deRIuFD4zhClWWJou6"
    "8jfLBVAjQt7lL506fJTOnnU2K99+i88v+gWnn/QJ7rzpcoaOGgzW07OXSg4LhAH4PITDgWFl6xh69qTp"
    "tXTUj6AKVNKxe6sfM+7QoKNTf1yIoiWgIVDsLWpJAAH8+KETGt7b+t4/nnfkdCGVst9d8ivGfWwEjyy5"
    "BhOA27O77PXECqoQGHZt7yBIKdUNggnSEChGLIVchLFCEFqc84gKYgxbWrbSMGQQYRgkFo3JOUdQKfrk"
    "k08FO1tbiw0NDS/s2LFjL7cpJ1P+u2H7hnFA3fTRB2rn9i2ybMt6vn3BpzBVaYptnVgbYK3FWIOxFmsM"
    "Ygy2upJzvzqPK6/9FWGNAc3j1ZLPR6TrhhNW19LZlcOaEJupYPvOHRx+5CxeeH45QUUdANbaeG5jsDbQ"
    "D7ZsAdg+c+bMrQnz/fpkuU2Joqga0AEVGd2VbUNEGDdmJD5fxBizn6Br2LxlN1s/aoUoi63Oce+iBxl9"
    "4OHcfeedfPlL32DSlBlk80UwAdlCFzt3t9K+pz1moR/W8oUCQGHixIlR36c9VHIhBQiCoD2KItnd1c4B"
    "jaNBlbXrmzktFVBwDhNapFdUFAWiIotuu5T6mirIObRzGyf801E8sPQwvvaNb1JXW8vVc68gXVmBy3Ux"
    "cvgoHl26iOnHHI1GHRhrerGlMqh+IMCAJ564v5o4gfZLUvarR4+cOPCV5nfWLTzt0/WXn/tlPWHeFbI2"
    "2sOa139Jusbi2rNI7xwggAdTHYLz+KwHLWJqG6FqAi3NLdRWVVNdPxiXa+veOraiGopduMjvNZ1znqCy"
    "jheffUZnnXSOZILgmGwUrSw93pcAANaIOK/68KFDh3/qzbk3uDc3bQiOuP6HHD19CnffeikTxo+il9f1"
    "zOISwWwSnYpFqBoIQembkLLslvBi6OuXCgQQdURjxk4Ntm778EeR9/O893tl4H4FAFxFEEzPRdGyG848"
    "N7r0rPPtk6/9Ub6y6Fa2F7qYPGksmUwVPplHtRSN4qkkCZcilshFHDK6kXtuWUC7q+T8b1zGjl2tWCso"
    "Lvl2H6SKDQJ97fW/4POFncAPgLvoCX/dVNoDNnmYzkbF5YEEt8/53W8vHlE3yH92xsmyYewY/nPlSyxf"
    "vYbOnZ2IsDcDoqAeFUFFsKoUPNRYj3vgz2ixSMO2PfhChEVQLfOEHvn3VoUW5dOHHc6ubFdD01/fudN5"
    "1wXcR69MXMpGWp4VJWbkdoP+yyXHnmB+ePzppmHESDAWNCKOHDYGHgD4eJhEF16ACMRDRy5+v7YKMinI"
    "VEKQLkNtvSXRUt5TcGDDwrTZ55vX1q951Bhzbm9XKnFwKnBYwkkpdUbAt4BRNTbQ4w48RA5qHEplKsQg"
    "iApePKCICpp8JniUAPAIHrGx73tXxKtBbYBJB4iNrRUzoVgbEISp+Mo5UCUwho86O/nFC0/Tlc1epnCD"
    "9qTwbgEWAFfUDR6CWAOqSNnWsMZQiIp0FfJEqogYjEkE0CSCaF9s1NdbE8t6QH2f1337nvJLBdYDqUSp"
    "jwGXE0OJvWYVQE/7+rfcl66/UdvadxMYmyBmFfU+jikiYONE5rJZakSoy1QQhGFfJCwlN5CeZ2V+3h+p"
    "QseOHby9YjlPLF7sX33uKUlbe//MqSdc1JjJFv6rqWm/eaDtyFPOqD3re3N8ritrglLG9RbEo9LjEhZl"
    "4LiJDB1cj9++he1bNiMm3n3qQ8CBJPtLS3GhBOT2xYFgjWHYqNGMPHAkhQgevPkOf/P3v2O8Ky7G8yVV"
    "Dekf+QHwBWB38tCXrdjvuPrWBbrZd+hnvnje/3oJefRpZ+jiP/1Z31DVOXfeWwCrQRDMTvi0+7IAo0aN"
    "OrC5uXnFZ86a2XDZpeeRb+0UG5TkTfCCCiIBhx3SSPXgkbTsTLFh/VaMCEoU+3eSmGK9KyqxT/XAD+3e"
    "uNBTEBUjx+ur3mThfyykGFby08cfZ+q0o/zl55zPs0vv+2j8UUcdtO6119pLn/UWIGWNKTjvF02fNukr"
    "y5bfHZHNxflBSgbpjraQzaHOIA2Hgqkq1wM9oNHSHVqBOLCZsuv+KMO2ls0cM+047MAG7n1lJe++8Sd3"
    "0XGftOrded77JfSKQKWZ/ZVXXWWA195d8z671jfjcnmiPe249o5kdHb/qleECN+5kyjXTpTdQ9TVDlFX"
    "Ml2QCBASB5GK5J4kv/0NC7QzdPgYbr71J6x/803+9NIyDj5qmo44cIJ672eI6QfCJF8zf/58D3yYzRXo"
    "6MjKwMY6vAMjJc33QYtIcTc2PRDvwaQzbNqwiYsuvpRcoYgYiUtGFVBDZXUGDHTmspiyUFQKVIIwbHAD"
    "N920kBnHTidtLW+9/grHnnS8NI4aKZvXvDMqdtG+m7i8pEyLNdggiGfu24LpITHg2tFiBwTVCC5JoAbv"
    "FPHxHvB4wiDgmRdehGyBTx50KAVXjFWisUPZ0LJ19y6e+7CJy797CQcfckgsnC+V9/vBTCUB5s6da+bN"
    "mzemvjrDgNqM+mIe70ubcB+kinY2Y6o+RuRyjBk3jKf/8Hi3hWLyQC2nnXECudUtPPuzu6Fjd4xYlbht"
    "Ul3Fildf5pPXXEXDkEEs++Ny8s5x6BFH01qIdFvzZgU+SFo5faQJALn22ms88InDJx9E1ejhQmcbRvqN"
    "WuVmAHWQ2oUJxyRzF9m7iI9zgnOOXCGP69iNtreBjRtj3inGRbR1dKHqeXftBi6+6NuMmTSFqTNn8NdX"
    "V0rLurVijHnJ+/6VGQDFxsahB23dunXGkKED9NWX/mJye9oxJg5CcY9R6Aaf3aYl9nUcEjRCWI8m0KK0"
    "4dQ70pVV7Ny+i6pUiDWCNyTKETDaXQcDnHri2aQHDOSGXz1EZUXoH7rlZnFRtG3q1KlPr1q1qk9LpSTA"
    "F1paWm4Dau9Z/JTes/ip/Tvd/5BOmzIVfBIBE29QURDFGIP3ypQTT+KSBT9l8pSJLLnrXvfMQ0vCIEjP"
    "X7VqVVvCq6MXQAmAn0875cyasy67wnfmu0wgBpOoWyVBxmVlpIhgysJ5T1kgWPVkgoCMtRgUrxGZulqu"
    "u/hfybbuBpNUYJKUPprg5mT+7998GwccNI57fnqLv/0Hl4UC9zlXuCNZoHc1JoAEQM2QA8a6CUcco217"
    "2rw1YYJ/AOcNqiZeU2JQJ/HWLLlWmSiggkVJiVCdtgQaUV9fR1XNAHTnjrIaQBBRjAJqurt0zzzwIKte"
    "edm/+uTvxAb2/mPOOOai1rbW6iA1QsN0ukeLw+GNu37XpaoqIAtAr6gbPBgSJJr8iXOwCIJQyOWJ8sXu"
    "or6keemNpLsfxCMMAjrb93DK5Mk88cNr8V2diImzgfMeW1XNM6+/wokL5pVrtxxOl6JCb2z7LnBpADrH"
    "QlPb9u2lgqaUubLAgcDXgWDAiDoZO2M8tcMawIIzcQIyZcFBEyitQApDmoCKTCUv/eZ5CoUosYASaYT4"
    "vltt5ldPpWZELcVsURDGl6rs3pJZY3nj4WWjtr635cGAGAA/KSJP9qhOGTxmTONHGzc+VTes3h53+VlM"
    "Onsy1UPrQWwC1PaeuLwkVaBG0wwMaqgzA1j95joKa7pQiYugsLoGTAgd7Xjfs6FO+s65jJ90ADmXQ6yo"
    "YLSnqxorJuciam0taTHRw9fdP7GEOW3sTgioVA+rrv1o48YVQyY0jj1n0cV+2OFjpOX193n+Z79ny1vN"
    "FAvFfhoiva+EwFoq0vDByo2MHj4ewRBU1vLIipdY3dzMV487mcENA3FJdPr5hT+morIC57o1IipJaPZx"
    "BzzIpMmEab92xVsp4NkSlCjFV4vgOrd1/iBdkxl7+m1fLzZMGhkuv+Fpnpp7PxkTMGniGNJBCBrX9CUj"
    "+x4fiq8F1FhS+Wo2F4Sqigx5hdm3XM+9y14A4MbHH+WxudcwaMAgRIT6zhTVksF5h8GUTgoQNK60bQUb"
    "39qkaz7cKsBtwNw+KhwydkgjsGf67Flufsev/am3XKCAfu3zp+rWjUtVO59T7XwxHl1NZaP3dZOqblJV"
    "1c+de6bWmZQePGSYYtFFd9+uG9a+o9OnT1NAjxp7kALavOnPqlpQ1dZk7Ckbu1RVo38+/3NqrHklCGLd"
    "9z7giHZs/Oh4k7Y1kz53hMt9tNM896OlnH7cNO5a/CPoaCPak+3ppuyTBNWIKJciqKnjyivnsLmlhSAI"
    "WfKz3zB5yuFAgWVNv+faaxdy35KHWPjvVzN0+AiK2W2YEvotRUOvGGspFDbrS00v453/vdOrjMg8W85K"
    "IEYi9Xpd/QFD5sxefpXbsmJd8Mtzb+LFJ25gxqypFHa1kw77x+V9yeNsBVIzERNWEDtZXFu7rnYQi7EB"
    "kqoB1wU2jeY7UYnPEEjcRyVuYthUmi2bP3AHT/qE7ejMflFEfq2qQe9DPoAB6ZqUVFSkaPuwFTHCiOGD"
    "IF8gCJJObqLl/UNdg0Q5yO/G+bq4Ko15wtgQRFF1uOwOrAlw+RzW2jLm4zXiDokHIxSjIs45KOtW96fO"
    "PcXOgubzjpqGetQr27btREOLRtHfwXi5CCD5bVgvGAxGJAFuPUjfmjDO4Hbf6FdEwDtqqqs1nU4DDOxX"
    "gASTvN22ZZe0rmmRkUeOJjWgkhtuX4qprCJIhbhIca40/P6HF6JiJ8X8FtQY1Ety3+Mij3PE83iHc/sZ"
    "3hPlCgyoH8jQYY0Ah3rvDQkWKpFHYeDIgc/vat7V9dYjKytOXPhZPXnOOfLb7/+S733zRubOvZDahorE"
    "i/rpxAG9U2es1w602IKpGochzd7IoNwt90cRUGNOOGEm763dcHwYhp4Ea+61nog44I50fdXsCx+bU6z/"
    "eEP4ynVP89zCR2moqmLylPGkk4O57kJbelokaE9WNsZQLEbMOPowLpt/AWv+2sq8K28lV8jHsKJ79f1U"
    "fsljVcWmUqxbt1FXr1sPcD1wTW8BDED10OpBHds6Vg2bNGbUZxfPLjaMGxJuWrGJN5a8SPObm/DJYcZe"
    "B929W4wkBU/kGTvtY5wz7/NsWrmah+cvwXiLlTAOLyX41U/FXm5UkbhODivSZCoq/Pur3jO5ztyj/e1G"
    "A/jKynBqV1fx6UGjGxtmXXW2H3/mJDJ1NWIixIgnbgIHSe+oJ0SCBy27rwEOR3tHJ2GYpjKTIlQhk6qk"
    "2mQI1XaXG72PHLr1UXY/iiKqUpXc/28/Lz684IFwX+EkPrWvSU0otBduBU5snDiSkdMmUDusAWvjIkQo"
    "nVyWmlml7mRPpCn9byyoL3W0PYqSlpCMqYj7q+xtgX4MmlwogRVd8Zvn5YO3N7+3D/67hUCMYK39NPAI"
    "sI2e9tv/1yiZ/B1g2n8DR8F6WSVEtrUAAAAASUVORK5CYIKJUE5HDQoaCgAAAA1JSERSAAAAQAAAAEAI"
    "BgAAAKppcd4AAAEIaUNDUElDQyBQcm9maWxlAAB4nGNgYDzBAAQsBgwMuXklRUHuTgoRkVEK7A8YGIEQ"
    "DBKTiwsYcAOgqm/XIGov6+JRhwtwpqQWJwPpD0CsUgS0HGikCJAtkg5ha4DYSRC2DYhdXlJQAmQHgNhF"
    "IUHOQHYKkK2RjsROQmInFxSB1PcA2Ta5OaXJCHcz8KTmhQYDaQ4glmEoZghicGdwAvkfoiR/EQODxVcG"
    "BuYJCLGkmQwM21sZGCRuIcRUFjAw8LcwMGw7jxBDhElBYlEiWIgFiJnS0hgYPi1nYOCNZGAQvsDAwBUN"
    "CwgcblMAu82dIR8I0xlyGFKBIp4MeQzJDHpAlhGDAYMhgxkAptY/P0ds4FAAABkBSURBVHiczZt5nF1F"
    "te+/q2rvs8/pPj1mICFAgJCECCEDYQiEBBEQEUSBCE6ID5wAwQHBCypPRgHRq6gXLldwAEFUkIuihAtI"
    "mAk3DCa5SCJJSEhnTrrT0zl7V633x96n+/SYgPp5d30+9eneU1WtVWv4rVV1YOckWWME1OXD8BPGmN8C"
    "a4AyoP/Lms/aJuDSjAczHHPDkck6IzThubGPLwYmAzRGeRrr6imEQTrszkgEYy3a72VB+sxCtd9z6TvF"
    "nT1HFQ+8sb6FUpJgMOd4/O2ABdyAaQ0z5QrzjYEJ7kh88sEQmH/QLH/azCOYOW4vaaqrkdAYjOqwHakX"
    "pKaANNTh1feqVDYFrf64H4MMwmDfx32fe6/YKOKJV15OTrrpW7bs3WJUZ2k65IClCoaYc+XlBiv2j4lP"
    "Dp82bs/kh6d9wsyZsJ8hX5tOJEmyN6v7HUQdvEBtDdTVpc+rp6L0XYb+kuzf3YDn2veh95DPs88e48Ra"
    "4/Eu71VFRCoj9elxWAEYCX7uNDn8xMkHlH967vm5UYVGiGOWrFrOfy1fxor1LZRcgpHeeQxmDaoKoUWC"
    "oMdQ+yz6EJPYJaoSgALee2wQ8PT/LKWzXLYi8mDG/KAmMBhZgNCYcwA9aPfdy23X/ED1+7frumtv1vPm"
    "HKs57P9vR7crTlAF7gFqoZ/VVVF/DRDAj4LiFtUrImv05tPPtnUNI9iwfT2n/8fNPLNqFXuNHsk5Z53M"
    "zJkHUlusrIIw0NlW1EIx3iCFcbjA9t6vvDKsA6ma2VDkDYjBE/K5z3+BlatWay6XO62rq+v+Yb4CBgrA"
    "AsmOMDzJx/GeH5gy3c2dONW62PHl39zDM6tW8YFjZ/Mft17GqD2bUx+gjl4B93dYFdvwYBUKewMj+gqg"
    "R2h+kHtKr9YOGckyqmP1iiXurbVrrff+xe6u7vuzjyqasUsCUIA4SU4GdP6hc1SjPAuXPccvX17ElMl7"
    "cdcvvk6xLk+8eQtGhp+UogS5PGBwugPXuRGbD0E8sfcYDNZYUMFpjCJYY9LQqIoEFhOEIEpcKgEgg7CS"
    "JI6wNuBPCxZoV6lMFIULSqW4opLJcHOs5kAAdwVXGKc6tT4fyaxxexuJy/z21UUAXPqFMyiObCBu6yAM"
    "Q6y1WGsGbQBBY5Gbb/0VJ37oq7S3e8KwGwNYY8kXm8gVG1FVVJVcsZ6o2IQ1BiMWm4voKiWc9L75fPua"
    "7xPmGzFINubgbcWKNwQgCHKvMsyqDyUAAO5qvrkIjBpRbGRUPi8k7byybjUiwpxZU9H2rmzV+n5XrcA9"
    "du2F/3zov/njwsWsXrkJMSVceQsaFvjzo4/z7MInCWrHEhTH8uJzL/Doww9DkMerh9CyZu0q/vDIn3ng"
    "P/8E4oZ2A5KayuYt20wqADZWzWRYGhAGu5MkAILQhoTWgHo6SyXEQr62BvEZq5XZDDeEWHJRDoAwF4J6"
    "YCOlrpGcfurZbG1r5bJLLsaGlmtvuAlrhE3r36BYGwFKLgwBiHIhYFIIofQFTlWk6nfmUncugAlNTZ1r"
    "29o6ujq7RnYmZY2iGhld34C2rGX9xs2MHd+AlhWTDVOxyT6qJGAUcGUu+dJ8jp13EBP3GwslBy4hKpT4"
    "9vXf4ssXf51rbvgOAIV8nuuv+7/UFgv4uBujlvHjJ/DD713NlP33B+dBhmBeBbCMGjlCAZzzo96JABSQ"
    "hatXd4OsWd+xffyabZu1cbcxvGfygfzptaXcc89CDp43jXJrOxLYASi1jwyMgY4y8+ZOY97xB8H2BNRg"
    "RaF9Bed+7uMc856jefKphTjvOeqIo5g4ZTJaak2/VY8Rz/lfvAgoo6X29P6QpEzYd18FSBK3P8PE/qEE"
    "AGmwSkKbezp2pTmPrXhdD5o0nVOnHcZ3FjzIj3/+W44/8RCO++DhsGU7zvkUeg4pBcG3l/FtjsCG2T3Q"
    "pITb+Bf2nTiBfSf+n0z2JcodAyNLUtqMEcGYoYGc9x7nupk2Y38BKJfiOeyiE+wvIQP4mrDm4M64c9GB"
    "Y8boMxdfZepyRW5/+hHO+dXtFIs13HT15/noh+dSbGoa2iCHI9VUcFEjZdeEOkNUqAFTSxq1KpB9JznG"
    "gKmXdcrkQ+W111e0jx07dp+WlpbNpIs8ZCgcbPYG8MaYP3jvT7zxpPnJxe87JdBuxw1PPsJlv7sTD+yz"
    "x0hmHjiJKF+LV0cl10ihudAbF2TAtYjBuRKHHDiBL156HrZhP15e9N/86/duw3lHiiB8yvQuJgqqis3l"
    "WLjweV2zdq1Ya+9LkuSbwFKGyASHIgtICAcYMV1RELg/fPYrTm++W/W7d+rTX7hMT59+sDaEub8bt+9d"
    "V6dbfnKL6oKH9OZPn/OPzgcUpBU4JONrUAciVX+rX7BA2RjzWe/9LXVRnjs++ik9bfrhQhCC72b11q20"
    "tG4ljkvph2oA0zc/lzQvUSARg2DSNEqUso/Zq3Ek44sj0HJMYi1/2bGJOAxALGildNK7cNWRV6X3ianc"
    "FIhdTBDleGDRc+XvPvhADnhIVd9PVXGnvwCGVQ9jzKe9998Faj45+yj52rwTZf/dxkChJp2FVGF1NWBM"
    "VXdZYiaAGNAMQKkHScA7cI5KjCcXQj6AfB5ytWBsxnXGumZT7fHv2XVlOBXQBKKIzs2b/dhPn0Fbd+fr"
    "qvquoeoBPRqQz+ePEAlHOJKqF6wVo20axx933p/tkoT6fEGOnjSVo/belzHNzdQGFputLgoeD+IzfCBo"
    "alGYzLl5DGkhLEm1RWyK/UnwqngVvAiEITYXINZkfrZfFcULqg7VtDdRxYg4r16DKOL+F190tz/+x0jg"
    "fq96KsPUA/YAnuAfZ3//a5qIvAUcwOC5erryIvKwqh4/adqhbu+DD5JSEmOQ/llXCvw0rcFZI3gjqGom"
    "fciHQQpT+9f03jFVGXnfCdPetp01y5fxt2XLcHGiIiLW2q2qcmdaHCCwIm+Wk+QXwFqGMXMB3Igxu+tN"
    "T75kC7uPpuQS7EABpC9nVqQiaQ1CAefIG8OIyGI0Ndt/NrnEE2/bzhuvvcaCe+/lgTtu93FphwsC+/Mk"
    "cef2e31Q51chETHtNfX1+S//9B4ZN/UA40oJgbXZN4Jq5qDEoQI+rZghmmBFiGrriRPHboWIfACdnW29"
    "EFnB+zD9R6qwiPbXyF3TGsl8QSFfoLahAbVA7Fn6wiJuPO+z+rdlr4gJgwU+Tk7JOk3YSR1QEHs16i7P"
    "5SKa99idcinBO9+z3JI5rYoANDUQjPGQKKd/5Zu89+yP0FBOuPKCT7H0mRcwxuJ9pVJkU/0TX6WHfbMa"
    "QXsuh8eVgogwYmQzB82dy7wz5jNl2nSsKbBlfQuXfPjU8orFi3LW2u84577KLhRChTRwXazwZYXR+VxI"
    "Y0NBnPOpyKurU9kXAogY8MI3vv5pzj3/NJLu3fjYxz7HU089TxiEOJ9UMWT6RDBgAIKuNrnBM760M+8c"
    "W7ZuT3u1IWddcjFnXHIZkY1oWfmGfv6YY3z7thZjIntY0pUs2pkQpPJCbW3tMZ1dXY8eOXu6PvybayXp"
    "ilMme77tWwBQNRhjKDbk0bgTKY6H/Gh2bO3EqEElATTrQ1DpzedBUaPVMkW0t//hBeDZsHkbDzz4ENdc"
    "cz3bWzs47fzz+PzV36amUMevv39z8r1LLwxMGNzn4+Q0duYDsmbmzZsnTzzxxJL6Yu3k1174qR+7xwhD"
    "d5J+LkpfbJ/9VUWdR3BoOBpqxyM2jdHZzkLV7H1lqB6f0rPsmpmZSnZvJz7BWjCNvPLSs5z8gTNYs7aF"
    "q355D3M/9GFa16/Tz8w9StavWdmZb2rav3vbtjXDCaEHtj3xxBOJWPtcW3sHS5at8BqEJEmCJq6qJX3/"
    "dy51TGLAt4N24xOHdy776/Euwbs4HUarmdOBkbvCvO6kJTFdbWuYNmM2P/h+WlC59wc/pNTRTv24sTLr"
    "vcc5oIZyeU6/VRtAQfULoZXlZQdr1mxDApMiOlMtvKFqDIK4EpQ7IGoiVeM0jhsbgInpbOvGYOkpJWlF"
    "7Q2Kw5Nus0mmBFJlH/31wamjtlhDHG/gpJPfywFTJrHsxefZsGoF+82cwX7TDlZAtZwcuKsCAMBaux0S"
    "dnS072pkqurf45MtSNRAquaKGOguK6ee8jEWv7qEIAzSgmflK+31JUHO4L0ndm6AmKunYm2KN953wrH8"
    "6MffxwYRM6ZNZ+n/vM76lreYwgxGjRoNIM4nowfpYmgBgOYAwjCXXVZseGebEpl7T9rRpB3CRvAxaBoy"
    "FfCqOOfxXnu4V8CKsKOrg7Z1rRSMZUSxjkR96ka0V+dc5lbKImxsbWXBgsdJujuwxRpsVkVS7bv5rsOs"
    "/KACSBI3DmDkyCbSjC1zvbtEguDxXRuwUgRjUXVEkeGPC35Nx/b21AQqAEsg8Y6oppGFj/0XJ5x8Jmcc"
    "9W7+7XNfpdy+HbEmiw5p7w6woWHLjk0ccOGF5PN5jDW4uIMXX1yMsQGjdxtHrLBpU1oVNybY4JxjOCYq"
    "AvAAceIPNMCE8c2icRkRnyLBXSaLidvQ7g1QGJeuRhKjItTW1WSK2OsInXPYfJ4osnjvCYB8LiQf5iCo"
    "cpiVLbYgoBQUMOqIyzFhYTS/u/8uli5/nYOOPJrd951Id1zm9ZeeFwCbC5bEcQl2YgIGkPHjGxpXr26d"
    "OW7sbkyeOMFIkmDDYDjhDUEh+E1AHglHAdnhiUporCqP9T/c4FBUE5x6jPeZ8QAY1CviPYkXnPfU1BV5"
    "afGzXHhRegrmtAvOIyrW0bpurb644DELdJLLPUVHx04FIIDbsrH8HjFm1MGHTvRBITKtWzvSSODT0GOy"
    "qJXm8FXBrP+JjSxquI6VBJGDoB5Fs7ydPqVt7xy52na627syNlOoK+Izr1OVWUk2tipRPmLV6jc57riT"
    "2LK1ldPPv5AjTjiR0MBjv/2N27h2VRAEwcM7wwAVAShwSXtX11cAfXTB87LfAaeSeE19YL+NoMpFD9v9"
    "ZNu7qIp4gzc2VfpMUGJ6exIUI0Icp2jTq88qTJW0s0eqKB4RQVHCMGRraxsYyycvvYwzLrmM0OZZ+dpr"
    "esf114kRo4RcRzUaH0oAInKlql4e5vI0jRuLSxwdcYJYSSs12SL01OAGOaMzWOqsFSFIVQokvfcrnXpr"
    "UGKgtSfbq5JQ9pqiGZoUEeJSmebRY7j67nuYMms21obsWP8WV539iaR188YwtNF3467STvMASDXgi7X1"
    "De6Sn90rYw+YYko+JsjwezVjPotHg53S6gNcGDzRyalSE0UUxGJFUfV4Tcg1FXnl4cf42pmnV/XRN13u"
    "FVoq0DiJaW5s4uAj51JSWPrc89xwwWd05dK/hCYIHomT0uVAjh5VGpQ84ANVLRRqizph6gwTjRlFOU4T"
    "XqjAAO1hYnCSXdobkQzGOhGiSKixoM5Tlzc0NO/WI8xqltEUjRpVVCW91lSTEmKWPPciD/76Dn7/k5/6"
    "pLvL2cD+wiXJOTufTQ+ZQMQ8srnlrfd+a/773fgZB0lcTrIaQD+utXdJRKTXlrVf9lbR8/5QTkA0RYjW"
    "CKFNHVq+ELF11bpetvtowUCpe/XkojzrV67mvOPnUip3q5HAhEGwHdV2rL2ZVPUHWzIFDIZNLnZ3A68F"
    "qv5cQe5c/tKiectfWjSctDw7h4R/F7mqo2YqPhPaQPUyxuDiGEcMIF4TfEIzcOGuDQTARcDpAbBW0Xf3"
    "LYun+MhmOaoxtr2UlC7SxJ/sXNnXNteZCbMnMnb6BOrHjEACg5csAcogbK+kJPUfVNZUEYU6E2LVkisU"
    "aFmyivuuvyvVqqrw4km32avxgoiQlBKaRo3g1KvPwluHVDCGiBMztLF6hTAXsfK5Jf7RWx9qUKc/ruAA"
    "7e7ufhq6B/0wMOabifcn2MD62Z8+QQ77+CEU92nGRBESmrRQMXgRt0/Y67mnhjFSJGdy1NTWseThOri+"
    "V2CQ7viKMYgN8Elc9SRFkLnmOg4/63is6U5XVEBFbSX36ImgXntyCQ+YwHLYibN46f7n/eZ1myZWcED/"
    "KiVk22MicnXi/eW1o+v11H89W/Y6en+8eJKSY8cbG+nc0EHcHacdeAZ4S6lsd1eX1BS22AKhzREVYc2i"
    "1VXvpElTrljExyW2t++gsaEZ4jLep1Umaw2lji5e+/2zpK7E9PohFVS0F3j6dJPGG6HkPVEQsurZJcm2"
    "jVsDEVlTyQWUvvHSAmVr7bHe6+X5xkLy0ds+a0ceui++5Nj4ynqev/0RXnv8FZK2wbXmnVDiHYqQKzbz"
    "1JLFXHL37axoWcdph8/l2g9/kqZRdSSt2wijkK1rN3DT/CvfyTBKauMx8MWhjsp6IOdVb1L1HPfNM6X5"
    "kAniumOW3fsCD33jl/iyY+zoZmbMPoj62iKqafg0PWNURqsomPS548WAzROGRTau28AjCxdSmysgUS3X"
    "/uYWrrjnThKU+sYGbnnkIZ5auoTbLvgSM/bcF++UuroiJ59wLBjt2ZKvqH9lnEq1Wb2SyxV4+tkX/Bsr"
    "Vxlr7aNJklwOPD8Y8xYgl8udAujeR+yX/MuKf9OvvHmrnnJruoWdCwK98coLdPPa36l2PqbaubC3dT2p"
    "2rVwkPZkVXtCtbxIVTeqquriZx5RQI85cLqeecRRCmihkNef/PuP9K01q/QTZ56ugOaN1QtPmq81YU6n"
    "TJqoqp2q2p61Hara1u+60tpVtaSzZs3wQKmhoWGfjNdgKA3AOXcmoLM+doSGtY7O1e08euX9WBHuveUb"
    "nHLO+/FbNxC3tqcHoio03MGh3pfw0orW5DGhY99JEznk0Jk89sJiAGYdPJ3b/v17TJ95CPgOfn73HcyZ"
    "cyRfufRyfvD7XwPwqbPOxLlukq4d6bG9StG1H3zw3mMLNfz1Ly+5lxa/bIHF27e3rhJJT8UOdlbYvetd"
    "5JYtc4dEzTUy+uC9jQ+EFY+/SvtbWzlr/vs45ewTKK9fjzUh1hrM26ufAQbRGNUujDE0NNfz0B9+xT13"
    "30tNvsAZH5lPbbEG17kJMQGqCZ85/wLmzZ3NHx96mAn7TeDkD52MjzsIc0FPbTHlwGezMenxBMDaAq8v"
    "X67OK6G1L4q4Hqg2mAD0jZb8btA9pnnsaGobG0TLnrde+CuI8JGPHo1PujEqiOg7YB4qSY13rSCOJPGM"
    "bKzjgi98CfCQdOC62rEmSivlAknneiZPnczkqVMBh+9uz0BnP43L4HMPNz4Ffy0b1qfCCO2q2PX6+0FN"
    "wMdBLZCP6gNsaPCxY9vm7aDKuDEjMOVsv6DnZHqFdh0oCgZJymj3Vmy+CecUX96cTtJYjEl/W4B40PT4"
    "revegXepQKxNpz74Jm5VIpVlo92lNFqJSFf1u4MKQEycAM4lznoPQS4gH9UA0NXRlVWolL93I9iiaHkT"
    "EtRl5iQDVxTpWVFDgBnSaw1PtTVFAJxqXfX9QQ/414ys2QRsb3+rjVJbGROFjNl/LACPP/MXpJDHJ0n2"
    "tqlqb5csuA5cvDktSA9IhLKmpqpC/fYo9cnK2N3HAOCc27v6+WACMNve2NYqIn/dvn6Ltv+txSOO/Y47"
    "EBNYfnTb/bSs2kjY1EBcjnGJxznNmn9bLXGeRIWkexOqm8EYRE128DHrL9Gq/itjuF1ulUOUEydMkMAa"
    "XOymZdW5IcvFAZAEueBrSTm57rCz5ybvue5DgS+HPPG1+3j27seYe8R0fnbbVey9/2hIusFpdZGwb7f9"
    "jwH0sdksufcJ3jk0vzdCAybKA9m5gj5TrNTo3onjRWdMP1xefmVJ54gRIyZu2bJlHUPgAA+Q2PBOkeTy"
    "xfctqplx1jFaP6lRZv/LCWxc38LCx1/msCM/xic/dRKzD59CbT7CZIwb07eSU71VIf0zO9KfueXzEUdO"
    "nQSsh2I9ry9dyptr1hLYYJAlenvMC5D4hHyxQcbtubt7dcmymq6ujnOAqxjmBKkFECtXAbrvUQeWv7by"
    "R3rRmzfqpS/fqHPOfb+aQlRlpH9/+84PLtbXOx/Sx1+9Sxujf2zf/ZoDVET+BIwZCrZVwHtkjVnovJ81"
    "9YOz4/ff+JHQ5DxOcrQu38TqZ5aw6fUWknLlfC9VNcOslNZvCbXPf2k90UQh0z8+h4ZJY/E7Onj5Z3+m"
    "dVUbURRhMJlOuiqs/3b3Kiqa4DC5kHUvLfdvLnvTiMiDw/VUMbi9rLGPOu/2G3/45PiEb8wPmmeOFhMK"
    "qEUSj9E0VKmCiE2RmSQZi7YyfMZ2+hshJMl8fZpClctdxGWHGCFfU4PgiSSkkKuhYPOEPi2hVf8+sb8x"
    "9E25+j2vgKLIUnpzK1e8+1K3bePWnQL3HiEYa+7yzs8JoxxTPjDT7/++6TRN2kOiuhoJrUF7ivAZwz0n"
    "SHsZ7ulS+z8HsT7dOleLdwoSU+E2tCFNFAlsrk+qMZgAqmmAt1BPmLOsW/I3/eFHb9SO1o7yruhSRQih"
    "CYKLfJJcCOwJEDUUqGmux1qTnRmshqaZiveR8dudcqWIphiV9LcEu5RsDUGqWGPZsm4DpfYSwA27+mmv"
    "ay8yKoiCz4vIH4B1pIWFf6bT+mc4we2kRbjg/wHkDxKAi5UXEwAAAABJRU5ErkJggolQTkcNChoKAAAA"
    "DUlIRFIAAACAAAAAgAgGAAAAwz5hywAAAQhpQ0NQSUNDIFByb2ZpbGUAAHicY2BgPMEABCwGDAy5eSVF"
    "Qe5OChGRUQrsDxgYgRAMEpOLCxhwA6Cqb9cgai/r4lGHC3CmpBYnA+kPQKxSBLQcaKQIkC2SDmFrgNhJ"
    "ELYNiF1eUlACZAeA2EUhQc5AdgqQrZGOxE5CYicXFIHU9wDZNrk5pckIdzPwpOaFBgNpDiCWYShmCGJw"
    "Z3AC+R+iJH8RA4PFVwYG5gkIsaSZDAzbWxkYJG4hxFQWMDDwtzAwbDuPEEOESUFiUSJYiAWImdLSGBg+"
    "LWdg4I1kYBC+wMDAFQ0LCBxuUwC7zZ0hHwjTGXIYUoEingx5DMkMekCWEYMBgyGDGQCm1j8/R2zgUAAA"
    "Qp9JREFUeJzt/XecZkWV+I+/T9W9T+g0eZhhmIEhSBAQkCyogOgqCCgqBoKgqCsGMK5hDbuuCTGu7iqy"
    "u4KYAAURhBVFxUVJkpOEYYAZZpjQ3dPpeZ57q873j7r3Sd09HaZn8Pd7fc7rdbuf57l1656qOnXqpDol"
    "bB0w2X+f/S8C+wEvsnCohz0EFgn0+HBvq4HI5u+r/n0/31IWFOhF+DPK14EbAAm3pgcToDet+oTGwO8B"
    "vAHheJR9gJIFEAkvFsHPNAY5InnPywR9oxMg8Fw/HwrVh1hV8aqg1IAvA5+iQQTTJoSZANP0eS/g+8Am"
    "BBVBjTEqxnjAEQjE00D6/11TuMSIa/r+T2P0/6RhpuafJQxsCcwHgQ+An2tEECPOOZ9zBukE5nV1090z"
    "i1ldXXTHhVF0O9GkaQeF1pYYwVgLgFfdLI80E/BoPwGP3trPQ1gmvCpe4G9PPcGTvb0gdS47gnIQ8CCB"
    "CPz4NY2GaCqFx4F88PcA810wL7YoGOOcemOd2nkIB+y2O8fsvi8vXrobS7dbSFd3mVIcY0QQBMk6SmBa"
    "jExFQBUVi53ThcRFRMGJR2nQRztxiWQTZ5xx8Lr5/jSy+Ym3pc9D6A7vHIKwuq+f937nK1x1351GjHXq"
    "XSfwOuBfmcaE3lICyAf/ZcAPgO2t4CLBVL232xeLvPmgw3nTgS9m7x12ptDdCSMVUAdpDT9UrTMuyTpq"
    "qrM/BxWTEY5BSjE4BaeIAQRMVu94PTQuh5geOjP2PAScIwKOS7fbnk+cfBq/ffBehpzDIOrR/bKiU+69"
    "LSGAfPBPBC4Buo0hdZpGxsOb9zmAf3rlSeyzbDmkKS5NSAb6UOcQFFUFgUwcbMzQaS5K9Zar1okJgozV"
    "skSM0UXCJGWxrQCTe63iEbx3mOFB5i9YQEehwODIMBJ6rFwvOEWYLgEYsplvMJd4tNuKOOd9NL9U4jOv"
    "ezNnv+hlFCo1dFM/LgIxFuuyGREXwBiwpjHiU9GHxkUpLAN0dkKxBF4DmbYLAWN9Hm8kJhqhidCe8PmJ"
    "KmgsYBaBzk5+/vurWV8ZRoygQchY1fS2KXXkdAggFzSeJ9hLPHRbg3Pe293mzOU7p5/N0Xvti+/vx6cg"
    "RBivUChguktUalXWbexlbd9G+mrDOJU6EYzVVzpJwlARUgXnHeVZXagxkAlO7apm+3ueS91p4vYF+VlV"
    "MVHEXx55gO9feSVGA+m4UOB/mwpPCab6QC7NF4HrwRwpFqfO273mzOV/3vF+DtxpOcMDQxRNBE6JbAFK"
    "RR5bt5pf338Xv3zgLh556mk2DQ8w5NIWAW0smMrgNNc1JVH4/0cgG3DI6V2JgT8TZLCRpmKThqlygNzI"
    "8wHgSDHqALuwWOTC09/BQdvvSK2vn2JcJBXBlsusHhjge9ddwU9uvYmHN/Vl1ViILSYqNpkvxsF7skuD"
    "ZoNvWpeU6QqVzxk0yyoC3nlUPSCoKMaKV68G1VjgCYWzgWGmoQLC1AjAZGjtjvARoygios7z6ZNew+G7"
    "7kXa10scGxJXI+ru5ob77uSjV/6Ue1Y/DQiFQgGfpKTqIHFbZ5a6rVHpcwsiMaqKiFfvvUFJjHJNBB+p"
    "wSO0Wl+nBFPlAAp8SJSezMBjT95vP9569Kvw/SNI0ZI6R2H2bC758018+NL/YW2aEsURpFCr1SgJvPCA"
    "Pdh1551ZtHghnV0C6pBRCtPUFCgBRBVxCWgBW5yHMwW8qfL3vyBI41JBEbwaisUyV19zDbfeehsieFU1"
    "INej+gkPd9TCw9Oa+TlMlgDyl+wewSlGRBOvZkm5xEde+To6tIgzNWpGKXf2cPUdt3Duj39Ab5pSLEZU"
    "qykF4O2vfTmnnX4cB+23D+XuHugoQDQY7AItBhGZnl6mgPegZShvD3RQ1w7+7sE0/VfC0Fj+8Pvfot4T"
    "WSup9wnwaeAOgn6jbCF1T5YA8h58kxe6rYhXVXPy/gdz0A67oQODIJZiocSja1dz3k8uZmOSEBViqtWE"
    "HRfP41vnf4RXv/blkAzAyCCajKB9inqf1S6tr5sMAbQoPQLiQWp4ikilisSz8KbMZglA2ziNjNOf7eXq"
    "5duFjOkIHXl7w+W9EpW7uf0vd3DTH27CCk69swK3aGPwc1/KFsFkCEAIK2sR4URv0ZpTnW0j3nDQS5DE"
    "4YxivKDO8MnLL+WxgQFssUhaTdhzp8X85IdfZd8DdyXtXYlgMdZkTZVgD4AxBnwyS0C789GiNkbVol6I"
    "pIixccv4t/eYtA2sjkMA7eUmKj91aOIALsVGXfzxpj9RST2xNZJ6j8JVQEpj9m8xTJYAFHgByvOtN+LU"
    "2xfutJz9lu8KtSqJFUrlItfffTvXPHAPBVsgTRK6uwz/feGH2feQnUnWrSGOC9RHo26A0da31GGy0r/g"
    "61wERFIwCWgpmIIjqWsEzRbB9gEVNZm9zaDixx3wdvA+Vz4VY0YvN9PRQowI6DC33/HXDG0xqiTAH7Ii"
    "M6bbTJYAAA4GYg3TzRyz7/50dpRw1X6KaYQrCJfeciODKFGmvnzgfadyyFGHUV23hkKhEDSbzaE+haXa"
    "A4hD8JiuWeEHUXy1H9EESEFq4ItkNueG0bH5lTlVaIgh0HH6th3v/GtU6sm+WTQZylS26YKgCjY2DG/q"
    "48EH/wagqiqZyvdQ2+u3GCZD5vnL9hcBr17LIhyyfA+oJOA8Yi1PrF3NjY8+BAbStMbypXN515mvxW8a"
    "IhKL6Mzp5PUuFiE1jv++8DJOO/3TXPGT6zBxD2iEkqA6PLYdoeWnfNZOJCyalkuxSKGD31x9LW983el8"
    "9UtfIUkUEZv5I6bTXiWjANauXcuaZ56BQAAQ1L2BqdY4EUyGAwQrBOxMoABZ0NXJ8lnzwKXB3l6IuO2J"
    "h3lmZBhbjHDVlBP+4UgWLZlH0t+LtTPhdW6AAZzz2K4ufnX1DbzzvG+QAFdeeyO7LF/GfofsSjI8gDHD"
    "WEkgCr4SxeM8iDGZfVgzoU+Ce100i7gBo4rW2XoDVEC9w5Q7eezBhzj19LN5tm+Qn17xSxYuXMypZ56K"
    "G+7FZvEIUwXFA5YNfX1sGhjISFJRWJkVyZ1wMwITcYB8SnQAC3OKntM9m9lxGdIqYh1EcM+6p8LMzAzv"
    "Rx62L2ghCObeB8oOoUybZWB5qNAo0PYyCqbAgw+sIRGhXCwyWPOseGINmBjxKaQjqOsnyE0GFYhKs7CF"
    "MqZUxBQLOBeCa1Q8zjtMXCAqdWGKRWy5E/WgmYAaBD6P0yCAr1y1kmf7BuksFDDGcN+9D9S7dDocQEXx"
    "eCCit7efJHVYkZyJPTu12iYHk7W2lICenB66uropFwvgkrCuqmPT8BAA3nuKxrBs2TJI0q2ugRdsAUFJ"
    "nENEgqCZmYW9JjjfD34E7z2m0MHtt97GSa9+I2ecejaPPbyCqGMREhWRqIAtL+DZ9Rt519nv5oQTTuH/"
    "fn8TptiJNgKaAgcwgRCstRgREufx3hPH8Ra2Jp8dQqVSadfzhrew8jFhsrzZArk+JTbztOXoqSoj1Wr4"
    "7JVyydLZ2QHZoLRE+bST3BbKBc55RARrDd47RkZGMoEvJqDZh7oupKOLykiF97/3o9x8620A3H3Hvfzr"
    "5/6Fww8/lDiOuPXOm/nYxz/B7bffC8AjjzzOn//yB2Z3d6NpEgJNRethXLVqJUgPAsaYYNNAW2Z+/nny"
    "dq2M2/htY72cLAE4Ah8Fmuw2EthqkJ4zMJAkKVWXQjmGSljTtgqo0jO7C++Vai0BVbq7OwKOYkLgCRXS"
    "dJBYU0gtA/2DGGMoF4rc/dDfOOF1b2T3nZcjAg89tgKAYqlEmqb09g/ik1omJ+TzMecGhu6uLpwqpCke"
    "6OzqYPOC5ESQ68JKuVwOc6WhZXZsQcXjwmSXgCowmKlIWtk0SJI6sAZvQCLDdj2zALBiGEmVNavWQVRt"
    "VatyNUwa11gIjYmUtJaJjMGPDHHcSS/l+FccxKxyzOlvfBkvPmo/dGQYi2BUEDoQ5/D9fZQ6OvnkJz5A"
    "bAxDlRFKcYFCFPHw4yt46LEVxNZSiAtUKxXUpXzmnz/C3IULcLUREB98914xEuFrVQ465AjOfc9ZdHWX"
    "OPqIgzj1LW8AVwmBGrL5do7ZRBVMFmszZ85sCrHN+k8AFkyulqnBZAlgGFiXP7Kuv4+NIwNgstBUgV0X"
    "Ls7FHzzwp5vvgrTJ8DPDICKQVlkyN+ay//oUf/3997jo6x+ioySIc3WdXzTC4BEdxg89wxtOO4UrLr+Y"
    "vffcg0pSo5bWGRuJc9SSGjvvuCM//uFFvOucd+KqQ4gdY91SRXB89YIvcN/dN/Ora69g6S47okk1aBlb"
    "0i5S5syZTU9XT10FA5ZmRWbU3znREpCTnweeQDkCMfpsZYBVmzay45wd0bRKWks4cOluLIpj1mTRq9df"
    "92c+ft67KHcU0VxYZHo+nvEwM1pAhz2lGHZ+3gKoplCTLCYgvMiox+MQHUDSFE3KHHficbzosBdx2eVX"
    "csPvfseaNWtw3rFg/gJefsyxnPia49l+2Q74Wl+DDTeB5PELPkVRdli+FJIEXx0IdoAtAoE0ZcH8+Sxc"
    "uB3P9vbmosdyDbF/I4xhN50uTEYGyOP/7lb0VEQY9J57Vz7G4bs8DzNSwVVT9l66CwfvugdXPngvpajA"
    "nQ8/xo9/9mve/t4TSDasJrbB0CIZSW0x9nXJMsabYUhGEFNCtNxW0GDwICnepWg6iGCZvbCbs9/9j5z9"
    "7jOpVvpQr5TKHSDzgE2kIxuwsQl2js04jATFV4OAHma+H99xNMmGeefontXDsp2Wct/DD0mQZ9xyhR0J"
    "1sAZI4CpWAJvAXFRJtH95qF7cSlEFMApNrK88YDDg5dCHDYyfPb87/DIQ6uJ58yh5iqN2nR6evIoEI+Y"
    "BOOLGJ2FaImxl5wmS9/wRkzahya91KqrqNV6sVFEIYpJqhWSkdW46hCRjQJ+Yw2mmuzKXFpis5kvWzj4"
    "wVztvENsmQMP3CNHXoFO4ICmBs0ITIUA7hT0UVUH4P/y8EM8uG41Uu5AxFAdGODl+x/CMTvtQjVxdBnD"
    "0+t6Oetdn+KZNSmF2QtI/AiqfsrC0cToGQIz21xzQsiJSSu44X7EV4iNx4hBfXDqGDFYa7LNImYSgylN"
    "xDCZ8pMBX1exDz70IACcr+uER2f/t7kvwACDCtd6BTFGV6UJP7vjT7iSDaqg88yJOvjMa89gcRQzkjg6"
    "rOVPt9zLa17/Xu6+cxXx3MVIISZJE1KX4pwjdQ43I1cycZm0hnc1tDKIG9yA+CqSmYRb9pIquFRnCK+p"
    "X14F54bYZ+/ns938uXhVyWIdjwJm05DNthgmW0lmf44PgPRmMRRUVZZ3dnLthz/LbnMWwkgF8WC6ZvGf"
    "/3ct5/zkBxgj2NhQrTrm9nTwvnNO5rTXv5Sdn7cr5FazFnvHRK7CLbivmSyrDsSCE0gNvrQQb4oYLIrB"
    "eBfYeXEW49utZyQWYwJQoJuzzjiN/774h1hr1TknwAnA1UBMsM1sESJToaK8h69AeK2Iceq9/eDhR/GV"
    "09+F27gerOC8JeqcxZd/dyUfu/InAJQLMSO1BIDt55c56vAD2Huv3Vi8eBGlYglVwm6eMYIrtB7UnwlY"
    "+RRtNipM8r6iiEkRn7BgTjdHHHEIhTmzUduNmjl4LRKZlHSkwo033szG3iFsnEddNYw0jfcEy2fonZkj"
    "CJVgUo/L3Vx79e/4r4svwYo4p2qBa4G3AWtaGz49mAoB5F6ogxH+IEoBMdKhXn549rmc9IIDSYb6EClg"
    "kggzfy7/+X+/5l8uu4RnRoaJrRDZiEotqZPsjLq1pggWeM9pJ/D1r30IohKU56GmjEjEu9/9Pv7jez95"
    "jjAbDdYYfIgIyil7NXAp8Hmgjy3QCqa6juTU9i3gPSLiVNXuPGceV7/vk+w1Zz7J8BAREaoG093J3Sv/"
    "xgU3XMkv776D/qyCookwxpCqkopkslOuGrQ1ZRRtaxbZkXXHqCZs7n6miqI4l7Ksq8Ct//V15s5fQFU9"
    "xdnz2bipyn7Hn8jaoYTYWpzmcQI5J6B1ttffsXUMXj73ombvFlDvc7YofwZ9LYEbTIsIpkMACswFbhLM"
    "nlaMSzW1B2y/lJ+f/RF27OkmrY0gJsI7JS6X8bFw0yP38ePb/8SfHnmYp9etp6ZKSoMDbMvA7XxITzn4"
    "YC5849uJaxWqFuJCERcXOfcH3+XCW/68DTGaIgTXS4qaGPwvgNczTcFkOmSbc4EjQK4TpENE1Kszh++8"
    "K5ec/i52nrcYv2kTYce2YIxAV4lawbKuv4+n167lqd5n2TiwiVqlgqkTb/NMCv9lzP3zzcKZNn4RQjoS"
    "qMf0CY0J60TxRhGXMrejm6MOPIQlthNqNbwI6hQbFdjgq/zvg3eyCUfqPc5pZqKVlvdtDsbq2BzrsdTf"
    "nPk1T2PNuKJK8LhKZPnLQw9x2f/djDeoqPGq3gKvIOwPnPKqOl2+lb/oDOC/BdRGhjT1Zt8FC/ji60/l"
    "lXu9ECoVXJqCKC5rSIEIKZbBZARb38qVt7o5Ph7G3S9eFxibeEfmoWytp6lufHivd5AqJGlIvGAM3gc7"
    "vMkjlctl6CxBuRTqzEetBZ9pdt941DFWuXo7A4X4KOazl1zEv1z2I7IEERb4d+C9bEMCoOll7xXhm6pg"
    "jXjn1XQA7zj2Fbznpa9il7nbQWUEVx1BvUdNhEgUYgVUUeNCdE8dWgdwbA4AyOjFwwuomCw+1LbMfqMg"
    "WXoiNR5H2JoeGYNR0IwPgYBzqFc8iitH2EIBE8dgbFAhEbzk+I2Bm44zxpvxh9SDo9ucpyq+vrvZe6VQ"
    "6OTR3vUc/OF30lcZcUbEetVrgeNg6nJAuy8gt5kyyYpi4FuqVIFvqddCJKLDBvn6b67nhrvv5IOH/wPH"
    "7HcAS+fMA5RUUkghEoXEhSViFApN/+ud1Wz70NHlAKutLLbRmdk78s0XXsBkYWXeN+JGMyePiuLjwIIl"
    "reHTGhJZTDGGQjeYGCOZo7ZpMOsEJCB1JJqSVRCWxEZARf2ljdbkH3xem2CzKoyCFApUvEfR5iiLaStT"
    "7SLylshihwj8B7AfAmKMeBeq223WPI7e64Ucvc9+HLxoO+Z2dVEuFYlMkMjrrLuZ1danSda2XL9vkbqb"
    "iaBJUhdtsw80dbb6JsqQtqtVx28831iDNYqQKIIoCkuFsWHU6j2Z1+XHttdp68CP0iByT2Pz/FMCxxPL"
    "oLO893sX8D83Xkckxnn11od0cR9lC5aAfPDnAC8nJHXsmkI9lqCP7kmwVBkgBEZYA0nAKQKWl2axcN5c"
    "Zs3pYU7XLLpthAUMkoWPmZa2uzY9odFdJuumZpnBI9k1qfsalowx72dLkEqoxyEYMSQuxVrBRgYxEmQY"
    "CVyj0aW5UQraw9JF8xyJLb/W2xzaN5r5Kh5jI25/dCU3PXo/WFHrNA+3PQK4hWmaVvIeeAPB1ZhxKtni"
    "S0TUIBqJaGQjNcZqYyr/v2uCy493SSwpxiQGowLfzsZvWvJc/tDbgQsBRMRDfTPCdOobU2rLGXHdoJqz"
    "zTHsOC2YtWM6LbRmENq486jFu13Cy2QAMaaFw3kN63i9zvxD/XPejU2rsgn1e58HnuqPFc0TRLTUNFkQ"
    "go/5D0BXbtkDIG6TD5tY1ERvkabyLeOZc7oxKhENcXSBUsZS4Z5jmBCP8SZgJggk1dZKBEwU2umdb4xz"
    "qGYwGHmIw6aKFhgB7ke5CLio8YLp9VQEfJAw+F5V7dLdD+ZN//hOundazIjVLLCyYagAJuX3qKs1TWq+"
    "Aj5X75vLZAuDAbpKxSAPaL6E/r1QwEQwFltoSIEDmzaxds0qnnrobh679z4evPseakNhL4WxNoQTqFdC"
    "hog7wH8KGEQp0iqc9wKP04jSnvbgh4eFNSJmoaqne848+cQPr2bvww+jf2SIxErdntK8ibdZvRr97vDb"
    "aGEnJIbWTMZr0rozjqEURJlXKGC0IfA91yAzhIUxBmMV0hrJ0BArHv4bf7zhBv7w81/w+P13AxGFuECa"
    "jGimA15fgjOH4ZlxqpyRHAGC4IyxxjvHfi86kg/98HJ6E4eNgjwsRkC17gSYrNezvgw09Z+HhoGuziEE"
    "q0FPj62hpyRZFG947yhzQPtLRuGzOQS3PUnl67yIRTyUnMFYi8QRthgzvKGX317+Cy7992/yzIr7MSZG"
    "NVVRFRWeUOVk4K8Em4urVztDi6OAGTDWdKl3LF6+C//6q98SzZ7NSGUEsSazqUtmC88IrqnjtS70NOnR"
    "5LJQIKLm+5LVYRA8YTNmbAyiQmQNcwvFEIXqQ5SOWI+IguQ4NKGuoD7k1Gm8e7y+abcbNMPWWmZC+/JV"
    "TL1i1WCzkDP1KTYSujs6WLnyCS766le54aLvY0nRCKfeW4WnsbyShPvYclvNKBAwfxSRI8Sg3jnz4jef"
    "xVs/+CFkdhdVgaK3gZ1L89TNp7YEAqhLdnlQhwb9WUDra4iA5nq2glestZSKHQy7hBSlYCLmFQpY7ygX"
    "LF5TkloFJARKjupeBfHljAiVeib6sdhUUwqWsQlg5olArEEkJISOCzGFQoxGEcO1EUZqNYxISKLpPHGx"
    "SHexxFXf/i5f+9dPUh3qQyKTauoj4GGUowjLwYwSgYA5BfgJYpyAUU1l4ZJl9Gy/kJp6ItfMivNOavB2"
    "ybMxq6GxhcqD5DMz/2+y2R9mtKqnYEscf9q57H/S8fS7Cl0aMatYYFZJePiv/8d/nf8l+p/tDYGb4yVe"
    "qCeJzglwcxyA0Wpa/fZWIAARjLGIEWbPmsXy3Z7Hrgcdwl6HHszcpUuouJR0qELBRGg2yeZ0dvPry3/G"
    "59/3jySDm0BJVTUCvRZ4DY0wsJlaAjAgFyG8FcVbwTvVmd3Qvxkozd6F83/1M+btvIhoyDGro5tu63n3"
    "6Sdz1//+fluhsU1hwU678tLXvoaTzjiNpTvvxOBwBTRCiBn0NRbPnsX1P/kx/3bOP0J1GFVS1EcKHwa+"
    "wsxzAToFLsqDm60RjU2ssYnVmGirWrx6ujr09nuu0HVDN+oza/+kg5se0aHBdXrE4Qdv1fdu80tEoyjS"
    "KCrUf1u4ZKl+4Mtf1t/2btRrejfp1at69Ver+/WaVRv01qrq6Z87X8GqNbGzIh6hj3AMz7gGt6lCs3EO"
    "C68EzlB4jWBjRRCDbL/9QrrKBq8pSub8yDnQKDTaWGy7Hi8N4a2jXOLsU0/knPe+hmp1I4ZO4uJ8KO7A"
    "zX+8mQ9+/BNsWD9AJPkmyearUV3O1n2z3tmGXp79x48lAjSXH4exTudso6ypDA0O09fbx+BQpY5NMY6o"
    "JiFQ9vi3vZ33fPGL+LiIH06xotg4IkL4pzefwa3/+3MiU3QpVYtwCY7TmSEu0C4W583/qYh9Q7AMpvZr"
    "53+Et5/1amp9a7DS1fJubfc9TJR3L3eyYLDW0t3dgU8H8eLxGKLyHIxdAKUeknSQyiaDEIUEkLmQKU3q"
    "by6D1F0obc7lXHzJCMe3+ppaGk+97Gi7s7YUnCQo+NRRrVXZsH4j997/AFf84iqu+uW1VGuOUjGCRKl4"
    "x0te/3o+8R/fwfsoxE0odJY7WHnXPbzrpBMY6V+viKqiVbweDtzFDMTVtjepQBAy/kHE/spaQ5omcvKJ"
    "L+HyS78EI88CHVmnZwOr7e+fSMUSqKeIdyHxgsnUIjwuLhGVdsBJESLFameI4a8Te0YA+YiYxhwPP7YR"
    "oLZ9GW+K13+WVkFxS/IACg2zto1AYsDwl5v/wMc+9il+/8fbKMYhgVYldbz67W/jQ+d/laFqDUyEOJjb"
    "WebrH/s4P/72V7E2ck6dRfkWqu9jBrjAWC4XBbqBO4yR3byq32HhAnPbH37AdgsNWtU2fbypQ5vDl1p7"
    "oen31mdb6/IoMdKxOxqV0UzglTGnXx45NEb7R8UDNOOqYw/qqG1dYzhjpgP5iqSK9z4cnFHuoToywvvf"
    "ex7fvehSirHFeUid4ws//hGHv/okNg2MEKklLhnWPPoIZx/zCiqDG70aDKpP4vUAYANbaApub3U+hQaA"
    "P3pVjIiueXY99z/0N6TcQVDjaLpkjKv9/lifaRv8rLfUgxsiHIWQHYhioO3BxmVs0yXZRdPn7BKbBXDI"
    "BFd7Xe3fp3hleIox2CjCGCEd7seK8B/f/TZnnPo6qonDZrGR3/3i+Qys34CNLGqESpKybI/dOfwVx6Lq"
    "jRWjwDIsR4wzhltEANkoAHAzCmKspKrce+89YGzQ6ZsHYEYhE+a0H6jx95/le3pgbRT2KCp87RvfYJ+9"
    "dqeaphQLMU/cfTe/u/IqOkslfGZFlELEoa86FhDUhR0iOF46E7hsjnoeAFIJZnp9+NGnIQz/2DBjOXNB"
    "02FEE8aKjBkbgoCoNNK45JeqQ9UFWcW7lns4GpfXrJr8mdyMmz3vdYsvxQUcJcXESrW6iTlzt+NT//yJ"
    "TDwJy9Pvf/lLfK0SuIIYhlPHbgfsT+eseXitG9cPgHruhmnDWASQj+RTQG/ujl2zegRGNDiHoCGN16Xy"
    "xkBsEYhiXQK1oeCHaKOBltw7We6/kF9vBGOrGCOIiRETISbC2BhjYySKkCgOly2GZBK2FD7b7HNURKLs"
    "mSjKrvz5/Nm2K5rsFWFsVJcFFCWKhbS2nle+6lj23XsPKkmKUeHxe+9j3aqnKRWDA8kNG+Ys2IHFz9sF"
    "wFgRLLKcEMIHU9dP6rA5i98mYCMhOZE+u6FPqsMVirFBvY7B/WeQXStQG4K4B0xh/HLi6y4mW+yBWpWR"
    "kRqNLWA09h201C9Z1G6zgBq0kJyg28XYHK/mz803J6MmKp5yRxkMpEkCAolL6OyZx9HHvJR77nuIYhTR"
    "t+4ZHnnwARbtuBOiHkmVnq7ZLFq2lEdvuyWX+uYVYLvaFgqCmyOAqsBgXu/wyDBpmlCM7WjjzoxC8Cmo"
    "DqN+AGPntiw8DZN92LGrYjCFHq6/+hr+7UsXMDgw0EjStBmNVFq8mOF/YyfO6PbVS42nRU4w+ILgXMoO"
    "S7bn/PM/z/P23Is0GQ5sn5i99tgra1XQVJ56+sksrX4IAbPWMG9+ligsWL/KPmzRG6ulk4bNEYCnaX3J"
    "3fPbBhSlhksHkXgWEGczrDWNu3qPKZXp39DLued9lIcee2JbIThtuOueh5gz9wIuvuQShErgOiiLFy0C"
    "qEdADQwMhPyL2iD/7u5uaKXF0pbiszkCsBqCEAAwxjYddNxsLMlpZEZM0/V4AUEwtSGIhyCaE/b8SRYs"
    "ApneLsGVGkWMl+Z9ii8PcXoKEYJL3YxtXxdriSKLTx1rVq8FX8GK1md8ZG1LD3oXBFGy4+JVW6e5n6EJ"
    "uTkCKBIMQgCUO8oUigXQZMvfOiFkJ4qow9UGiGwHIqOJXYzg0hods3q44IIvcP5XvkFvXx8tC3NTr2nb"
    "/7ByBtZfLBR4ctUq1q/bgBFBvWf3hYvo7CjjfGZGzquVhom5/bwL325IFKg55eHVq3CpxztHFDWO+8m2"
    "srL2mTUhTbQEwX7WrFktGVjFwMDgYPb6ujOmOq3ubYLNEcAsYE5+qOecWbOISiWoVMffrzdT0MTkNB3A"
    "VTqwxQKamXGDoS8InVYs1AY47sTjOe5VxzI8NAximtb4Boy5N08NzqV09sznM5/6JJ/7wleDEUZTPn3m"
    "Ozluv8OoDg5hbL4+txFAA9VRBKB4Ctbx1MZ+jvn4h1g7HJxBOZtXzQ2ZEfffe3+j8WJZvHgJIQZGQi6F"
    "1LN+XcjVmYnbIwQhPbxqmjAWAeS65Q7A7LyJSxbPB2tw3mEtDSPQVpQLghEwwVc3YW0HEmXpcuvbxIR8"
    "l7Gv9mOMpaOz2NAT2xGUtsoVwOCcwUaWjpJpudXtDZ1Rkc6ollkR/RgVtb2m5ZaDuMa82JKZ0BrYaAiK"
    "sYUCmzau5prrw+mvaZrQNXchu+2xF7XUhVS8Vtk00Mfap1Zmr1II0n+eJmZGCSCH5wFWfEjtuMfOs6DQ"
    "oN5tAaKC9QYj/ZAImGVAGUxC2HsXg4bt52JNMNy4hkyS2RWBrIfGRD1kGTeaUqtV6r8KkHiH+gSvSdiD"
    "40N9mm8MbcE1+9D0XwExhpoP2oXFkRJM4GogVaUUd3HNtZfywCOPhlyFLmG3/V/Adst2pFpL8cYTlWps"
    "XLWCVX97DMB7762qriCEiI/bssnAWASQV3YgCM6rt2D32H0XSPKUr3nSJBhzNswwiPhgHbSboGgy6ace"
    "pxyuXDto0vtDQ/I9tOPZKSRbVS2apXmtD64Ew1fIGpCHvIUjXNtbPV4vCDFIRBBvG2xCnRLHJTZseJov"
    "n38BIYTOoup5+evfQFzuZKR/CMTTEZd48NY7GO7bgBGDD+vGHVmjtsglPJ4lMAYOFiN49bJwbjd77Lkn"
    "1JJRR6hsTfCieOPxYhBNobIW7zY2WHGeI2BGEjQ2QDPRLNiKsqQSbaZuo60XeZ5zNY3PoyZJ+J+qR6IS"
    "SMx5532Uu+55iIKNSNIKO+3/Qo487lUMVatYsVgx2FS55brfhhpMPXP1H2aire0cIKemPYB9jAgOL7vv"
    "sTs7LFmUJUOW1mVgKy8JTvIDmDwwTLWygbgYYe2s8Pp6XMJEMknrjYaEEHwEqq5lQ0rgAFuH2EulMtWq"
    "49xz380ll/yCOLLZ8XOG0899L+W5cxjYNExRInrKnTzx0H3cfuPvAbz3zojIk6r6p6y6LTLBjkUAHjgW"
    "KGfuEXPkkbsTd9kgc8bZwSFGgpNDaPXJtw+AjGOVq5cfH3+BBsfJZmNBRtDqOqRkIJ4VZlzTitTiQKqn"
    "/xxfaBPx4IMbu2g3c+RLfenTphnfVl+LWjDWK8NLVz75FK95zWu47rrfhmNngKpPed055/LS41/NyOAw"
    "RVsA5yhZ4Vc/vJTh/vWYSFRTxWCudrgNzEBASE4AObrZecS8FsA7r8WS4dDD9mdw0yB+2KFxrv9knEAJ"
    "hAD1PX7N0q7kCRXHIYCJhEppsr2qKCIO1RFkcAO2kOKjzrDTeIz66vEGbTM5jFOGFx6XOjqlwFClWn9O"
    "mp9vxXiz+I4PYfgjG3HPPfdxzz33UYhjjHoqqeOlp7yZt/3zx6l5ITYRznk6yx089Nfb+OUllyAiqmHA"
    "Kw53UVNTtggiWsfrlcBZwKGhdrWaGt5/7lcoxQbxFmcUJ3nnZKGaWafnE8BoI4gytx76cdCtZ9ocB3Lv"
    "Y4MOwlQTH4EKzhrGW5EaDGD0ixucIqiUBWt4evW6us3e5u0SxYsfLSyNQrtRoh4XJX7UYTlePcZa4iii"
    "mp2zdOxbTue8r36NxMbYxNcDYLym/OeXPs9I7wastd6FhFBXAHcyA65gaHCATuAbhBSkocOyWaBiePSJ"
    "NeM9//93IJjpqbotOuF4oXEBvHNUnWP2dos48wMf5oR3nM2AC9qtFYtPE+bPm8N3LjifP197DQVjvPcY"
    "MJvA/xszMPNzyDnAtwkp37wxRr33Fs3CqLfR6VV/NyASEpzo2KJDo9zon/xmg2Iy1VGFrtlzOeq0t/CG"
    "s97JTrvswsBwBesNkYlwkrLdrC7+90eXcsnnPosVg1fxqkRgPg/+QWZwY0hESA1zBmKcwRjvUzN38VJm"
    "L15IiseKRbwjP/SxIeNM0tQ6AYunjcVP1d3awt6FTGcfCzvf9pvUn0+NUpCIdStXs27t0/XlbSrgN/Ot"
    "+Y1eHXvv90I+9eWvsKma0j8wgjUGYxTVGtt1dXLd5T/j8+e9B18dxopJ1RMpej24r9MwgMwIRAjnAGos"
    "4tNUjjntnZx67rlIV5laJIQzAsMRbM32dTPGiDQ7S+or7ASHKYfjUBoDP92NGWEHosdqSJ/W1dmBFUG8"
    "Zhp5VnFdOg1HwzrjqXnHou7ZfOczn+PiC75IZOJwbp8bC5npqoYNqcOIoTI0xEjNYSXGOU+hWKCjGHPZ"
    "9y7kq5/6KLXBQSQ2aZq4iHBu8NsIzp8ZJgDYT4wRn3rZfuddOf3jn4DOLtKkio0sVUtww2rQtSazh7KV"
    "ACaS8hsHS27ZwhZwi71iVRn0wX3dJREipu53D0XzSCKlFimJT/C2SNgWQZPFbuvYOELooeBViIuGrlIH"
    "q596mi+d/yV++18XAh6JjdPURwirUF4HrGKG9wQCRKjpkCwcauHixZQ7Ouir1QCBVLGpZLMyk2czfVfH"
    "jK0faxAnN6z1rt5c8QnHo54LlGS4hqinIkIUGYqFOGy5Eg/q64RsvcerA5e0ZCwNgvhmZnt927vPyvsm"
    "/PLdT2Mj7CJPR6kL2xHxbO8Krr70ci7/5oWseeyRsBMaUU28JRwY/TrgHhqbdrbEOpV50RoQAc+q1+2M"
    "sTz60MPy1MOPsftBB9M/MkyahSSNjp9TvIwx2jp97MZTE6cOoX2mznmykIsowsRCh5h6BsGw9CiJT+nq"
    "LBNHWxxgMykQ73jq/vv51bW/4YbL/5snH3gAgCiKSNM0Nyn9Bngr4WwAaNhothRaUstEoL9V5S2I+MEN"
    "z8o33ncOp/zjO+jacQnDxhN5m82WplCs0ArGnJLTYOWhvnFuTtEc2/DPS9PnEPJpI0PR2rAaa5A/IyDB"
    "s6Cjhw0rV2QIaW7rCuVaXH/Tn4DB2Cvcd8ttvOllL6U62BdqNOGATeedZq/9o8LngO0IR8XNBNsfBlYA"
    "g9l3A/gI9CsgJ6jXboy4Jx+63Z7//tshyrdejWfbnOH1cVwCmMjGv7kKmw+uFrDSkAXy9xkDFowTbNVh"
    "xeLU5yn5xoDcETVVfLLXiVAZHEAIB2fUTAgTD9yzbtM8gJD+PdZRgz+uTX3MX5v0mQR4Argc+DrBsG8i"
    "wi7TDwAX4tUaYzyq6tN2omtVjZoXhPD6Fiu8YaIukhD3Z5sK5gvU5vLpbxE0+Qw0Q7KghorJ8NdGC7M9"
    "Ig1o4gJextdWxoe6+oFIhLWCV7BZeFGdXCWCpjS9ugWuzrooK6Bo5L3fE+WfgVcDJwOPZ4ft+e+D2STw"
    "WbzfI+DZ3t1NAugYHSCYzdolJRMQDBI2RmgQktKxCm8d4XtU3Q5IcHWDamhdNAEKoVTd1D3l8RGcprgx"
    "Gz4epjMDFpNtS2E/wplDr4jIPH7gf6bwGw2ewP1Q7W59vGnNH82XaEq90AdyNMGfENY0IyGAx3myMDc6"
    "lnSzcNn2dM7podhVCnF4zY6jOv01s/GpMsAGhDqUSIQoLoQt5xoOsfAC5UKZR++4n5V/fTykdW06gHpU"
    "+M80IRiCPPMXL2Cfl+1HLU5Am3lgS1lpPDX9F3qE2Fs2PvkM9/75LmGk7kM4FHhn7gvIiIBe4GfZ1Qa6"
    "mW/Nv5gzgLdKPQ88aJbha/GeS9j9mN3Z+YW7M2fH7SkvmEPUWSLvYTWZ+bmp3bmlbyJbwWYFyQxEhVmm"
    "QDkuNiybaki9Y/HsBVz8ue+w8q+PYqQ5Jd/MgSB4PDvssRNnfvEDbChuopj6sa2q+TPTjkkQvAiJhTj1"
    "lJ3l1xf/nMs+eSmSiqioopzeHA+Qr5D5GyfLgnLLlBW4APx7VITYWnVpKg7Y8bDdOOzNR7D7i/ekOL+b"
    "SppQSxwj6Qi+NpR1TGP99zL5lzdcvhNgLFlgj4tI4gLG5DMvQl2N3uGY4eGML2smKuoMTf0McvQqPmV9"
    "MkxFh3HJ2ATg2+Z/swKfRyWHgpnaSya35NwzE6RUhBFVhozlJa8/jtt/+BdW3PeYyULLdmsPCFGmRvpC"
    "g3v8p8CZAg4jppam0rW4hyPfdzIHvvIQit2e/qSP/v6N5FY7Y4JsoOppTvc4lV3nY/vsxwKDUYvRGKMW"
    "qxGKkBoTAjSlcQzM6CaODfkO4snikY9ZasEZspNA3KjlNDeNS9tvOfhme4vmdo/Qb82u+Dxo2ihYEgpq"
    "MK1tNFuSDi7nFg74JnCmh1SsidR5lr9kF076+Bl07rWEwcoAQ0nYTxACfBSsIS6WiIiDsUkazWz2DUyI"
    "xCQJIBy9YijbEsVCmShI24gkSBozp7ubzmLHpOpSFPVKZGzoQvX4NAWRtpjJnKS1joMiFG2BuYUO1CcY"
    "2zEqkFWllaE1z3xXFz6zH32DAPI9CYGDSj1pVpQqXSbm/355IysefhwR8T4cyfrklhBAPvjnAueAcUaw"
    "3nn2esMhnPCJ07A9nsrgMxgTkYoBiegoFCjamMHeTax56EkGnxpmqH+YSqUSuEJG+SHuM3zZHC2YdgIY"
    "la+/SXX1ISVNIYqJjAnbyk0NXIWu8lyeuP3BUIX6xgC0Vee9hk2bXWVGRoYYGOqnZAv09PRA4vC1KiFu"
    "M5/XjRxGikcwrFuxiuu+92MsVfBlkEbYSE4ugQO0KtrNS6SpF85kmZb7gRIUwRulrJb1jz7N76+6AV9z"
    "iIgSfGRXTJcA8sE/DOHzqHhjxHjvZP837MdJ/3IavQVPmoxQNkVq3lMq9tAddfH4bQ9x/3W38vjND9C/"
    "cj1JpcLYuuBzBYLPkmM3ayJ4g3MO29XFiKtx0dW/4OKbfseqjetY0NHDy/c9kPe8/i0s65qDG+5DIhck"
    "G7EhY2i+phvh2Uef5rJPXfxcNE6BVFVj4FHg69MhgLxbOoCvo6YsEd6nTpa/ZC9e+dG3MCRVpAYlYvDQ"
    "3TGHoRW9XH3hT7jtVzehm7IzhGxEJBFqR8/xZk1wc3LwVGykdWbcxDXycwoM4NST5Jwnx0IMPpNKbWcP"
    "jzy9gg//8Htcddcd9SKrewe4e9Uqfn3PX/n3t76HlxxwIFrpo0qVUp4ssG6B8lgT3Oz5drLGLoMmvLK/"
    "jZ5pXRCk7df8qTrnUg3e7HqVXr2qEAZ/NXA68Mx0CcADbwNzcLCcetu1vIdXf/J0KnPK+GqFyBhShcVd"
    "87n/93fyi8/8DwOP9yJAHEckSUo6CWvItofG9jBU8E7QOIauEpffeB0fuvQHrNy4gVIU4RVqLs0OkDLc"
    "t+opTvy3j/HRk0/lQ687hZIp4mu1kBUkGykjEk4jHSP59Yy3JOT9zb8KIfnXNcBnCedDTVkIzBe3ucB5"
    "YQEKGv+x7ziRnj0WsX5oAx1iqOIpdnZx089v5NpPX4zvc0TlImmSkCQpPd1FXnTovhyw/3KWLllCV0dn"
    "SJgMdQeMSNMunHGkwnq8wSiPZb1EvflKWB/VWArFTlQs6rvwDjo7uvjxj37Kz668MuTzTx3GG0ypk2cH"
    "NvKFi77Lf15zDTWgs9TBcGUYBfbff38eeOABqtUqhSii36V8/IqLuX3Fg/zrGe9gr512JRqsENmIghES"
    "73nBPs/nY/90HjgXwsha0tqFNpisPY1AGG25cgeVl7b2O6XQ0cUtt9zOBV/7JtlJMALcRzhj+OHmsZwq"
    "AeTovBFYbqx477zZ5cW7svcJh9E/NEgsMRWf0tnZydrf/pVrP/EDdMgTlyKSkSodVnjH21/PmWefyPP3"
    "XIItxpt3OLWw5Mmit7nbArYb4qVZvcXsRolH/nYPl111FWKEFEhQbnv4Lv7pO1/ld4//DSJD0UYMVYaZ"
    "1d3Jpz/zac455xxuuO56zjvvA/xtxRPE1qLAz/96G3esXMEFZ57LLkt3ZMSnGDUojh2WbM8pbz6T4Jhr"
    "94bA9LbeNStlndzx17tDZpHI4lInhEPBHibYuuvJnKZKAPm2sVMBVa9KDIe8+Shct6HQn4T8N+UyfY9t"
    "4Mp/+yl+yBNZS1JJWb5kId/9+sc49hWHgQxSq2wgHYrqrtuxJrnM8FY0FVBbwZQ7UWNQLD6FqHM2c2Z1"
    "Bd0+S8nyqUu+y4bhTawdGCQuhN071WqN/V+wF//+ra9x+JFHk1b6edWJJ7D//s/nfe97P5dfdV0gp0KB"
    "lRvW87av/SvLFi5m/fAgRRshTpgzqxvnNuFqvVl3tm5kzeMXA8cK7R/le8nlhxZFQTESM1LZyDW/uib8"
    "Eg5s6AV+RZO9KH9kKr2bZzV4gYEXihFRVbv9fjuwy4v2olbpx0Yp1kBXWuQP/3E1mx7pxxZi0tSx99Lt"
    "+PVPv8Wxxx/C8PBaasMDCJbIhpzBkbFYuw0uYxAqiAxjI8HaiCiyGFfjmGOOZX5PDz51SGR5YO1q1g4N"
    "EpdjksThUs/Zb38LN9zwSw4/8jCS4TWI1EhG1rB42QIuu+KHfO3Ln6Ors4NKrUYpjtkkNe595glMbEky"
    "w9EbXvcarI0wmCAIZ+2vX9ZiTUxkYmJjiU3b/ayvImvr92NjsSJEpQ4ef3wljzzyCATJD+DPhFiAuqV9"
    "OgSQw9FAwWSxULsdtTelWQXiJGHEJKSxYc0dj/HoL2/HmBifeDqLhgu/+c/sfsCuVPt6KRY6iEwHRjsQ"
    "QsyemLGvmYbAa2qkySCoZhZJg6YVlu+5J5/72peJCpZaNcuE4iEZSVgwbx4XXvhNvnfht5k7t5N0ZGM4"
    "PVYckVVcZQDnqpz74Y9z9S+vYL99n08lSdA0TF1XdTjneP8/nsVxrz4OV9mUmaNHjUkrvjp5o1iwXBe4"
    "+647GammIdNJkJH+mBUZ1aFTWQJyLA/NtoWp9FiWvngvBrVKzQaXQMEWuPvKm/AjjmJsqCaOc952Coe+"
    "/IW4vmcoFAoh4rZu6JjxOMfxITuYUESQdBjxAjYEiImJcNUh3nnWW1i+bC7f+sZ3efjBBygWShx66MGc"
    "e+57ef6++1EbWY9BiUwMTbKbMTHqIR1ex0uOPpobfnM1//7Nb3Pd9b9l4/oNLF6yhLPOOpXT33o6mllF"
    "W41czfsrm8ZJmvIbhDeFn7VNdmyq54H77w+tNcYS8iXcOV6XTJYA8iWpA2GPYIBS6d5uLouWLSbxDoeh"
    "YGOS9cM8cscDCJCmKYtmz+KdZ78J9dVwho5XGsGSzS6ObQG51m1AU9QNIrYYgkEyM2pluI+Xv+wfePkx"
    "R7Nhw3qsscyeux0g1Eb6iGxbmrz6YJl66uJkeAPz5s/l05/7PB//yHr6Nw0wb95cpNyNrwxkBqLshdJu"
    "MZxCa9qNniKgVR5bsbL55wEC+887oAWmKgQuAhaLGFSdLFq0mHJHmcF0CBSKccwzjzzBpqc2EIklUccR"
    "R+7Dzrtvjw6vD46ItnRXZlsSgEDuuxJSUt9LrLMJadwVMUpkDLXhPqy1zJs7D3UpyUg/Ymx22jlh8JpP"
    "wCSvN3C1yBo0GcH7IeKSZX55Duod6cgGbJ3t5zDBwLdFH49qUq4FajiEyycV1jy7PrunEFLJrM9ra39+"
    "smSXN3M+0JV/nbN4PnEUh6NPJexr2/DEanxVERPs2y86bE+IE7xLJt4ltE3AgwqCw7thIM1ak3v1wNpg"
    "vnVJDedcOPRRzCTdlGFND9xA8ZrgXBUlDbmVULYssnszIEKtWmVkZLjRIOgnJJQaE6ayBAB0oUT5t+Jc"
    "i5rGGmVE6O/bBDQ21Wy/eCGkPhztJoxByeMtA1srE4kJUodaosSh1V6kECMmQbEtARh5+nsgS1CR4SW+"
    "yXSRJ6hoXbcbxmQb6KblNLNGH0za6zlO6FlzXgwRqKYJtewomgz1Kpvxtky1l8O0zvsE37QcavbXtPzv"
    "7uoO3i419da2zqPnkisortoPfjjzm+d7BSZvfpn8q4SZTmUz5mtG/zSWebQOU8UobapJvXeZ+daSu1Ti"
    "jPXnKtxAf3/r+3N37zRePpNQf79WIOkHHwRUyQ+3VI+pf257uHkg1VA/M7E5c3r++zYEFSiXSnSWyuF7"
    "wLtMU8bXdpgshnkXDBAspABUBqshY1VmYlVVeubOAkAyH/fjjz9JOFfItZFni0HqOQEBrNbQ2gC4JPyi"
    "pnW2TjSILenyn0sQ1DmKpRId3T1A3T0wh5D/YUyYKgGsVdiUfx1eOUha9aixGAw19czdZRGmM6pn/rjp"
    "L4+RVio0hN+wN68xQ8a7tgGoID4GHcS7Z8JOZi2Bhp06rTBaN2+ty7Re2xhEQJ2CxCzabh5QD7OaS9hh"
    "FH5rg6li+iywKsvMpc+sWEXl2T4K1qIiJLUK83acz7zlC3BuBDGWP/7lTu6673FMZze+JcjyuecAAYKJ"
    "w6VD4AZAaoT0c7qZgZQ2dj/jEsO0IFj9yizfaSkEjVQFKQM7ZUWmTQD5yFWBB9Qrgmj/mo0MPPY0HRRD"
    "FG2S0DG3zC4v3gdwxJEwOFzlm9/5KcSdeGMbiaWaa36u5EBR1CpeLKjD1TaADoIk9cEVNW0SeNMSUZ/t"
    "zVLNc8DJ2mDv5+8DgPd11eUF45WdCoZ52T8BiBHBw8N/upeCNaikYJREEg486SUUF3SiiSOOI3502W/5"
    "4SWXE82aj3O+Kdz6uZs5Dc96iNOzKLghfNoHEvL466T0/olg27UxqKwJez1/T8oli7o6hz0k+z+K5U6F"
    "APJ5eiMwnLkZ9ZHfP8rQ+j5i60mNMlgdZu7zFnPgyUeRqFJQcE54/we/w43X3ka03Y6oLZJ6siPm8xSt"
    "bZdmlzebv9qfm+Tzkl3GG4wD4wwWQZN1+GRDthRoa97pendNYqZPijvM8GUE3AjLly9j5513ARBjBBE5"
    "kCAHjLJCTYUA8iiFB4E/qaqKGL/msbXc97u76Ym7w8w2ESPJEMeecRyL99mBoTTFWsPGviFOPvPDfO8b"
    "P0MLi4jmLERi8JLgtYZzVVxaxSXZlU7icpMsN8nL12qIq+Jqffh0A8hgfSnw3uOc+7u+vPdUKxU6uudx"
    "6KEHARgJ5wwuBo4Yi1qnyp/yVLJvAn4kxnj13izYbxlvvegDyJwazkGaQnfUxcaHV/M/7/4Gw08OEMWW"
    "NAlxcMcfdTBvf/vJHPGi5zNvcU8gTJFgKm6WB+pZRsdAsxH9ODamdVPcJJuoBAvQwBDqFBdHSKkbY5ei"
    "PsIUY5ACjeTTk43Yaea6W1PYEbLz74Burr/257zq+NeBiFOwqv5ilDOywvUE01MlgLx8Gfgzwr7GiPde"
    "zYs/eQove+cxbBhYjynEVNOEznInvbet5qcf+E8GVvZTtpZUIEkDIez1vCXstffzWLz9fGZ1daHkbmIy"
    "mggEMCr2H+p5iMbKQZQ/P96zo8qLkDrHsiWLeMvxR9PRFeO0gisUMLI9Uc8CVjy+git+dgUjwyOZkStP"
    "GS+NXmlWcuqQE8DWlwW8BMtsVCiy+pmN/Nf3f0C1mqoRI4puFNWzHPyakG3EMHHurTEhp543IvxYRJz1"
    "mGh+l5zxnX9i4aFzWF/to2gizEhCuaubwfs3ctW//Ygnbv4bAhTKBXzi6oTw9wQfeucb+fL5H6KWPkvN"
    "QEHKDG+KOPa4s7jjnkeea/SmBpmcLR6yvCh40dvU8Ekc/0vLnqSpQS7dXAUcVxDjaurt3H2W8o7vfxBd"
    "VKS30k+nEag5euwszFCRP17xB27/6e/of2xVvSKbednG3eI1EYZjctWmqTjJFlprqVVrLNtnCd+44otU"
    "yhV8Cl2FLlbcuZLzjv8osYlCbup69ZlTpN4dWXSPtC1l21rjEYN6j/NpA0cjqgLqvICvoZwKXLYlBOCB"
    "3QRutjAfY3zqvVly+K6c+dXzqC02DFZ66fERlUTxxRLljtkkq4Z48He38vSf7+WJ+x5leO0ALvGBp4y3"
    "RG5u6ZwWgYyuQxSkM+bYD57Ei958JH1uBNUiahK6qgV+8c8Xcf+v72nwv1yPbGb/m8NnW9o66vIRDZEv"
    "Z7YiKaoRIU7giC0hSws4G9KY/RTQ2FhT8U6WHLYrp3zhbXTv1MPQ0EA4a8iEI9I6CmViifGq9K7byNDT"
    "vdSGq3jns5kEec9qlq62nruleXHPKXsU52iRIpv2DYz9fFZJOIRvVhez91hGXEjxaqhQwNBLtzdoBZ66"
    "9wl8RbBYCnERKw0jkaiEAIwWM3GrE2xbQX6mgweSSCh7y/Djz3D1D65k/YqNiIhTVQt8f0v5kiXsdP4Q"
    "cD4YLybC+ZqZ+7ztOPETZ7H8Jcup+GFG0irOeuLU4xVSo0RRgYJERMbWA6Obp1aIMWhyytQzkzUPoszA"
    "/XAsTOoSKkkVI4Hmws59D14xJqJYKtbdxQUTUYpLFOIC1kSIF4wP+39Nk8l7LCF1MsbPzS0ak3k+l/Aq"
    "FuIU5kQFHrjxr3zlredTHapm80pXbykB5Hh64FMgnwVRY0S9d4bOiEPfdAxHnvEKSjt3M+QGcJUUnMci"
    "9VQg+RCEHa5hDc37zdTVrnzVydZYMjWgxTizhfdFMVm0Zb61um7M0ZC+PWQZ1cwVYIgiGwihUMSqIXLS"
    "0GSYgAA2M8KTIoAJnod855DiXMq8eDbfeOMXuPeWezDG4L13W0oAORpCsLG9HzhfIRZjnfHYFMfsHeez"
    "/xsOZ7dXHcj8ZfMhslTx1JIa4n04d4egsispjXBXyVTBzBwnuZDl6/fr17TuQ12ebbqv4lE28zy+Ecuo"
    "gXdZG1GKinRrMaR8z/NpjSPcTqR/TZSFbMLnMzIJDtiQIVUGPF884dM88/hqxAjqdWimRNPc3uksvMoZ"
    "vglmF6OGSNTVvDOAdMwts/yw3djp8D1ZuNdyupdtRxTHRJEJGzYM+CxGL5840s4B6mzcNL2aNhbfvLWq"
    "fQmZ+Hkd6/mWTTVNo5OHbWsINuv2HRRtgSgOMRhjHbI1WXFgy+TJEJfoRImdosPDXPGtS7nxO7/DGOPV"
    "qyh660zrJkFGLrMDFfksKmcKSGCt4pz3OaEgZUPnvFl0zO+ho6szGGyCZYfGUR+ba21eZqwmTHaVHA/a"
    "sh6OU6IJizpKkp2yHUU2fJ4Rh9I0QLJlygnWCBvWr2PVA08BaLZh1BJOh5lxaD4l5SjgWvJpI6LGGDVi"
    "shChlin1/66tfIkVRwgQVcLRM4WtRZ7t2vGLgFOAlwO7AtZkQlbDnhIead8mMVHIyNjzWBmfgU4GJvP8"
    "WBxi9DOTZfdbDXIRRjVEDAW4AngHsHFr86eWzNTAHOBAgmfqQGAXhIUoXUgWuJiXbCeh8eA54rCThuea"
    "AnI5VhlCuRf4HvA/ZFT+/wEY/MPvy6oFcAAAAABJRU5ErkJggolQTkcNChoKAAAADUlIRFIAAAEAAAAB"
    "AAgGAAAAXHKoZgAAAQhpQ0NQSUNDIFByb2ZpbGUAAHicY2BgPMEABCwGDAy5eSVFQe5OChGRUQrsDxgY"
    "gRAMEpOLCxhwA6Cqb9cgai/r4lGHC3CmpBYnA+kPQKxSBLQcaKQIkC2SDmFrgNhJELYNiF1eUlACZAeA"
    "2EUhQc5AdgqQrZGOxE5CYicXFIHU9wDZNrk5pckIdzPwpOaFBgNpDiCWYShmCGJwZ3AC+R+iJH8RA4PF"
    "VwYG5gkIsaSZDAzbWxkYJG4hxFQWMDDwtzAwbDuPEEOESUFiUSJYiAWImdLSGBg+LWdg4I1kYBC+wMDA"
    "FQ0LCBxuUwC7zZ0hHwjTGXIYUoEingx5DMkMekCWEYMBgyGDGQCm1j8/R2zgUAAAqUVJREFUeJzsnXec"
    "JEd5979V1T1hd28vKtyd7hRQzjkThIRMEMIkkQ0iGSecyAYb8GuTbIwxmGiTcUDI5CAECKGEJE45nvLp"
    "pNPp4t7uhO6uqvePqu7p6ZnZ2bx7Qr/79O3MdKqurnrqyY9gd4cofLfZpwFghYQDgcOAg4A1AlYDy4Gl"
    "wICFEqDmprEzD1F8/knC2v7HPHn/ycO4PzGwDbgHwTXAj4DfAGOtBhTPlO1XmGVMs/sWAETbpxVYDgVO"
    "A04EjpCwFzAElNsPb/X93HT17EDI/seMBzvNh/9dv/+EIbDA48AvgM8Bvwb0kwRguhAsAU4AzgXOwnIg"
    "bnUH2ruzOFayLu7WC7tLz0y3ndNdAX/X7z/Z67n9jwH/BnwK2Nl+wJMEYKLYF3geghfiVvslQMcLeJIA"
    "9MHuPgHn+/6TvV5rfwz8B/A3ODHB40kC0A8HAS8HLgAOQxTk9y4vQAJKCaRUNOMECQQCjABjdi8RoFQK"
    "2r7baQqxYppC9O/6/fOw1mKsaWtT+rGHqKFB/ivwXqDevutJAlDESuDVwIXAoaRt760EBNzkz3elKBwm"
    "6eQMdidMd5hM99l/1++fh8GNqw6SJFrKyk5CIMeAPwG+0nm12cduQABkFXg+8FbgVDDtK36/J7B+kkuQ"
    "UhElGoHnCoBwApdYyNjdOejd/f55WNoJgAai/I0EvRp8I/BC4AHskyJADvJQ4K9wLP8i91t7xxQpeHFy"
    "AwwDwwPDVAeqLF+yjOpAleHhYYaqAywqVZB9RpGYJVNREXact2GE218ul7M2WQFmmiywnCYL/Lt+/zyM"
    "tVhjMxFAS/jtrTfx4OObeGjHTjQ937EB3g58/EkC4BCCfAHwXpDHQDrRDQLrbCcCKpWAIE6IE6dRCfxx"
    "i4E9K0Mctc/+HLt6Pw5auYa1a1ejAsmSJUsol0Oq1Qo2MajCAOg22fsRiJmC6fI2dGIJyiXUQAVZDrDC"
    "6QCUcYMpEeMPlH7ESxTsaOMRoW6w07SjFe8/Wcz3/YvQRmdEwFpLvdbg+vV38sn//SrX3H8Po4CReFah"
    "TUD9FfD7wI4ZbVAfLEQCsBT4c5BvdZ8lkpR70qQ8VNpti3AePyWgIiQnHXE0xx5yOKcceSyrB4fZS1QY"
    "RCIC4amIBm2wxmCMBtoVQaIwoOa6g2yBp7GxRVZKMFiBcgjSS0C+mVbYNsJRJFZ9219cASdLAMw0lXBy"
    "mkrAeb5/N7TaJBGlKvU44qr77uRdn/wYN2/fTCSgy0r/OPBc4PoZb9A4CPofMqfYF/gH4GX4tqWTX2JI"
    "yYAFpIBBCYs1HLp0T551/Kk8/diTOGDPVQyUK1hlieoNStaCMI7sWoM1CcZTaXADoE2TXGAp54r9z27f"
    "5YbWWkSmTk7/+p3TFqLteF9nHdOdwAv//harNSfsdyAvPOMZ3P2D/yXJ3TK33AzjlNu/swTgKODjwDnt"
    "P7e6SGBYpAJGdcIyC4fvtYoXP+McTj7wUA7bYx/KTUN9xwhVGUBYoVqyxI0mGuM0MoXr7S6wJkcAnsRu"
    "BAPSEkiB1HD2qWfyzz/4XyQCg0Ug8laqMrD3XLdwoRCAE3BeUae2fjLZ/6FShKEiakRYnXDC4BLOP+VM"
    "XvT0s1g5vITQaGSzgQWqS4bQaGzDuVtLJUC0WGNbEHKLdmBRXFLnWAbodv9s6oucPSn9I9ub2KHTmiTd"
    "mEGd2JMAbBxTqlRo1hsMDAwwFFapmYSmjjEdAh+VuW7fQiAAJwKf8X8zZBNTOBYqFM6h/znHnMirz3kO"
    "J67al6HYEMQxeI24FWBlgvWKHacpN3OmxJsNCCkw1mCsQUox6Qn9JOYX9XqdslJQLbHtsRqRSTDCrf9g"
    "i/xoY67bN98E4CiJ/DfgxFZHuE82J+tKYFVY4Y9f9lLOP+WpLCeg1IgIBitQqzkZ39tZpb+EyFZ8f70Z"
    "1vbOGUSOSRRdCIAQ7av2ZAnE7h6ON9/37xAp28dZRQXExrAxGuWSG65hxMREim4+AU1g0zQbM2nMJwHY"
    "F+THaWP7XY+kXRjgtPtnHPAU3vLil3PSfgeyl6xgd40SBgHsGIHQH93GB6cq8vaXYYR736kUYES38SPn"
    "nWMwot3XSVsIJJRkS5Whcs+gc485WTNmfvx3M0P2w3zPv/m+/3i+hAZJeY/F1Gqj3P3oRn7wq0uJU08h"
    "gSPe2NQ7cBdw53RbM1nMFwFYKpH/APIcyEv7jjFSuD4aBM4/9Cje8uKXc+zBB1PbvBUtY0oAURNUQGoc"
    "EIARlgiDUhIVBEgp0VGEMYbS4CDNXSMQhs4tMFQgBYmnBnnVwGQ0/9P1Re8GI2S2ODQaDcJqmdJAGa1E"
    "h92/aAZs/d76PNHnmawPgD9rKifNIKZ3f2tmQincPZ1EIg2NaBe/WHcl//lf32TDps3uSO3dAIRFt5p/"
    "G3DvXAcDzQcBCIE/B15WZPtTD74Yl7Xjlc96Nq8761z2qS5i9JFHKQmVrXyOguaor3VfpZLEwtC0Am0t"
    "DFRoRE1qIzt4fOsWHt+xnZ21UbaO7GBkbJSwND29y+wQgNbrj3RMGISElTIyUJjcgM1P/Kms3k9iJsyA"
    "vTmARMF1d9zGzXfegVGKGu2xKLmhY4DvA9un2ZhJYz4IwAuAtxpwy7f3ipLWEOA6aB/gRSeezhvOeS7L"
    "ghLlMKAkB5GeXGbeX0q1mcOllCgpaBjNNh2xzcT8/KpruefRR7j9rvXsGNnJrkaN2BpiDDHt68dU5tBs"
    "rH/FRCUtR6jZu+fvKmazL7XfDJDEPVZ0N+huwXLxLDalJ+aaAByKC31c2vrJKfCEdazBIPCac87ljWef"
    "x75DS0niOs2xUQIRIAPn3a+FalFS4VyEjJAkEh4b3cHN99/L5Teu48b77+embRuzjAtlVUYHgsR46puK"
    "D2Lq7r6zaZ4Xwkkr6epuzBxmsHkSM4JQOTk/U950rjJjwCeA++ewWRnmkgBUgb8GjnFfTdYZQShJmo4D"
    "eP2Zz+DVpz2D/YeG0SMjyEBSlQE2dQmWAYmJSSyEMsBGmiQM2GIa/Oz6a/jZdddwz6ZHeGB0Jw3SOa4w"
    "SBraz3wh3aYALNaCzl7MZGfYDFMA2/7ZGFGQzdvvt5vaNp7wSEdRbGwrQg2KbJzGpQf7nzltXA5zSQDO"
    "x7n4drRAGkMFOG3NPrzy7HPZf2ApjIwRBAqMdtp7QGsolcuMxU1iY9GlEmMYbn/wHr5+yQ+55q5beIyE"
    "Gi3WC1Ln4UJOoJSnTvUIee3sZDDrHnqiTYknnhQAFjxamaZai1w23mw2CiPgC8a5vheSgcwd5ooArEbw"
    "51gX0puPgaoMlGnsaHJMqcxbznsxh+y5Cjkyho6bBGEVtEFKiREGAdSbY5SrZYgTHh7bzjd+cwXf/uXP"
    "eGjXTgSQkHJbIpssIrMzaBcTkKfGueVVgA/VmjjsLEzIfAtEoX35++Xv/KRksMAgTLsPh1+DFCDhUQWf"
    "NPDpBHbN57ubKwLwKuBkaA3utGsaO5osAS487/c5/cDDsLvqBDKEwQCSyCn8rMUKhRbQ1AlKVbn2zrv5"
    "+i9+yv/dfjP1SujCgaVEihDp4+SlTcCYwsJuMKb1Q2pHznQAIgsamBBmmgHIMyCtQKgWnLHU5TEymE5f"
    "sicxC+i3KBT29+YiHwd+DnzWwBXkIlTmC7NPAAQHAa/DojJ7vXUTb1EJkiacf9JJPPeMZzCkSpRjN2nB"
    "oKVFGEiwCCUQlRKjtTq/ufE6/v07F3HTY5tcfHUcgwRtBcZoDAkAZQK0W/cBWFQVRJGlXJZUBwYolQJU"
    "YJH++Ik5Ac2N1C0sWKtdFKSxCBSWACvK/m+IkQYrI55c/2cSXd6vdyhzyljZ9lsjarJly3YqlQq10ZEO"
    "07RfWq5EmB8huExbbtRQb1n751eLM/sEwPJy4FCJm/ga7+hjodGEIwYHuOCsc1k1tJjose1UQ2eXN8qg"
    "jURJQxiUSMKAmoB1G+7jCz/8Luse24QuS0zOvGKtm+olFCGgSRgIYNGikIMOfgrHH388Bx98MMuWLWOv"
    "vfZiydIhBqqASHIN7vNC7Oy/sIwIWY1Mk0zaAEOJwUXL0ZQwBC4jkEgK7X8SU0fh3ba9a+mkRdvKImmQ"
    "3HDjDbz+wjeya9eIi1HPm2nc+Q8jzF9g+S2QcQfZUfOs0plVAiBhXwEXpAFrOT0IJVzmnt9/6jkctXI/"
    "ZCNm8eKlUK+DgFgEEBhUYkAqdoyOccPjD/MvF3+T3zy8CQnoOCdftZQrCDRlBUODihf+/rM4+5lnctpp"
    "p7F48WIajQZKKUqlEkHJEptdIHzmtr6Te+6oteMALNI6wmltGWxAaelSXO+VQEhsn4xAT2KS6BgDre+m"
    "jQBILJKLL/pf6mO7/AHF2WwAfoDlpt43HD+WYLYx2xzA84DDUpFIAmFFUmsYqhKOWLmK33/aWSyxAVUZ"
    "QuK0psbL+wKgVCIxhnt3bOE/vv8d1j28iXracNPiuFIX4hjYe2nAq192Aa999QWsWbuEyqIy9a3bkJFh"
    "USV0cr6IIUkIRBNsawXtGzQ0BxwAeGLpk5k4jsBgRAh6lJQAOB8I2RE78CSmgXEIQPo91cFgJb+49GfZ"
    "ql4uSeLIeEIBOM++bwELlkWbTQKwxMALJai8Eq7WMG71F5LnnPxU1i5azmATqHtZVihsaqIXblpvtxFf"
    "/NkPueSe9S5eUkKCQAiB1YZqCeLI3eOZJ+zLO//6rZx77tmQjIFtQmMX1UEF6FygkNtEm4pQjh9cMkeT"
    "P4UQ1rGUntWXSIjrLioIQARIWZ7emtHvmSbLYUy2jxYSB2MLyRW6iASJNU7ZHFa44rLLWXfD9WB8oJbn"
    "SHN6pGvBs/49MN9PP5sE4ATgRCMcZxTmdkhg7aIlnHnYsVQSUF7pl+23EBhIpGSnMFx0xWX84IZ1jAGx"
    "xMtaEmu9PiGCsoLX/8Fz+dO3vJ6DD90PZAN03iMgF1Kbhynq2VlAooBp2ZI9F6CTCKVKoALnH5CLbnwS"
    "04QwhXdf9B0xBFIRxwmBjfjNb37Dtm1j3urUYRHSwA+BkTlo+ZQxWwRAAOciWZL2X5y4yapw7r5nHX0S"
    "h+29GhW7AZx3xBMWlJHoElxxz6189gf/hxGC2Fo3+QnASpQxSDQDJXjLH76SP3zzH7B29RJIdtGs7aBc"
    "LtGWOgfo0LoUV6CF5mdj01ckgYDESISWSBnQyoM8zul9Lt+Pdky2OybtRzXJ42cdPR/AEQMpBaWBAXY8"
    "PsKll16KFG6md4RVWx4DLpvl1k4bs0UAVgDPbPvF+9sLYI9KmbNPPh0x1kSFIcK2YtpVqmiRECnJ//zi"
    "EtbHTUIUCoO26XJoEMQMVeBP//hV/Plb/5BlyxbR2LWZSgjlsnLUxrglMqPlxRdcHIGCPg73bamcZwB9"
    "wj+Fz2OAwXhOJkkSStj5T+fyOwijDTIQPProJu69/0E3+XOvLheVeT1w35w3cJKYrSF0JHBgViuJ1uQH"
    "OPqAQ1iz154EBpQGhEFLzwkoyVi9iQhDfrLuOq658zYAmggUIVrHIBJU4HSGL3nxKbzz7RcSBgmmuY1y"
    "CdxkUp43Fq1MQdDJL8912t+sHXmXqBzyyUyEcSa+zKU08daOkj9Oej1Gl8v3WMlEH/Em3Z9aF3p9nzv0"
    "a+8cNYNcnxrDjbfcxObNmzsXkNb3q3CBPpPE3GoFZosAnEquWm9+qC8Gjj/sMBZVBxnQEprOBCctaCSR"
    "1gTVMpsaY1z626vZYmK0AGMFFotCOnu/geOPXc6f/emFDAwYTBy7HO/Gpg4YU+cv50KmzuTNnNyZdzQR"
    "RU5D42okeLu/9aGBNmcBKCQBmaxuoC3mYM50Cws5nEm2CDEABiEFSRLzwP33E8fad1LHQNvJHKf3nipm"
    "gwBUcQrADCn7LYE9qkOcdPRxVJTEag0ShDUERqIAUarSlJqbHljPVXfeSgzEiJY5TLh0KnvuEfDmN76O"
    "o444imZtK4HPDiRgytl95gLtgSKp1tgNtDZPswwBqRVJWh/daHOcQZ6A5DHBydvRP7kEC9MlIt3QnQGT"
    "PfbPt468hXy7onqDW269lUYUI31Hp4/tn2STmYf0XlPBbJDfZcARxbuk7veHrF3LmqV7YKOE+mgNk1JX"
    "A8IYopFdJAiuuuMWNukGDcAKV2ZJozNfi6efcRKvuOD30XGT8qJFriyznnfX6kkidXk2aCGxlLC2grUl"
    "5+7rN2yQc0BJLQMJmXm5R6YQ0UM86A3Z4/PMwWVQku2b7bJlbVhYHIK1ljjWPHD/Q+ORpzuZ4xJfU8Vs"
    "cAD7AXsBOfOVgwKO2v9glgQlVFNTCgJUqiewjk8oLV3CPZs3cNXtN7KTbO3LrhUqWLYY3vonb6ASWEgS"
    "zFjiRAPMglvxUxQHi/XPpEKo1WPQZR6472FuueVuyuWQww5/Cgc8ZS1hYDC62XYVa2OsiRCiBKbU7n8+"
    "afRyfEn5tsmuwv3aYjEaVCkkabrn2rJlK9dccw3bt23jgIMO5OSTT0YIi5CCMHTxc8WSbfOJhx9+mI0b"
    "N1ISsldx0ruYkvw/95gNAnAgztLXgl+GhoBDVu9LWTvvICUFmaLQLwy7Rnbw4ObHeGRkpyutLPG8qLtG"
    "pOGppx/HwU9ZTVTbSbUcZvtmutDjbCJlr5tRzK7RBl/76kX85xe/xeZNEZUq7LHnIO94+59y/vnPolJS"
    "yMBiTELKARgTo2T6HbrlMrCiyBTMf/9IKSEI0FFMEIZcc9VveO97/5Z169ZRr8PgohKv+YNX8c53vJO9"
    "91mJSeYtVJ580po8RkZGaDQavSa/AR6c5YbNGGZjROyP81V1CNwkVwIWDQzylDX7UNKp849o5bkSTp9l"
    "KwE333MXWyLvn19w3AmAF7/wfJYvGSAM7IJaGcaD7LJhJao8yE8uvYKPffwbbNoc0TCKR8dg/f1jfPxf"
    "/5P77n0Yq63LhJQkvpahxtgIaxKw2vugd1y9y507W2KFyTagTTcxE3EGWcGW9B6BBCWwNuHBBx7k7e/8"
    "G3595TqEKpMAW3dFfOrTX+KLX/gyu3aMtBSlCwRCSR7fuoV6rYbx2RkKeRnqBh6er/ZNFjNNAAJgVcev"
    "1r33wUqVUEOgNUpYN3izgee8/B5rjHLzg+tb2X+zazgP7IP3G+CYIw5BN2PKQal4p90Mkp07mlx88U+J"
    "ImgmigiJImAMuPWux/nud36MNU7Tb61FGO/ZaDRWN0HHOEGpfZJMRYOfn/Cdk38G5fG4SRAqrr9hHTfe"
    "eBMG2DXaxFdxQwn4zne/TxQtFJ1Oqy+EDNm5cyfNZtzLyNRgHgp8TBUzTQAqFAscej2VQLF8yXKGywNO"
    "7jfW7RQGpFOGRcKyRde4Z/MjOZurzfpfAkcdcRAHPmVfpAbidMEy2eYqf+Q32rdJwhS2vuhxn+J13BYw"
    "VrNs3lyjGaXTOEb7TouB7Tt3IWXoyoRbPMeU+DwBEZg6rqiMnyy5cFWLS6MmwzKyVEEI5fpVOq+szLYv"
    "RLYhLUjb9psQgjiOkaUB4ihBJ4Y4ShAywFrRtmXdkHEVbks5gWa95toQSB7c8CD1KHXrgsSbjCMLjz6y"
    "ia1btjlFZsE8md9mC679rb8Orl83btxIYmGoUu52asQ8pPeeKmaaAITkM/7a7D8whqGBQaqlMkJbjInR"
    "xstYfnBoCaNxk5qJW66VWSCx+3/1PiuREoTo7wa7kJENKhtk7r4GmU0GZCrDS5cMxIisXqIjBAnaxGjb"
    "ANsAmwZTtcv+YXUInYBuxFgjaNQjrI9/iGON6BdJqCTNOCEMy9i4SVgqEQwOURocRCeTD3Kzgt2ohkEX"
    "km8NURS79HPdrU51dhMFIMy8EjDE+frkIBBCYqxmeHiYcrkMDSffiy7pd+r1OnEUYWyqgxYgBMq6nDgH"
    "HXQQUimI4xlu+vxAdlvJJjxBDMZGSBMhZAlsCUQrdsAIEEnCtq3b+c3Vv+HKKy9nzz335JRTTuG4445z"
    "0ZSphaUHhBWUB4e56YZ1XPnrX7N582bWrFnDC17wAoaHhwk6PBnbH6a1evow2ZQrEO63KT/6nMFZQ1Ki"
    "JYyl1myAhGacdFZzbmPHFj5mmgAonCOQh8Qx/y7odmhgwK1e1mDROf2eyU5vNptEUdQ+MIxNGQVWr3Qq"
    "BmstVpvWeN9Nka7q/UaMEMLb0HNsNhpoYKxCmZKzKRJirXBekQgefvgRPvyhf+JrX/kyu5rujRx64Bou"
    "vPC1/PEf/zGZHb7LamcEWCP44cX/xzve8W4eeOBRYg2VEH78o5/y0Y9+lH333RfhsxapQHnRrtOE2GvV"
    "z1uKF97k74SxlmaziTWZw3kRxXozCxozzUNL2iN/e95GQpboIo96o0Fic4NCuCEihWBoUDA8PAxAI47c"
    "CmczKcINoKLML/ps8wRh/ervCYABBquDjigKSKv+JrrFZjt5XCJEgBAShUUQYU0NaxpgIoxJqyEAVvL1"
    "r/03n/28m/yDgfO2vOeeDXz4w//EJz/572x5fAdGS4QISRKBECFChGiriBLLf37pa7z1L97Gvfc/SuRr"
    "2iHg4u/9gn/+l0/QiBJkdQCkj/WUAqRq1yFIixICJQTlsERUbzhOxVhX/IR0qXDXD4CBgQFnMsz1VzeZ"
    "f/Z1Aq4NXjWCFIK40ZxSBvmFiNlYP8ftF2MN1rgkn+k0L9qr0zXEiPRirrsTa2lETRCCMAgQCzfRyqTQ"
    "bDYRwEh9xEU759BoNKjVxihXNUGpnOU9BO//IyLnU2CaCFlBVhaDUcRJQr0e8etfX0VJuSCqJHGKxgFV"
    "Imoa/uljn+Cyyy7nwtddyNHHHMXKlXsjhCCKIq64+iq+94Pvc9G3v0Ot3iBfQ9MnbuInl/yct71tM/sP"
    "VJBSYk3iOY/eiOOYcrmMTSJ27drVsd8CSgjGxsZoNBpT7dJZRbVaHW+Qh+xGyqmZJgAGpwXNoRfvJ0Ao"
    "53Pu14B0NWxThPnJb6wro1yr1UFJgkoZ29xtRK2eCIKApUuXIHisa4rvxYsXI6VC65hQBdgk/8wGKTXG"
    "NBC2AWYQmWneHUZ21jBaIAnQaCwwpiMGqbBrtM7Pf3k5V15xNatXr2blKufA+egjj/LIpkcZa8QYICiX"
    "MMap60Ov+TYmYrTWzGR6kdo2UqE//9pzATVCCFfANY4zbi4PAWhrGRisUCotPPlOG8PQ0GA2w7swHWV2"
    "IwIw0w3tQgBaN5LW27KVciY6v1rkbdZp2LCBjt7VBprN2BGPUGBSO+BujFJJss9+qzBAWTqJMiWDAli7"
    "z94MLB4gCATdihCkbK+1FmuamNFRiJqEUrGoOsjhhx1CRJQVFBkKnIqmpptYb2MYi2PWP/AAt9x8G9df"
    "t477H3iIXX7yK1UiaUaOWANxo0ncaIKxHH744ey9x57u5eoEZH44Fd6L9/EPSxXnCixDDjjgALIH9lua"
    "13GffVaxdOlS5hed00MIQbU6gFJ0cGseVYqesAsYM00AEmC07RevvAqAXdt2EAQBSIHRxsuLImP3JYZ9"
    "Vq2kDGkGrAxpuMCjGzc7g3HJgmjQTXnl7kvbKtTySGvf+qGXf11P9NAtdLuOEQY1oHjxBedxyCF7Ehsn"
    "ZJcECA2nnfQUXvj7z4JkF4EPdc5kUdIowjISl0rdaoNMYogSSAzCWF73qgs4+pCDKIWSBMtoUidA+Ilm"
    "iGkpWLePjlKL4yx1uwSXfwFXhxHwvvmwbOkAb/uLP6FcDsHEPqhLY9PNugAu58dh/XeBSVpei88/7wW8"
    "8hXnYyyUA68XEbBsKOTNb3w9y5ctyXqv1/ub7PucKISVXq8gc7oFg1KSPffcEwDdXedQoq347cLGTBOA"
    "CNha/NH6PKpbtmyh1mi02YKLL28oLLPH8OJcAo9WUxMDt925nmYzJt65AxkGu3c+PGGoluGcs0/lfe/5"
    "E848eV/2XVlm7xUhv//cE/j4R9/HqpVLQSQ+FribXTpA2MATBgNJBCZ2f23C6U87hQ9/5IPsvXIFAVBC"
    "kPhpWhGlttAfaKddLYEMrNYoBIGEFcsX8U8f/RBPO/N0EMZZYzIrRS8UhpqP+PvgB/6ON73+AoYXV1i5"
    "apjjTziUD3zwfTz/+c9pZyjmFbmGCCeWuXRzXVHCZcTaLTDTQlYT2JL/QQjHumpg8/Zt7KyNsnxwkEBJ"
    "UmO/8KpvIQSLylX22WMvbh/dSWzwbK/E4qr43rDuVh55dCt77REQKulKh+2OEAaJQTd2EsqQl5z3VM48"
    "4TA2PvwYw8PDLF4yyIrlw17Rabosb+lz52Lp0VgbIQgydb1uNnnO857NpwPFhz/0T/zyymsBKBGQ2Njz"
    "AroYuNmGEgGRTSgJOOjAA3jv37ybF73w+RivkJxY/oVCe73otmr1Sv7lX/6Zd73rHdTqNZYuWcryFcsp"
    "lauO5dML6/1ao1m+fDkDA4M06gm6k+hVgdXz0LQpYaYJQAQ8UvzR4OQ6LWGkWSceHCCQAms0RrjJbXzM"
    "/5AqsXJ4KVXh06nm+tdYeOjBR3nowU3sv+YodDTiMuQsoGCRiUL6CaqkxCZNhNDsuTRk9apDSBoRSoIQ"
    "CeBdmsfTO1vpUxkmTqFqm94NWqAGhrE24tznnsuhhx7Kpz/1OS761nd4eOMjgMX4yS96kAAJJCTsuXQp"
    "z37Oubztr97KUUcfgdZNlILp9n2SxFQHquy73xoAhAqIGnXQXVVJ8w5tjOcAytniVkAArJmHpk0Js8Fk"
    "PUDOr8UVt3By/iMjW3h813ZUxbFPwliEMVhrSDBYYxiSJU489Ci0doEFSnj7t5dKtzbgxz/8JWOjgHUK"
    "1/EYz5mWDaeN1D/BBKAVxAGCktOwByHEDQKJC222eG+cXtF90usDvCZeGiABXXcp0XUdTISQGmyTpcsW"
    "8f4PvJdvX/y//OVf/Bn7rVnD0sVOE59gCZWiXArRuBc4UClz8P77c+FrXslXvvwF/vmfPsSRRx2OtTFS"
    "4WL2J2iHbx1j2rZKKcTqBIx2AU5x03N22ps8JxyFMSewiWG/tfuwYvme3qXatpFm/2YOwFkDFjxmw85y"
    "P1ADVwqclABIGDNw38YNnPGUQwiQTsYzGiu9wshahsKQw/bZj7WVQR6yTbZH6QrvfOIHMFz6s8t57ate"
    "zmGH74NOmruPzaUDfrhYAyJysn7mJpvPAjRR5DIFmcjnWhjEmaYF5XJIqTrIMccezhFHvp83/+GbuP2u"
    "27j99tt56KGH0FqTJAnWGFatXs2hhx7KmaedyR577EF18TA2qpEFcM3EpJyIBWfOk5D2hwoC1qxdw003"
    "39brkINx47/Z64CFgtkgAPcA20gJAIDVWOmGzG1338XYqWcypBQohUzSaeBs1QrFwWv244Qjj+bu66/2"
    "eTItacYgJUvccN/D/PBHl3LY4W90QUG25TpcXOwzM9lC4QLSdqRJQVMbuUxANMkKfdrAcTi2X9CT91RL"
    "J6T3sQcwpo5N6sighDBQKofEjRpSKGQoWXvASg44dC3nveDZ6KTJ2OgIQkoqlQqBUiSJIBAlRKkKtkmj"
    "MUqlWsqu70Ix0w7uM1H7TvZu+1v+AwuFECglKYWSgw8+GMuPex22BhcVu6XXAQsFs9Grj+NSIrXDOrZy"
    "/aMPMWYSEgQYBVYisw1IEkrW8tRjjmeRb6DzFHTsoLaWISX5z699k19fcR0EVYwIWr7muYQWeSzMVGEG"
    "I1yQTLYhW9uUiJbJ/lqrMUkDoSPPYUSEVYWqCFQoCAKL1XWSeJQkqVOplqhUSlibEMUNLD7XQOJk8nIl"
    "bHki7ub+F1OD43zCULF27cqujlseS4Cj5qxZ08BsEIAR4KbWytRCAty3bQvXP7DerSraEQCRTn7cZA+E"
    "5JT9DuH01QdQLQGBW9giNLEyjGjDg49s4d+/+BVG6hYbDJAgSJTx9ujcqpHK3HT6jc87URAGSYK0BmkC"
    "pK4i9aDbTBlpJhPy3C4umFSESJqYxk6Ix0A3IBnFxKMkySiJbqKN4ziUCpAyRFqXkCQQoQ/i0hjTzNKR"
    "SUR7/7Ul8RwHPRN/Fttf8JaY6PXnCLJUAWE4/czjWb6sp5hfAY6bw2ZNGbPVs1cDtTTAI72JBh4Drrhh"
    "HXWtIQwyDzNhFdJCYg0GzfKgwjOOPZFSAjQhlC6YBWEolyRWwvd+fDlf+NI3icUAqrwYY1TmY2B6cAIL"
    "Dlk7JU4iy29TfT3uPIFBmhgTj2GbY04xaJoIErL6Alkf9bpXj3QoMzEpF9DEHh+t57dxExFIVqxYwpq1"
    "K8c76QQ6QuMXHmbrDawDNrqP6Wrs/pSAdbfdygPbtpAEYJXw0W3OD0AnCSbWVMKQZ5x8Gsev3o9B31Ah"
    "DUFiqQqBlFDT8NnPf4Mf/vDXjDUkBEMYSr4gUJo2O5ckYxY9xxYOWpyXc6s2SK3RcRPbbAItDXyXdAwT"
    "vH5udZ4uunEGPbmE+UA74TPGgJCsXLWKE044cbwTj8BZAxY0ZquHHwWuMnRalhPgsbERbrjvLkYwRFKi"
    "8xPRu7uaKGH/PVby/FOfztogBAO1yF1QNzXaQLUEDz28nXe+54P89KdXoBlAU3FEAImRqUbdoRgp/ISH"
    "MEjjNQpGo+M6WEcYhXUBPJMhAnNfFmzhQSkF1nk+HnroIW37CjzSCuC0uWvZ1DBbbzQCfoxLkJjBCJcv"
    "aQtwyW+vZott0gycg1BaHFQKgbJQEhJZiznv5Kfy7GNPZQjHFAv8f9pVFTMW7tuwnfe878N8+9s/o5lU"
    "sHIIbQOXJUe4wCPr/dF/Z2ANWUCFNUibII2G2ggkDSByXobGIoxo+e4X0JL38zL5XD7IQoHjfJy52qCk"
    "5JRTTmWPFUsRPhYS2oQlBTyDtgQ5Cw+zSdKvBNZDjjJan0VFwlV33sa1d91CE50VBjWCNF8lJSkJjWF1"
    "ZYhXnPt8jl6xkqW4uR/bVs6ZFA9u2MZfvf19fOITX+ThR0eQ4TCGEkmiiXVCbBISnbQNcksH1X5iwaYh"
    "uu6vNBEmjqBZ87ECU336hcKezxN8eaq1a9ew//77k/SmiKeywMWA2XyLG4Hvtw0xATKEEeNshT/45aVs"
    "2bWzw+QlcIoxZQ2BFRy692r+/DUXslS54xq0lIuq7L6E1ZBdo5p//PAXecMb3sq3vn0Ju8aMMzcqSVAq"
    "ocIQK0Wb2e2JD+8dSOL635p2IpDm6vMoZgPuiWxXN+19D43+EwB5TmnNmjWcffbZBL4zujzlKhwXsGAx"
    "i1NAAhwPfB/MquxOFgIFJe1UpP/0uj/k2ceeTBVBqEGaJGeiU4yO1bCVCtHiAf7rikv48P9+hcd8aqrU"
    "31iWnONbelcDLFsK5zzjBF7xonM5/JADOfjQQ0FBnMsyI6x3R36CsbQtuT6vwU+djtJhKqFUwVaWYEQZ"
    "ZBok7Cas8W7GwisNWxPZZ8HzJcutmUDniTyDvPsiy3WSpVAP+fnPruFlL3sV23fu6PV0PwJeDnSmP1oA"
    "mO01sAR8GnhjywMOsK402CBw5h6r+dS73seqcIByYjBx061SabgwAUZIYikZCyVf/sWP+Zfv/jeP5p4g"
    "8PEC1gqSlK31Yed7LobD9lvBM57xDI448jCOPuJIyuUylWqFcrnMQLnS3iHp+RM0IdoONiKdYBO8Tld7"
    "+Eyc768hUvu9q5sYVErQdFmVUAobDiDCMqgBrAyxNlWiBu54YpCmJXcZQAYkWtBsNikPBGSVm3ui97OY"
    "IgFZoKbbosXItTJg48advPpVr+M311/bJpbmnmIb8ALgijlo5qQxF0zwGcC3Eb5gaBrYZp23xJ7AG895"
    "Hn/10tcgt++knLKp0jhNPhJpA4SVRFLyeGD44S3X8Tdf+Qzb/ODJ/A2UQgsvogkfP2/cfSyw9zLJYLXM"
    "kiVLWLn3SpYsXeJ833O58UWWc68wEHu4pNoOW2JxCBQG/7gTdmbOz6ZUloLbreLKJiwerHD0kYdz1tPP"
    "YL/DD8XqBjYIkEEV1BCIKkaUMNblCpCBxdRGkarE45u3cNG3LubOu+9lx7Yaw0sW04zGMMJ0YX+LE7k7"
    "EXBKNdl130JCx9MIwAbUxhJuvOk27r33XrTPe9Hl+P8B/hW4gwVWNXguCEAI/BuCPwTaNMgKNzlXEfDP"
    "f/QXnHvkscixOqFJCgRAokyAFpK4Wma0GvCd63/Nx776eR5t1BnDuwzjogeNACMVxmhKuJByDSwNYGfi"
    "rAmhUw24ffmQ40k+3EKUHnp41bv+lq5M2+knHc5HP/J+nnLgclQAIqyArEJlEfjUISCp1+uEYcCdd9/D"
    "X7/tHVx22fXEnkaGZIWfdnPmfuqQgApDtNYopdBaO1+BdhjcxL8JRwwuxqnB5h1zpQY7DsG3gf3zMyZd"
    "uYeAp649kA++6U84eGCYivZsq1QkxjoCoJ38GgmBrpSJBkv86o4b+OzF32TdA/cxRnuFvPTB0vU8ZTwE"
    "oBCZ6cYifapM1yID0FYOyuSukL9yunsBiwA5vUsqBpQVVAJBo2l50yufy7986O1IEUFYBVWBgUVOTyC8"
    "N6IqQWL4oz9/K//5tW8TeV8MBZTDMrGJeihTi6x99587LI+7mXUhnexSyp6m1AJi4FfAPwKXMc9ryFwR"
    "AAG8G/h7uihLA2BZtco5hx7FJ17/Z+yhStRHdlAqB5jYoAxI45VQAscJSIgC2Lh9Kz++9kq+fcXPuWds"
    "R8Zf5dNbSKFQuBhz7XILIZ1UTNzNI1DkXJj69dBEl74eE2DCmPT5xW42WVsHQ7AxnHLEPlz0qY+wbMVy"
    "GByCWg3KFQhKUCqBLEN1mK0PPMRZLzyf2x/Y6vw1rFMLuKv2mLBTYed3s8kP0JYZNCuKMqETNwDvA/N1"
    "5rGS0FzlXbbAl4BzgacXdybA5mady26/hS/+9Pu87uznMByUSBoJQaa09gPYrz7CQBjB/tVhXvHUZ3L4"
    "oQfxg2uv4GfXXcP2JKGOO1wDxmoEGoFCEWDQaIxPMyboqcGaKfLYmWjPYaKTeUrn51RSmfNONmtpACNb"
    "drDp1ocIhrYQlquu5kIYYIMAFYbIoIxUA2zbNYoaixhUzoSLSK/Uy8xn6Kg21Isg7I6TPo+JWEG6Yw3w"
    "T7jh/40Za88kMZeJ1x/FsT2HAXuCzEQACxhr2Nys828/uZihZUt51dGnEzQ1qqLIbNWyc7Uul0P2VCWe"
    "MXw4R61aw6uf+RwuuvQnXHrtVWy2mlFcVoYYkDhCABIlJIk1KGzbSzTpDOueIasDfX1p+l2n3z2mfH77"
    "5JRIBAkhFrRlWMCR+x/BkniYylYgSChZ0DaGkkUGhkBZJDGLjObk/Q/lkc3XMZpO/qxdE7Tz9yg/9jun"
    "PWjn5FbguOL7cAF089acuYIC3us2GTgCILGYTPbGwmqp+MeXv5kXn3QGpbhOaExbFuH8qhFFMdXBAWfS"
    "ShJGRcIIhofGtnH1nbdxze23cP8jj7DhscfRdMYCpLoBmBp3PpvDdyoMQv68fNtSJeAAihjNfsuX8743"
    "/xG/t8/BlMYiLEkrW7OUqDBAKEU82iBcupgrHlrP+z/7SW54/HGKydhlXwIwv5N8snefLE8y3vVTLtQC"
    "JtVUQ24MG4DvAq8Fdk7y1tPGfPjCLQM+B7wkHTqtDjSoQGATy2HL9+INz34urznhdFZo4RRT2ru1Wttq"
    "ec5bzUhIlCQKIJZOT9CwCVu372Tjo4+wdcd27rjvHmpxk9HaGLVmg/ro2CSzBrUPDyEmM1wmNxTzyrXM"
    "CaULy9xNgjFet5HeMfUDqArFwQc8hbPOPJOjn3Igi0Y15cQpPdMMy9q2PNtEYhDlCqMlybp77uDym3/L"
    "rRseYKTZZMmKZWzfPpLdYaaee6Yx2ajPCTuGebGm2/WN//2+jRt5pBETA0bRTgBaYlkNeB3wrcm1dPqY"
    "L2fYw4GvAcd3OK4AKhBIAQcvXsafnfUcXnbG0xmIXYAQcT5vHk4J45dxSy6wyGcJEkJghdPSagmRNTRs"
    "Qj1qEkcxMve2u6sCCgPbFgnAZEdXD/t4/pcCt9OuZZcd7ew2YK3PNGTTklw+8k9qwVClSjUoYaOYAQJU"
    "6mLgPf5STXZawBQVQCmkKQxRKGhISxIGqErJlcrObtqfGE7X/Xqi0YvF+0yUCBT7Mr1fer3i9yxPQF4X"
    "6D9rCRu3buXbl/yEb/7op+zCcwHQqZeB/8URgfrEWjozmE9v+GcCXwT2L+4IQ+Vyzidw6NAgzz3+ZF7/"
    "7PPZb9FSwlqMMibrSJnJ7CYjAPnCI0KndQUFSIEMJYkEbbTzdJOulLa0vSj/+ARAziIBMJ4A2AIB6DVI"
    "i9ftRgBGduxi8dAigiAgajQIpfP4a3EAss2UpYRyXJa3vtSTiNJgFVUuYaVABLkC2YW+MV24o+navCba"
    "28X7TJTwdBDXHtfLrpl7nzb/O34xEpIkDLjolz/jn//zizxUGyMGb2oVYDIDwEPAs4C7J9bSmcF8EgCA"
    "C4B/wzkEutVU2EyxVnY1KxgGzjn4EC4878Ucv+9TqCSgrDMPKmFzLLw7MZtAxnjzIQSlCihFbWQ7VgqU"
    "L2GdU/t1n0h9PO9mgwOwBQLQjwPoRQAAlxMB510JToTIirBa6/zaXYL/Tg5ACGQaTm0NBosgILEaIQRB"
    "uYQYGuyihEg9+1ptbu+Dbu2dACZLPSbJBXQsAMXv3c73Cw+0E5n0cxwlhMPDPFIb4RP//Q0++5Pv+hh5"
    "6bjXFgGoAa8CvjN+K2cW800AJPAHwMeAFfmBibfOhelfYI+S5I9f8mrOOe4k9gmHEGN1lgwN+tx0GpMk"
    "beWzrbVI0omu3HEZtUhZt1T+7TW6+okAk1QZiaLJd7IigOorAkibv0+7Q1Eq31vROk91ZLbPXVtIMMb3"
    "Zdow/0dCUlKIUBGUyyBV+zUyPU3rmna6BHSKmtGpcgA9001n9zEtV7HCMcKCrAxCvcmYEvzijlt48z9/"
    "kE2NOiBQSHSuhAbwF8AnJ9bSmcF81182wFdxI+bD1to9sj2+49Nakk0Jtdjwzxd9nct+ew1/eN5LOXyv"
    "1Ygkpopw3n1SIjUIT1WNcGy/Ft5xJTfos3nhFTMLyaVXWjdghW9X+j3dl0cvcaC7XqD11+AWIOk9InvJ"
    "1tY6DslVwUlvSia/GmMg1pgkRimFCsMs0MhNfDfhu62S0KbDnRAmSm6nqgMokuNMVy9691GqyM73eXa/"
    "0RoWQUmV2Xf1Ptk1sviV1j0FjtmdU8w3AQD3/F/GKT8+gi+rlH/R1vsAGQWbteGHd93NuvX/wCue+Xu8"
    "5tRz2Ke6iCVDVUzkXDGFtzlLHOHwXsQEBsKis5b1Iu5EKUBxAk6Wh5rgfZRtFwVU3m7p0UteFZbO+wjX"
    "VgvtKdh6oLM/nN6ljTvJHIu8/sVo0AkiVM7IKwOsKnu34l6YppFu0h6HXZyWxkNKeNPPpjsJ6vjVK6Zj"
    "NEFpgMQaduwayfov8ItWoXLInHsELgQCAO4t/BfODvoR4Mh0hy0clUgIKrCpAV+59Kesu+o6nnbEcZx+"
    "wgkcuHYtyyuDBMYQGEAYdGGWWD8R2sKTmbh2uc3DDm+SnCrGGbwtaSXvbCsB3WVy5qMZCxcp3tIfo3I/"
    "9H/2QgRfbvK3nWuN6w5j0YlFBAYRBBgZIaVESOkIW749k6agTMh5qmOaT/A1dZ3I/drS6xghCStVKJUZ"
    "rY/xyPZtaJEbO+1303SprD3bmG8dQDccB3xIOrfh/DrT1lrpB3EZF7e2Z3kRR+53EKcffTzHHXoYKwaG"
    "OHDvvTHbt1G22idzBIzF6gi0k2utFAhps4GYyfTCM2jjKQZFFwJQnNQTsSx03dfDjbarqa3LbzZtX+5a"
    "BaLX/Xpd7l88Pz1VtJ9vc3kcMmeioOTMiFK6Lcu3kJpx0gQjqdmm37OZCRGAVqP6rfh9hIounNC4x+Tf"
    "lQhAlqmHkvUjW/nbf/84P7rxWmK8OzsCQ1ZeZAR4EfDz8Rs0s1iIBABgLwlvB15vYGnPoyQuGwggIksV"
    "WEqVvRYt5dADDuSYtfvy1EMOYkkYMDgwSKXikoCI3LJltUGYJCMA0g9MmRIAeosHVuASWvTR7LduVzCT"
    "9cwF0H4d2YNNXWjnp/YUA+DNq2n5bKEkUknCwKVlkz6IRtDy10jRKa93+opMBKKj33ud24Otn8jk77hp"
    "3q1NYtQAD47s4B++/Fm+c80vGPO3SxNW5yTSW4Fnk6XTnxtMlAAM48odrcBlOZ2st+RkYfx9XoRzkRzo"
    "OELgtFjKN8VY16nGDcsSihDNKjnIikWL2GuvvVm6dAlLly1maHCIJUuXsHhgiEEVoKw3eVlynEC2lPVk"
    "kY2gzergTuwcJO1seW7FFO76behIjmG89cK071+A52tsZrWQQqCCgLF6DSEESgmklKiSas83mBIC38ld"
    "tfXFVXwScr+77NQIQOv8FBO8r29fQsD6Bx/he5f9knX3380IsVuwLEhtiwTgX4G/Zo71AOMRgBJwLPAc"
    "XFafg3Ch+2qcc2YSadcv7npPQSd75jU16eAKhaKSgEDjrNgtzWtAgERQxmTsmD/ba2hF/qI9oTveV2H1"
    "7zhjolxAcfU1hf0L73yLzb67Yq8KnXp3KuHTtrn+EtKxviIlAMK2KxY72tNrEveblJ2OU5PFpAqo5IiT"
    "FpIdTc1OE7dGSSCcQsK4Qe0JwCbcYjfnAUG9lIBHAH8K/D6uyunCg20zobjhYQBaOdoTNDWEt197ZxdP"
    "NYTX3qQDPJ3wlpQy2/yVx4HpOQS7n1kkGEUGuzXQJdlDLbjz8wTS0t5/7iyLi8FMTysQEt3FW4/ZwXTZ"
    "1anKyRpvcWlZQ/3V8lc04Nzir5vibaaFIgGQwAuBD+CIwIJHak9N4d0GMuSULP57/khy/HkvQb9PAyYy"
    "OnpqiSd4/QV5vvX7iv3Xb7rJTha+2IfF7+O1fzz486bMU0/XOSSd/Pk+NG6TZKv/z3HOP0nXa8wyii5g"
    "rwU+jHfNXfAoznzah1+X3Z0WhelO4In8tpC8jOYafehr38kPPSwfTEwXYMc5vxfarC7dDuinUyC30Mtc"
    "O9rPBn5jMG8BbpxcA2cO+e4+H/g8+Oy9uwvSJyh0bs/JP5mJX7zARM6b4Ko0aRSec7c5f7IEYLIMe89M"
    "Q13uK3p8Lh433m8TcSRqu3aOALS+GeASA+8Ec3O3u8wV0qYeiAtHPK5jT6EDhaB7FpweA2S2zQUTacZk"
    "ZMsibRcSrxXogd+leoMTxXyl+ZI5RWPO80fiPJORgsT6YLN0hc4Til7Eajy/gm4EqNdwcde9H5ce7/NY"
    "HuvzRLOOAKcdewP5yZ8i7QgVOnONtVil3OfxHzLD1FOmTez6PVFc6XutYF3bKx2lEwYrHNVLtdWddQGe"
    "JAALCbZeBxE6QzsGrHFKd43L/54WPxrPgy+P1jh3+ZCFEX3rGNi2TxEwCtyFk/e/A9xGuq7M8/AJcDn6"
    "Xtyxx6a7S4SDSzns6CM5/MTjWLz3HsQKYunswCrXB0W6P9MltyZbz77db70T3QJpRM5uLK2hUq203bd4"
    "zpMEYGFhx/YdbN22lUcfeYQdWzfz4J23YaIaSb0Okfa6y7TKb49313283IHlK8DjWUBA/1efANtxsf4b"
    "WWBFQcDN8OcC++V/dGyUBSEJl+7Na978R/ze+echq2XCpYtoKoi9Z62gc2JOJGPNdNCPEBQnftG5ZLz2"
    "Se/0kmbDWTw40MqM0+V82zcr6JOYSxhrSeKEOGlikojats1suG89t990Cw/efz9XXvZr6lsed27JxtKW"
    "yrtj4qfOTwAcIuFM4IO4Ah+Tb9tUTpplCAQ/AJ7X/qt3VpBlLnjH33H+q15LZWCACE2CRUtIBG2Zd/KY"
    "SwIgZHsDhGhl0Ek7PM8BCCE63nP7hLauPJgwlEXA4lLJczmt1zdVu/ATEZPOiDRnMC4dvNVIrRG4ALGN"
    "Dz7INVddyW+vu55rL7+SePMm3BvViHAQGzdBCJQKsCZGGI3NfB8AuBN4H/B/TNLCOJFpMNdEQiC4j1xa"
    "LiEl1hjKlQqrDjuKv/7E5xhavS9WQKVSodZsYIRzcOi2wnZbnWecAPTZn5/4Qoj+HEB+n5BZgdCyEgyH"
    "AYHNX3Xmn+dJzBwyF2PRilZ0CVFdSrRQBSTNiF2jO3nw3vu4+pJfcskPf8yW++9FhGVso0lYCgmsoR6P"
    "eicyr08gGytbgY9YV/i21tGGHm1bqASghvO7dz9IifVeW+e95kJe83d/z9YEVCkkDEMSo7NSWukEy87t"
    "8YSTld37NrrP9YqEqVumljzyMQBZwgYhCZVlqBIgbNJGdGb6eZ7EzEGI9tDosibLeWiAZrPpqkMJGBoY"
    "pAw8dPe9fOd//ofLfnwJm+++E9DekdliiL2vZ+oanaFu4FPAP1BI591rgVqIIkBaBTKDNS5MSUiJ8gkf"
    "NZZASXaNjVKpVDISJ2wntZvLyTGZTK/5FFi9ILs8TwpDp5Ns18CfWWGJJzt05skMNw8oKmGFMJmlRlnn"
    "5pwlUxGSUjmAQBElTWpRTCwVK/Zby1++73089/nn862vfZNLv/99mtu2etc8Tevt5yL9BFVcCq9h4D24"
    "MuBgF+ZE74UAK0dxATcACCWxOkHKkO3btmOtZXh4mCiKKIclF3WXl7s7ltf0ezGIpDsmXF47f07bnnGi"
    "2fKsu/Vuwv7kLGuwFxFU2m5/vhUaCBBGEthS2zntRR08a5jlGnR6iYnmCjS6F1XKPfdkacruXm5rAmhN"
    "fNH+PZftxWCJpcplQPL9oi2BCECBtRorFaNxkzWHH8o7PvL/OOppp/L1r36Nh6+7FhFJhoRlVzySXd60"
    "rOChhTfi3vp7gO3Fd9Uvg7OeZztggDNRHJX+UKlUqI+NouMmt912G/fdtZ6Vhx2OwFINAqIkwVqRhYIK"
    "m18bu43VLr7f+QFqLd1XrJTitlPefAhqliuv24C37r6yUJIqfSFFj8H0uy3+bmXWfDnORGxb+I11K9E4"
    "cGYoiUSCbU/F7W6ocu2eLAXoRVT7YfdZu1JVrknzDfjvsvDs1uurRLYYtMZOukhYfApvYNuunZzzwhdw"
    "0HFH8d2vfZOf/MdX2DWylYAKpbKkHteK3KTCEYEI+Buczd+1aTcQFQXIr+Ay8wJQrlZo1uu4blGccMGr"
    "+aN3voPq8GJUucRoHPt85wCSwAo/yfwFRbdo4V4hnq2J0L113bmAYr75YqbZ1sO1n9/Nnp9yM1aKdqdH"
    "KSlJweLQWwGE8ee3pb1wqcjzmWEn6BdgU8JnS2CDwnmF555s3rs+qcx7YzciAB3WH9H2t8WZ+ffbTWGN"
    "yTzVUj2QEMKlk5eSsBlz+cXf4WN/+37qzVF0XAMb06bOyz6KJvD/hOWjOGKQXXc82AIHMPdKQOSrgc8A"
    "Q13do0qLOOKss3nNG9/IHvusYmDZYhJfdgugZJU3k7kfesvA3ePJbYcdsSACFIhA/8nffv54RMCtF6Er"
    "3hCIHGGDAEloBcOVMoF1YcMCQ2ATx/XkCEIK7dNnT8Q3ICN8tgRIbNFlskj8JkoEpjz5Uyx8IpBNdi9q"
    "tbI5iTYrgEFipEJLMD79uxGtMSMsCGMzXxYhBFIqojhCCsGisIKq1bjiZ5fyb//6Lzy0/g6I6kDiONfO"
    "6TIiEH+Bc/V1bdoNCMBKXE2yM9wv0j1cPg00kurSpZx05ukkJUUsJYlfQsNUy5oWnshy6hUfpTsBkB25"
    "PsYnAFDIk9+lcEZ6fMbm5b5rozHGUK1WWbJ0b572zPM55NgTiSqKHVEd6+uRhwYCKxkeqHgCkKBIKFlN"
    "bWQ7l/3iUm698QYaO2rTcgwSPTPm9nr+fuihE5lwg3YPApDfZI4Q7LHHHuy9994ccMABrFi5ksE9VlJd"
    "thQrBTvGdqHKJYxSxHFCGAaIxHEBijSOIOUklPMEFQGhMdy87rd86O//jvuvvQZ0BNUKNBvutbSJoeYB"
    "HEf9ayjWXOjEQiAAAK8H/h0o54s4YA2h+5DpQrP4Zum/pHqwlIVtTxPb//Z5jqFnoEUvT61+q13hfIW7"
    "n7ZO4AsqLF5zNH/xvg/wlJOPpSY1YtC5/pa0SyM+NFAlFKBICGxEY2QrH/1/H+RX3/k21JreFSSvSTAT"
    "e273wN0eKoeZEiInqkPYDYTWNmSa3NZfo1HlCkuWLKG0aBFrDzuSw487jhNOP5U1BxzA4LLF7ByrM7hk"
    "mEajgRISaWVuoqacrFuY4jjBJBFVKbnnttv4yN+/nwd+ex1ojQglttag/T1agMuBVwMbFj4BcO0bBj6P"
    "lS9r32va5rNxZ/gOz8nuNt2R/5udkV3LHVuc5JPgAIoKP5E/nvbr58/LcQJCBY4TiNNsNctZc+IZvO/T"
    "/4xcPowuq4wAhAYGBwYJhUGRENoGP/jWf/Hxv3sPIgD7eC0XWJKmfcm5lvZEr6wFXZ6/4/NE8MTXAWRo"
    "W0DyfS+91tYlfBvedw0HH3UU55z/PE59+tMYXL6UeqOOCgKkkU6nkL1DRwAMElUts2NkO6ExLKsMcPO1"
    "V/O3b38H2+9ZjwwCTG1XW3NkKwHNx4F3CyGitv0LzAqQ94s9FPgP4PRubcqyOFvaTH+pTJ6vJ9dC/wHV"
    "XWmYR/s1ilZD28fcJnIsubBgjEEphbXWVbVhEXLxCv7u3/6RE555KqNJ3TmQJAHKSAYGBwmEJLCGwCS8"
    "911v52ff/zaIGHY5+iVMa+C0lHkTmUyy0F/dn8XR18l4Ihb1JJPDQnXuzaOoM7GZQF60nKRpxz13NjTE"
    "YaedwgtfegFnnPV0KgNVtJAYJbx/hwQbIK1EYxlp1lm6fBnNXbsYLpdRScRN113Le9/2dnbevR60q1bt"
    "KiwlpAXvjWAHcKFAfCffzoVGAILc/e8E/gz4Vx/00I5s/GX8f7Yjr8GebHCcFX0yIRWvV/ze19zWOi8z"
    "8VlNoAKaxiBpUtGPc+DwLg4deAzra7UoXUGaEkMVgZRlpAmAKsswiHqMTYDAKTHb87tOpgN0IdeApudq"
    "3U3x3AWOOOgJO0n1udXChcxp+K0FU+z7wlOkC8GuXdzxs1+w4Yab+NUJJ/KKN72OQ084nnDxErbs2kVl"
    "aAhhBCZ2uoGhoEw8VicQkmazSagUR5xwEm/4q7/k4x/4e3hkM8JoDAki4wABWILgbRZ7rYBH0hfSofOe"
    "584uaqDWSbgQZ898CS4LcAHFeHjhQud9/DwAIrdS93nAuYwlsdqNAw0ksSM8ZRVz8L57cdIhe7NXUMNa"
    "59otiUFWGAyUp3mOnTzh8EP4rsBVeE3AW5Gn0ahiB00vK7Tt+PDERcsCByIAgePsrC6KTyI7WgJYy9jj"
    "j3HlT37MHbfdwosvfC2//wd/wOIlw8QIjDBI5Qi7tD61AM56YIHy4BCnnXUWr928la/8/YewjVF/7TRK"
    "2KRz4VRaafYW5BuRWWaUlgPVPbiMwK8HfkTq4tjlVHe6wlqFMdYnXcBZSWK/JX7ipX/9JEw3M4dbxgz4"
    "FxoGUAosf/ym17Bqz2Uoaxy7LySBlK7miBIu6YHnDl/58gs499xnIFOuX7T3yORfQOdWeB90eUd9r9F2"
    "nV4H9NoK95voaR3tnOVNSL8JN75MorHauFeWqreBlr2uJSYIT7i3bXiAL/zjR/j4+9/PyKObqAqJkgKj"
    "LDZIVVQ5fVSgiJKY4eElPO/5z+foM86AYND3QIc4q4A3WDjC+kWxuM03OmJjCzLKMHA0cBbwh8BqkT2k"
    "615NzMDAAHvtsZRlSxcxWJYgEreBc3IRsuU/X5CNRd/ggX7TajIKNzDameoWL17CHsuXcv6zzuKcs89g"
    "cNiiTR0hddZubEB5cBjEIJgBZ7MPAh7ftoVPfvoT/OrXVyB0BQizfms3A/a35YseVhBTUHCmg6Wfa2la"
    "xCPTRIj28/uh3/X7YaJluGcKpVKJsVqNXSMj1GpNtm/bRrPZpBk5il/0tC6OJgXIsIIeqHDYKafwV+//"
    "O/Y97Ajq1mCsQCYGaSQI402O0vt6WCoi4PYrr+Fdb/0zRjY8iOMRnFnMCJN/3x8F8W66DdYZT5k1OUzm"
    "df0T8NftSjsDwuVYe+PrX8jf/s3bCWggRANlI9fZpkS7pFFQ6hUr63RghglA9l0iraE6UCYMLEFgsMTu"
    "xQGGAJCUyoOIYAgYBEpYEaBlqruQjO6MvX4gfZ6CErCPHb/TcapABMax43ckYincJ52MGRHoeSXflj7X"
    "nyjmighY4xS5iU4ypeAD9z/I448/znXXX8+6deu48oqr2TkWoWSuNEEOJVo8ga5UOez0U3nre9/LEaec"
    "xPZdY4Sy7JyFhHBHCSdmCCFQBszIKN/+6lf43Ec+hkC7fAKpbTytSQ8PAC8Abu5owG5EAE4FviuEyqUM"
    "bykATz55X77xpU+z3+plBDQA7yRhK241zZ3Tjj4EoJ8jSz/HlQ6zY+G7NmA1lggrUzu+9OGjEhmUUeEQ"
    "BItICYAFrHIKO2WrYAIyx6kOn37o4ATyyMxP+TZmO8d/tuwZe/ye08lMCh2K117tKDzPfLC0xmCNzVyr"
    "jdEEpRJRFLFrrM5tt93G9773Pb73ve+x/r5NgPPhUUpSHzOZxGPwKp0g5MizzuK9H/0wS1etxnYtnUFG"
    "AEpYHn/wId75p3/KPdddRSuGo40AAPw98Led7d99CMAA8DUh1ItaP3kCIGCwCt/4j4/ye888jZAxlG14"
    "YbvS2Yn5Aoptttsipmu/HscrLk0YIWxLEVlYcY2AWEpK5UWIYAngat0b6UQfkN5aEGQvsiUCTJQDaJkQ"
    "s2bm30qHp2MXtr/rlXFxCkx+Re4UKyZGAOZapm0rKOpdsKUMXb1IIUApTKyRSrHuhnX8539+iW9+87/Z"
    "MZJQdh5uJI7+I2kF/hKEHHfu2fztRz7K4Io9MTLM7pOavRXOU1BZQxAn/PTb/8c/vOfdUKvhSInvm1Zn"
    "3gqcBzzY9hDzTAAmo7eqAT+krd4TBOUAoWCsBtf95haULCFFCFKBDEEpRLYJt0mVbUoKlFQ9NjHBrd/5"
    "/rsSrU0KlEonf6bmbW3OkxyJwSQRJEnWXcK6AeDcRy1I7RSFyiCU9Vv6rH5Touvzo6RbNNJNSufWmiq4"
    "/CFSuU3537JtHK1ceh0lyKpz99tUXrnmr9Fb89fe9rbz5mBDAaGEUCJCiSwFoARJs0FtbBdJfQxZdu0/"
    "/rhj+MhHP8SXv/wfHH/sgTRjiGJHHIVyJfvSZUpYzQ2XXcZ//tsnIWq6eBJhsFkdw5TwuBESSzjznLM4"
    "8oQTaDmnSQqs1KHAsyYx3+YEkyEAAL+yVj9krXZx1NZijM4i6n51+W8ZGY2wQQkrA7Q1jiXO1P9dtl5I"
    "lSgzsdFly7PHQra0y9Kzbv4dSxO5YCdbBlHJlINpFB+QRQQijKP4bZtwW37WprO5W3xxu/Ioa6+wxjs1"
    "FZ+DHlv7dYQPZuq39X8PhfvMJ4yFRLtNGy/ka4JywMBAhSBU2GYDGzexOqFaKnP++efxta9+iZe/5Nku"
    "P4SBUEFi8TwdjnNtNPn+177Gtb+6jKFQ0Ww2neYex7VaY10CUmFp2ITBPZdz3stfki0eQalUbG2Ay73Z"
    "Wel6HjFZAvAwcE32TaSsFygkGx7exH33P4SQIcb6QQ+0Bux00GMiTwRdicLE4DwftbcjdrGpiXR18FsP"
    "c09rk22fJ4xJtntqRsknAHym31RT738EHBHUccJhRx3Dxz72MV798vMol6EeQZCbr8KAshbiiP/68pfZ"
    "uWUrA+USOm53WnOGRIsNQnQYcPxpp7HqsEOAgCRuY5RTnIrjBBYMJjtKmrgopySl/tZHA4Yq5OHN27jl"
    "lpsRUmCsmXBWnIUOayyYCEyDSROfftcWssfWj5D02JBu6yA2U936tWuG2j3DWy+oQKEbdfbee28+9KEP"
    "8bILXoIAGpFnAJVTHzjVlOW2q67mf776VRcVKFsWsHxGKSEEiTEsWbGM3zv/fDchbNJt/O8FPG1GBs4M"
    "YSoz9HpcsYMM1rNECrjvvvvB1xWQ6glAAHxmIWfV8LHgT2K3RbPZpNlsYqxl1apVvOMd7+TpTz0eJWgF"
    "tXqdCQiINN/71sXcddvtmFQf4GG8kkaogMRYKoODnHD6qQyu3AsVDLhsUu0KVIELu6+yQNDpCdhvczbN"
    "ezNlmQBrBInVSOD6G37Lpk2P+okj+m8LHMI7fhiaYBtAXNArPIndCYEKKJfLSJ/555DDj+U97/kbVq1a"
    "TknSVvdSWECGbL/3AS7/yU8pC4HU3StFGixNHbP/EYey72EHef2OF0OMyEQTYTlBWFYJy4JIGTaVJXon"
    "zqTRAQM8svEREq2dpvSJUDbLU3BjIoyNeHLi767ImWVF6x0mzV0869nP5U1vehNJ4bVKLFUhIEn45aWX"
    "8PD9D3hPv/ZrGpwokEjJwPIlHHnCCT7FXNdkdXsCh8/0000VUyEACa7QYVc8tqXOxo0bCcNwanXzJq3s"
    "mgsYhI2xuuk/MwvtHJ+wpCtGcSvqJDKNvsVbDnqfO5mtd/valbIzdb9pt7eg9LV+S910jUwwwpDEmqQZ"
    "c+Hr3sDTzjzZPZJt9bkL903YcP067rj1Fl8mrrMf0mI5daM59pSTUDLoNbkGce71CwJTFdLvAcbyPxgv"
    "Q0VNWL/+IShVEPIJoAPwENZgTYSjf4kbHLOSftuQxlLYCUQGtrORnatTV1jZewMKIT5PIHgf/TzBkhZr"
    "NatX783LXvbyjjMS47X5KuC3V11FYB2BVW0dLzPzcFCqsGb/A1i0x3I0Qa+3cDhQntlnmxo637Dtszk8"
    "BNShaAoWJAls26LBloibXUwhfW32KaZg7psFGJE6BEGgNTRrTsNrcEEifTAxbX26GRBR2yass3FnbhOp"
    "vTvdrHW+6n7D9tiMaC1TZgKbFW3n2wlunffts/Vq7zS3tD3Gb+1mQQ9hkEpjaZLomOef/zwOP/xA994N"
    "lKtldMrGa819t9zKpkceZtGiRUhPBKx1FcOFVggd0mxYyoNLWXvYIdiSsxqk40eSuYfsLy2DC6HCVK+M"
    "lP2wGdgFrMj/aJGYBHZsq2OiBPkE4gAyAhhHICMIXIWktOrQzMKtTML7HQjpFardOI7xihV0Q1/Oxe8T"
    "rh3us5k6L9BtkKe/tRTLMwzjukUbDHacgDPn2CSQGJOw1157cPY5Z3H3+nuJYstYvUlJSLTPCr1102Y2"
    "bniYNYccjIt9t+7d5LgnHVkWLVrMXmvXgk3c83X2wT64YjzbZuPpJ4Opvtc6sCX/QzoJEgyPbdlCo9FA"
    "5uymE8cCV7Lp2G3CiQJThud4OlOCOS9Dq0OsCVv5DLTNNvxmtMUmE99IWud230Trc2Kx2m/+/Hwbum2T"
    "v58/JrdN5nl6br4thjTLr8QItwmh2raM4VGWxBpOO+00lJRZPoF0DBssOzZv4u477yBpxhhjXP0AP7lT"
    "x0/lrQz77rcfBGEvS9cgsHLqg2fmMFUOIAZ2ZN+ExclXEmktO3ZsJ44iBspPEEtABk+cdAN0GYLUq3P6"
    "nI4LM9XkE1OCpF6rZ5+7kcXJ6Flk19W/13fjnV1aXEC/N1kc6vMbTuzaXa1UcM+UPofoOCaFEIITTjiR"
    "ffbZh3vvfZBqtUyzHmU5VQywYcMGtI5cEJt39JG2xQkOVKuY5ijDw8MEgwMkzUa3xpUpcM/zhUkTAD88"
    "EpwI0JHU2ACj9VG0Mfjia+0XWPim/wLyg8cACZYYTB1hQxDj63I6bb3poHMJQS04UUkIhKpgo4jbb7+T"
    "iy66iNtuu8MnLnWD00AWd9GWD2+isLLQnt7EwEJOJ1MgBuOgeMXJ2rpnVpwyDC1axHOe/Wyede65DA0N"
    "tN9A+Bw+Ir2xYI9ly1i1997cd++DjNWbbeHCWM1DD93PyMgIlcFFLjlI4Y61ep2qhLVr15Ik2olond1W"
    "ApZDZ3/NNe87VQ7AkCt/lKJQM+2Jg7b6ggZrY4xpIk0DGYRMlQOwaQEWGYLRxPUm99/7AG98w1u44Ybb"
    "EAoaTzoeTguBgIsv+i7veNfb+eu/+iuCIGgRttRcmOO6VBCwbNnytmvkh/RYrYaxFiVdKvGOjENCoI2h"
    "WqlQKpU6J4lvFi7b1rxjOgSga7TDExtOaWSJMUaBSXpO/TQWf/xYeudlKKTEJoax0Rof+9i/cP262yiV"
    "QhpR7PiPvNNkqqPz3ycrYbUR6HGUgW5B7L0e9VqpiwvAXHMAWZFmvxgpBSM1w+c//yXOeOrTeerpZ+A0"
    "fwYQHSt4qVRi9erVQHeyPjIy4mR/JYkTjVDtU0gIgU40AwODlEohUfd4GMECMQNOlQD01N+2jS/b3W1y"
    "t4MwOR/RdGJr7xiU5gloaYInM4i1BonEWkG91uSKK64gkGC0QSlBrC3Yzok+0azLRdi2c0x3IpCy+1Pg"
    "5jra2bMRPTDVAZMniF7zboFmBIGETY9t5porrvEEoDfCIGD58mXZAC+SwHqtThzHPgtR9+ZaY6hUK4RB"
    "2GVvho544flAMNmX7DtE4h+g2AHp5ZR06ZnUeFl5gM6UYAvLdNipenNytNIx2tQgqLsSUf59WiGzvILp"
    "+W191OZs41hGfDXawcFBlFI0DIAmSBNf0GXCT1Yjl/9u8z/mLiQEPr82mNhp6WXuMKfrdVl3lSJKppfC"
    "vGuz0xV8sifmqa6LTwevp7PWGW4ajbEsaSe+wGvxCYRUBEIRKoXWuqtMrpPEVxAO23wfLGQcndEaFSjy"
    "wQUCkVdwirSp84mpcgASqHTbYYBqterNJzM/QBYCfHQA1hpM0kTKEkIGOc/vlia9H4QQ2CRCyIByJeS0"
    "00/hnnseILG0pTKfHRSvboHIZcjAW3AKhENICIXLhpRmv+u4aoH49E1p1uMh0+t0twq0NPCpF6qzUxQy"
    "8VhL53N69+D0+UTa0RKbJGzfsd2d2uWulUoFFfSeNsZaSkrRaDRc7YneKb8WhAg91eU2ZBwlxtDgEFLJ"
    "KfoBLFR0c401xLrug4QSHypqJmj+yoWVek1/uVLh9a9/HcefcCQGKJfmnh8SARBrSAyi3D7zpHRKNa01"
    "NkkI8VnMCpsobMUkSR37e2y9znebQdqWa29gjUvikbr6+nmfmuhaaPc2ddfx1wQajQaPbXqMWHcv2jU0"
    "NEi1UkFKmb23IpSU1Op1ms1mtsR35N/3tWXmG1PlAEJgaa+d1YGq05KKAov5BIPAgIkdFyACkBJhS1hh"
    "soCR8UXalieaNQlCBpx22il89rOf4gc/+AE333wbtdpYawWcROxBv1W41/WUkpRLVTZufISbbr2ZhnYL"
    "VRpkE1sXzP6UPVdygFeWdXuu4v0mWtcg/d6R0rxnR7bMqrEIuPT6a9EpEzDO0Os0n7q+iKKEbdsdB6Cz"
    "PS0rUKVSISyVfE3LTgLg8mA4DiBOei7yMTDSu3Vzh6kSgAE6CECrQ5ctW0xlYBCSHkaQ3RHFCeX/ShJs"
    "PIaxATJwySGElZ2ZvjPtdG7QWIkkXaIsmAiE4uijj+Too48EYHTnaNtkkhMkAr0mYAcK13MZbgIe3fQo"
    "T3/GM9hU3+F+zzU7kPDsM5/Gn7zyDxC76qgevg79lKH9iEFx8neKEoZAWaLIiVD37dzJbbfdxiP1MVrO"
    "y+OLobI0iG40kFIgSkNs37KR226+mZCWT6pIeRGrWbVyH8qlKsYUvTgdyuUy1jTZvHlzVn7Oig5rQ8QC"
    "cAOGqROAvXHujF0vuGzZcjDaKUqm3LTdAe75jI3RcR1sgBRlzwlMwBogDFk9gRTWmQdTO9/Q4oHW9+y4"
    "CeoYxlMEQlcOQMcGIQUDlYDBajm7Z/5UYaGkDYMxDKkBysWKG8J0tCydvG2TXPR2HMomfeH8PKRIUDIh"
    "lgqrQkZVidCYNs+9bkhlf2stUW0XIFE+KeCtt95CrdZEAyGSJgabEoDKIGv3XUsQKKLYKQytT9uehmRY"
    "a4njmM2PbfahxF3RxMXTzDumSgD2oUdao8HBCitXrkQbg81lDM5QpJq7qYSQDbC0BJqJ0XETGVRwyVBl"
    "Ky69H4rHeIagFWUnsokjbHp3GI8ATEgEgA4ioMIAsITK1U5MkT2vZ69DA2UjqASyK6HJPOzS63a9d+/v"
    "onCd7tokp5QIcQ5VpVBmKbtSIjAeDTbWYrAopdDWEI/s4Dvf/x47x0bROBNZgEJjkAQML1nGEUcegwxK"
    "EEcu2tB3X9a/SULSbPLQhvshbkL3xDhjwKZxmjZnmCoB2J9CeuNUWVMpC1YsH2JBB/TMENzqD8qCJcHY"
    "OjYOXb5/Qm+DCmh3JfZIJ56Po2i7aupEJADjqy/nV3/beWwRxYE/0aBBnUTOmUVHxGlm2zYOxW/a6Tl0"
    "nLi06cX3Ldu/Fxb+7ijOE9F9V6YSEQmChDiOkUKh47zIaRDdot1zk1FJSRAGCFWiNlrjsc1bufzyKzNb"
    "QoylhCIhBikpDw+zz777OcuNVBhsy0VapOy+IUnqbHt0s1OmdscjuMxa846pEAAFHJR986uT8PV/lg5p"
    "Dtx3KUolaP2EcAMaF1L7LpQNhIgQ1jr7uVoMtgJ4u7pI2l1P03JpVrccb+gtNhRc2MfFdLzpVCjBWCya"
    "OEmymecKoZHJ+9pap2yTqbuMKBAj0fZcnpa5z+NxfT32iS7HOBk8dBeUAWkNBrf6e0rlFdHG4uzzIn9B"
    "SaBCdBwzUB3ku9/5Mvc+uKHQHANYrIk45NhjWLJij1bqMKFaOh3hqgFJBSPbN7P+ppsJZYk4aWJzD+X1"
    "BvcAo+P0wpxhKgRgEXBI8ceU3dp3nz0ZHAjAap8W+QnMCRjv/ec9BaUwWFND6BBExQ3KCXdxF22JLdi0"
    "05/nnK62rDlpK60taPqLnEiHCJIze47T/r46I1u4tg3AGlppW9ruSk+K4hE16sSxZsuWTVx00UW5PcJZ"
    "ZxBABaplznreswkrZWJtsMiWEjA1PYoEJQSbNjzEzs2bIWn20kXcgdMDzDumQgD2Bg5sfW1/xIMPPpih"
    "oUF0or23FbR3QT/N1G6ELk13GWJip9GXZZARWR9lgSfFk3KsfGF//+IhMxtPJpBYYTF0RroZ2gdMm5m3"
    "w+wx14S/3U/DeErR0Xu2XWyqNessXryMr/7Lv3Hlb9bljveKPxEiSgH7H3cs+x98CEGl6j0g3ZGpsld4"
    "XwKShGt/fRW2XqOHGDJGtyrB84SpKOmPBJblf8i0pMA+++xDuVIh6a0BfeKgWC7Lw+oIdB1XRyBN75V0"
    "P3dBo+XZaLoS6oXyDN2ctLog74btPw8ODPLLX/yCb3zjG1TbHJ8cRyEqZWyzxlnPfjZr9z+AxDjiKIRC"
    "WhfDkYo0yoDeVePGa651yUBQ3cjxY/TIqj0fmAoHcDw5C4C1GotLgTy8SHHG6Wd4+6dsL7z5BEP2VKL9"
    "r7TGyfXRKFYniAHt0ocRtNjXtvDi1H4k26+3QFE0yxkBKq/w62PV6e8lWYwd8X+7+ZRNwIKU+RL4zxpB"
    "oFwUZhAMseHh+3nnO9/N+vUbMTZzMM7Oj+oj7HHUsZx59lmuBJgxziUyfWTtON1qtYxsGtbfdhf337Ue"
    "Es1gZYCxRit3rhcZbmCBWABg8hzAYuCU/OmlcIBAKGJg5cq9WblqpfOGeiLlA+wD28HaJ0CENTXieBST"
    "lRSjrzffwsqnYLp+S5s457qIGbhfuVwmiiKklDzw4F28/W1v46ab7qa7e7+ExUt4wQUvZtnKlRAq8npt"
    "YUEJRTkMSaKIUhBy5S8ug1Hn5RvrDiuABa7AJ9RdCJgsB7A/haIG1lqn7LNw9NHHsHr1aozeQSCf2ArA"
    "9OmscMowCYXYf5crINZ1dCwpBQFSBoWzobOPCll7Zp0gdL4j4ZNgthxqBNIvwdLLu0LIrp5wCx06SZAy"
    "ZPv27XzgAx/gW9/6KcZAtYIr+iQgzQ6EFDzlyCM457zzGF6+lNG4CThLQuqX4FzeAaPZ8OCDXPbTn7nc"
    "+NAyo5Kt/o8Bl8/h4/bFZJfpM4A9Wl8NceKCYQRw5BEHgomRwqJM3hTcK9zjCc4lCOOSh+g6cTSK1Q1c"
    "0Y5WAY356I+JlKVaWJxIDxR0L71gTOp/5vr4jtvv5C1v+RO++pXvkcbz1BteyrBeVBASJLzsD/6AxXuu"
    "oN5sUhtrALIlxgifGrwZMyBDbvntb9m84UGXZkTELnVcO4G9lnGK6swHJsMBVIFn0sUpKyhBJYTTzziC"
    "gAbKmpzbWAEtn0n/g/Bfezi09BuIRS35JBelXvedCNyYkpltvE2+lS7JrrIJwrjQ02YcURlYAqIKqozL"
    "mWja3dU73HV79Etx9S2mDBoPbe69BYedKEEgCISkrKagIsqaVYy6Sz/3aV/7sJi20UgIhcH5WtQadX5x"
    "2WW8+93v5tZbb227VvqklaDKqE6gWuHNb/9rTnzqUxGhK3e/aHDQq/xd/0uck1YlDNi2cQPf++//weg6"
    "qDgnJ/lgIksC/EAg2grq6HkOmZ/MGz4AOLnbjmYTjjtmL9as3Qttm0iTILR70anyJUNqNTLt2YK6jfPu"
    "VvB2iC4UYjJZZacx/939c55l+VdpERhpcGHC3kvCWEyz5irPKkCUADFOyLhzV+2GTg/riT90y5OuSzSb"
    "dn7yRuMTu04X8ysGxlq70F1tuPjb3+Gb3/gmjzzi3fBTxa3/qIHRpA7BAM984Qt47ksvYHDZChLjKl1L"
    "N/MxuRcmjcbomKsvu4zb1t3gEqmkroSW/KC4G/jZnDz0JDAZAnA2sKrtF8+CKQnPOOtMhpcsQpUlwgSk"
    "TtLCx7FkdD+fzK5N1s19yVHPCVCAwvdefuM9MN2ULN0mXrZ65cxk1uX7Ryjfb96HWIbIcV6D7NW+4n0n"
    "UyAk86TrjEEQyvHLQblCKawgcv8Q/n1qfNTgwtcBKD9pAe6774G2fYOVMs16MzMwGAQMDHH8WWfx+j//"
    "c8Ilw458S4UUKuMW07EsLJgkZsvGDXzjK18Gm7TTu/ZX93/Ag7PwiNPCRAnAIPBcivybBalgyRLBscec"
    "TDOCRq2OsoZAB4AkkabdjbVXOuvCMphP5NArTBRwKbXovb8fplTANIf+k8CNCCNcbS+JQcoGYRCBLJGE"
    "ZSdvTrJ9xftOZDJ2v0trxApLFua6dfsOtm7f0feaCxkWCCtll5ijCxr1KMtqlCBABBx80kn88TvfyepD"
    "DmLryC4GZeB8/63xCu/8FQyhMVz6ox+w4fY7XNWo/OLVOvYh4FvMgUp3suhHABbhKpk+Bzi92wHSSKJR"
    "xUf+8TN8ogQDlQBpJcIGYCU6RwCM6CQA6V9dGOh5KgudiSJSFAf+ZE1Tc0UAUueTtF/AeflZocZt80wS"
    "ANeKjkDd9uv4781mky07G351dP+wTmSyvl3WWldpN58DsV93TtYPoGsryTirfhqPZtP74nsOqVwOadYj"
    "EG7MlcMqtTiGMODAU0/l7R/8IPsdeRQjjRjjc/7ZXMMbjQYDA4MEgULXmtxx0zou+trXQCcEQUAS5Ry+"
    "smc1F4FcMM4/efQiAFXgecDrgNNwyT86RphEkhjBrkbMzbc+kIaEtLHgqTd2FghS+Ater9Jj/GaqrR4E"
    "oMj5TraqzLR1AIUR2G8CCCuwxi0PbgK1pJCsLV10Jp0X6vN9AqcUkX+UNMTfaWrS1Bi7KYQ3aBrrJr8U"
    "hGEFrTV1rZEDQ5x53nN401//NSsPOpjIR/uVVYC1aXkxAcKwaGgRO3fuZMnSJWzf+jj/8dnPsu2B+1zU"
    "pi8JboXIE+77gK+wQBNkdiMABwLvBF4ODPU60dmH3aBQwgXABUFuIhvhgjOEbjPXSD/w02Sq7li6527M"
    "oVfvLbRe7d+eVAB3f7NJKVvExHY5vAPF2TwBHYBlfAJlsS2ry3zN916PMRMux2mVHmOJm3VQIYtXreKl"
    "F17IC179aqp7rGAsjrFSEVqXVli1+XhLao0xhhcPMTq6i29+4+tcd/VVYFytZ2FiJMpVI24FwXwZuCWj"
    "7R1Wnuk/1nRQJADHA/8CPK3fiQZHBMKwRKks2TXaIGlzd29XgabonmrxdxDpqj9jE25i/Tr52yx8Rd94"
    "cNl/8jypc/ChVOWYU0/lLX/1lxx01DEESxdT15pmoimrAOGMd6Tcj8C5eVeDkMBYfnbJT7j4a1+HbVvT"
    "q7ZEJfBBR/wGzJeY92neG3kCcBjwKRzLn0EoiW1L+ZSPuIJYG0zTr2YSpBG+E1LHlvYhJ6cwoMbrPTvN"
    "vu2SrbWwf3YhEV3FFid7Wh/VNkfjRwAl5RwYksQXLLVO4+9D3qZtBZjgKWaGgoxEmkpNKKyJoFpl7eln"
    "8MIXv5RnPuNsqosXoZHEjQSDZCgouwxM/lyjJKEKsI0GJWsZMvCLH32f//jwR2DL4yAVyhgfD5MbTdLu"
    "BP5ZIB5u1wcuLKQEYDHwfgqTH8Bq41xYfaEPoI3dtFJhpQRrXSiplNi0oKU7ODtWehfSiWIiiS3tdG3V"
    "uZiFfkkqJ4pJWSFEdxIkMBhrkV77nLt6+4EdDgF9+sO2P6/0Oe2c1dZAYkC6SDZn9hLTVpTOFwRQCso0"
    "4wYqKHHQiafyvNdfyKEnnMiBBx2CNmQWAmml9wfw5mufqDVUilAJmlGTUqi4/cab+PJnPs3jD9yPSnQr"
    "2ZPz/2tZgC1fsYIfzPEjTxopAXgp8AL3sTVAlGdstCtQ7/YJ6zREmTnfkhgJSZJLX932J4Pp9uNE0WtS"
    "TXNsdozt3Pe50C/ofquoUAXBseDlUKSKkzCD2KJNQPhqznHskpvaxMmywnTpqNlBb/LVa8/4C4pTuLro"
    "v5NOPIWXvvSljFlBnMRYIwiUwpo8kXNJUcEiLdhGTDNqYuIG6+95iA//wwe4/ZornMKrC4frr3Il8C/C"
    "tpJ+9M7KPG7zZx0BzrnnQroUK9QIVKkKUZPK8uXsd/DBLN5zBbHnEsFViQmEJE6aSL+a2bynVOGaExUB"
    "JprU0o7nRjcBiMIKOtGqNb0wWTNkL44oZa+VD8kRQnTlSDr9ICbPEVkB3nETE2sWlSo0to/w61/8Ah3H"
    "uYSkOsvxkpoBFzoSHaNUCZ0YBgYGsMaSGO0YHaEoZl0S0llphBQIaygJCEPF+nse4m/f/Q4euO4aqJQh"
    "iRCBWwsL7+Vh4G+BB+byOaeKAMHZwDHZD6WAJGo5NOhYc+oFr+Klr3wFe++zD2qwSixBBymD73MCekXL"
    "eGzzdCdTL1l5OsjLsdOd/CmmEyab3TO1c1sAFzwkgYHBau53Wt5pbW01/YN9hMRK5/TjRADH/AZYgsSy"
    "feNjrLvtFnY++ijeld5FAvrz02o6/bFwAr6McRNcWuGeRYiMscn8U4ylXC6zc2Q7w+UyQaS5/uor+NhH"
    "/oGHblrnGLC4CRYSmyC8Bczzi6MK9ffAL3u1ofhe5puEBsCzyOX4T6LIlavWTv475RWv4E1/+XYGhhcT"
    "Y4ilIJFkCSGzCZSXLdMPXWLfJypXT7SwxUw78kxXDzBZP4RuaDHmxidcNZlnZFB2BCA1T6W/W5lmpnHn"
    "9my2JyzGWF9TT/tEGY7lLVmLlpZYSuehaCV5Ycha79thTc84hYUCK5yK2BjtMzV3ovj+G40G2hj22msv"
    "tj68kct+8mM++ZEPs2PbYxAKl+ohhWnr5wj4BM7mv7A7JocAOK7tF9uaVMv2P4CXvfb1VFesIDaGWjOm"
    "pEoIIQiE8xlLRHHQ966NJ+zk5OqFwAFMRQ8wUzXupW2FnqY5B+LEEd0EUEJQMsKJAdqLVz2VgO0JSax1"
    "Ez8RwokAaLDO4BVai7QBLn4hNW3ZXMac3Qc2M8d7AmA75fY8VOAsH3fccQdf+fSnuf4nP2bs4Yd8EUSv"
    "9Ot0wtJYPgd8lAWS7HOiCIA1+R8ys58UHHn00azcdw2RVDTjBBWWEcprrW1+QqbDwnSUrppOXHn+XCu6"
    "r8bTjuXpc98pXXPa9L/d1JqGGxtgrN5oO2pRWCmU5uqRaKTgriuVcLpcJZwFoMNBRc7AcywEWBBez5Ef"
    "r1ZihPBJK9yipSyUAsmVv7qM//j853jg8l9DnAACTCtFemF9N7hV//3Arrl5pplDgJUFb7+UQkpWrlpJ"
    "JSyhhSUMJc1mExnkCgJZCLQ7x03OiawPu7FL6Zyh3XTaxlFkg89gLYxFDQKhUIFASkkgFSJHKVVLqdB+"
    "TR/Yoqx2tMEL+ApnAhPpjBDtfK4QLXNut0CsvuiTPTgTfzqIzxR5D4Gb5NIQK2jGEVBGUCKxmvKAJY5q"
    "KCu49dp1XHLx9/j5D35MtGULrjc0Ga9f7EpLguBLwN/ga/1l8f1Z+9vdOztpavG5xp8fkzu6PwKc7NJK"
    "8umz+UqpGBkZoV6vQVBBoliyZBlj9TpGtA/QFgFIL9LjZQnTdu5EMFVb/FQxEzL8TKIj9iH94Fc0YyG2"
    "BpG4ElcVJVEIZ13IKxL9dUTKuYm0gIZwwzwTO3L3tZ06gN0SwpJ65lZUiBIlGtpVbIpGR9n08D384Fv/"
    "xxU/+wVbbr8bmtq59hL7MOGumrsm8BngA8COOXyaGUWAy1C6f3GHtYb71t/H449tYe8le9FsxsS6jlCS"
    "VjRbylbJtmSJvQmA+zPRSSYtzEdxoYVGBFK094evg5drq9QGqy2BdNyAQqCy1apTOeiIgVcK+uu7/H8W"
    "S+CIdU7G2m0lAuNYfWVAJjGD1QHGRnZy/73ruewn3+aH372I0fsegOqAp4TCZRHqjW04ef9TuDz/uy0C"
    "4DZyBKBcHSCKIqzW3Lv+bq7/5eU8f9W+LK2WiS00TYKWhkQAQrZpnlsTvwdj4tnZzpDUHhAzIU9PDlYs"
    "YEVXl/6Quf4XUmASTaI0wlislJSDIJd7sLPfpXGcQsokpJy/6rRv755IH8yAsobNGx7m11dexA9/cil3"
    "3noL8SMPtOSsyLhgHhKq1UHq9a5zez3Ozn8R7TaB3RIB8Cvg94AQoFlvZO6lyY4dXPT5z1E2gqefezZD"
    "ey5HVco0lfOgNcKgTJ79T0OExoOZFAcwH07Uk+EA5jIrTk8/Bf9BetdhYQRCWkIEUus260BmYRDCp7V2"
    "Pxhf0pwkYbhcZVuj4RJc5F6Alxx8VmCROSeNTyjml5y68GvAWH540UV8/UtfptmMoZEm7PRyFAqSxPvz"
    "CxqNho+FcJyAdCz/j4APAjdmpLQvkZxZKjrTGrQA+DHwJuDg1l2sdz811Ldu4ouf+DBX/PIHHHfGqQyu"
    "WEGkIPZWFWWkrw6bYpzsNtDfV70L5ooLmIr5bu7TYsnehIBUQecIgEtl5SZ/sQ9dUkuT+RMYLysEGqoy"
    "INo6gmg2fIKQ3TMfQOo8lbb8sYcecu84Z+GYRDDZ3bic/kfikuQsRFhczYFNOE/EzTgdX08EuEKFFwHv"
    "aduTFjzUo9AcY/1dv+XO6y+DYqZYKwtEbhyKn9lkJ4m5YkWnMpcnqdScPmSnjqXYP0I4Li5zF9SdzyZE"
    "bkmnFVTUiKmUB9C7msR6DEUIWUIH25bdaWKcUtEcOZFzZhapMxUAtiWCakBL696hH8eOQOQ8HluXOQT4"
    "RzMvTzApaKCBm/zXAN8Hfk4PRWVavP4/gGfj8gE4pOy3AFmW6G27XG/kSkY/CboPhznsny6+li4yTbow"
    "XmNMa5XLtzX9LKT7nGoLhaKxcxvKSsoEJF5ky5sjdz9eoAWZ+9v+HF58tWSmT2nbXmUpf37+rPlED7em"
    "Ki6L1yG4QL/LgI/jXJTbDk+X8/twjgyfx1X/bbN7mppOF4AJDO4+ikAmoiWY5VU1Z9vO+8D0erTJWgXm"
    "V+r1Rqv0EWXu+dJ3iPurLIRey99MbCsuRijvBTkFStbpduBa5b/Pj2KxVelYZ6u/D/v1k9yJBNZlYbat"
    "cPb++SL6PdDsPrClQAQ6HLoYwCX0PQH4MPBZHIcAtI/VHwLvxrEO5A+QTCb4owdSbqLvgXJmJpDoskkz"
    "rg6ieHjWopTwTWDrkM8nuc00sgLGxnmyep8Yt1lQWB/QlXMsMAKDwGDR2Cw5STo3LOwm0YDO0wFaIktx"
    "k5nFw7jCrrmFaxKvfd62FNmc6XUA7AX8A/A2cpG/eYHeAF8FRoAPSKfs2I3RZaKnYk3+bw55wmO6H7Jb"
    "opOwtJ7U+blJZ/XOWIVORje17xjfKRNXmBYY7aJjU59iqTOBdKJnEK1VvpO7m1x7FgIRTFvcLdzJpmnp"
    "3dcBXL7PTcAXoTMnoAEuBu4E/hh4IcViILsFcoMuz5J20ezkk5To4vHd/va7c3E8THZ8zDQb0O3+tqUE"
    "i8GzB9ByWzWuZl4qQ2TZ8UwvmXPBwmKRNk27ZrDSa/g6zCLph0l6PS6AzsiSYqVc6PiHDwHvAq4HbuyV"
    "Fvx2A3+Jy2j6HFxR0IP9yYqpDNPpE0oDVMiFLk/kfsqHamUsUSr0Kxz50zj1TrkEYQA67rzWeESgLb95"
    "9zZMGtMhAsV7NiNXukmlBS5sy50w/1xpv2hXFciMNiA2mLEk4wjyVZ7acgLO/yLYA04hqjGUwgBblujQ"
    "YmSSWy5bBG5KWAjVkVJLnAFGmhgFUiikhaShu72fpwBvBv5ivMIgMY5KXI8rELIUWI5jI+ZSz5VO3UOA"
    "t5JLXtL9UMgrIrWyLaK+CMTSKsv2XMaqfdeybK89GFy6mHK1xODAAKVymSDwq51sd53tpQgs+gEUdQCT"
    "7aiZWFDy91RCUlIBoVJIEboEIgU2xQrpPDuBklAEVrHz0c187uP/jqmZLiLB7gOBpURAFEecetYZnPuy"
    "5xIFEVGQeDfowHlDTvX6c24GbsEI9+6E12MEFnY+to0br/stV19+JeZR7Ra5LmsacB7w5YmWBtvlt4dm"
    "pukTQToVJLgiJX8IHNXzcGEcNTaCTIKvAMOwaL9FHHb0kaw58ABW7b+W8vAAg8uXUBkaxEpBYhO0TjDG"
    "InNJTkxhgetGBNryCRT3TXFlnLl8AjAUlAmkIggDpJAuK06OAKRuwlp6Ra+2LFJVxrasRH8m6Wln2h3g"
    "mu7XDwVrDj2Ag085irFyRK0UoaWhrKfnaDYfjmApLHmHPAgNyBhOfO5JHHX5UXzt379M/a6xXgRgFfDc"
    "KdR/nlMMgnkLyHcCe+R3tI1L6d0zXEobELD8gL045PhDOOaZR7Ni/z0ZXraEhk4wJUVsDXVidpltSBUg"
    "lcy0IVnJK3/pvONLN/QbAPORUSiFMhATUbEBgVaZCNBSXEmEcVYX4/UCg6UqY9qws7Ezc4PtihlK2z3b"
    "sFgiYmSlRN0k7CJiREQ0RAQ2JvGr50TQdQGYF6Ovu6eWrbkd+M3amGVLlnLM2adQrzf42nv/A6UUWne8"
    "SwWcEUyavHfaGQsY/3r975YdsQfwd8AbwFRSlfzQwACjtRolFA00QblE0oxcnyyGfU58CoefeiQnnHEc"
    "y9fuTRJYIhMzomMSa1qhnQKkkFir2zrH5hLfFR1fuqYl7/c0fSb0bK4gVnrTH8ZLwwKp8rpimWnhhX84"
    "YzXaBqBDt9mIVAqzXhowgDU2qxmwUNkEp8cUKAJ0FJEYDeUAWTZUpPHm7VzEZL/rTeC4fiJj50XbR1Cx"
    "BF53btC9M0WBDksgEOysNwjLIUefdioHH3MN915zZ6+7H7pQOYC1wEckXIB/2rSfarUaARCWFFHkIt9Y"
    "BHsefyBnnHsaxz7tWMRigRgUbLc7SbTLbmyzmHBNW9RioYOFadmNU3OXyH2f6WE+paQaE0XKGGEQ1hMA"
    "RNvzm9Tvwo+ktFipJWBisv/CzhdgEJkFSEtIZCv0ebK+F9JOgKDnjm1rRy9HqF46o5QQpF9Tva3N/wqq"
    "wIEIJdFaY7Rh2fJl7LvvWu6+8raWArgdKxYiAdgf+KSE8/JrS2qD9oFd7IoiF7+4T4UzXvJcnnrWGVQW"
    "BcRhE2MTolqMEQYZBL7zWp5frfDlLtNZuAhPVxkOcgxD9vtMQsx48oHUlCcJLARGuYpN1vMAWZIPN6jS"
    "Pm1LNOInyqx5J80RsuGu3BbLXAyDcJ6QViRTIuqTZfwzvUzvVrr96XgrEIx+bZS5cSoFmERDFPTTbxQj"
    "e+Yd+wL/itNQAm5tycZhfhYOwv6nHcbz/+x1VPdeQnmwRL25k+pAldg0kMZiSdpYKGsMGk3gU5h3Y68y"
    "X5jC77Plwjqb80tYiRES64UAhQBbfOULk32fCaRcW3HWpTkPJEzYhNlvwnebaMXx1U1J3ObNZ9s/G9Fy"
    "RityH/nPbZPfuuuGQiG15aEHH0JKieleQWskmPQInD2b717APwHPh8KQ9GN0oAw1CaWVIee84nxOft5Z"
    "NBcFNAJNzC6ogDY1F+0l0zcvWznfAWsEMYZSqeSUf4A2Bp1VNpVzatrp52s+WaQyvVvxFUaW0CpAqJI3"
    "4rcTAOWYZIKMK5AEVhAY/AicHRKVsqPp31QJKQt9P20dSakEugnVEqUgRGpLIC1KG6TPq+ja0Ud31acZ"
    "XTNWd/m9YyEp6gDSn9NrdFFCO/NfeoDMJr4yECIpCUWoAm6/9TbuuXt9r8kPcN9C4QAW4RR+L2r7NSV/"
    "gYDIUpOw5KClvPSPX82+Jx3GiKiTBElms5cYNMb3acrytzpYBUE2nrWxiMiAVkgbEshyq0pQDyLXqpAz"
    "E4/srzkLEyw17UkLgQmQKJR1VgCVr5QrnLlUYlHW+pRjhtBKBiihghJazE6WaynT9+MVWmlZsinFGHTP"
    "VyAtlCsVaomE0TFCLRH1BJKI0CYIazxBlOMSml6Te9wWiZaIVWxT+4ETUwK2EQBk2z7ImwEtZRVy313r"
    "+d7Xv0Oyfdx0ANfPPwEQBMBbsbwBkG000LoDMBaGoXLE3rzqnW9h+X57UC/FlMshJDUCA0bIAtVsXSfl"
    "Bax1gS9CCISSBCIgSErIKMBoTaK1C581pqsyZzYIwGxwG66dGmsNVmiMlBgVIYRsS8pqpMGKBESCso4D"
    "0lYhpcGMNRH19oxAvR+CSXOG2SQ3qaNRoXNTBWRHZ7f5h9BPfKmN7AApoaQY27INO9pABg2EjT1brdyA"
    "kRN7DxN9W8q3LD+BuyVyyXMe+f2KdiKQ/65sS1GdXj80UEog2lXnunXXcvE3v8XmezaNp5/dAfx0/gmA"
    "K0r6l/h46zRSx1unMdLCIKx9xtG8+I9exdKD9+ax0c1UQglJQuAHgIvdFmjh89xmrLCjjmnqMmUkI1u3"
    "sWnjY+x6fISNd28kGosYGRlhbKxGo9FoC1DJO9Xkv7sv05edJ8QBjJNleTwYa0FrpFQopZBSZPoPACOM"
    "c4sViYuEEwaTCAZLi9FbY5IddVzRAO9MU7y+oLfTUnp4juBY4QrJaOm8kbWUjI6OknIrysDQwGAmxyoL"
    "IZasIGH73f3f3lNSYAiEIjEJypa49he/5t4Nd6FVRKBjpyMxZQxBXxGg7bq2nypYZ8+btbaHFcBa23NB"
    "6Ti/MA6KBCDQUNu2i60bNrkEZuNTq6uByzsJwOzJ+N1wJC4PwXLpJLJsR0hAIpym/6BnPoUL/vQVlFcv"
    "YUe8EzWgiIWraydM4HyehTP5GCMIgxJhWEYkIOqWZKSOqVsevPt+brj8t2xa/yDb7tkAKMddeNbTfaZF"
    "Nccz2RQ15FPl5CfS372Omcg9J9OuzIi9uTXnhWVCS3x2iMydCyiXY7g2Okp1yTANYVl3zx18/6rLufWB"
    "e7h/w0OUy2X2XLSMNcv35GknnsoJhx3JAavXUI411GMfhJAG8ljHumcERmRxCVmewmzVFWhrQSp0HFPb"
    "HFHbMtL+vPm25vtg3H7qxweYVp/k+6fn9Xp8HscHoCvxL9Lp3qv/CC73x/b55ACGcKGJR0LaZYK0FHWT"
    "CALY5+mrePmfvRq1vMSOeAe2EmZlstLBZrLPAoWkbMuUoxKinvDY/Y9ywxXXc/3l1xDduclTihIlXfVp"
    "sWMSGzuLYPeFjm5vwqleTO4IMSXZYGLibq8B13vVyvakK0fPAdiaTKnlL7ULWDwX0YeKODNian4sbAi0"
    "EJSWLeHeLY/zlR98m//75c95LKqzzVecZ7TBHY/vpHzf/fxq3Q0cvnZ//uBlr+T8pz6DZnMHpVgjSikn"
    "YpxvRqFgSa+WWc9hCT9QpJ8UrZyA+b9pP/eb4BMkAD2/90N/QaMzac6E72lxQX4/gc5w4LnEK4AXZ9TU"
    "K/KEBJsAAwF7HbmKF/3hKzGLqzRJkEGAsY7dEb5uXmoesUgkAUEkWaTKbFv/MLdefQM//vb3YWvDSTxl"
    "XN53ExGjENb4SHfGmfz02NFFoJs1TFPUEN1YaI/c5J8KDKkzip+QmasgIKA+MopeNMjVd93Kv37zK/z0"
    "jjsIA2jmuSzhTosNPK4jfvPgPdz88Q9z09138KfnvYTVi5dBo44wEUiJSf0U8Kms21CwIliwWOf5mXEN"
    "9HjX/fu52I3d33rvyTix8zvvN/HR1fcZvovLDNSA+SMAB+Mi+1p1xjxLbQVQgmD1AM957YsZ3HdPp/Cr"
    "VjybnluxrCMEykikkCgTIGuaa371S6767iU8ft1G5ywtcSNF+y31EZhCw9PhVXyRC62OXqYi69eu3P50"
    "9U/PzxJi97yD1+QL43UFnRfZmUj+90ff4wvf/xYPjI64RPpKYpIc4ZUglVPM1uqamtGouM5nL/5vHr9/"
    "A284/8UcdeBBDJUHsHEdYZLcC5iAH4Ntd3Tq/676TaLZ9pvo6/bj//bnznLQwP/icgE8mv44aQLQj/GY"
    "AALgzSBbGYfSYJ508KwQPPfCF7P21MOoVeskgcXqJEt5nW9JIAIGywOURYWH73qQn/zXd7nj59fAwxBW"
    "IU7Tv+etId68LQTkUsD1xXiS8GyqAKaKNuk90yi1ZGX/ldR+Ir1WOqOZUtHsR0GMm8FGWGrNBqVKGSMM"
    "pZLit/et54uXXsL//PynjGKpqoBAJ9jIuMAV4RgyIUBHFhPobIBpYMTC/95wJTesv4s3v+TlvOAZZ7NH"
    "pQz1BJmAqlYg0VmAUxbIlWPvW/4GZMlf8uqbyfb/dN/XdO8XBooo0eMc0RUbgc8Bn8bXMEwxHxzAScAr"
    "s2/5N+FX6sPPOJ5jn3kSO6lhlXChqrlnNsJpkZWRVKxCNQXrb76Vb33hG2y99kFXrKkCSRcTtlR+YBTy"
    "JORXvmJ8BV2+d3AA/Z+7K2aLAGQm0ex7Ttq17ZxBemyaI6WEY5yaJu100Ub9Uv2LNJKSlIg4hkAytHwJ"
    "2xqjiEqJ7/36Uv7ta1/lhq1bqQcKEk1NJ86VOiVG1v9noFwt0WxEbR1pBNSAB5u7+NCXv8gDjzzMa5//"
    "Ag5ZuRqRNKGZYKXFeoO7NcIFKaUXsDBQKVFrtKh/qWBdtFOhBhPl2/thsvKAhSjRlAJFYjVCCHTS86Q6"
    "8DBO1v8GcB1d1uu5JgAl4PXAyswDvaXbAQmVfQd5+gvPRS4dIJCSBk2E9XXwaE3+SLlM1s1RzQM33srF"
    "//5lRtdvJQRiz+pbBZlK2PqB78d0ICEIYY8VsHjxIlbutTdLlyyjWq7kmts+/fOJUdtzBph2R5JJmAfb"
    "nF46tMsTlcy73y+1+TulmfDK08AXDhEYAjAV8u7BwliUEOzcNcYPf/xTanEacOrVZMXxlhgQAZE17KyN"
    "siWp81/f+SZf/+632Bb5wnl+kC4qD1JvuoS0WVIiabHa0KxH7l3595RCA1vjJjuBL1zyXe7ceD9/8vJX"
    "c8rBhyEwDJWqhEQIWaIUlimVKpRM3NIN5fr3mCMO5djjjmx7DpNmTE3RVcPf+q1YBbu7h2BvHUB7bsIu"
    "VbJsccy1bP4gkSrkjjvv5KZbbqVe6+mkdSeugtHVwAbGsQfMNQE4GTg/+yb8rE87QcHvXXAe+xzxFLYm"
    "NZJS+4sxwrj0XkIQGqjEkgdvXM+3/vXL6Lt2ukptzrkNyqELdYhiSFkm4cbYkYfuxemnncARhx3Aaacd"
    "T7VaZvHQIqoDA75Szji25XQVLNjvhWi3CkwU3b3epucc1OEzbqXzSiNg8fDyloeaDbB2ICMAwuKThUg2"
    "bd7CNddeS23TJvLvSHt52kVNSsaaDYaWLGJXfYSbH7yHf//fr3HNnTezJXbBN6UgIIoSBsoDNJtN8rwI"
    "wLPOfhZr1qzhkksuYcOGDW0cVrougHu1u4TlR7fdxAP/vIFXPPf5vPRZzyUUEmslyjo6kxiD0TqzrjSs"
    "zbi6819wHu961ztApBmAWwS8NzoXgf4EoNs1W2JW26/jmfpy90vfYyOKec+738s1v/ntOG3mG8B/jXdA"
    "imCyPOg01B8KeBmwZ9uv2jjtvIJDn34Ih555HCNBhBXWmaC8hj8dtE2TsCioUB5tsumm9fz03/4bfcdO"
    "MBAEgrhmCSshcWygUWdQlbA2oQGcdcZhvOSl53H0MYdw1JGHUFbahcpici/GTsg2l3cccR5ddkYcg9zF"
    "p0cA8g4kbuV31X6FrBCoKgiJFQlWuKfHimyl0VGMCgSViqVc9pMnfS4vs8dAICVIQVRVPLhzK1feso7P"
    "fOMr3LrlUWq4yQ8QRc7DsNmso7EMVEpEUcTee+zBH/3RH/HmN/8hQ0OD/Obqa/j7D/wdV131G2JaEmEe"
    "iXUr1p07tvGp71/E7Q9v4A3Pu4DDVu/rnGC0JpFusiibllDTCOHSZYVBSLUcAklGya11BL9/3YJeXFb7"
    "99b5E+PmuhIA2yr/JgNFHGkqQQDhYh66/WZ++ctfIr0LS8GOCS5r13d6PUURc8kBHIwrUNAGUQ2w9QSW"
    "wsnPfiqlPYcYFc5AHBjpwzeN9/aW6MRiraEyavnhF/+H7bdtdQYN6WzWMoS4ESMDhZQwpiOOXr2UV7/m"
    "Al7xqhexfM8hZClGqSYkTaRxFv2JavGzuOz0rxemZ9Slfyav5UOAXStTzbts89Br5cOXqECidYM4rmFt"
    "7JpSUDYHwI76KI/Xx3h8x1a+ftF/8ePLf852LA0gyjFR5XKJZj1CY1ECoiji1NNO5G1vezvnnHM2QRCi"
    "hOCZ5z6T/fdZyRe+8AU+85nPsLOpvYnRN9n/TZm8R8fG+M6vL2fDA5v401ddyJEHHcTGHduJhAEpvdgI"
    "gXXcQALYlBMWhjTs28uJXfptPLv6eFqi6UK2LSQmASl88hVT5+Ybb2TTY485Ubb7OPkFro7hhDCXBOA5"
    "5MqQp7D1BEJYdcK+HHTykeySGiudW6P0BEBLiL2v9lB5EWxv8H9fvphNN2/JdAcYsvTIZeWUJQJ44TnH"
    "8+53/BmHH3Egg1WFkRHa1DFR3Ve/6Z4UcsLhvxP0IZ9/pIO+XeaV3s1W+NVEKIHWhmq1ysq99mLjQ9uQ"
    "QOyJgFSQaMFPr72aHUmDux++n/s2buBxLAMlQRR5Nbu/RbMeUSpLoqZheLjK7517Du9///s55PAjAIuO"
    "InQcEeuE/Q8/hPe+72848aTj+ft/+Aduvv3e4hO4NuNUDztJ+M1Dt7Phkx/h5COP5d6HH+SxkZ3eDUFn"
    "zTC4gb5i6TKmxcPSPuemosDNLzTd3ahb7bNWIKxGyQBtDPHYKL+87DJGdtV7Xb6OK/AzbgRQHnNFABbj"
    "CEDnI5eAYTjlnDMQwyFaOSWRtM7FVwmX1117WaiSBPz6J1ew7kdXQx1kKDDar8L43A9eqnjT687nve99"
    "q5v4eozRWoxUBhUYZOoc45VF81Oyao4gDI7t9VsmFcuO46x1UZNLly3jwAOewrrr7sjMZ+DYznBogPtH"
    "t3Lf5Ze6CaaAEMaMdeqEPGsKRE3D6lXLeMfb/opXv/rVLF06zM5tmxgYHCQQksTGBEEIxFSqAS968QvY"
    "e/WefPCD/49Lf3GNa1qu1WEYoJSk0YgYAx5pjPCj31zOTiJMmtItq4fqxJg9lg9z0MEHep1LoYEekx0D"
    "gpYj2pTOt+PzD0LYzERtrKVeq3PzTTdT6jAFZrgXp/ibMOZq+TpawvEdN/Mkes9DVnHUmSdQE02s1Eih"
    "EdJvwiKFILCKUkOw+bYNXPW9X8LjQAQ2kdm7VDh6MhTCu//sVXzog+9ieBCCoEG5aiiVBeVQEAjh2ODU"
    "m7CgpX1CEQNrvWksRscNSMZa7G8XiHLFZVFKEp7z7OcQBqolj/t+2VGrEeOWmTTFlknNqr5qhFQtav/U"
    "M47lS//5Of74T97CkuEBrE5YNDiAwrVLKgsiwURjyBBQhtNOP4n//u+v8553/gUrli7KVvOSAJskRI3I"
    "vTUJY0RsJ/1uQVgXbCQsgXAWn6OPPpJTTz0FYY3fZBaKnJ4GXhHabcM/T5pRKZdZqc061Ot8213MnMjx"
    "RhvC6hC33347d919VyuHZSctuxJ4bJzR0IG5IgBPA5Z1/CqApXDkKUcSLAoxyhJYQ2ANVhi0dFp/ow0D"
    "skzYlNx86TXYh0YyFbHVwnG1uLE3VIY3vvYFvOOv/4SBQKOkcQRFOG+zlgebZH49oecOLiegEwES08Sa"
    "Zk+F5diWLST1BrJS5YwzzuCYE44HpXKxBTnzZxo8kMKSeVsa7Sben/7Ra/nv//46zzz7aURxrcWFZNyI"
    "weUpdcy61TGgEQqWLFvMe9/3Hr74xS9y3HFHU/aKr7AUoFLzbjozW46JrinStTGxECp42ctfzkB1oMNp"
    "aKEjMy/rmLvuvoudO2u9dNRN4AqcumPCmH0CIBjCVRbqfvdBOOr045FlJ4+WtCEwhkQamoGhLhKiRDOg"
    "yjxy273cdMlVsC1xy48sZxbOlAA87/dO491v/0sqi0pgI5QAoUKkDMAGCEKwJSQVJCUEgduEywQk5OS2"
    "3QZeDIjjJtq2xkhxZRocXkRQLmGTmL3XrOYv3/su9tx3H5c/oVzKzkkJsNTeScuQTf6woli1cgWf+9yn"
    "+PBH/h+r9lmNJGGgGtKSyt0mChvCYE2CSWKwmlKpxPOe91w+97nP8MIXvYByRTLWTIhST6b0vinSZxEW"
    "K6AUwCsueCmvevkF6LgX4cu3aZLd2meFny6EEEgladZr/P/2zj1Kjqu+8597b1U/pntGGo3e9tiWZUt+"
    "SLaxhTE2tjF28FlwjF8hh4eXJHASCEtYYAM5Z5fNkmTDOSwEzi45hCS7OcvLPgRihyR2DIasAVuADRiD"
    "ETI2tixkSch6zLO7q+reu3/cqurq6u6Z6XlpJM1XpzQz3XXrVt2693d/799jjz02lYHqMPCDXq+/GDN4"
    "GLio5ZOEYivoP3sdA8NDTJqg5eVY6aK+QqvRxtB4cYzdO58g3DeO0AIhC247iDUpCti4zuM9734H1ZVF"
    "qB1DKIOUCRVNUmDnWbgTaBHPBlmTojAIG7rFpXV7ebyMKcNai7aWV91wHX/+4T/hjDNPw+oA4YyyyetL"
    "Ca/LqwNYuOGaa7jr7s/z5je/EaUMujFOENSxJkJI27rgOx4OxhiMiRCeZNv2C/j4xz/Gn3zoj9l85gYA"
    "+orC5fbLsMKilSXmN15/Gx/84/+CEJZCqT10aKlDCOfdGAQBu3dPqdzfjXP57QmLwQNvI8P+F4tF5xAS"
    "C+wXXXc5Ub/CeJrQRPi+bCZJsJpGI2RFaYDGnlGeeOjR2CRlkTZIHUU8fFZWDO99z7s46+z1YCfBT0q+"
    "JDZV46LCjKW9mMMMAkpORKQEzwPrAkitCZAmcPKvKjjDPiJOBd6EUC6JaFUJbvv1V7NhdT8f+8hHefjh"
    "R5gcBy+2z3ke1BrQV4K161bz9t97O2984xtYtXo1QThJwfeACF95WB3ncMhkJe523+4rZ740UQNPCtav"
    "Xc3vv+P3uPD8C/jMZz7Dffffz2Qjch7k1jEC0oJSsH37+dx+++28/z+9N80EbU3isSlSUaZ9Q+0yD2aY"
    "lKWDarF5qm39CVOMQfaa1rJ//3727HluqtOexFXv6gmLQQAuQlBOOLZQR03ZcdBn47lnEhVAKoWuW4Rw"
    "CSTAuUGuXjWEGpM8vvP7TO49ko5wsvOAj0Jz2aXbueM3bqZSBai3jKyw8fK3Np5YHTTgJz1iIicM6ACi"
    "AFSZqZwOJIZGfZxqX4UbXnUtl+94CQ994xvcd//9PPPMMxzYf4ChVatZuXKIK6+6khuuv57t27ZjbYSx"
    "EVJJpNUtXWQVb8LmFkDHReYWWJKzpVQp8+obb+Dii7dzxx238d3vfIefPvkzDh48SKXSx5rVa7hsx2W8"
    "9qbXcMEFF8TzJc/ex4rjRa5uZEXvYoIrviLZv38/k/V6N9OjwXEAPT/QQhOAMnBe9gOjdar9Lw4NsWnT"
    "mQiFW/ixV1Yi6AgLtqHxA8lTP4nZn3SrcucUlMBXgjvfdAeDKypgx9q8cqy12Lah6+bYcTIj3nmtxdoA"
    "QUiaiY12rzSjDVIqojBACEG5UOTmW27lxhtv5OixY+m1VgwM0tcXR3bbuF2hDKaOiQzWTsFhzSj+ISEC"
    "Fh1olPJZv3EdN7/uJm695WbGxyYYH5/AGM2aNWtQnoxTYTvlQDPyMXcPVnYgAgu/MfRS+zHUEYVSheee"
    "e46JifFup00AT8/mXhaaAFTIO/9YXBSPtQwMDCCljMM2TSrvJJBWIgLLyMEj7N+zF+qx7dSS5pEc1wHX"
    "XrKVK15+KV7BYkPbyocZi7DWhf7OKHDjJEKHrDlOKorQtoZnCjjq23nSCykwkSYIImeK9X2Ceh0hJOs3"
    "DIMJCIIQYzT1+iRSKgqlElIVGD32Kwaq/TlN+ywWlzAtREII4eaPECgENtKUyh6FYj9SSqQEa12IsPQk"
    "Vju3oBOllmEexhiQ8MKB/dTrXU9LIv96xkITgFXAhuaf8U4gJYSaLVu2UCgUaBBiTC6iDlAIKsLjid1P"
    "M/7cYXwl0KFNubpE+fvSy7ez4bTVzgMoinDeEzLmFpoTsBP7ddILApmJL6wLhjJGY1UDY+tIUenS0C0c"
    "X0m8NMmeTn83wQTgHLWUSkbRYgLnhFbtq7hFmL7TWGmQ97psI8qtCzX7zpIcDkRBk7AI3I4fU3chmmKe"
    "NSZz/W4EYI4zIM/B9EhopksIWuorEkxOsP/AAYJmuoRmwhf34xjOCtAzFpoAbAD63K9ZI60FH1asWIFS"
    "CmsDdMxuZiEsiEAzcuCQs/mHNn2fFkDA8GrBjh0XomTojM+pv7ttRgYuoxXClUK3ukhhpqVxZ4GmzmWu"
    "yOpskvvNr5zU/jcvPS4ZxEVY6/X6VE92GOcH0DMWmgAMkRUyofl+SiXWrFmD5zk/52al2SakBdMI2P/s"
    "LzOEtTWwZWhogCtefimWRoYA2DjI4ySbDLNCJgAISHIvWoxzCGrxPW9/B0sHyX12kedT7XDu/m2XPfME"
    "gTEGrTVjY2Np6owOOEazUnhPWGgOuJ0AAFiDKEoGBitxRt7OE08AJgg5cvAQ0Hx1WZ3u0JqVVCsFokYd"
    "E8t+GLu89rsg8T8XFoSOSGMEIDWXnmiL5GSGtRatteMAus/pcXr0AEyw0BxAFduhDwG2qKmsrqCnKS2t"
    "I8vho8cyLs9ZZxXYvHkTvu9EB6MlMin9mpw6I5mslwl/omkNZOZ/MFa64pGAFhpTG0UWFcKWnAO/dRuJ"
    "yUibU3EF+e9EW4LF+Dpp+fH8BTpo5jt2lHAuOcTnp5ftat7r/I7n23tPdLv/LpjKImAFYA1BFNFoNNJS"
    "9a0nAW73nxXVXujZ3GH3j3+qCC3Daf2xp/peAiW/gO/7zYnYs3ffqbnbSVzlHaMnQU9CXCtPxLkB5Ik8"
    "LnNMqLIUkC0pZq2lpQ5AO9Vw6Q5mgcUlAB2onZ0u62zbgo6LvceXK5fL+L6PVDJNztHs7wSexAsME/+v"
    "wwY2ajgxIE4Aki+HdkIiE613CiAfltVTw4VE+xQSHT+dHl0khUKh4LLKJD7+XR7plJkKPUJgMFHdcQFE"
    "sT+9zITAmhmHti5j4TANMS4wyym+0DqAMO8DJqTExuW/muhy71YilXRcggGvUCIKWnf1Y0eOEjUaTgTo"
    "NEgZ69AyEWgdA4OzmxsboKIaCA9EGZBx+HBifpsBJzXdbtvt+17t6KfOrg6AXyhS9AOq1QoFJWmEiZWr"
    "5bQSs5zeCz2adTotSwUYG6c1nvoWlPKoVKvOxdRkJ4drd+jQISZrtUxSzmW2f6aQGJQwSBuBaYBukBZI"
    "hWk5tWUuYBFgDb7vU6lU0VHr3M78tYJOVdJmgIUmACPk7JM2dm3EWMYnJqa9gOcpBleujH3Mbey66g4h"
    "YO/e5xkfGc2VdzZkzAY5dA49PVUhMWADtG6ACXCl16aYFnnZeq6ydpKXP5+ffxkO1lIoFBgcXEmQmc8G"
    "EhkNBIN0UrjPAAtNAI6QJQDpopQQSaLx2LlZio5OKFaA9SSlgT7HNdh2Cnjg4CgTk1FsLVieRD3DghIS"
    "QcwFmBqpU5lNUqd5p5pSbcnAGoP0fCpV51CbblutS2UVLu6mZyz0Gz1g4iqkLZg0MGIY/+UYnihghIxz"
    "/0uEcGmarZBoCf5ghQ2bh6EAvuc1CYiQaBT79mse+8EvMEhqYY6jyDq22OTolBCkl+MkgsUtbiORRBg9"
    "gdFHQY+ACQEPbKF5NNN+TIEu4zTTHT7/fjrk4DsVkChanXOrZnh4GNX99D5aYm5mjoUe0YM4L6W2ly9D"
    "ydF9hwnGW12Ys3Z/I2AynOC0zadDVWFUzsPPShrA/V/7Jg0t6Kv29xRqecrDSheck3BmIsLYSYytY2yA"
    "tVM7aS1jkSAEa9asoa/cdXKXgdNnc+mFJgCjuNpk6W4spfMss9by/HN7qB0bRYUGJV3opo3DdhOHlIYO"
    "OO2sjaw9eyNaBLEve3zEROXR7/+QZ/e8QBgp58KSjFPX8N9lHUCKjOMkuEhBbcLYJyD2D0jHOjNms92R"
    "l2X+niCl43ZPP30j/Suq7sP8vLaUgc2zuv7cbm9ajNMlUYG1lkMHDhCO1yiGFr/D1i2tQUpNYaDE+nOG"
    "nTZBNrPJgkEAz+75FV/+h38hjDwMXpyxbmq/gGXgiGmm7FcKE4Gpg63TjBVIxnyWmAmxOIVY/JlCCAFS"
    "sG71GvrKcWCty+KGK9qcvrhzmYUlYKFHPAR+mv0gm455/IVjHNn7AhXrUxIFV6Enk2tdABP1cWRJsuXy"
    "ba6qoNUgIgQaiU1zw//jP3+Vp589QLHcj8GDYrFpBLCZIw87zfcnO4STAkya6hOsbqCjCUxUi5WCAS1c"
    "V0uOAdlytCNDhGck35/COplOkD4gWTU0xNbztqIyjyxaE7mcB/T3fPm53t8M8ASZZIWt5bDh2Sd/hpgM"
    "CCYmnc9zXAfQwVAqFTDKsvmiLVTOHXZ6qOw1BFgFP911lC/c9WWOjIzjV6sEQYg9kdJ2Hyck4lKz5qFE"
    "yCYRcFxA2MJ1LWPxEE5OoifrVFcMsmXzOfg5TWBmPW0CTuv1+ouxQnYBL3T8xsIPdn6PyWOjVMp9FDzZ"
    "Ih9aAdKXREKz9syNvPTal8Ng0SUVgrRwZajdLva//++XeODBrzM6OoK2It3RltFEuwbEFWFJdlRpXels"
    "JQzW1DBRA2xAs5AHqZ5mWeG68PArFZTn/F62bduG7wmXwc0QpztLMQhs7/X6i7FCDgKPdfzGQmOfYf/u"
    "fQTjSU1A47TRgBGGKIqIbMSRxjF2XPMyNm7d5CQd4zwfKuUiNt6cRkbhE//zb9j11F6UV8GYuPKryBxT"
    "sZCnwITu9OSdS2EZlHDRgsbUwDbIVvNpXu14Yyncw8LBNBqxPTDg/AsvQPheN3NgEdhBj7N4MUYvKVnU"
    "blMywFHY/d2n6C/3o3yc9tlojNBoLEiJloYGEaV1K7jiputAuYv5VqFrjXRAtIXvPXaYD37w4zy96yDK"
    "VsDvA8/JUTb1IVCdD2ZxGNnb0Sb3zrLf2fafOaTNHsRH8zNniamBPgbRmCMCSYbejOjQmSPIk5l5kunn"
    "RW+w9I90PGWc0doahodPY/PZm0k8gpUnXJ2F5vEyIcRg7rMpj8Uin9+kkxgQs/K7vv8TfvHkU9iGTmo7"
    "AokjmsBKgZaGUEVs3XEBZ1x7ERQgjGlK/iEeeWQXf/rnf8HeF45gTBFUFatKGDzndCRwlYek6Z2dnavS"
    "8Hi3n+pa2cNINxVNA6NrTimoJ7C2Fitho1h0WMZCI1GcDwwMsH37tpbPc9iCswbMGItFAH6B4wLaYIDD"
    "u4/x/Ycfo0IFX3txCa8EMaUXbsEOrV/F6950C97aMo24NGBcTSBFKOHu+77FW9/1Pv7fwz9mckIh/CFU"
    "/zoQfrzYW7XaSV26FgnZGucbnz3sPBz5PmZ6zFf/PfQnMQijsTpAhzWMroGZAFlHEGBjXc0yFhYmJgBX"
    "X30NKwdic2A7Tz2EK8Q7YywWAagDX6GTWzCADz/e+QRH9x5G6UIzHr0tFVXE0foIG88b5td/+3Z0FUIV"
    "W6iTUyUpi/TQzid5+zvfx2c+fy/P7zlIYzzEUMBQwOLFO79pOZpmrpzDynweWQLQSzs5T/3P+D4hqbcn"
    "rAYTYKN6hggEcX2/ZSw0Ei5g+/Zt9FVK3U4TwHX0YA5cTNq9HkcEXtr2TcndySvfdRs3/tZN/Cp8kVK/"
    "h5GGMIzAutgAZSTULeuqaxjdd5h/vesrPPqFf3N1USKapoF4TkqXRoC1VY9XXLmDO+98Pa+85nKqAwXq"
    "k8colSXK166QhDYu3DjOUJyIIt0SMbQRp1maHFujGKdHWwjufJs6jVO8SimRvg9CgIn9BITEKg+Uh/AL"
    "SFUBBnFxAk2WNAnscjkapr4/Iec6BU9OAtQqXkkMEiU9XnzxKG/9nd/l/gceJNSdNkkOAjfRTfGew2LU"
    "BkxwAPh74DKynEdy/zXY+dWH2XrFJQxuGaI2MUJ1VZkwTQBi0FhEQfDC5EGKQwWuv/M1jBw9xlMP/tD5"
    "qtSAqLloTdzR0fGIB77xHb71yHe49podvOr6q7nqqss5e9NGil4BYwJ0kg8v9rBKsotldRJZyFw1nZlO"
    "5Px07bVGfZ4gzX0B5a6nBF45dijTgWOnrHGFNwRoa7BEGGHAekgRgozLhguBKBTQ9TpRGKLS4K0p+pur"
    "/HCS6iHy+hUT/9/fX+UVV1/NV+57EE/GtV1bsQ54NTMkAIstvZ2D4wLOT3tPBHgN9MPWN97ATW+7FVEa"
    "o1D1qAetMqYQgvHJOqogWVddy+hPD3Hvp+/mFzufgCOg6mkNmnTuZTMmSqBchOHhFVy+41IuvewiBlet"
    "YuPGdQwOrmJFNeaeRFPA6kQAcl5YmQo40yNbg68XAtCZEM3vK2w0GkgpKZVLDPaVqKpEHNCAxUjQcZi2"
    "kH0gV+PJKomLmigWIYqYGB1lZGSE6aTMudchODkJgJGZ54o5YCl9ao2Qxx79Ie94+zsZHZ1o017Hc+th"
    "4BbgxWYVjc7jfDzUN/8Z+FPIuDEL4ju3sLmfO//bf2DLSzczZkYwyqKlwQgQ0iUEsdbS0A28ULHGX03w"
    "whj3/vUXePJuR/T8uP6oJVYSSlcy2lrn5p7MOR27G/tF6OsTFItFvGlY6rTEc76ISZf6ennkC3DOVQSY"
    "ab8zRbFYZLI2yYb1G7jkgnN57+/eydZzznRl10QIaLQ0RBKQJSQDKFlFKh+Uz9h4jc9+4S6+dPeX2PP8"
    "L3GORlM8z4IQgMVSbS0MTAeuxhEAj4laAyk9Dh44gpQCYyxYkecM68CXgK8i7EPA80uJAGwC7gEuTjkA"
    "43ZtDYiVBdZtP5s7P/AOBs5ayVF7gNAPsZ6PUNJppUPwjGOHa42QocoqGvvH+O5XvsXD//Bv2BcbBKMR"
    "PgLp+2hpXEFRa7Fat+QVsbQvyl4w1/nbowQw7/1PBd/CdVecz1/+xYfZfNZagsYIhaJFq4hQgsXDhAJf"
    "ligUB2nU4SOf/DQf+rNP4QuBJxWRjYhs63PGqVtSSKZ4B7N5vhM9pmOqseg0eLHptoMnRWAFPzOCzwGf"
    "BQ7kqfHxIJXPAn+Fk9pbbqQI2GMBBx7/Off8n3vw6gVWFgYpeyWkUBhjUg1/4rjiVzyOBkcpraly9et+"
    "jVvf9gYqZ62BikeIpaEDIq0JjCHUJnYRzpi7YU4TxiLmdMwVc+1/qiMU8O3HdnHPNx6iXioSrehjvE8x"
    "XvaZLPvUSorJQkTYB4EM+NHPn+Szn7/LiWBWMq4jtIkXv3QEPlO9MUVHHigXptz291QQJ/jRy/NlPjO0"
    "zYeCQVwEfBhHAF6ev9RiKgGz+CJOU/na7OJLJ0Jd8/S3d/LgvWdw1W1X0L9mBbpRI7IBVlrCuKClshDU"
    "Avr7+gGJrSgue83VDJ9/Hl/7pwd5/KvfhCN1aFiI/abdwGTo3pyVSMd7u1m4/q2ACQ3f3vU4Vx59FaoK"
    "garFWZ09N/8Ciwo0JRHx8NO72X/oGAKoo+nDIyL26Ow6zKLZGZDuSQmbljFHzuymT2z2f0rIRDudZada"
    "KYbuqBQ2SlhuAM4A3g38a/LN8SIAR4D/geVScqmMPAlRCBxt8PUvfJmh9X2cd+VFVFaUCYIIU7AYAZE0"
    "CCzFYpFGrU49bFD0+hhTDQbOW8+tm9/Mtqtfyvfu+yb7f7aHsZ8/F+cTiPlRRy7nvH7EjEh2d/RqBZjv"
    "/qeClRbK8Hx9hB8f2ks4HtFQAUY4l2FhJCW/wORYg8HqKp4afZG655Z0CUFt2nJ1+XvPuw6beEHPlEif"
    "xIsfp//pOlvyQ5mICwBGJIHzW4QQnwB+G9jZqdliQgJ/BHxIgpf68xPLgxIogTpjBW9457/nwmsupVGG"
    "ETtGIF14qjJQthIRQWSss1gJH6TCigIF4+ONG/b/fC+PPrSTXd9/HPvsIUcINBCB0oCVJEHIIv43HWzu"
    "VeT/ninmTEDmkQOQSBQSISTaaiKlEcMF3vKHv8OFV22j5jUIlUELQDtToUEjrMSLFJVGgU++/8P88lt7"
    "mmtWxY5EucdMlH9S5Pag2AmsyZnlOYHpFvnJSwSSTFo65o6scNaoFqtSEKbnCiFyqfRTPAi8GTh4PAkA"
    "wCoJfwvcmr2RFj2HD6VNg9z+zjex7brLGC/VmaSBFiHSGgoaFIoQS2gtVnoYJUAopPXoV2WoW0pGMXHw"
    "CPt2P8P+Z55j1+M/Zv8z+zDjBkLh3Gy17VqBqA35dTfbdTjXNzDfEoAPTAIFUBsr3PjWW7jw6ouorC0T"
    "yJBQghESYxwB0KKBxOCHinLgceBHz/D5v/w7Jn426pQ6tcw95rkuS+fnzz5Tr+NzvCWyhUSyqyfjlmyU"
    "CQxuc0ssVRK6GJk08AHgY8eNAGTuezvwOQEX5b8XxJpCD0pnD3LHH7yZ4UvPRq32qFPDWo0ynvP4kwKN"
    "dcFDaXw7lFQBYRTCwOToOBvWrqNWqzE2Mk4wMcnBn++jMdFgYnycWq1GpGO2dZqdJs+6z5aVn6sZbK4i"
    "RB7JrrFq1SrWnnk6/ZvWI/t9yiWBVE4Ja/EIKGKEQTCGbwMKkcTXHgXpM/arY/zg248xfnQCZf00U5C0"
    "rZWG838n76xp0spxAdPi5N39ockBmMTjUkCkHO/sG2f+Htt/iOd++hQHnjnk6EVn53uAH5HbeBcVuVd1"
    "E/DXIqMPcJH8Eh+fMRrgQ+Hclbz2t27hgqsuprCqQN02nIIpziIkpdMPmDhARQhBrC/EGIiMduySUAgp"
    "wRiKkUIZkNLDixOWyjRvQIL8BJSYHGmdssjpFCWwZ+bJ197/jPqdQf9ZKKVQyllbgiCggaHhu2zMBTQK"
    "i7EiJgA+RkYIJvBNQEFLpJFYz0NYyYBXpDEZ4YkCxOHGANX+Fenv0hKngY9v0zafzZ2TY/+nuf+THQkB"
    "SIi+ERDGwnNBQzECVY84vPcFvv5P9/Mvd33NZeXsTD/rwHuOtwiQTGUBvA34KDDQ8g1xoWphnPF/leSa"
    "37yZq2++ATEoCfsCjBdS8Hzq9RrS85ySULmillJrPEuaLdgk6hDcpFSJq6+VU+wf3Rdg2w6eTM6WSdu9"
    "fRuWUHsLRNLtNFJYFDGXZQRWSIxw2YMEJq7MLFP//ySnY9pjMsZCUJCKYrGMr5ryvxDKKblM06kltQu0"
    "8bEZAtgjBzRXm89cSc989q8FNGL6qSwUNXiBoSw96kdGuOcz9/LVv/oawnbVB/z9UiEASYKf90j4r0Cf"
    "yRCAFAkRqCrOvOoSbn/rbzK0ZYiR6Ah+sYgqedSCGloadGIqjGwzNkDEzkAiuZxs6aF7rbtur022uuJ2"
    "LXTZvX0LlnB7IUQ6fp3aW2udAi87Hrn+XVyFRMXCq+/7KKXwlYeUXnxO/E6MdGdlFn+n99MLAZivsOXZ"
    "1kSc7/61dKHvVjhHTWWhJBSEmoIRHHn6EB/9g4/y4tOHXICblHkisPu4E4AcSjjlxAdAljueoYybT33g"
    "DQ9x/W3Xs+P6KzEDHvRLGipEK5e6SliDMKJloVtrmy8wN+FTQtCyq7dOYpt7i1kWtuWabYsv+ZnfQ7os"
    "wqXYXoq2529nxzMkveU6zYmbEAIhBEpJlPLwpSMGUjrxqxmNKVva5dELAZiLx2cW05TqXrT+jQCdiRmQ"
    "FiQCHYYIY1nnreaT7/4Ej/zzt4CmCJHB+PHyA+iGOvARQIP5I5BpvTM3rQwChbYaJiB69jAP/O0/8pPv"
    "/oQbXv/v2PqyC5G+IPCJ4wcceUzmrLEgYk/ANOtQpiZhc4kkbypWJmaUiqbFCSMvNsgM3ys7tm9Bp8Wz"
    "lNtnJl7aXuTa07m9tLHZyrr2zoPVYo1B2xCNQXkepVIpbSehRavfaQHNZi3OdicW+eefJeaz/0THlVyz"
    "VqtRLpep1+tYKVi/fj2FgovWDIIW51uA7rWGjjOKwNuBD0qX5QRohveCdBXGAS0tFCTF1WXOfsm5vOL2"
    "G1hz/ukEKwSmpJgcH6dSKhNZw+TEBH39Vay1REGItRZPJrZvJ3smSjkRj3ZaHquLHbqNA8jvgNPasafZ"
    "QZdYe9P1fFqv38WOn989Ze5+lPLxlEfB8/GEh2+SSe7OsybPgfU2hee6eGe7+89b/9NoERSWRqNBsVik"
    "POHz6ff8Lx594DvdTh9bqgQAXIDp6wX8GXC2htgO6iaCH+/Tzixq0VJjS8AAnHfdDrZceTGbLzmfcrWA"
    "KjnfgPFGHVlwwUGJKUVasGgUoiULkRDCKcLS+niddtGczLuEZfj5aN++c/Xav/vZcpkOGn0pnChQlB59"
    "+Pj4jjBb2cby90IAThodQOZ92vQzN5frkxPoMGRo5SC//NEe/ub9n+Lgrs5Z+VmCOoAWxL4ArwD+uxZc"
    "45wfYlbUyNhUaDAY57+TsAUKKMK6c9ZxwbUXs3Hr6Wy6cCveQAXRV6QuI0JfIj1FbWKSRMklaXpQCWFz"
    "BMChTQfQlqS5mwzcRQafsQx9/Nu73Wuu/bfKsFOF8/pW0UeJovVQGUVhy5k9JESZqwa+9e56x7z0H4tT"
    "0KoDSJSAvjF4VlAfGeOLn7qLnX/3CEortNYpscwQ0eNvBZgKMQHAwplG8IcI3oKUVRfoH4cGA4lkbnB1"
    "AiZqDYo4JyILsAH6Tx9keOsm1m86g7Wbhtm4+SyMFFSqVawwLTu/kKJdBIjRvgPNUAToeE63p863m2rq"
    "zJCFX1L9ZzBFMJa0kqL2USikVCgp8WN5Nj1nIeOhlyLi8RKxTiURKVQsKplajdHDR7nvnnt56IsPwUEo"
    "lUrU6/W8FWBp+AFMhQwBwAhKCG7HyvdheUn2HIBsQbGWdjLzgcBxB1WPvoEBitU+qmuHKFWK9Pf3Uy63"
    "Gx6SBZ9nNTtQ0x6frPU6U2O+9q72/meG+e5/Zn0KodJaBSYmxOVya0LMfGamUwVJvkph3dtMuIJDBw/y"
    "7NPPsG/3XueGnW3TagU4vp6AM0W6wFPNM+eA/H3gTbhyockZPV1XyJh79WKVtIx38ihqVS1nhayWC+S+"
    "n3nPuT97fQXz6UoyGyxW/87smMJmQuGyt3Bqrv9mTIChOS5KoKTCWIswBqNtt9elcYF4H13yBKALPJxu"
    "4B3AjcCKmTRyir2YtU8GRkFGm9jkFBIsE4Dj1L9pHRtjm+8oG1B0os7g+UC3uSfdBge4snnt+DpuAz3u"
    "0YBzRQV4JfAW4Hpg1UwbpgNkOv+9jOOPLHefcq75SX+iz+C5INm4kt+zn3Wfx7tZIvkA5hN9wOXAbcCv"
    "4bIPd3Vy6mUPzI9jvu3x3o9PdSzTa1q51m6E0uEp4D8C92ebnkyQuKSjr8IRgstxedJL2RN6wTIBWNpY"
    "JgDMhAAY4Bu4OJud+aYnK8rAMPASXDLES4DNOH1BheW1d2Kh20yd33QIJx5E7mcrAajjWP7PxceBbs1P"
    "dkhgENiIK0qyFccpnI5gffzdAM4FuUB2XKaTOec6AU+VNzBXdBunU50FaCUABssEsA/Lj3G7/gO4TNwd"
    "8f8BIzdumYNY13AAAAAASUVORK5CYII="
)

QSS = f"""
QMainWindow, QWidget#central {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #eef1f8, stop:1 {C['bg']});
}}
QLabel {{
    color: {C['text']}; font-family: '맑은 고딕'; font-size: 12px;
    background: transparent; font-weight: 400;
}}
QFrame#card {{
    background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 10px;
}}
QFrame#card_header {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f0f3fa, stop:1 #e8ecf4); border-bottom: 1px solid {C['border']};
    border-top-left-radius: 10px; border-top-right-radius: 10px;
}}
QLineEdit {{
    background: {C['surface2']}; border: 1px solid {C['border']}; border-radius: 6px;
    padding: 0px 8px; font-family: '맑은 고딕'; font-size: 12px; color: {C['text']};
    min-height: 26px; max-height: 26px;
}}
QLineEdit:focus {{ border: 1.5px solid {C['accent']}; }}
QLineEdit:hover {{ border-color: {C['accent']}; }}
QPushButton {{
    font-family: '맑은 고딕'; font-size: 12px; font-weight: 400;
    border-radius: 6px; padding: 5px 10px; border: none;
}}
QPushButton#btn_green {{ background: {C['green']}; color: white; font-weight: 600; }}
QPushButton#btn_green:hover {{ background: #16b87a; }}
QPushButton#btn_green:disabled {{ background: #a8d8c4; color: #ddf0ea; }}
QPushButton#btn_blue {{
    background: rgba(34,114,216,0.08); color: {C['accent']};
    border: 1px solid rgba(34,114,216,0.25);
}}
QPushButton#btn_blue:hover {{ background: rgba(34,114,216,0.15); }}
QPushButton#btn_gray {{
    background: {C['surface']}; color: {C['text2']}; border: 1px solid {C['border']};
}}
QPushButton#btn_gray:hover {{ background: {C['bg2']}; }}
QPushButton#btn_danger {{
    background: rgba(201,53,53,0.08); color: {C['red']};
    border: 1px solid rgba(201,53,53,0.25);
}}
QPushButton#btn_danger:hover {{ background: rgba(201,53,53,0.15); }}
QCheckBox {{
    font-family: '맑은 고딕'; font-size: 12px; font-weight: 400;
    color: {C['text2']}; spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    background: {C['surface2']}; border: 1.5px solid {C['border']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']}; border: 2px solid {C['accent']};
    border-radius: 2px; image: url({_check_svg_path});
}}
QCheckBox::indicator:hover {{ border-color: {C['accent']}; }}
QProgressBar {{
    background: {C['bg3']}; border: none; border-radius: 3px;
    height: 6px; font-size: 1px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['green']}, stop:1 #2de49a);
    border-radius: 3px;
}}
QTextEdit#log_area {{
    background: #f8f9fc; border: 1px solid {C['border']}; border-radius: 6px;
    color: {C['text']}; font-family: 'Consolas','D2Coding',monospace;
    font-size: 11px; padding: 8px;
}}
QScrollBar:vertical {{
    background: transparent; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['text3']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QListWidget {{
    background: {C['surface2']}; border: 1px solid {C['border']};
    border-radius: 6px; outline: none;
    font-family: '맑은 고딕'; font-size: 12px; color: {C['text']};
}}
QListWidget::item {{
    padding: 5px 8px; border-bottom: 1px solid {C['border']}; color: {C['text']};
}}
QListWidget::item:selected {{ background: rgba(34,114,216,0.1); color: {C['accent']}; }}
QListWidget::item:hover {{ background: {C['bg2']}; }}
QTabWidget::pane {{
    border: 1px solid {C['border']}; border-radius: 8px;
    background: transparent; margin-top: -1px;
}}
QTabBar::tab {{
    background: {C['bg2']}; border: 1px solid {C['border']};
    padding: 6px 18px; font-family: '맑은 고딕'; font-size: 12px; color: {C['text2']};
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {C['surface']}; color: {C['accent']};
    border-bottom: 1px solid {C['surface']}; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {C['text']}; background: {C['bg3']}; }}
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 정렬
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _extra_num(s):
    m = re.search(r'\((외전|번외|특전|특별외전|특별\s*외전)\s*(\d+)\)', s, re.IGNORECASE)
    if m: return int(m.group(2))
    if re.search(r'\((외전|번외|특전|특별외전|특별\s*외전)\)', s, re.IGNORECASE): return 0
    return 0

def _side_story_rank(s):
    if re.search(r'에필로그|후일담', s, re.IGNORECASE):
        return 1
    if re.search(r'특별\s*외전|특별외전|특\s*외|특외', s, re.IGNORECASE):
        return 3
    if re.search(r'외전|번외', s, re.IGNORECASE):
        return 2
    if re.search(r'특전', s, re.IGNORECASE):
        return 4
    return 0

def natural_sort_key(s):
    """권·부·화 번호를 정수로 비교해 자연 정렬.
    100화 > 99화, 10권 > 9권 등 자릿수 무관하게 정확히 정렬.
    화-선행 파일명(제N화. 챕터제목) 은 sn='' 처리해 화 번호만으로 정렬.
    외전/특별외전은 반드시 같은 시리즈 숫자 권호 뒤에 오도록 is_e 플래그를 3번째 키로 사용.
    [태그] 접두사는 tag 변수로 분리해서 sn 불일치로 인한 외전 끼임 현상 방지.
    """
    is_c = bool(re.search(r'\(완결\)|완결', s, re.IGNORECASE))
    side_rank = _side_story_rank(s)
    is_e = side_rank > 0
    en   = _extra_num(s)
    vm = re.search(r'(\d+)권', s)
    hm = re.search(r'(\d+)화', s)
    # 괄호 안의 "N부"는 부록/완결/외전 표시일 수 있으므로 모두 제거 후 부 번호 추출
    # 예) "(1부 완결)", "(1부 외전)", "(2부 프롤로그)" → 오탐 방지
    # 괄호 밖 "N부" (시리즈 파트 번호)는 그대로 인식
    _s_no_paren = re.sub(r'\([^)]*\)', '', s)
    pm = re.search(r'(\d+)부', _s_no_paren)
    vn = int(vm.group(1)) if vm else 0
    hn = int(hm.group(1)) if hm else 0
    pn = int(pm.group(1)) if pm else 0
    num = vn or hn

    # [태그] 접두사 분리: "[이레망] 시리즈명" → tag="[이레망]", s_notag="시리즈명 ..."
    # 태그가 있는 파일·없는 파일이 섞여도 sn이 동일하게 계산되도록 함
    tag_m = re.match(r'^(\[[^\]]+\]\s*)', s)
    tag = tag_m.group(1).strip() if tag_m else ''
    s_notag = s[tag_m.end():] if tag_m else s
    raw_pm = re.search(r'(\d+)부', s_notag)

    # 화-선행 파일명: "제N화." 또는 "N화."으로 시작 → 챕터 제목이 달라도 같은 시리즈
    # sn을 비워서 화 번호만으로 정렬
    if re.match(r'^제?\s*\d+\s*화\s*[._\s]', s_notag):
        sn = ''
    else:
        # 일반: 시리즈명 추출 (숫자·괄호·확장자 제거), 태그 제거 후 기준으로 계산
        sn = re.sub(r'\s*\d+[권화부]\s*', '', s_notag)
        sn = re.sub(r'\s*\([^)]+\)\s*', '', sn)
        sn = re.sub(r'[,\s]*(?:특별\s*외전|외전|번외|특전)\s*$', '', sn)
        sn = re.sub(r'\.[^.]+$', '', sn)
        # 화/권/부 없이 끝에 숫자만 있는 파일명도 sn에서 제거
        sn = re.sub(r'[\s_]+\d+\s*$', '', sn)
        # " - 부제목" 패턴 제거 (예: "시리즈 6권 - 크라켄의 바다로..." → "시리즈")
        sn = re.sub(r'\s*[-–—]\s+.*$', '', sn)
        sn = re.sub(r'\s+', ' ', sn).strip()

    # 화/권/부 없이 끝에 숫자만 있는 파일명 fallback (예: "시리즈명 1.epub" → num=1)
    if num == 0 and pn == 0:
        base = re.sub(r'\.[^.]+$', '', s_notag)
        # (완결) / [태그] 등 뒤 부가정보 제거 후 숫자 추출
        base = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*$', '', base).strip()
        tail_m2 = re.search(r'(\d+)\s*$', base)
        if tail_m2:
            num = int(tail_m2.group(1))

    # 인터뷰/작가노트 감지 (3순위 — 외전보다도 뒤)
    is_interview = bool(re.search(r'인터뷰집|인터뷰|작가노트', s))

    # 정렬 키: (시리즈명, 부/권 우선 플래그, 1차번호, 2차번호, 종류플래그, 완결플래그, 태그, 원본)
    # ※ sn 먼저 → 태그 유무 무관하게 같은 시리즈끼리 묶임
    # ※ tag는 마지막 보조키 → 태그없는 외전이 태그있는 권호보다 앞에 끼지 않음
    # 종류플래그: 0=일반권호, 1~4=에필로그/외전/특외/특전, 5=인터뷰/작가노트
    # 파일명에 명시적 권/화 번호가 있으면 "인터뷰/외전" 단어보다 회차 순서를 우선한다.
    part_before_volume = bool(raw_pm and vm and raw_pm.start() < vm.start())
    if num:
        if part_before_volume:
            return (sn, 0, pn, num, 0, 0.5 if is_c else 0.0, tag, s)
        return (sn, 1, num, pn, 0, 0.5 if is_c else 0.0, tag, s)
    if is_interview: return (sn, 2, en or num, pn, 5, 0.5 if is_c else 0.0, tag, s)
    elif is_e:       return (sn, 2, en or num, pn, side_rank, 0.5 if is_c else 0.0, tag, s)
    else:            return (sn, 1, num, pn, 0, 0.5 if is_c else 0.0, tag, s)

def human_size(n):
    for u in ['B', 'KB', 'MB', 'GB']:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧹 공백코드 제거 — full 모드 고정
#    (tokki_organizer remove_invisible_chars 동일 로직)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_FULL_PATTERNS = {
    b'\xe2\x80\x8b': 'U+200B',   # Zero Width Space
    b'\xe2\x80\x8c': 'U+200C',   # Zero Width Non-Joiner
    b'\xe2\x80\x8d': 'U+200D',   # Zero Width Joiner
    b'\xe2\x80\x8e': 'U+200E',   # Left-to-Right Mark
    b'\xe2\x80\x8f': 'U+200F',   # Right-to-Left Mark
    b'\xe1\xa0\x8e': 'U+180E',   # Mongolian Vowel Separator
    b'\xe2\x81\xa0': 'U+2060',   # Word Joiner
    b'\xe2\x81\xa1': 'U+2061',   # Function Application
    b'\xe2\x81\xa2': 'U+2062',   # Invisible Times
    b'\xe2\x81\xa3': 'U+2063',   # Invisible Separator
    b'\xe2\x81\xa4': 'U+2064',   # Invisible Plus
    b'\xe2\x81\xa6': 'U+2066',   # Left-to-Right Isolate
    b'\xe2\x81\xa7': 'U+2067',   # Right-to-Left Isolate
    b'\xe2\x81\xa8': 'U+2068',   # First Strong Isolate
    b'\xe2\x81\xa9': 'U+2069',   # Pop Directional Isolate
    b'\xe2\x81\xaa': 'U+206A',   # Inhibit Symmetric Swapping
    b'\xe2\x81\xab': 'U+206B',   # Activate Symmetric Swapping
    b'\xe2\x81\xac': 'U+206C',   # Inhibit Arabic Form Shaping
    b'\xe2\x81\xad': 'U+206D',   # Activate Arabic Form Shaping
    b'\xe2\x81\xae': 'U+206E',   # National Digit Shapes
    b'\xe2\x81\xaf': 'U+206F',   # Nominal Digit Shapes
    b'\xcd\x8f':     'U+034F',   # Combining Grapheme Joiner
    b'\xef\xbb\xbf': 'U+FEFF',   # BOM / Zero Width No-Break Space
    b'\xef\xbf\xb9': 'U+FFF9',   # Interlinear Annotation Anchor
    b'\xef\xbf\xba': 'U+FFFA',   # Interlinear Annotation Separator
    b'\xef\xbf\xbb': 'U+FFFB',   # Interlinear Annotation Terminator
    b'\xf3\xa0\x80\x81': 'U+E0001',  # Language Tag
}
_TAGS_BLOCK = re.compile(
    b'\xf3\xa0[\x81-\x82][\x80-\xbf]|\xf3\xa0\x80[\xa0-\xbf]')  # U+E0020~
_BOOK_TOKEN = re.compile(
    rb'[^\r\n]*name=["\']book-token["\'][^\r\n]*(\r\n|\r|\n)?')
_TARGET_EXTS = ('.html', '.xhtml', '.htm', '.xml', '.ncx', '.css')


def remove_invisible_chars(epub_bytes: bytes):
    """
    epub_bytes 에서 공백 유니코드 전부 제거 (full 모드 고정)
    returns (cleaned_bytes, total_removed_count, char_counts_dict)
    """
    orig    = zipfile.ZipFile(io.BytesIO(epub_bytes), 'r')
    mime_dt = None
    for info in orig.infolist():
        if info.filename == 'mimetype':
            mime_dt = info.date_time
            break

    cleaned_data = {}
    char_counts  = {}

    for item in orig.infolist():
        fl        = item.filename.lower()
        file_data = orig.read(item.filename)

        if item.filename.startswith('META-INF/'):
            continue

        # OPF: book-token 메타태그 제거
        if fl.endswith('.opf'):
            cleaned, n = _BOOK_TOKEN.subn(b'', file_data)
            if n:
                char_counts['book-token'] = char_counts.get('book-token', 0) + n
                cleaned_data[item.filename] = cleaned
            continue

        if not any(fl.endswith(e) for e in _TARGET_EXTS):
            continue

        modified = False

        # 패턴 바이트 제거
        for pat, name in _FULL_PATTERNS.items():
            cnt = file_data.count(pat)
            if cnt:
                char_counts[name] = char_counts.get(name, 0) + cnt
                file_data = file_data.replace(pat, b'')
                modified  = True

        # Tags block (U+E0020~) 제거
        matches = _TAGS_BLOCK.findall(file_data)
        if matches:
            char_counts['U+E0020~'] = char_counts.get('U+E0020~', 0) + len(matches)
            file_data = _TAGS_BLOCK.sub(b'', file_data)
            modified  = True

        if modified:
            cleaned_data[item.filename] = file_data

    orig.close()

    removed_count = sum(v for k, v in char_counts.items() if k != 'book-token')

    # 새 epub 재조립
    orig2   = zipfile.ZipFile(io.BytesIO(epub_bytes), 'r')
    new_buf = io.BytesIO()
    new_zip = zipfile.ZipFile(new_buf, 'w')

    for item in orig2.infolist():
        if item.filename == 'mimetype':
            d = orig2.read(item.filename)
            item.compress_type = zipfile.ZIP_STORED
            new_zip.writestr(item, d)
        elif item.filename in cleaned_data:
            if mime_dt: item.date_time = mime_dt
            item.compress_type = zipfile.ZIP_DEFLATED
            new_zip.writestr(item, cleaned_data[item.filename])
        else:
            if mime_dt: item.date_time = mime_dt
            d = orig2.read(item.filename)
            new_zip.writestr(item, d)

    new_zip.close()
    orig2.close()
    return new_buf.getvalue(), removed_count, char_counts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧹 EPUB 단독 정제 — 공백코드 제거 + 판권/표지/목차 제거
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def strip_epub_in_memory(epub_bytes: bytes) -> tuple:
    """공백코드 제거 + 판권·표지·목차 페이지 제거 (합본 없이 단독 파일 정제).

    returns: (cleaned_bytes, removed_pages: list[(filename, reason)],
              chars_removed: int, char_counts: dict)
    reason 값: 'copyright' | 'cover' | 'index'
    """
    from urllib.parse import unquote as _uq

    # ── Step 1: 공백코드 제거 ────────────────────────
    cleaned_bytes, chars_removed, char_counts = remove_invisible_chars(epub_bytes)

    # ── Step 2: 판권·표지·목차 페이지 제거 ──────────
    removed_pages: list = []
    try:
        in_buf  = io.BytesIO(cleaned_bytes)
        out_buf = io.BytesIO()

        with zipfile.ZipFile(in_buf, 'r') as zin:
            # container.xml → OPF 경로
            try:
                container_xml = zin.read('META-INF/container.xml').decode('utf-8', 'replace')
                m_opf = re.search(r'full-path=["\']([^"\']+\.opf)["\']', container_xml, re.IGNORECASE)
                if not m_opf:
                    return cleaned_bytes, [], chars_removed, char_counts
                opf_zip_path = m_opf.group(1)
            except Exception:
                return cleaned_bytes, [], chars_removed, char_counts

            opf_dir = str(Path(opf_zip_path).parent)
            if opf_dir == '.':
                opf_dir = ''

            opf_content = zin.read(opf_zip_path).decode('utf-8', 'replace')

            # manifest 파싱: id → href
            manifest: dict = {}
            for mm in re.finditer(r'<item\s([^>]*?)\s*/?>', opf_content, re.IGNORECASE):
                attrs = mm.group(1)
                mid  = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
                mhref = re.search(r'\bhref=["\']([^"\']+)["\']', attrs)
                if mid and mhref:
                    manifest[mid.group(1)] = _uq(mhref.group(1))

            # spine 순서대로 idref 목록
            spine_idrefs = re.findall(
                r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf_content, re.IGNORECASE)

            # 각 spine 항목 → is_skip_page 판정
            skip_zip_paths: set = set()
            for iid in spine_idrefs:
                if iid not in manifest:
                    continue
                href = manifest[iid]
                # zip 내 절대 경로 구성
                if opf_dir:
                    zip_path = opf_dir + '/' + href
                else:
                    zip_path = href
                zip_path = zip_path.replace('\\', '/')
                # ../ 등 경로 정규화 (Path는 POSIX용이라 직접 처리)
                parts = []
                for seg in zip_path.split('/'):
                    if seg == '..':
                        if parts: parts.pop()
                    elif seg not in ('', '.'):
                        parts.append(seg)
                zip_path = '/'.join(parts)

                try:
                    file_data = zin.read(zip_path)
                    reason = is_skip_page(href, file_data)
                    if reason:
                        # 단독 정제 시 표지는 보존 — 파일이 1개일 때 표지를 통째로 잃으면
                        # 책 자체가 표지 없는 무미건조한 형태가 되어버림 (합본 시는 별도 추출 경로)
                        if reason == 'cover':
                            continue
                        skip_zip_paths.add(zip_path)
                        removed_pages.append((Path(href).name, reason))
                except Exception:
                    pass

            if not skip_zip_paths:
                # 판권/목차 없음: 공백코드 제거만 된 bytes 반환
                return cleaned_bytes, [], chars_removed, char_counts

            # skip 항목의 id 집합
            skip_ids: set = set()
            for iid, href in manifest.items():
                if opf_dir:
                    zp = opf_dir + '/' + href
                else:
                    zp = href
                zp = zp.replace('\\', '/')
                parts = []
                for seg in zp.split('/'):
                    if seg == '..':
                        if parts: parts.pop()
                    elif seg not in ('', '.'):
                        parts.append(seg)
                zp = '/'.join(parts)
                if zp in skip_zip_paths:
                    skip_ids.add(iid)

            # OPF 수정: spine에서 제거
            def _del_spine(m):
                idref_m = re.search(r'idref=["\']([^"\']+)["\']', m.group(0))
                if idref_m and idref_m.group(1) in skip_ids:
                    return ''
                return m.group(0)
            new_opf = re.sub(r'<itemref\s[^>]*/>', _del_spine, opf_content, flags=re.IGNORECASE)
            new_opf = re.sub(r'<itemref\s[^>]*>[^<]*</itemref>', _del_spine, new_opf, flags=re.IGNORECASE)

            # OPF 수정: manifest에서 제거
            def _del_manifest(m):
                attrs = m.group(1)
                mid_m = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
                if mid_m and mid_m.group(1) in skip_ids:
                    return ''
                return m.group(0)
            new_opf = re.sub(r'<item\s([^>]*?)\s*/?>', _del_manifest, new_opf, flags=re.IGNORECASE)

            # zip 재조립
            with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    norm = item.filename.replace('\\', '/')
                    if norm in skip_zip_paths:
                        continue  # 판권 파일 제외
                    if norm == opf_zip_path:
                        zout.writestr(item, new_opf.encode('utf-8'))
                    elif norm == 'mimetype':
                        zout.writestr(item, zin.read(item.filename),
                                      compress_type=zipfile.ZIP_STORED)
                    else:
                        zout.writestr(item, zin.read(item.filename))

        return out_buf.getvalue(), removed_pages, chars_removed, char_counts

    except Exception:
        # 어떤 오류든 최소한 공백코드 제거 결과는 반환
        return cleaned_bytes, [], chars_removed, char_counts


def add_noise_to_epub(epub_bytes: bytes, level: int) -> bytes:
    """EPUB 표지·삽화 이미지에 랜덤 픽셀 노이즈 추가 (PIL 필요).

    level 1 (미세): 픽셀값 ±3 내 랜덤 변동
    level 2 (보통): 픽셀값 ±8
    level 3 (강함): 픽셀값 ±18
    텍스트 파일은 건드리지 않음.
    """
    try:
        from PIL import Image as _Img
    except ImportError:
        return epub_bytes

    _AMP = {1: 3, 2: 12, 3: 25}.get(level, 3)
    _IMG_EXTS = ('.jpg', '.jpeg', '.png', '.webp')

    def _noisy(data: bytes, ext: str) -> bytes:
        img = _Img.open(io.BytesIO(data)).convert('RGB')
        try:
            import numpy as _np
            arr   = _np.array(img, dtype=_np.int16)
            noise = _np.random.randint(-_AMP, _AMP + 1, arr.shape, dtype=_np.int16)
            arr   = _np.clip(arr + noise, 0, 255).astype(_np.uint8)
            out   = _Img.fromarray(arr)
        except ImportError:
            # numpy 없을 때 PIL만으로 처리
            import random as _r
            _rng = _r.Random()
            px   = list(img.getdata())
            px   = [tuple(max(0, min(255, c + _rng.randint(-_AMP, _AMP))) for c in p) for p in px]
            out  = _Img.new('RGB', img.size)
            out.putdata(px)
        buf = io.BytesIO()
        if ext in ('.jpg', '.jpeg'):
            out.save(buf, 'JPEG', quality=80, optimize=True)
        else:
            out.save(buf, 'PNG', optimize=True)
        return buf.getvalue()

    in_buf  = io.BytesIO(epub_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                fl   = item.filename.lower()
                ext  = Path(fl).suffix
                if ext in _IMG_EXTS:
                    try:
                        data = _noisy(data, ext)
                    except Exception:
                        pass
                compress = zipfile.ZIP_STORED if item.filename == 'mimetype' \
                           else zipfile.ZIP_DEFLATED
                zout.writestr(item, data, compress_type=compress)
    return out_buf.getvalue()


def compress_epub_images(epub_bytes: bytes) -> bytes:
    """EPUB 내 JPEG 이미지 재압축 (PIL 필요, 없으면 원본 반환)."""
    try:
        from PIL import Image as _Img
    except ImportError:
        return epub_bytes

    _IMG_EXTS = ('.jpg', '.jpeg')
    in_buf  = io.BytesIO(epub_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                fl   = item.filename.lower()
                if any(fl.endswith(e) for e in _IMG_EXTS):
                    try:
                        img = _Img.open(io.BytesIO(data))
                        if img.mode not in ('RGB', 'L'):
                            img = img.convert('RGB')
                        buf = io.BytesIO()
                        img.save(buf, 'JPEG', quality=80, optimize=True, progressive=True)
                        if buf.tell() < len(data):
                            data = buf.getvalue()
                    except Exception:
                        pass
                compress = zipfile.ZIP_STORED if item.filename == 'mimetype' \
                           else zipfile.ZIP_DEFLATED
                zout.writestr(item, data, compress_type=compress)
    return out_buf.getvalue()


def apply_epub_timestamp(epub_bytes: bytes, ts: tuple) -> bytes:
    """epub_bytes 내 모든 zip 항목의 date_time을 ts=(y,mo,d,0,0,0)로 교체."""
    in_buf  = io.BytesIO(epub_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data     = zin.read(item.filename)
                new_info = zipfile.ZipInfo(item.filename, date_time=ts)
                if item.filename == 'mimetype':
                    new_info.compress_type = zipfile.ZIP_STORED
                else:
                    new_info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(new_info, data)
    return out_buf.getvalue()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 커버 이미지 추출 (유저봇 generate_epub_thumbnail 참고)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def extract_cover_image(epub_bytes: bytes):
    """
    EPUB bytes 에서 커버 이미지 (bytes, ext) 반환.
    1순위: OPF <meta name="cover"> → 이미지 id
    2순위: cover 키워드 파일명 이미지
    3순위: 첫 번째 이미지
    실패 시 (None, None)
    """
    try:
        with zipfile.ZipFile(io.BytesIO(epub_bytes), 'r') as zf:
            namelist = zf.namelist()
            cover_data = None
            cover_ext  = '.jpg'

            # 1순위: OPF meta cover_id → 이미지 직접 or xhtml 내 img src
            try:
                container = zf.read('META-INF/container.xml').decode('utf-8', 'replace')
                opf_path  = re.search(r'full-path="([^"]+\.opf)"', container).group(1)
                opf_raw   = zf.read(opf_path).decode('utf-8', 'replace')
                opf_dir   = str(Path(opf_path).parent)

                cover_id = None
                for m in re.finditer(r'<meta[^>]+name=["\']cover["\'][^>]*content=["\']([^"\']+)["\']', opf_raw):
                    cover_id = m.group(1); break
                if not cover_id:
                    for m in re.finditer(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']cover["\'][^>]*/>', opf_raw):
                        cover_id = m.group(1); break

                if cover_id:
                    for m in re.finditer(r'<item\s[^>]*id=["\']'+ re.escape(cover_id) +r'["\'][^>]*/>', opf_raw):
                        href       = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
                        media_type = re.search(r'media-type=["\']([^"\']+)["\']', m.group(0))
                        if not href: break
                        href_val = href.group(1)
                        mt_val   = media_type.group(1) if media_type else ''
                        full = (opf_dir + '/' + href_val).lstrip('./') if opf_dir != '.' else href_val
                        if 'image' in mt_val:
                            if full in namelist:
                                cover_data = zf.read(full)
                                cover_ext  = Path(full).suffix.lower() or '.jpg'
                        elif 'xhtml' in mt_val or 'html' in mt_val:
                            if full in namelist:
                                xhtml = zf.read(full).decode('utf-8', 'replace')
                                im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', xhtml)
                                if im:
                                    img_path = str((Path(full).parent / im.group(1)).as_posix())
                                    if img_path in namelist:
                                        cover_data = zf.read(img_path)
                                        cover_ext  = Path(img_path).suffix.lower() or '.jpg'
                        break
            except Exception:
                pass

            # 2순위: 파일명에 cover 포함된 이미지
            if not cover_data:
                for fn in namelist:
                    if (fn.lower().endswith(('.jpg','.jpeg','.png'))
                            and 'cover' in fn.lower()
                            and '__MACOSX' not in fn
                            and not os.path.basename(fn).startswith('._')):
                        cover_data = zf.read(fn)
                        cover_ext  = Path(fn).suffix.lower()
                        break

            # 2.5순위: 스파인 첫 번째 xhtml 페이지 내 img src
            # (meta cover 없고 cover 파일명도 없을 때 — 19.jpg 같은 케이스 대응)
            if not cover_data:
                try:
                    spine_ids = re.findall(
                        r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf_raw)
                    manifest_map = {}
                    for mm in re.finditer(r'<item\s([^>]*?)\s*/?>', opf_raw, re.IGNORECASE):
                        mid  = re.search(r'\bid=["\']([^"\']+)["\']', mm.group(1))
                        href = re.search(r'\bhref=["\']([^"\']+)["\']', mm.group(1))
                        if mid and href:
                            manifest_map[mid.group(1)] = href.group(1)
                    for sid in spine_ids[:3]:   # 첫 3개 페이지만 확인
                        if sid not in manifest_map:
                            continue
                        href_val = manifest_map[sid]
                        full = (opf_dir + '/' + href_val).lstrip('./') if opf_dir != '.' else href_val
                        if full not in namelist:
                            continue
                        xhtml = zf.read(full).decode('utf-8', 'replace')
                        im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', xhtml)
                        if im:
                            # .. 포함 경로 정규화 (OEBPS/Text/../Images/x.jpg → OEBPS/Images/x.jpg)
                            raw_path = os.path.join(os.path.dirname(full), im.group(1))
                            img_path = os.path.normpath(raw_path).replace('\\', '/')
                            if img_path in namelist:
                                cover_data = zf.read(img_path)
                                cover_ext  = Path(img_path).suffix.lower() or '.jpg'
                                break
                except Exception:
                    pass

            # 3순위: 첫 번째 이미지 (natural sort)
            if not cover_data:
                imgs = [f for f in namelist
                        if f.lower().endswith(('.jpg','.jpeg','.png'))
                        and '__MACOSX' not in f
                        and not os.path.basename(f).startswith('._')]
                if imgs:
                    imgs.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
                    cover_data = zf.read(imgs[0])
                    cover_ext  = Path(imgs[0]).suffix.lower()

            if cover_data:
                return cover_data, cover_ext
    except Exception:
        pass
    return None, None


def extract_cover_candidates(epub_bytes: bytes, include_all_images: bool = False):
    """EPUB 내부의 표지 '후보' 이미지 리스트를 수집한다.

    반환 형식: list[dict] — 각 dict
        {'filename', 'data', 'ext', 'size', 'source', 'is_default', 'label'}
        source: 'opf_meta' | 'guide' | 'name' | 'spine_img' | 'first' | 'image'
        is_default: extract_cover_image()가 기본으로 선택할 이미지이면 True
        label: UI용 짧은 라벨 (예: 'cover.jpg (OPF meta)')

    include_all_images=True 이면 표지 후보가 아닌 내부 이미지까지 포함
    (EPUB 내부 이미지 브라우저용). 이 경우 source='image'.
    """
    candidates = []    # 순서 보존, 파일명 중복 제거
    _seen      = set()

    def _add(fn, data, source):
        if fn in _seen:
            # 같은 파일명은 첫 source 만 유지 (우선순위상 먼저 넣은 게 더 강한 신호)
            return
        _seen.add(fn)
        ext = Path(fn).suffix.lower() or '.jpg'
        label_parts = [os.path.basename(fn)]
        if source == 'opf_meta':
            label_parts.append('(OPF meta)')
        elif source == 'guide':
            label_parts.append('(guide)')
        elif source == 'name':
            label_parts.append('(파일명)')
        elif source == 'spine_img':
            label_parts.append('(첫 페이지 img)')
        elif source == 'first':
            label_parts.append('(첫 이미지)')
        candidates.append({
            'filename'  : fn,
            'data'      : data,
            'ext'       : ext,
            'size'      : len(data),
            'source'    : source,
            'is_default': False,
            'label'     : ' '.join(label_parts),
        })

    try:
        with zipfile.ZipFile(io.BytesIO(epub_bytes), 'r') as zf:
            namelist = zf.namelist()
            opf_raw  = ''
            opf_dir  = '.'

            # OPF 읽기
            try:
                container = zf.read('META-INF/container.xml').decode('utf-8', 'replace')
                opf_path  = re.search(r'full-path="([^"]+\.opf)"', container).group(1)
                opf_raw   = zf.read(opf_path).decode('utf-8', 'replace')
                opf_dir   = str(Path(opf_path).parent)
            except Exception:
                pass

            def _to_full(href_val: str) -> str:
                return (opf_dir + '/' + href_val).lstrip('./') if opf_dir != '.' else href_val

            # 1순위: OPF <meta name="cover">
            if opf_raw:
                cover_id = None
                for m in re.finditer(r'<meta[^>]+name=["\']cover["\'][^>]*content=["\']([^"\']+)["\']', opf_raw):
                    cover_id = m.group(1); break
                if not cover_id:
                    for m in re.finditer(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']cover["\'][^>]*/>', opf_raw):
                        cover_id = m.group(1); break
                if cover_id:
                    for m in re.finditer(r'<item\s[^>]*id=["\']'+ re.escape(cover_id) +r'["\'][^>]*/>', opf_raw):
                        href = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
                        mt   = re.search(r'media-type=["\']([^"\']+)["\']', m.group(0))
                        if not href: break
                        full = _to_full(href.group(1))
                        mt_v = mt.group(1) if mt else ''
                        if 'image' in mt_v and full in namelist:
                            try: _add(full, zf.read(full), 'opf_meta')
                            except Exception: pass
                        elif ('xhtml' in mt_v or 'html' in mt_v) and full in namelist:
                            # xhtml 내부 img 태그 파싱
                            try:
                                xhtml = zf.read(full).decode('utf-8', 'replace')
                                im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', xhtml)
                                if im:
                                    img_path = os.path.normpath(os.path.join(os.path.dirname(full), im.group(1))).replace('\\', '/')
                                    if img_path in namelist:
                                        _add(img_path, zf.read(img_path), 'opf_meta')
                            except Exception: pass
                        break

            # 2순위: <guide> 내 type="cover" 참조
            if opf_raw:
                for m in re.finditer(
                        r'<reference[^>]+type=["\']cover["\'][^>]+href=["\']([^"\']+)["\']',
                        opf_raw, re.IGNORECASE):
                    full = _to_full(m.group(1))
                    # xhtml 이면 내부 img 파싱, image 면 그대로
                    if full.lower().endswith(('.xhtml', '.html', '.htm')):
                        if full in namelist:
                            try:
                                xhtml = zf.read(full).decode('utf-8', 'replace')
                                im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', xhtml)
                                if im:
                                    img_path = os.path.normpath(os.path.join(os.path.dirname(full), im.group(1))).replace('\\', '/')
                                    if img_path in namelist:
                                        _add(img_path, zf.read(img_path), 'guide')
                            except Exception: pass
                    elif full in namelist and full.lower().endswith(('.jpg','.jpeg','.png','.webp')):
                        try: _add(full, zf.read(full), 'guide')
                        except Exception: pass

            # 3순위: 파일명에 cover 포함된 이미지
            for fn in namelist:
                if (fn.lower().endswith(('.jpg','.jpeg','.png','.webp'))
                        and 'cover' in fn.lower()
                        and '__MACOSX' not in fn
                        and not os.path.basename(fn).startswith('._')):
                    try: _add(fn, zf.read(fn), 'name')
                    except Exception: pass

            # 4순위: spine 첫 3개 페이지의 img
            if opf_raw:
                try:
                    spine_ids = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf_raw)
                    manifest_map = {}
                    for mm in re.finditer(r'<item\s([^>]*?)\s*/?>', opf_raw, re.IGNORECASE):
                        mid  = re.search(r'\bid=["\']([^"\']+)["\']', mm.group(1))
                        href = re.search(r'\bhref=["\']([^"\']+)["\']', mm.group(1))
                        if mid and href:
                            manifest_map[mid.group(1)] = href.group(1)
                    for sid in spine_ids[:3]:
                        if sid not in manifest_map: continue
                        full = _to_full(manifest_map[sid])
                        if full not in namelist: continue
                        try:
                            xhtml = zf.read(full).decode('utf-8', 'replace')
                            im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', xhtml)
                            if im:
                                img_path = os.path.normpath(os.path.join(os.path.dirname(full), im.group(1))).replace('\\', '/')
                                if img_path in namelist:
                                    _add(img_path, zf.read(img_path), 'spine_img')
                        except Exception: pass
                except Exception: pass

            # 5순위: 첫 번째 이미지
            imgs = [f for f in namelist
                    if f.lower().endswith(('.jpg','.jpeg','.png','.webp'))
                    and '__MACOSX' not in f
                    and not os.path.basename(f).startswith('._')]
            if imgs:
                imgs.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
                try: _add(imgs[0], zf.read(imgs[0]), 'first')
                except Exception: pass

            # include_all_images: 모든 이미지 추가 (후보에 이미 있는 것 제외)
            if include_all_images:
                for fn in imgs:
                    if fn not in _seen:
                        try: _add(fn, zf.read(fn), 'image')
                        except Exception: pass
    except Exception:
        pass

    # is_default 표시: 첫 번째 후보가 기본값 (extract_cover_image 선택 순서와 동일)
    if candidates:
        candidates[0]['is_default'] = True
    return candidates

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── 파일명 패턴 ────────────────────────────
_CR_FILENAME = re.compile(
    r'copyright|colophon|publication.?right|rights?|imprint',
    re.IGNORECASE)
_CR_FILENAME_KO = re.compile(
    r'판권|저작권|크레딧|credit',
    re.IGNORECASE)
# info / last / end / tail 계열 — 단독으로는 오탐 가능성 있어서 텍스트 확인 병행
_CR_FILENAME_WEAK = re.compile(
    r'^(p?_?info|book_?info|pub_?info|last_?page?|page_?last|'
    r'end_?page?|back|tail|notice|credit|closing|afterword)$',
    re.IGNORECASE)

# ── CSS class 패턴 ─────────────────────────
_CR_CLASS = re.compile(
    r'xnmManagedNote|(?<![_\-\w])copyright(?![_\-\w])|colophon|publication.?right',
    re.IGNORECASE)

# ── 텍스트 강한 패턴 (1개만 있어도 판권) ───
_CR_TEXT_STRONG = re.compile(
    r'초판\s*발행|ISBN[\s\-:：]|발행일\s*[:：]|출판등록\s*번호|'
    r'무단\s*전재\s*및\s*복제|무단\s*복제\s*금지|저작권법|독점\s*계약|'
    r'all\s+rights?\s+reserved|©\s*20\d\d|©[^\n]{0,30}20\d\d|'
    r'출판신고|무단\s*전재[,\s]',   # | 구분자형 판권 (출판신고, 쉼표형 무단전재)
    re.IGNORECASE)

# ── 텍스트 약한 패턴 (2개 이상 조합 시 판권) ──
_CR_TEXT_WEAK = [
    re.compile(r'펴낸곳\s*[:：|]',        re.IGNORECASE),
    re.compile(r'펴낸이\s*[:：|]',        re.IGNORECASE),
    re.compile(r'지은이\s*[:：|]',        re.IGNORECASE),
    re.compile(r'저\s*자\s*[:：|]',       re.IGNORECASE),   # "저 자 | 르뮈" 형태
    re.compile(r'발\s*행\s*처\s*[:：|]',  re.IGNORECASE),   # "발 행 처 | 블리뉴" 형태
    re.compile(r'출판사\s*[:：]',         re.IGNORECASE),
    re.compile(r'전자책\s*발행',      re.IGNORECASE),
    re.compile(r'e-?book\s*(발행|출판|edition)', re.IGNORECASE),
    re.compile(r'뷰컴즈|텐북|카카오페이지|리디북스|네이버시리즈|'
               r'문피아|조아라|로크미디어|대원씨아이|황금가지', re.IGNORECASE),
    re.compile(r'본\s*(도서|책|전자책)는?\s*(저작권|무단)', re.IGNORECASE),
]

def is_skip_page(filename: str, content_bytes: bytes) -> str:
    """판권/목차 페이지면 사유 문자열 반환, 아니면 None.

    판권 감지 전략:
    1. 파일명 강한 패턴 → 즉시 판권
    2. CSS class 패턴 → 즉시 판권
    3. 텍스트 강한 패턴 → 즉시 판권
    4. 파일명 약한 패턴 + 텍스트 약한 패턴 1개 → 판권
    5. 텍스트 약한 패턴 2개 이상 + 짧은 페이지(2000자 미만) → 판권
    목차: 짧고 목차 + 장/화 번호 목록 포함
    """
    name = Path(filename).stem.lower()
    raw  = _decode_markup_bytes(content_bytes)
    import html as _html_mod
    text = re.sub(r'<[^>]+>', '', raw)
    text = _html_mod.unescape(text)          # &lt;목차&gt; → <목차> 등 엔티티 디코딩
    text = text.replace('│', '|').replace('┃', '|')  # 박스문자 파이프 정규화
    text = text.replace('ⓒ', '©')           # 원문자 ⓒ → © 정규화
    text = re.sub(r'\s+', ' ', text).strip()
    head = text[:800]   # 판권은 앞부분에 몰려 있음

    # 1. 파일명 강한 패턴
    if _CR_FILENAME.search(name) or _CR_FILENAME_KO.search(name):
        return 'copyright'

    # 2. CSS class 패턴
    for cls in re.findall(r'class=["\']([^"\']+)["\']', raw):
        if _CR_CLASS.search(cls):
            return 'copyright'

    # 3. 텍스트 강한 패턴 (본문이 긴 경우 복합 파일 → 유지)
    if _CR_TEXT_STRONG.search(head) and len(text) < 2000:
        return 'copyright'

    # 4. 파일명 약한 패턴 + 텍스트 약한 패턴 1개 (본문 긴 경우 유지)
    weak_name = bool(_CR_FILENAME_WEAK.search(name))
    weak_hits = sum(1 for p in _CR_TEXT_WEAK if p.search(head))
    if weak_name and weak_hits >= 1 and len(text) < 2000:
        return 'copyright'

    # 5. 짧은 페이지 + 텍스트 약한 패턴 2개 이상
    if len(text) < 2000 and weak_hits >= 2:
        return 'copyright'

    # 카카오페이지 chapter_0: 파일명이 정확히 chapter_0이고 이미지만 있는 화 표지 반복 페이지
    if name == 'chapter_0':
        has_img = bool(re.search(r'<img\b', raw, re.IGNORECASE))
        if has_img and len(text) < 100:
            return 'cover'

    # cover 페이지: 파일명에 cover 포함 + 실질 텍스트 없음 → 제거
    # map/삽화 이미지 페이지는 유지 (챕터 구분 삽화, 지도 등 의미있는 콘텐츠)
    # (<style> 블록 제거 후 텍스트로 판단 — CSS 인라인 텍스트 오탐 방지)
    if 'cover' in name or re.search(r'<img\b', raw, re.IGNORECASE):
        raw_no_style = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL|re.IGNORECASE)
        text_no_style = re.sub(r'<[^>]+>', '', raw_no_style)
        text_no_style = _html_mod.unescape(text_no_style)  # &#xc218; 등 엔티티 디코딩 후 길이 측정
        text_no_style = re.sub(r'\s+', ' ', text_no_style).strip()
        # cover 파일명 + img 태그 있음 + 텍스트 60자 미만 → 표지로 제거
        # img src 파일명에 cover가 포함된 경우도 표지로 감지
        # (bastian_cover.jpg 참조하는 bastian_000.xhtml 같은 케이스 대응)
        has_img = bool(re.search(r'<img\b', raw, re.IGNORECASE))
        if has_img and len(text_no_style) < 60:
            _img_src_m = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', raw, re.IGNORECASE)
            _img_is_cover = bool(_img_src_m and 'cover' in Path(_img_src_m.group(1)).name.lower())
            if 'cover' in name or _img_is_cover:
                return 'cover'

    # 목차 페이지: 파일명에 toc / table / contents / index / book_table 포함
    if re.search(r'\btoc\b|^table$|^contents?$|^index$|^book_table$', name):
        return 'index'

    _chap_num_pat = re.compile(
        r'\d+[장화부]|\d+-\d+[.\s]|Episode\s*\d+|Ch(apter)?\s*\d+', re.IGNORECASE)

    # 목차 페이지: 짧고 "목차"/"차례"/"<목차>"/"Contents" + 장/화 번호 나열
    if len(text) < 1200 and re.search(r'목차|차례|<목차>|Contents', text, re.IGNORECASE) \
            and _chap_num_pat.search(text):
        return 'index'

    # 목차 페이지: 매우 짧고(200자 미만) 장/화 번호가 각각 다른 블록 요소(<p>/<li> 등)에 나열
    # "3부 2장 - 제목" 처럼 단일 요소 안에 숫자 2개가 있는 챕터 제목은 오탐 방지
    if len(text) < 200:
        _block_texts = re.findall(
            r'<(?:p|li|div|td|dd|h[1-6])\b[^>]*>(.*?)</(?:p|li|div|td|dd|h[1-6])>',
            raw, re.IGNORECASE | re.DOTALL)
        _blocks_with_num = sum(
            1 for _b in _block_texts
            if _chap_num_pat.search(re.sub(r'<[^>]+>', '', _b)))
        if _blocks_with_num >= 2:
            return 'index'

    return None

# (패턴, 제목 캡처 그룹 번호)
_TITLE_PATS = [
    # 0. sigil_toc_id: NCX 연결 포인트 (가장 정확한 챕터 헤딩)
    (re.compile(r'<[^>]+\bid="sigil_toc_id[^"]*"[^>]*>(.*?)</[a-z0-9]+>', re.IGNORECASE | re.DOTALL), 1),
    # 1. h1~h6 태그 (sigil_not_in_toc 제외)
    (re.compile(r'<h[1-6](?![^>]*sigil_not_in_toc)[^>]*>(.*?)</h[1-6]>', re.IGNORECASE | re.DOTALL), 1),
    # 1.5. box-line 계열 챕터 (알에스미디어/신규 양식)
    # 예) <p class="font3"><span class="box-line1">프롤로그</span></p>
    # 예) <p class="font3"><span class="box-line1">#001화. ███(이)가 ███을(를) 숨김 (1)</span></p>
    # 같은 파일에 <span class="t-num2">책 제목</span>이 같이 있어도
    # box-line 클래스가 붙은 것만 챕터 제목으로 채택된다.
    (re.compile(
        r'<p[^>]*>\s*<span[^>]*\bclass=["\'][^"\']*\bbox-line\d*\b[^"\']*["\'][^>]*>(.*?)</span>\s*</p>',
        re.IGNORECASE | re.DOTALL), 1),
    # 1.6. id="id_top" 챕터 (Calibre/탈옥한 천재마법사 등)
    # 예) <p id="id_top" class="block_">#001화. 입소 (1)</p>
    (re.compile(
        r'<p[^>]*\bid=["\']id_top["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL), 1),
    # 2. 챕터/제목 관련 class
    (re.compile(
        r'<[^>]+class=["\'][^"\']*(?:chapter|chap|Title|title|header|heading|'
        r'part_header_title|section_title|np|toc\b)[^"\']*["\'][^>]*>(.*?)</[^>]+>',
        re.IGNORECASE | re.DOTALL), 1),
    # 3. p태그: 숫자+화/장/권/부/절/막/편 (단독 or 부제 포함)
    # 긴 부제(예: 221화. ... (1)) 대응을 위해 허용 길이를 40→120으로 확장
    (re.compile(
        r'<p[^>]*>\s*((?:\d+[-−~]\d+|\d+)\s*[화장권부절막편]\s*[.\s)）]?.{0,120}?)\s*</p>',
        re.IGNORECASE), 1),
    # 3.5. p태그: #N 형식 챕터 제목
    # 예) <p>#101 전쟁의 결과</p>       — 공백 구분
    # 예) <p>#1. 집행자 (1)</p>         — 마침표 바로 붙음
    # 예) <p>#001화. 입소 (1)</p>       — 숫자 뒤에 '화' 바로 붙음
    # 예) <p>#12: 부제목</p>            — 콜론 구분
    # 예) <p>#1</p>                    — 숫자만
    (re.compile(
        r'<p[^>]*>\s*([#＃]\s*\d+[^<]{0,80})\s*</p>',
        re.IGNORECASE), 1),
    # 4. p태그: X.X 형식 제목 (e.g. 1.1 서론, 2부 3장)
    (re.compile(
        r'<p[^>]*>\s*(\d+[부권]?\s*[-\.]\s*\d*\s*.{2,40}?)\s*</p>',
        re.IGNORECASE), 1),
    # 5. p태그: "1부. 부제", "제1장", "서막" 등 선두 키워드
    (re.compile(
        r'<p[^>]*>\s*((?:제?\d+\s*[부장절막편권화]\s*[.\.。·]?\s*.{1,40}|'
        r'프롤로그|에필로그|서막|종막|막간|외전|번외|특전))\s*</p>',
        re.IGNORECASE), 1),
    # 6. p/div 내부 b/strong 단독
    # 예) <p><b>제목</b></p>
    # 예) <div><b>#147화_마경으로(4)</b></div>
    # 예) <div><b>#167화_임모탈(5)</b><br/></div>  — 끝에 <br/> 오는 경우
    (re.compile(
        r'<(?:p|div)[^>]*>\s*<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>\s*(?:<br\s*/?>\s*)*</(?:p|div)>',
        re.IGNORECASE | re.DOTALL), 1),
    # 3.6. p태그 내부 span 인라인 bold — 예: <p><span style="font-weight: bold;">#1화_용병단 키우기</span><br/></p>
    (re.compile(
        r'<p[^>]*>\s*<span\b[^>]+font-weight\s*:\s*bold[^>]*>(.*?)</span>\s*(?:<br\s*/?>\s*)*</p>',
        re.IGNORECASE | re.DOTALL), 1),
]

# center 정렬 + bold span 패턴 — 태그 제거 후 텍스트로 별도 처리
# e.g. <p style="text-align: center;"><span style="font-weight: bold;">5-8. 엘렌의 결투 대회</span><br/></p>
_CENTER_BOLD_PAT = re.compile(
    r'<p\b[^>]*text-align\s*:\s*center[^>]*>(.*?)</p>',
    re.IGNORECASE | re.DOTALL)
_CHAP_NUM_TITLE  = re.compile(
    r'^(?:\d+[-−~]\d+|\d+)[.\-\s].{1,60}$')

_CDATA_PAT = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)

def _read_dc_tag(opf_text: str, tag: str) -> str:
    """OPF에서 <dc:tag> 값 추출. CDATA 감싸기 대응."""
    m = re.search(f'<{tag}[^>]*>(.*?)</{tag}>', opf_text, re.IGNORECASE | re.DOTALL)
    if not m:
        return ''
    inner = m.group(1)
    cd = _CDATA_PAT.search(inner)
    return (cd.group(1) if cd else inner).strip()


# ── 판권 페이지 작가명 추출 ────────────────────────────────────
# 구분자: ':' (ASCII), '：' (U+FF1A 전각 콜론), '|' (ASCII), '｜' (U+FF5C 전각 세로막대)
_CR_AUTHOR_PATS = [
    re.compile(r'지은이\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'글쓴이\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'저\s*자\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'작\s*가\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'Author\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
]
_CR_AUTHOR_NOISE = re.compile(
    r'발행|출판|주소|전화|E-?mail|ISBN|http|\d{2,}[-\d]+', re.IGNORECASE)

def _extract_creator_from_html(raw_html: str) -> str:
    """HTML에서 판권 페이지의 작가명 추출.
    예) <p class="block_6">지은이 : 얼음커피</p>  →  '얼음커피'
    ※ 블록 경계(</p>, </div>, <br>)를 줄바꿈으로 치환해 각 단락을 독립적으로 검사한다.
       그렇지 않으면 `지은이｜진설우</p><p>편집부｜유서영` 같이 인접 단락이 한 줄로 합쳐져
       `진설우 편집부` 처럼 과잉 매칭되는 버그가 생긴다.
    """
    import html as _hm
    # 블록/개행 태그를 실제 개행으로 변환
    tmp = re.sub(r'<\s*br\s*/?\s*>', '\n', raw_html, flags=re.IGNORECASE)
    tmp = re.sub(r'</\s*(?:p|div|li|h[1-6]|tr|td|th)\s*>', '\n', tmp, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', tmp)
    text = _hm.unescape(text)
    # 개행은 보존, 다른 공백만 축약
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    # 1차: 라인 단위 라벨 기반 파싱 (지은이｜진설우 / Author: Name)
    _label_pat = re.compile(
        r'(?:\uC9C0\uC740\uC774|\uAE00\uC4F4\uC774|\uC800\uC790|\uC791\uAC00|\uC6D0\uC791|author)'
        r'\s*[:\|\uFF1A\uFF5C\uFFE8]\s*([^\n\r\|\uFF5C:：]{1,30})',
        re.IGNORECASE)
    _copy_pat = re.compile(
        r'[©\u24D2]\s*([A-Za-z\uAC00-\uD7A3][A-Za-z\uAC00-\uD7A30-9.\s\u00B7]{1,24})\s*,?\s*\d{4}',
        re.IGNORECASE)
    for ln in text.split('\n'):
        line = re.sub(r'\s+', ' ', ln).strip()
        if not line:
            continue
        for pat in (_label_pat, _copy_pat):
            m = pat.search(line)
            if not m:
                continue
            name = m.group(1).strip().rstrip('.,;:|｜')
            if _CR_AUTHOR_NOISE.search(name):
                continue
            if 1 < len(name) <= 20 and re.search(r'[A-Za-z\uAC00-\uD7A3]', name):
                return name
    for pat in _CR_AUTHOR_PATS:
        m = pat.search(text)
        if m:
            name = m.group(1).strip().rstrip('.,;')
            if _CR_AUTHOR_NOISE.search(name):
                continue
            if 1 < len(name) <= 20:
                return name
    return ''


# ── 판권 페이지 제목 추출 ────────────────────────────────────
# 판권 페이지에 나타나는 제목 전용 HTML 패턴 (우선순위 순)
_CR_TITLE_HTML_PATS = [
    # <p class="font6"><span class="t-num2">제목</span></p>
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*font6[^"\']*["\'][^>]*>\s*'
        r'<span\b[^>]+class=["\'][^"\']*t-num2[^"\']*["\'][^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL),
    # <p class="block_4">제목</p>  (block_4 = 판권 페이지 대제목)
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*block_4[^"\']*["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL),
    # <p class="titleE">제목<br/></p>  (하이스토리 등 판권 페이지 제목)
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*titleE[^"\']*["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL),
    # <p class="title*">제목</p>  (title / title1 / titleA 등 일반형)
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*\btitle[A-Za-z0-9_\-]*["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL),
    # <h1/h2>제목</h1> 판권 페이지 상단 큰 제목
    re.compile(
        r'<h[1-3]\b[^>]*>(.*?)</h[1-3]>',
        re.IGNORECASE | re.DOTALL),
]
# 제목으로 쓸 수 없는 잡음 판단
_CR_TITLE_NOISE = re.compile(
    r'발행|출판|지은이|저자|ISBN|http|E-?mail|주소|전화|무단|저작권'
    r'|\d{3,}|All\s+Rights',
    re.IGNORECASE)

def _extract_title_from_html(raw_html: str) -> str:
    """HTML 판권 페이지에서 책 제목 추출.
    예) <p class="block_4">탈옥한 천재마법사</p>  →  '탈옥한 천재마법사'
        <p class="font6"><span class="t-num2">환생자는 편하게 살고 싶다</span></p>
    """
    for pat in _CR_TITLE_HTML_PATS:
        for m in pat.finditer(raw_html):
            inner = re.sub(r'<br\s*/?>', ' ', m.group(1), flags=re.IGNORECASE)
            text  = re.sub(r'<[^>]+>', '', inner).strip()
            import html as _hm2
            text  = _hm2.unescape(text)
            text  = re.sub(r'\s+', ' ', text).strip()
            # 잡음(발행처·주소 등) 포함이거나 화수 패턴이면 스킵
            if _CR_TITLE_NOISE.search(text):
                continue
            if re.search(r'^\d+\s*[화권편]|^[#＃]\s*\d+', text):
                continue
            if 2 < len(text) < 60 and re.search(r'[가-힣]{2,}', text):
                return text
    return ''


def _normalize_title(s: str) -> str:
    """제목 문자열 후처리 (ridi_rename normalize_text 참고)
    NFKC 정규화, 제로폭 공백 제거, HTML 엔티티 디코딩, 연속 공백 정리
    ※ 전각 물음표 ？(U+FF1F)는 NFKC 변환 전 보호 (Windows 파일명 허용 문자)
    """
    import unicodedata, html as _html
    s = _html.unescape(s)
    s = _strip_filename_parse_noise(s)
    # 전각기호 보호: NFKC가 전각→반각으로 변환하면 _safe_title(_FORBIDDEN)이 제거하므로 임시 치환
    # Windows 금지문자(\ / : * ? " < > |)에 대응하는 전각 버전을 모두 보호
    _FW_MAP = [
        ('？', '\x00FW_QM\x00'),   # U+FF1F → ?
        ('：', '\x00FW_CL\x00'),   # U+FF1A → :
        ('＂', '\x00FW_DQ\x00'),   # U+FF02 → "
        ('｜', '\x00FW_PI\x00'),   # U+FF5C → |
        ('＊', '\x00FW_AS\x00'),   # U+FF0A → *
        ('＜', '\x00FW_LT\x00'),   # U+FF1C → <
        ('＞', '\x00FW_GT\x00'),   # U+FF1E → >
        ('／', '\x00FW_SL\x00'),   # U+FF0F → /
        ('＼', '\x00FW_BS\x00'),   # U+FF3C → \
    ]
    for _ch, _tok in _FW_MAP:
        s = s.replace(_ch, _tok)
    s = unicodedata.normalize('NFKC', s)
    for _ch, _tok in _FW_MAP:
        s = s.replace(_tok, _ch)
    for zw in ('​','‌','‍','⁠','﻿'):
        s = s.replace(zw, '')
    s = s.replace('_', ' ')   # OPF 제목 내 언더스코어 → 공백
    s = re.sub(r'[\s ]+', ' ', s).strip()
    return s

_FORBIDDEN = re.compile(r'[\\/:*?"<>|]')

def _strip_filename_parse_noise(s: str) -> str:
    """파일명/제목 파싱 전에 변형 문자와 보이지 않는 문자를 제거한다.

    ᵘ 같은 modifier/superscript 문자는 NFKC 전에 제거해야 일반 문자(u)로
    치환되지 않고 완전히 사라진다.
    """
    import unicodedata
    if not s:
        return ''
    s = unicodedata.normalize('NFC', s)
    out = []
    for ch in s:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if cat == 'Cf':
            continue
        if cp in (0xFE0E, 0xFE0F):   # variation selectors
            continue
        if 0x02B0 <= cp <= 0x02FF:   # Spacing Modifier Letters
            continue
        if 0x1D2C <= cp <= 0x1D7F:   # phonetic/superscript modifier letters (ᵘ 포함)
            continue
        if 0x2070 <= cp <= 0x209F:   # superscripts and subscripts
            continue
        out.append(ch)
    return ''.join(out)

def _safe_title(s: str) -> str:
    """Windows 금지문자 제거 (ridi_rename safe_name 참고)"""
    s = s.replace('\n', ' ').strip()
    s = _FORBIDDEN.sub(' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

_CHAPTERISH_PAT = re.compile(
    r'(?:(?<![가-힣])제?\s*\d+\s*[화장권부식]|[#＃]\s*\d+|프롤로그|에필로그|(?:외전|번외|특전)\s*\d+\s*화)',
    re.IGNORECASE)

def _is_chapterish_title(s: str) -> bool:
    """제목이 챕터/화수 성격이면 True."""
    if not s:
        return False
    return bool(_CHAPTERISH_PAT.search(_normalize_title(s)))

def _is_series_volume_heading(s: str) -> bool:
    """'케이 18권'처럼 시리즈명+권수만 있는 권 제목인지 판정."""
    if not s:
        return False
    t = _normalize_title(s)
    t = re.sub(r'\s*\(연재중?\)\s*', '', t).strip()
    if re.search(r'(?:제\s*)?\d+\s*[화장편회식]|[#＃]\s*\d+|프롤로그|에필로그|서장|종장', t):
        return False
    return bool(re.match(r'^[가-힣A-Za-z][가-힣A-Za-z0-9 ._\-:：]{0,45}\s+\d{1,4}\s*권$', t))

def _series_volume_label_from_heading(s: str) -> str:
    """권 제목 후보를 '제목 N권' 라벨로 정규화."""
    t = _normalize_title(s or '')
    t = re.sub(r'\s*\(연재중?\)\s*', '', t).strip()
    m = re.search(r'(\d{1,4})\s*권\s*$', t)
    if not m:
        return t
    vol = f"{int(m.group(1))}권"
    title = re.sub(r'\s*\d{1,4}\s*권\s*$', '', t).strip()
    title = _safe_title(title)
    return f"{title} {vol}".strip() if title else vol

def _extract_series_volume_heading_from_html(raw_html: str) -> str:
    """본문 HTML에서 실제 권 제목(h1~h6/title 계열)을 추출."""
    import html as _html
    candidates: list[str] = []
    for pat in (
            r'<h[1-6][^>]*>(.*?)</h[1-6]>',
            r'<p[^>]*\bclass=["\'][^"\']*[Tt]itle[^"\']*["\'][^>]*>(.*?)</p>',
            r'<h[1-6][^>]+\btitle=["\']([^"\']+)["\']'):
        for m in re.finditer(pat, raw_html, re.IGNORECASE | re.DOTALL):
            raw = m.group(1)
            raw = re.sub(r'<br\s*/?>', ' ', raw, flags=re.IGNORECASE)
            raw = re.sub(r'<[^>]+>', '', raw)
            raw = _html.unescape(raw)
            raw = re.sub(r'\s+', ' ', raw).strip()
            if raw:
                candidates.append(raw)
    for cand in candidates:
        if _is_series_volume_heading(cand):
            return _series_volume_label_from_heading(cand)
    return ''

def _find_series_volume_heading_in_zip(zf, opf_raw: str, opf_dir: str, max_files: int = 5) -> str:
    """OPF spine 앞쪽에서 '제목 N권' 형태의 실제 권 제목을 찾는다."""
    try:
        manifest: dict[str, str] = {}
        for mm in re.finditer(r'<item\s([^>]*?)/?>', opf_raw, re.IGNORECASE):
            mid = re.search(r'\bid=["\']([^"\']+)["\']', mm.group(1))
            mh = re.search(r'\bhref=["\']([^"\']+)["\']', mm.group(1))
            if mid and mh:
                manifest[mid.group(1)] = mh.group(1)
        spine_ids = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf_raw)
        for sid in spine_ids[:max_files]:
            href = manifest.get(sid, '')
            if not href:
                continue
            full = (opf_dir + '/' + href).lstrip('./') if opf_dir != '.' else href
            if full not in zf.namelist():
                full = href
            if full not in zf.namelist():
                continue
            heading = _extract_series_volume_heading_from_html(
                zf.read(full).decode('utf-8', 'replace'))
            if heading:
                return heading
    except Exception:
        pass
    return ''

_SUBNAV_HEAD_PAT = re.compile(
    r'^(?:prologue|epilogue|chapter\s*\d+|ch\.?\s*\d+|part\s*\d+'
    r'|프롤로그|에필로그|서장|종장|외전|번외|특전)$',
    re.IGNORECASE)

def _is_subnav_heading_candidate(s: str) -> bool:
    """한 xhtml 내 분할용(sub-navPoint) 헤딩으로 쓸 수 있는지 판정."""
    t = _normalize_title(s or '')
    if not t or not (2 <= len(t) <= 70):
        return False
    # 본문 문장 종결형은 제외
    if re.search(r'[.!?…]$', t):
        return False
    # 챕터/화수형 제목은 허용
    if _is_chapterish_title(t):
        return True
    # 명시적 헤딩 키워드 허용
    if _SUBNAV_HEAD_PAT.match(t):
        return True
    # 숫자형 챕터(예: 1.1 제목, 2-3 제목)
    if re.match(r'^\d+(?:[.\-]\d+)?\s+\S+', t):
        return True
    # 너무 긴 일반 문장은 제외
    if len(t.split()) >= 6:
        return False
    return False

def _clean_opf_series_title(raw: str, *,
                            strip_genre_tag: bool = False,
                            strip_interview: bool = False,
                            preserve_complete_paren: bool = False,
                            protect_edition_paren: bool = False) -> str:
    """OPF/판권에서 얻은 제목 문자열을 시리즈명 기준으로 정제."""
    t = _normalize_title(raw)
    if strip_genre_tag:
        t = re.sub(r'^\s*\[[A-Za-z가-힣0-9]{1,6}\]\s*', '', t)
    t = re.sub(r'^(?:(?<![가-힣])제)?\s*\d+\s*화\s*[._]?\s*', '', t)
    t = re.sub(r'^[#＃]\s*\d+\s*', '', t)
    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화]\s*', ' ', t)
    t = re.sub(r'(\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부)(?!\s*[-–—―]|\s+[가-힣])', ' ', t)
    t = re.sub(r'\s+[-–—]?\s*([A-Za-z가-힣]*(?:외전\d*|번외\d*|특전\d*)|단행본|합본)\s*$', '', t)
    if strip_interview:
        t = re.sub(r'\s+(?:인터뷰집|인터뷰|작가노트)\s*$', '', t)
    _wk = ''
    if preserve_complete_paren:
        _wk_m = re.search(r'[\(（]\s*완결\s*[\)）]', t)
        _wk = (' ' + _wk_m.group(0).strip()) if _wk_m else ''
    if protect_edition_paren:
        _ED_KW = r'(?:19세\s*)?(?:개정증보판|증보판|개정판|완전판|외전증보판)'
        def _protect_edition(m):
            return '__EDSTART__' + m.group(0).strip('([（【)】）]').strip() + '__EDEND__'
        t = re.sub(r'[\(\[（【][^\)\]）】]*(?:' + _ED_KW + r')[^\)\]）】]*[\)\]）】]', _protect_edition, t)
        t = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*', ' ', t)
        t = re.sub(r'__EDSTART__([^_]*)__EDEND__', r'(\1)', t)
    else:
        t = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*', ' ', t)
    t = re.sub(r'\s+\d+/\d+\s*$', '', t)
    t = re.sub(r'\s+\d+\s*$', '', t)
    t = re.sub(r'^[\s.\-·]+|[\s.\-·]+$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if _wk:
        t = (t + _wk).strip()
    return t

def _series_from_parent_dir(path: str) -> str:
    """numeric-id 파일의 시리즈명 폴백: 부모 폴더명에서 제목만 추출."""
    try:
        parent = Path(path).resolve().parent.name
    except Exception:
        parent = Path(path).parent.name
    if not parent:
        return ''
    s = _normalize_title(parent)
    s = re.sub(r'[_\s-]\d{9,}$', '', s).strip()        # ..._1776657938080
    s = re.sub(r'\s+\d+\s*[-~]\s*\d+\s*$', '', s).strip()  # ... 1-444
    s = re.sub(r'\s*(?:완결|完)\s*$', '', s).strip()
    s = re.sub(r'\s*[\[\(（【].*?[\]\)）】]\s*$', '', s).strip()
    s = re.sub(r'\s+', ' ', s).strip(' _-')
    return s

def _guess_tail_volume_unit_from_zip(zf, tail_num: int, numeric_id_hint: bool = False) -> str:
    """EPUB 본문을 보고 tail number의 단위를 권/화로 추정."""
    unit = '권'
    if not numeric_id_hint:
        try:
            for ncx_name in zf.namelist():
                if not ncx_name.lower().endswith('.ncx'):
                    continue
                ncx_raw = zf.read(ncx_name).decode('utf-8', 'replace')
                nav_labels = re.findall(
                    r'<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>',
                    ncx_raw, re.DOTALL | re.IGNORECASE)
                chap_navs = 0
                for nav in nav_labels:
                    nt = re.sub(r'<[^>]+>', '', nav)
                    nt = _normalize_title(nt)
                    if re.search(r'\d+\s*[화장편회]', nt):
                        chap_navs += 1
                        if chap_navs >= 2:
                            return '권'
        except Exception:
            pass
    chapterish_pages = 0
    saw_serial_hint = False
    saw_tail_hwa = False
    for xn in zf.namelist():
        if not xn.lower().endswith(('.xhtml', '.html', '.htm')):
            continue
        xb = zf.read(xn)
        xc = xb.decode('utf-8', 'replace')
        plain = re.sub(r'<[^>]+>', '', xc)
        if re.search(r'연재', plain):
            saw_serial_hint = True
        if re.search(rf'{tail_num}\s*화', plain):
            saw_tail_hwa = True
        if not numeric_id_hint:
            try:
                xh_any = extract_chapter_title(xb)
            except Exception:
                xh_any = ''
            if xh_any and (re.search(r'\d+\s*[화장편회]', xh_any)
                           or re.search(r'프롤로그|에필로그|서장|종장', xh_any)):
                chapterish_pages += 1
                if chapterish_pages >= 2:
                    return '권'
        if numeric_id_hint:
            xh = extract_chapter_title(xb)
            if xh and (re.search(r'\d+\s*화', xh)
                       or re.match(r'^[#＃]\s*\d+', xh)
                       or re.search(r'프롤로그|에필로그', xh)):
                return '화'
    if saw_serial_hint or saw_tail_hwa:
        return '화'
    return unit

def _strip_trailing_volume_suffix(title: str) -> str:
    """문자열 끝의 권/화/부 표기를 제거해 시리즈명만 남긴다."""
    t = _normalize_title(title or '')
    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부]\s*$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

_GENERIC_NCX_SET = {
    '시작', '본문', '내용', '내용 시작', '무제',
    'start', 'begin', 'content', 'section', 'chapter', 'untitled',
}
_GENERIC_NCX_PAT = re.compile(
    r'^chapter\s*\d*$'              # Chapter N
    r'|^제?\s*\d+\s*화\s*[_.\-]?$'  # 1화_ / 제1화. / 1화
    r'|^제?\s*\d+\s*권\s*[_.\-]?$'  # 1권_ / 제1권
    r'|^\d+\s*[화권부]\s*$'          # 숫자+단위만
    r'|^[#＃]\s*\d+\s*$',           # #101 단독
    re.IGNORECASE)

def _is_generic_ncx_label(label: str) -> bool:
    """NCX 라벨이 의미없는 generic 값이면 True (대소문자 무관)."""
    if not label:
        return False
    lo = label.strip().lower()
    return lo in _GENERIC_NCX_SET or bool(_GENERIC_NCX_PAT.match(lo))


def _compact_toc_label_for_series(label: str, series_title: str) -> str:
    """반복되는 작가/시리즈명을 목차 표시용 권·화 라벨로 줄인다.

    예: "[작가] 작품 17권 (외전)" + "[작가] 작품 1-19권+외전"
        → "17권 (외전)"
    """
    raw = _normalize_title(label or '').strip()
    if not raw:
        return ''

    def _series_base(value: str) -> str:
        t = _normalize_title(value or '').strip()
        t = re.sub(r'\.[A-Za-z0-9]{2,5}$', '', t).strip()
        t = re.sub(r'^\[[^\]]+\]\s*', '', t).strip()
        t = re.sub(r'\s*\(완결\)\s*$', '', t, flags=re.IGNORECASE).strip()
        t = re.sub(r'\s+\d{1,5}\s*[-~]\s*\d{1,5}\s*[권화부]\s*(?:\+\s*(?:특외|특별\s*외전|외전|번외|특전))*\s*$', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s+\d{1,5}\s*[권화부]\s*(?:\+\s*(?:특외|특별\s*외전|외전|번외|특전))*\s*$', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s+(?:본편\+)?(?:특외|특별\s*외전|외전|번외|특전)\s*$', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    bases = []
    for src in (series_title, _strip_trailing_volume_suffix(series_title or '')):
        base = _series_base(src)
        if base and len(base) >= 2 and base not in bases:
            bases.append(base)

    text = re.sub(r'^\[[^\]]+\]\s*', '', raw).strip()
    for base in sorted(bases, key=len, reverse=True):
        tail = re.sub(r'^' + re.escape(base) + r'\s*', '', text).strip()
        if tail == text:
            continue
        tail = re.sub(r'\s+', ' ', tail).strip()
        if re.match(r'^(?:#\s*)?(?:제\s*)?\d{1,5}\s*[권화부회장]\b', tail):
            return tail
        if re.match(r'^\d{1,5}\s*[-~]\s*\d{1,5}\s*[권화부]\b', tail):
            return tail
        if re.match(r'^(?:특외|특별\s*외전|외전|번외|특전)\b', tail, re.IGNORECASE):
            return tail
    return raw


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 TXT → EPUB 엔진 (챕터 감지 + 빌드)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import html as _html_mod

# 강도별 챕터 패턴 — 우선순위(앞쪽이 우선)
CHAPTER_PATTERN_SETS = {
    "weak": [
        ("KOR_특수확장", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:(?:제\s*)?\d+\s*[화장권부]\s*)?(?:특별\s*)?(?:외전|번외|특전|에필로그|프롤로그|서장|종장)\b'),
        ("KOR_꺾쇠N화", r'^.{0,120}?[<＜]\s*\d+\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$'),
        ("KOR_제N화", r'^제\s?\d+\s?[화장편권부회]'),
        ("KOR_N화",   r'^\d+\s?[화장편권부회](?=\s|[.\:：\)）]|$)'),
        ("KOR_외전N화", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*화(?=\s|[.,，!！?？\:：\)）\-–—]|$)'),
        ("KOR_외전N점", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*[.\．]'),
        ("KOR_장외전", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:제\s*)?\d+\s*장\s*(?:외전|번외|특전)(?:\s*\d+\s*화)?\b'),
        ("NUM_HASH_DOT", r'^\s*[#＃]\s*\d{1,5}\s*[.)．:：]\s*\S+'),
        ("NUM_샵",    r'^[#＃]\s?\d+'),
    ],
    "normal": [
        ("KOR_특수확장", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:(?:제\s*)?\d+\s*[화장권부]\s*)?(?:특별\s*)?(?:외전|번외|특전|에필로그|프롤로그|서장|종장)\b'),
        ("KOR_꺾쇠N화", r'^.{0,120}?[<＜]\s*\d+\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$'),
        ("KOR_제N화",   r'^제\s?\d+\s?[화장편권부회]'),
        ("KOR_N화",     r'^\d+\s?[화장편권부회](?=\s|[.\:：\)）]|$)'),
        ("KOR_외전N화", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*화(?=\s|[.,，!！?？\:：\)）\-–—]|$)'),
        ("KOR_외전N점", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*[.\．]'),
        ("KOR_장외전",  r'^[\s\-\–\—\·\•\[\(＜<]*?(?:제\s*)?\d+\s*장\s*(?:외전|번외|특전)(?:\s*\d+\s*화)?\b'),
        ("KOR_외전N",   r'^(?:외전|번외|특전)\s*\d+\b'),
        ("KOR_N외전",   r'^\d+\s*(?:외전|번외|특전)\b'),
        # 제목 + 숫자+화/장/편 (줄 끝) — 디비 없이 '아무 제목 N화'를 일반 감지
        ("KOR_끝N화",   r'^.{2,80}?\s+\d+\s?[화장편](?:\s*[\(（][^\)）]{0,60}[\)（])?\s*$'),
        # 제목 + 숫자점 소제목 (예: 성스러운아이돌 252. 세계 최초 아냐?)
        ("KOR_끝N점",   r'^.{2,120}?\s+\d+\s*\.\s*\S.+$'),
        # 꺾쇠 내부 숫자점 소제목 (예: 성스러운아이돌 < 56. 벌써부터 오만하다 >)
        ("KOR_꺾쇠N점", r'^.{0,120}?[<＜]\s*\d+\s*[.,，]\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$'),
        # N회차 (회귀/회차 장르)
        ("KOR_N회차",   r'^\d+\s?회차\b'),
        ("KOR_특수",    r'^(?:서장|종장|프롤로그|에필로그|외전)\b'),
        ("ENG_Chapter", r'^(?:Chapter|CHAPTER|chapter)\s+\d+'),
        ("ENG_Ch",      r'^Ch\.?\s*\d+\b'),
        ("ENG_Part",    r'^(?:Part|PART|Volume|VOLUME)\s+\d+'),
        ("ENG_특수",    r'^(?:Prologue|Epilogue|Interlude)\b'),
        ("NUM_점",      r'^\d+\s*[\.\:\)](?:\s|$)'),
        ("NUM_HASH_DOT", r'^\s*[#＃]\s*\d{1,5}\s*[.)．:：]\s*\S+'),
        ("NUM_샵",      r'^[#＃]\s?\d+'),
    ],
    "strong": [
        ("KOR_특수확장", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:(?:제\s*)?\d+\s*[화장권부]\s*)?(?:특별\s*)?(?:외전|번외|특전|에필로그|프롤로그|서장|종장)\b'),
        ("KOR_꺾쇠N화", r'^.{0,120}?[<＜]\s*\d+\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$'),
        ("KOR_제N화",   r'^제\s?\d+\s?[화장편권부회]'),
        ("KOR_N화",     r'^\d+\s?[화장편권부회](?=\s|[.\:：\)）]|$)'),
        ("KOR_외전N화", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*화(?=\s|[.,，!！?？\:：\)）\-–—]|$)'),
        ("KOR_외전N점", r'^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*[.\．]'),
        ("KOR_장외전",  r'^[\s\-\–\—\·\•\[\(＜<]*?(?:제\s*)?\d+\s*장\s*(?:외전|번외|특전)(?:\s*\d+\s*화)?\b'),
        ("KOR_외전N",   r'^(?:외전|번외|특전)\s*\d+\b'),
        ("KOR_N외전",   r'^\d+\s*(?:외전|번외|특전)\b'),
        ("KOR_끝N화",   r'^.{2,80}?\s+\d+\s?[화장편](?:\s*[\(（][^\)）]{0,60}[\)）])?\s*$'),
        ("KOR_끝N점",   r'^.{2,120}?\s+\d+\s*\.\s*\S.+$'),
        ("KOR_꺾쇠N점", r'^.{0,120}?[<＜]\s*\d+\s*[.,，]\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$'),
        ("KOR_N회차",   r'^\d+\s?회차\b'),
        ("KOR_특수",    r'^(?:서장|종장|프롤로그|에필로그|외전)\b'),
        ("ENG_Chapter", r'^(?:Chapter|CHAPTER|chapter)\s+\d+'),
        ("ENG_Ch",      r'^Ch\.?\s*\d+\b'),
        ("ENG_Part",    r'^(?:Part|PART|Volume|VOLUME)\s+\d+'),
        ("ENG_특수",    r'^(?:Prologue|Epilogue|Interlude)\b'),
        ("NUM_분할",    r'^\d+\s?-\s?\d+\b'),
        ("NUM_소수",    r'^\d+\.\d+\b'),
        ("NUM_점",      r'^\d+\s*[\.\:\)](?:\s|$)'),
        ("NUM_HASH_DOT", r'^\s*[#＃]\s*\d{1,5}\s*[.)．:：]\s*\S+'),
        ("NUM_샵",      r'^[#＃]\s?\d+'),
        ("MD_헤더",     r'^#{1,3}\s+\S'),
    ],
}


def _decode_txt_bytes(raw: bytes) -> str:
    """charset-normalizer 사용, 없으면 폴백."""
    try:
        from charset_normalizer import from_bytes as _from_bytes
        d = _from_bytes(raw).best()
        if d:
            return str(d)
    except Exception:
        pass
    for enc in ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'utf-16'):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode('utf-8', errors='ignore')


def _decode_markup_bytes(raw: bytes) -> str:
    """EPUB XML/HTML 인코딩 선언을 우선 반영해서 디코드."""
    head = raw[:512].decode('ascii', errors='ignore')
    encodings = []
    for pat in (
        r'\bencoding\s*=\s*["\']([A-Za-z0-9._-]+)["\']',
        r'\bcharset\s*=\s*["\']?\s*([A-Za-z0-9._-]+)',
    ):
        m = re.search(pat, head, re.IGNORECASE)
        if m:
            encodings.append(m.group(1).strip())
            break

    for enc in encodings + ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'utf-16']:
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode('utf-8', errors='replace')


def _compile_patterns(strength: str, custom_regex: str = ''):
    """강도 + 커스텀 정규식을 컴파일된 (이름, regex) 리스트로 반환.
    우선순위: CUSTOM > 강도별 일반 패턴
    """
    sets = CHAPTER_PATTERN_SETS.get(strength, CHAPTER_PATTERN_SETS['normal'])
    compiled = []
    for name, pat in sets:
        try:
            compiled.append((name, re.compile(pat)))
        except re.error:
            continue
    if custom_regex:
        try:
            compiled.insert(0, ("CUSTOM", re.compile(custom_regex)))
        except re.error:
            pass
    return compiled


# 챕터 마커 추출용 — 책 제목 접두어를 제거하고 "N화"/"Chapter N"/"N회차" 등 챕터 마커만 남김
# 비탐욕: 마커 자체만 매칭하도록 .*$ 제거 (여러 마커가 한 줄에 있어도 last match 정확히 탐지)
_CHAP_MARKER_RE = re.compile(
    r'(?:제\s?\d+\s?[화장편권부회]'
    r'|(?:외전|번외|특전)\s*\d+(?=\s*[.：:])'
    r'|(?:외전|번외|특전)\s*\d+\s*화'
    r'|\d+\s?[화장편권부회]'
    r'|\d+\s?회차'
    r'|(?:Chapter|CHAPTER|chapter)\s+\d+'
    r'|Ch\.?\s*\d+'
    r'|(?:Part|PART|Volume|VOLUME)\s+\d+'
    r'|(?:Prologue|Epilogue|Interlude)'
    r'|(?:서장|종장|프롤로그|에필로그|외전))',
    re.IGNORECASE,
)


def _strip_book_prefix(title: str) -> str:
    """매칭된 챕터 헤더에서 책 제목 접두어를 제거, 챕터 마커 이후만 반환.
    예) 'A.I.로 역대급 창업신화 1화' → '1화'
         '제5화 시작' → '제5화 시작'  (접두어 없으면 그대로)
         '13회차 멸망을 공략하는 강림자 1화' → '1화'  (가장 뒤 마커 우선)
         '전역 후 메이저리그 정복 445화(외전1화)' → '445화(외전1화)'
           (괄호 내부의 '1화'는 마커 탐지에서 제외)
    """
    # 우선 규칙: "< 56. 제목 >" 형태면 꺾쇠 내부를 그대로 사용
    m_angle = re.search(
        r'[<＜]\s*((?:\d{1,4}\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+)|(?:\d{1,4}\s*[.,，]\s*[^<>＜＞〈〉]+?))\s*[>＞〉]',
        title
    )
    if m_angle:
        return m_angle.group(1).strip()

    # "150 : 제목"처럼 줄 자체가 숫자+콜론 회차 제목이면 뒤쪽의 "2부" 같은
    # 부 번호를 챕터 마커로 오인하지 말고 줄 전체를 제목으로 유지한다.
    m_colon = re.match(r'^\s*(\d{1,5}\s*[:\uFF1A]\s*.+)$', title)
    if m_colon:
        return m_colon.group(1).strip()

    # 우선 규칙: "시리즈명 252. 제목" 형태면 숫자 이후 꼬리 제목 사용
    m_tail = re.search(r'(^|[\s\]\)])(\d{1,4}\s*\.\s*.+)$', title)
    if m_tail:
        tail = m_tail.group(2).strip()
        if not re.match(r'^\d{1,4}\s*\.\s*\d', tail):
            return tail

    # 괄호 내부는 마커 탐지에서 제외 — 동일 길이의 '.'으로 마스킹해 인덱스 보존
    masked = re.sub(r'[\(（][^\)）]*[\)）]',
                    lambda m: '.' * len(m.group(0)), title)
    matches = list(_CHAP_MARKER_RE.finditer(masked))
    if not matches:
        return title
    # "1장 외전"처럼 숫자 챕터 마커로 시작하면 뒤의 "외전"을 별도 마커로
    # 오인하지 말고 전체 줄을 챕터 제목으로 유지한다.
    if matches[0].start() == 0:
        return title
    # 가장 뒤쪽 마커 기준이 기본이지만,
    # 줄 안에 "외전876화 ... 외전 (1)"처럼 마커가 여러 번 나올 때는
    # 숫자 포함 마커를 우선 사용해 화수 정보를 보존한다.
    _num_markers = []
    for _m in matches:
        try:
            _seg = masked[_m.start():_m.end()]
        except Exception:
            _seg = ''
        if re.search(r'\d', _seg):
            _num_markers.append(_m)
    m = _num_markers[-1] if _num_markers else matches[-1]
    # 마커 시작 위치부터 줄 끝까지 반환 (괄호 포함 원본 기준)
    return title[m.start():].strip() or title


def _prettify_marker(title: str) -> str:
    """표시용 포맷 — 'N화(주석)' → 'N화 (주석)' 처럼 괄호 앞에 공백 추가."""
    return re.sub(r'(\d+\s?[화장편권부])([\(（])', r'\1 \2', title)


def _clean_txt_chapter_title(title: str) -> str:
    """Normalize noisy TXT chapter labels without changing body text."""
    t = re.sub(r'\s+', ' ', str(title or '')).strip()
    t = re.sub(r'^[\u2502|┃┆┊]+\s*', '', t).strip()
    t = re.sub(r'^시작\s+(?=(?:#\s*)?(?:제\s*)?\d+\s*(?:화|장|편|권|부|회)\b)', '', t).strip()
    t = re.sub(r'^(?:#\s*)?(\d{1,5})\s*화\s*$', r'\1화', t)
    angle = re.match(r'^((?:\d{1,5}\s*[.)]\s*)?)[<〈]\s*(.*?)\s*[>〉]\s*$', t)
    if angle:
        prefix = angle.group(1).strip()
        inner = re.sub(r'^#\s*(?=\d)', '', angle.group(2).strip())
        if prefix and inner:
            return (prefix + ' ' + inner).strip()
        return inner or t
    t = re.sub(r'^[<〈]\s*(.*?)\s*[>〉]\s*$', r'\1', t).strip()
    return t


def _is_false_txt_chapter_line(line: str) -> bool:
    """Reject numbered body sentences that look like TOC markers at first glance."""
    t = re.sub(r'\s+', ' ', str(line or '')).strip()
    if not t:
        return True
    t = re.sub(r'^[\u2502|┃┆┊]+\s*', '', t).strip()
    if re.match(r'^#\s*공지\s*#\s*$', t, re.IGNORECASE):
        return True
    if re.match(r'^\[[^\]]{1,80}\]\s*$', t) and not re.match(r'^\[(?:제\s*)?\d+\s*(?:화|장|편|권|부|회)', t):
        return True
    if re.match(r'^-?\s*특전\s*[:：]', t):
        return True
    if re.match(r'^\d+(?:-\d+){2,}\b', t):
        return True
    if re.match(r'^\d+(?:-\d+)*\)\s+\S', t):
        return True
    if re.match(r'^\d{4}\s*-\s*\d{4}\b', t):
        return True
    if re.match(r'^\d{1,3}(?:,\d{3})+(?:\s|명|원|LP\b)', t, re.IGNORECASE):
        return True
    if re.match(r'^\d{2,6}\s*,\s*\d', t):
        return True
    if re.match(r'^\d{2,3}-\d{2,3}-', t):
        return True
    if re.match(r'^\d+(?:\.\d+)?\s*%', t):
        return True
    _pct = re.match(r'^(\d+)\.\s*\d+\s*%', t)
    if _pct and int(_pct.group(1)) <= 10:
        return True
    if re.match(r'^\d+\s*LP\b', t, re.IGNORECASE):
        return True
    if re.match(r'^(?:제\s*)?\d+\s*화\s*차\b', t):
        return True
    if re.match(r'^\d+\s*회차\s+인생\b', t):
        return True
    if re.match(r'^(?:제\s*)?\d+\s*화\b', t):
        if len(t) >= 36 and re.search(r'[,，.。?？!！]|(?:다|요|까|니|죠)[.!?。]?\s*$', t):
            return True
    if re.match(r'^\d+\s*[.)]\s+', t):
        if len(t) >= 28 and re.search(r'(?:습니다|됩니다|합니다|니다|다)[.!?。]?\s*$', t):
            return True
    return False


def _is_structured_txt_chapter_title(title: str) -> bool:
    t = re.sub(r'\s+', ' ', str(title or '')).strip()
    t = re.sub(r'^[\u2502|┃┆┊]+\s*', '', t).strip()
    if _is_false_txt_chapter_line(t):
        return False
    return bool(re.match(
        r'^(?:#\s*)?(?:제\s*)?\d{1,5}\s*(?:화|장|편|권|부|회)\b'
        r'|^(?:#\s*)?\d{1,5}\s*[.)]\s*\S+'
        r'|^(?:#\s*)?\d{1,5}\s+.{1,90}$'
        r'|^(?:Chapter|CHAPTER|chapter|Ch\.?)\s*\d{1,5}\b',
        t,
        re.IGNORECASE,
    ))


_KR_UNITS_RE = r'(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)'


def _clean_txt_chapter_title(title: str) -> str:
    t = re.sub(r'\s+', ' ', str(title or '')).strip()
    t = re.sub(r'^[\u2502|┃┆┊]+\s*', '', t).strip()
    t = re.sub(r'^\uC2DC\uC791\s+(?=(?:#\s*)?(?:\uC81C\s*)?\d+\s*' + _KR_UNITS_RE + r'\b)', '', t).strip()
    t = re.sub(r'^(?:#\s*)?(\d{1,5})\s*\uD654\s*$', lambda m: m.group(1) + '\uD654', t)
    angle = re.match(r'^((?:\d{1,5}\s*[.)]\s*)?)[<\u3008]\s*(.*?)\s*[>\u3009]\s*$', t)
    if angle:
        prefix = angle.group(1).strip()
        inner = re.sub(r'^#\s*(?=\d)', '', angle.group(2).strip())
        if prefix and inner:
            return (prefix + ' ' + inner).strip()
        return inner or t
    return re.sub(r'^[<\u3008]\s*(.*?)\s*[>\u3009]\s*$', r'\1', t).strip()


def _is_false_txt_chapter_line(line: str) -> bool:
    t = re.sub(r'\s+', ' ', str(line or '')).strip()
    if not t:
        return True
    t = re.sub(r'^[\u2502|┃┆┊]+\s*', '', t).strip()
    if re.match(r'^#\s*\uACF5\uC9C0\s*#\s*$', t, re.IGNORECASE):
        return True
    if re.match(r'^\[[^\]]{1,80}\]\s*$', t) and not re.match(r'^\[(?:\uC81C\s*)?\d+\s*' + _KR_UNITS_RE, t):
        return True
    if re.match(r'^-?\s*\uD2B9\uC804\s*[:\uFF1A]', t):
        return True
    if re.match(r'^\d+(?:-\d+){2,}\b', t):
        return True
    if re.match(r'^\d+(?:-\d+)*\)\s+\S', t):
        return True
    if re.match(r'^\d{4}\s*-\s*\d{4}\b', t):
        return True
    if re.match(r'^\d{1,3}(?:,\d{3})+(?:\s|\uBA85|\uC6D0|LP\b)', t, re.IGNORECASE):
        return True
    if re.match(r'^\d{2,6}\s*,\s*\d', t):
        return True
    if re.match(r'^\d{2,3}-\d{2,3}-', t):
        return True
    if re.match(r'^\d+(?:\.\d+)?\s*%', t):
        return True
    _pct = re.match(r'^(\d+)\.\s*\d+\s*%', t)
    if _pct and int(_pct.group(1)) <= 10:
        return True
    if re.match(r'^\d+\s*LP\b', t, re.IGNORECASE):
        return True
    if re.search(r'\d{1,3}\s*\uD654\b', t) and re.search(r'\d{1,3}\s*\uD654\b.*\d{1,5}\s*[.)]', t):
        return True
    if re.match(r'^(?:\uC81C\s*)?\d+\s*\uD654\s*\uCC28\b', t):
        return True
    if re.match(r'^\d+\s*\uD68C\uCC28\s+\uC778\uC0DD\b', t):
        return True
    if re.match(r'^(?:\uC81C\s*)?\d+\s*\uD654\b', t):
        if len(t) >= 36 and re.search(r'[,，.。?？!！]|(?:\uB2E4|\uC694|\uAE4C|\uB2C8|\uC8E0)[.!?。]?\s*$', t):
            return True
    if re.match(r'^\d+\s*[.)]\s+', t):
        if len(t) >= 28 and re.search(r'(?:\uC2B5\uB2C8\uB2E4|\uB429\uB2C8\uB2E4|\uD569\uB2C8\uB2E4|\uB2C8\uB2E4|\uB2E4)[.!?。]?\s*$', t):
            return True
    return False


def _is_structured_txt_chapter_title(title: str) -> bool:
    t = re.sub(r'\s+', ' ', str(title or '')).strip()
    t = re.sub(r'^[\u2502|┃┆┊]+\s*', '', t).strip()
    if _is_false_txt_chapter_line(t):
        return False
    return bool(re.match(
        r'^(?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*' + _KR_UNITS_RE + r'\b'
        r'|^(?:#\s*)?\d{1,5}\s*[.)]\s*\S+'
        r'|^(?:#\s*)?\d{1,5}\s+.{1,90}$'
        r'|^(?:Chapter|CHAPTER|chapter|Ch\.?)\s*\d{1,5}\b',
        t,
        re.IGNORECASE,
    ))


def _txt_strip_leading_rule_bar(value: str) -> str:
    return re.sub(r'^(?:\u2502|\||\u2503|\u2506|\u250A)\s*', '', str(value or '')).strip()


def _clean_txt_chapter_title(title: str) -> str:
    t = re.sub(r'\s+', ' ', str(title or '')).strip()
    t = _txt_strip_leading_rule_bar(t)
    t = re.sub(r'^#\s*(?=(?:\uC81C\s*)?\d+\s*' + _KR_UNITS_RE + r'\b)', '', t).strip()
    t = re.sub(r'^\uC2DC\uC791\s+(?=(?:#\s*)?(?:\uC81C\s*)?\d+\s*' + _KR_UNITS_RE + r'\b)', '', t).strip()
    t = re.sub(r'^\uC2DC\uC791\s+(?=(?:#\s*)?\d{1,5}\s*[.)\uFF1A:])', '', t).strip()
    t = re.sub(r'^(?:#\s*)?(\d{1,5})\s*\uD654\s*$', lambda m: m.group(1) + '\uD654', t)
    angle = re.match(r'^((?:\d{1,5}\s*[.)]\s*)?)[<\u3008]\s*(.*?)\s*[>\u3009]\s*$', t)
    if angle:
        prefix = angle.group(1).strip()
        inner = re.sub(r'^#\s*(?=\d)', '', angle.group(2).strip())
        if prefix and inner:
            return (prefix + ' ' + inner).strip()
        return inner or t
    return re.sub(r'^[<\u3008]\s*(.*?)\s*[>\u3009]\s*$', r'\1', t).strip()


def _is_false_txt_chapter_line(line: str) -> bool:
    t = _txt_strip_leading_rule_bar(re.sub(r'\s+', ' ', str(line or '')).strip())
    if not t:
        return True
    if re.match(r'^\d+-\d+-\d+', t):
        return True
    _m0 = re.match(r'^(\d+)', t)
    if _m0:
        _rest0 = t[_m0.end():].lstrip()
        if re.match(r'^\uBC88(?:\uC774\uB77C|\uC740|\uC744|\uC774|\uB294|\uC5D0|\uC5D0\uC11C|[,.!?])', _rest0):
            return True
        if _rest0.startswith('\uD68C\uCC28 \uC778\uC0DD'):
            return True
    if re.match(r'^#\s*\uACF5\uC9C0\s*#\s*$', t, re.IGNORECASE):
        return True
    if re.match(r'^\[[^\]]{1,80}\]\s*$', t) and not re.match(r'^\[(?:\uC81C\s*)?\d+\s*' + _KR_UNITS_RE, t):
        return True
    if re.match(r'^-?\s*\uD2B9\uC804\s*[:\uFF1A]', t):
        return True
    if re.match(r'^\d+(?:-\d+){2,}\b', t):
        return True
    if re.match(r'^\d+(?:-\d+)*\)\s+\S', t):
        return True
    if re.match(r'^\d{4}\s*-\s*\d{4}\b', t):
        return True
    if re.match(r'^\d{1,3}(?:,\d{3})+(?:\s|\uBA85|\uC6D0|LP\b)', t, re.IGNORECASE):
        return True
    if re.match(r'^\d{2,6}\s*,\s*\d', t):
        return True
    if re.match(r'^\d{2,3}-\d{2,3}-', t):
        return True
    if re.match(r'^\d+(?:\.\d+)?\s*%', t):
        return True
    _pct = re.match(r'^(\d+)\.\s*\d+\s*%', t)
    if _pct and int(_pct.group(1)) <= 10:
        return True
    if re.match(r'^\d+\s*LP\b', t, re.IGNORECASE):
        return True
    _special_words = r'(?:\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC11C\uC7A5|\uC885\uC7A5)'
    if re.match(_special_words + r'(?:\uC758|\uC740|\uB294|\uC774|\uAC00|\uC744|\uB97C|\uACFC|\uC640|\uB3C4|\uC5D0\uC11C|\uC73C\uB85C|\uB85C|\uB9CC|\uBD80\uD130)', t):
        return True
    if re.match(_special_words + r'.{2,}?\d{1,5}\s*\uD654\b', t):
        return True
    if re.match(r'^(?:\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC11C\uC7A5|\uC885\uC7A5)\b', t, re.IGNORECASE):
        _special_short = re.fullmatch(
            r'(?:\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC11C\uC7A5|\uC885\uC7A5)'
            r'(?:\s*(?:\d{1,3}|[(:\uFF08][^)\uFF09]{1,20}[)\uFF09]|[-:\uFF1A]\s*.{1,24}))?',
            t,
            re.IGNORECASE,
        )
        if not _special_short and (
                len(t) >= 18
                or re.search(r'[.!?\u3002,]|(?:\uC740|\uB294|\uC774|\uAC00|\uC744|\uB97C|\uACFC|\uC640)\s', t)
                or re.search(r'(?:\uB2E4|\uC694|\uC8E0|\uAE4C|\uB370|\uB358\uB370)[.!?\u3002]?\s*$', t)):
            return True
    if re.match(r'^(?:\uC81C\s*)?\d+\s*\uD654\s*\uCC28\b', t):
        return True
    if re.match(r'^\d+\s*\uD68C\uCC28\s+\uC778\uC0DD\b', t):
        return True
    if re.match(r'^(?:\uC81C\s*)?\d+\s*\uD654\b', t):
        if len(t) >= 36 and re.search(r'[,，.。?？!！]|(?:\uB2E4|\uC694|\uAE4C|\uB2C8|\uC8E0)[.!?。]?\s*$', t):
            return True
    if re.match(r'^\d+\s*[.)]\s+', t):
        if len(t) >= 28 and re.search(r'(?:\uC2B5\uB2C8\uB2E4|\uB429\uB2C8\uB2E4|\uD569\uB2C8\uB2E4|\uB2C8\uB2E4|\uB2E4)[.!?。]?\s*$', t):
            return True
    return False


def _is_structured_txt_chapter_title(title: str) -> bool:
    t = _txt_strip_leading_rule_bar(re.sub(r'\s+', ' ', str(title or '')).strip())
    if _is_false_txt_chapter_line(t):
        return False
    if re.match(r'^(?:\d{1,5}\s*[.)]\s*)?[<\u3008].{1,90}[>\u3009]\s*$', t):
        return True
    return bool(re.match(
        r'^(?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*' + _KR_UNITS_RE + r'\b'
        r'|^(?:#\s*)?\d{1,5}\s*[.)]\s*\S+'
        r'|^(?:#\s*)?\d{1,5}\s+.{1,90}$'
        r'|^(?:Chapter|CHAPTER|chapter|Ch\.?)\s*\d{1,5}\b',
        t,
        re.IGNORECASE,
    ))


def detect_chapters(text: str, strength: str = 'normal',
                    custom_regex: str = '', enforce_consistency: bool = True,
                    force_subtitle_style: 'bool | None' = None):
    """텍스트에서 챕터 분할 → [(title, [body_lines]), ...] 반환.
    enforce_consistency=True: 가장 많이 매칭된 패턴만 챕터 분할로 인정 (오인식 방지)
    추가 동작:
      - 본문 첫 줄이 '제목@작가'면 인트로(시작) 섹션 전체 제외 (작가 추출은 extract_txt_metadata에서)
      - 파일 전반이 '소제목 스타일'이면 마침표로 끝나는 짧은 다음 줄도 소제목으로 흡수
      - 매칭된 챕터 헤더는 책 제목 접두어를 제거하고 챕터 마커만 제목으로 사용 (예: 'A.I.로 역대급 창업신화 1화\\n개같은 스타트업' → '1화 개같은 스타트업')
      - 마커 뒤 괄호 앞에 공백 정리 (예: '444화(본편 완결)' → '444화 (본편 완결)')
    """
    patterns = _compile_patterns(strength, custom_regex)
    raw_lines = text.splitlines()
    if not patterns:
        return [("본문", [_html_mod.escape(l.strip()) for l in raw_lines if l.strip()])], False

    # 본문 첫 비공백 줄이 '제목@작가'이면 인트로 통째 드롭 신호
    first_nonempty = next((l.strip() for l in raw_lines if l.strip()), '')
    drop_intro = bool(re.match(r'^[^@\n]{1,80}?@[^\s@][^\n]{0,60}$', first_nonempty))

    # 비공백 줄만 인덱싱 — 챕터 헤더 다음 줄 lookahead에 사용
    # 매칭용은 보이지 않는 문자(제로폭 공백 등)를 제거한 정규화 버전을 함께 유지
    _ZW_RE = re.compile(r'[\u200B-\u200F\u2060\uFEFF]')
    nl = [l.strip() for l in raw_lines if l.strip()]
    nl_norm = [re.sub(r'\s+', ' ', _ZW_RE.sub('', s).replace('\u00A0', ' ')).strip() for s in nl]
    plain_heading_idx = set()
    plain_candidates = []
    for _i, _ln in enumerate(nl_norm):
        _probe = _txt_strip_leading_rule_bar(_ln)
        if _is_false_txt_chapter_line(_probe):
            continue
        _pm = re.match(
            r'^(?:#\s*)?(?:제\s*)?(\d{1,5})\s*(?:화|장|편|권|부|회)\b(?:[.)\-:：]\s*)?.*$'
            r'|^(?:#\s*)?(\d{1,4})\s+\S.{0,90}$',
            _probe,
        )
        if not _pm:
            continue
        try:
            _pn = int(_pm.group(1) or _pm.group(2))
        except Exception:
            continue
        plain_candidates.append((_i, _pn))
    if len(plain_candidates) >= 3:
        _asc_plain = sum(
            1 for _j in range(1, len(plain_candidates))
            if plain_candidates[_j][1] > plain_candidates[_j - 1][1]
        )
        if _asc_plain / max(len(plain_candidates) - 1, 1) >= 0.55:
            plain_heading_idx = {_i for _i, _n in plain_candidates}

    supplemental_plain = []
    for _i, _ln in enumerate(nl_norm):
        _probe = _txt_strip_leading_rule_bar(_ln)
        if _is_false_txt_chapter_line(_probe):
            continue
        _pm = re.match(
            r'^(?:\uC2DC\uC791\s+)?(?:#\s*)?(?:\uC81C\s*)?(\d{1,5})\s*' + _KR_UNITS_RE + r'\b(?:[.)\-:\uFF1A]\s*)?.*$'
            r'|^(?:\uC2DC\uC791\s+)?(?:#\s*)?(\d{1,4})\s+.{1,90}$',
            _probe,
        )
        if not _pm:
            continue
        try:
            supplemental_plain.append((_i, int(_pm.group(1) or _pm.group(2))))
        except Exception:
            continue
    if len(supplemental_plain) >= 3:
        _asc_supp = sum(
            1 for _j in range(1, len(supplemental_plain))
            if supplemental_plain[_j][1] > supplemental_plain[_j - 1][1]
        )
        if _asc_supp / max(len(supplemental_plain) - 1, 1) >= 0.55:
            plain_heading_idx.update({_i for _i, _n in supplemental_plain})

    def _numdot_ascending_fallback(lines):
        """'N. 제목' 계열이 전역적으로 오름차순이면 챕터로 승격."""
        heads = []  # (line_idx, num, title_line)
        pat = re.compile(r'^\s*(\d{1,5})\s*[.\)．。]\s*\S+')
        for i, ln in enumerate(lines):
            m = pat.match(ln)
            if not m:
                continue
            try:
                num = int(m.group(1))
            except Exception:
                continue
            heads.append((i, num, ln))
        if len(heads) < 5:
            return None
        asc = sum(1 for i in range(1, len(heads)) if heads[i][1] > heads[i-1][1])
        asc_ratio = asc / max(len(heads) - 1, 1)
        uniq = len({n for _, n, _ in heads})
        if asc_ratio < 0.8 or uniq < 5:
            return None

        out = []
        for k, (li, _num, ttl) in enumerate(heads):
            start = li + 1
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            body = [_html_mod.escape(x) for x in lines[start:end] if x.strip()]
            out.append((ttl.strip(), body))
        return out if len(out) >= 3 else None

    def _looks_like_prose_not_heading(s: str) -> bool:
        """본문 문장형 줄인지 휴리스틱 판정 (숫자 분할 헤더 오탐 방지)."""
        if not s:
            return False
        t = _normalize_title(s)
        # 긴 줄 + 문장부호/인용부호 포함이면 본문 가능성 높음
        if len(t) >= 40 and re.search(r'[,.!?…“”"\'‘’]', t):
            return True
        # 공백 어절이 과도하게 많으면 본문으로 간주
        if len(t.split()) >= 8:
            return True
        return False

    # ── 1차 스캔: 소제목 스타일 파일 판정 ─────────────────────
    # 책 제목 접두어가 있는 챕터들의 "다음 줄"이 대부분 짧으면(≤30자) 소제목 스타일로 간주.
    # 소제목 스타일 파일에서는 마침표로 끝나는 다음 줄도 소제목으로 흡수.
    total_stripped = 0
    plausible_count = 0
    for k, l in enumerate(nl):
        ln = nl_norm[k] if k < len(nl_norm) else l
        if not any(rgx.match(ln) for _, rgx in patterns):
            continue
        if _strip_book_prefix(l) == l:
            continue   # 접두어 없는 헤더는 제외
        total_stripped += 1
        if k + 1 < len(nl):
            nxt = nl[k + 1]
            nxtn = nl_norm[k + 1] if (k + 1) < len(nl_norm) else nxt
            if (1 <= len(nxt) <= 30
                    and not any(rgx.match(nxtn) for _, rgx in patterns)):
                plausible_count += 1
    subtitle_style = (force_subtitle_style
                      if force_subtitle_style is not None
                      else (total_stripped >= 3
                            and plausible_count / total_stripped >= 0.5))

    temp = []   # [{title, lines, pattern}]
    found = []
    cur_t, cur_l = "시작", []
    skip = 0
    for k, l in enumerate(nl):
        if skip > 0:
            skip -= 1
            continue
        ln = nl_norm[k] if k < len(nl_norm) else l
        matched = None
        for name, rgx in patterns:
            if rgx.match(ln):
                matched = name
                break
        if matched and re.search(r'\b\d+\.\d+\s*%', ln):
            matched = None
        if matched == "KOR_끝N점" and _strip_book_prefix(l) == l:
            matched = None
        # 4-1 / 1.2 류는 본문 문장 앞 숫자일 때 오탐이 잦음 → 문장형 줄은 제외
        if matched in {"NUM_분할", "NUM_소수"} and _looks_like_prose_not_heading(ln):
            matched = None
        if matched and _is_false_txt_chapter_line(ln):
            matched = None
        if not matched and k in plain_heading_idx:
            matched = "PLAIN_NUM"
        if matched:
            # 책 제목 접두어 제거 → 챕터 마커만 (예: 'A.I.로 역대급 창업신화 1화' → '1화')
            _line_for_marker = _txt_strip_leading_rule_bar(l)
            if re.search(r'^(?:\uC2DC\uC791\s+)?(?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*' + _KR_UNITS_RE + r'\b', _line_for_marker):
                marker_title = _line_for_marker
            else:
                marker_title = _strip_book_prefix(l)
            stripped_book_prefix = (marker_title != l)
            # 책 제목 접두어가 실제 제거된 경우에만 다음 줄을 소제목 후보로 흡수
            #  (순수 'N화'/'제N화' 같은 헤더 뒤의 본문 첫 줄이 오흡수되는 것을 방지)
            # subtitle_style=False(체크박스 해제)이면 흡수 전체 차단
            if stripped_book_prefix and subtitle_style and k + 1 < len(nl):
                nxt = nl[k + 1]
                nxtn = nl_norm[k + 1] if (k + 1) < len(nl_norm) else nxt
                is_next_chap = any(rgx.match(nxtn) for _, rgx in patterns)
                # 기본 흡수 조건: 매칭X, 1~30자, 괄호/따옴표 시작 아님
                can_absorb = (not is_next_chap
                              and 1 <= len(nxt) <= 30
                              and not nxt.startswith(('(', '[', '"', '“', '「')))
                if can_absorb and _is_structured_txt_chapter_title(marker_title):
                    can_absorb = False
                if can_absorb:
                    marker_title = f"{marker_title} {nxt}".strip()
                    skip = 1
            # 표시용 정리: '444화(본편 완결)' → '444화 (본편 완결)'
            marker_title = _prettify_marker(marker_title)
            marker_title = _clean_txt_chapter_title(marker_title)
            if cur_l or cur_t != "시작":
                temp.append({"title": cur_t, "lines": cur_l,
                             "pattern": found[-1] if found else "START"})
            cur_t, cur_l = marker_title, []
            found.append(matched)
        else:
            cur_l.append(_html_mod.escape(l))
    if cur_l or cur_t != "시작":
        temp.append({"title": cur_t, "lines": cur_l,
                     "pattern": found[-1] if found else "START"})

    if not temp:
        return [("본문", [])], subtitle_style

    # 인트로(시작) 섹션 드롭 — 첫 줄이 '제목@작가'인 경우
    if drop_intro and temp and temp[0]["title"] == "시작":
        temp = temp[1:]
        if not temp:
            return [("본문", [])], subtitle_style

    # 기존 감지가 너무 적으면 숫자형(N. 제목) 오름차순 폴백 시도
    if len(found) <= 2:
        fb = _numdot_ascending_fallback(nl)
        if fb:
            return fb, subtitle_style

    # 일관성 검사 — 단일 패턴만 챕터로 인정
    if enforce_consistency and len(found) > 1:
        from collections import Counter
        primary = Counter(found).most_common(1)[0][0]
        # ※ KOR_특수/ENG_특수(프롤로그·에필로그·외전 등)는 항상 별도 챕터로 유지
        _EXEMPT_PATTERNS = {
            'KOR_특수', 'KOR_특수확장', 'ENG_특수',
            'KOR_장외전', 'KOR_외전N', 'KOR_N외전', 'KOR_외전N화', 'KOR_꺾쇠N점',
            'NUM_점'
        }
        _EXEMPT_PATTERNS.add('PLAIN_NUM')
        merged = []
        cur_t = temp[0]["title"]
        cur_l = list(temp[0]["lines"])
        for i in range(1, len(temp)):
            if (temp[i]["pattern"] == primary
                    or temp[i]["pattern"] in _EXEMPT_PATTERNS
                    or _is_structured_txt_chapter_title(temp[i]["title"])):
                merged.append((cur_t, cur_l))
                cur_t = temp[i]["title"]
                cur_l = list(temp[i]["lines"])
            else:
                cur_l.append(f"<b>{temp[i]['title']}</b>")
                cur_l.extend(temp[i]["lines"])
        merged.append((cur_t, cur_l))
        return merged, subtitle_style
    return [(c["title"], c["lines"]) for c in temp], subtitle_style


_NUM_PREFIX_RE = re.compile(
    r'^\s*[\u2502|┃┆┊]*\s*(?:#\s*)?(?:제\s*)?(\d{1,5})'
    r'(?:\s*(?:화|장|편|권|부|회)\b|\s*[.)：:]\s*|\s+\S)'
)


_NUM_PREFIX_RE = re.compile(
    r'^\s*[\u2502|┃┆┊]*\s*(?:#\s*)?(?:\uC81C\s*)?(\d{1,5})'
    r'(?:\s*' + _KR_UNITS_RE + r'\b|\s*[.)\uFF1A:]\s*|\s+\S)'
)


def _extract_chapter_number(title: str):
    """챕터 제목에서 선두 숫자 추출 (없으면 None)."""
    m = _NUM_PREFIX_RE.match(title.strip())
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _is_toc_flow_anomaly(title: str, prev_num, next_num) -> bool:
    if prev_num is None or next_num is None:
        return False
    if next_num <= prev_num or next_num - prev_num > 6:
        return False
    t = _txt_strip_leading_rule_bar(re.sub(r'\s+', ' ', str(title or '')).strip())
    if not t:
        return True
    n = _extract_chapter_number(t)
    if n is not None:
        return not (prev_num < n < next_num)
    special = r'(?:\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC11C\uC7A5|\uC885\uC7A5|\uC678\uC804|\uBC88\uC678|\uD2B9\uC804)'
    if re.search(special, t, re.IGNORECASE):
        return True
    if re.search(r'\d{1,5}\s*' + _KR_UNITS_RE + r'\b', t):
        return True
    if len(t) >= 18 and re.search(r'[.!?\u3002,]|(?:\uC740|\uB294|\uC774|\uAC00|\uC744|\uB97C|\uC758)\s', t):
        return True
    return False


def _extract_embedded_flow_title(title: str, prev_num, next_num) -> str:
    if prev_num is None or next_num is None or next_num <= prev_num:
        return ''
    t = _txt_strip_leading_rule_bar(re.sub(r'\s+', ' ', str(title or '')).strip())
    if not t:
        return ''
    best = ''
    for m in re.finditer(r'(?<!\d)(\d{1,5})\s*' + _KR_UNITS_RE + r'\b.*$', t):
        try:
            n = int(m.group(1))
        except Exception:
            continue
        if prev_num < n < next_num:
            best = t[m.start():].strip()
    return best


def filter_ascending_chapters(chapters):
    """챕터 번호 시퀀스에서 '연속 오름차순'만 챕터로 인정.
    예) [298, 299, 300, 5, 301, 302] → 5는 오인식이므로 이전 챕터에 흡수.
    숫자가 있는 챕터만 검사. 숫자 없는 챕터는 그대로 유지.
    """
    if len(chapters) < 3:
        return chapters
    _SPECIAL_KEEP_RE = re.compile(r'(?:외전|번외|특전|에필로그|프롤로그|서장|종장)', re.IGNORECASE)
    nums = [_extract_chapter_number(t) for t, _ in chapters]
    keep_special = [bool(_SPECIAL_KEEP_RE.search((t or '').strip())) for t, _ in chapters]
    # 특수 챕터는 오름차순 검증 대상에서 제외(항상 유지)
    valid_idx = [i for i, n in enumerate(nums) if n is not None and not keep_special[i]]
    if len(valid_idx) < 3:
        return chapters

    # 가장 긴 단조 증가 부분수열 인덱스 (LIS) 구하기 — 단순 O(n²)
    n = len(valid_idx)
    dp = [1] * n
    parent = [-1] * n
    for i in range(n):
        for j in range(i):
            if nums[valid_idx[j]] < nums[valid_idx[i]] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
                parent[i] = j
    # 최장 LIS 끝 인덱스
    end = max(range(n), key=lambda x: dp[x])
    seq_idx = []
    cur = end
    while cur >= 0:
        seq_idx.append(valid_idx[cur])
        cur = parent[cur]
    seq_idx.reverse()
    keep = set(seq_idx)
    repaired_titles = {}
    def _neighbor_nums(pos: int):
        prev = None
        nxt = None
        for j in range(pos - 1, -1, -1):
            if nums[j] is not None:
                prev = nums[j]
                break
        for j in range(pos + 1, len(nums)):
            if nums[j] is not None:
                nxt = nums[j]
                break
        return prev, nxt
    # 숫자 없는 챕터도 유지
    for i, num in enumerate(nums):
        if num is None:
            prev_num, next_num = _neighbor_nums(i)
            embedded_title = _extract_embedded_flow_title(chapters[i][0], prev_num, next_num)
            if embedded_title:
                repaired_titles[i] = embedded_title
                keep.add(i)
            elif not _is_toc_flow_anomaly(chapters[i][0], prev_num, next_num):
                keep.add(i)
    # 특수 챕터(외전/특전/에필로그 등)는 항상 유지
    for i, is_special in enumerate(keep_special):
        prev_num, next_num = _neighbor_nums(i)
        if is_special and not _is_toc_flow_anomaly(chapters[i][0], prev_num, next_num):
            keep.add(i)

    if len(keep) == len(chapters):
        return chapters   # 변화 없음

    out = []
    for i, (t, ls) in enumerate(chapters):
        if i in keep:
            out.append((repaired_titles.get(i, t), list(ls)))
        else:
            # 이전 챕터에 흡수
            if out:
                pt, pl = out[-1]
                pl.append(f"<b>{_html_mod.escape(t)}</b>")
                pl.extend(ls)
                out[-1] = (pt, pl)
            else:
                out.append((t, list(ls)))
    return out


def fill_numeric_gaps(chapters):
    """챕터 번호가 오름차순일 때, 누락된 번호를 본문에서 탐색해 재분할.
    예) 307 → 341 사이에 308~340이 본문에 흡수돼 있으면 다시 챕터로 분리.
    """
    if len(chapters) < 2:
        return chapters
    nums = [_extract_chapter_number(t) for t, _ in chapters]
    valid_nums = [n for n in nums if n is not None]
    if len(valid_nums) < 3:
        return chapters
    asc = sum(1 for i in range(1, len(valid_nums)) if valid_nums[i] > valid_nums[i-1])
    if asc < len(valid_nums) * 0.9 - 1:
        return chapters

    gap_pat = re.compile(r'^(\d+)\s*[\.\:\)](?:\s|$)')
    embedded_gap_pat = re.compile(r'(?<!\d)(\d{1,5})\s*' + _KR_UNITS_RE + r'\b.*$')
    out = []
    for i, (t, ls) in enumerate(chapters):
        cur_n = nums[i]
        # 다음 번호 찾기
        nxt_n = None
        for j in range(i + 1, len(nums)):
            if nums[j] is not None:
                nxt_n = nums[j]
                break
        if cur_n is None or nxt_n is None or nxt_n - cur_n < 2:
            out.append((t, list(ls)))
            continue
        missing = set(range(cur_n + 1, nxt_n))
        # 본문에서 누락 번호 줄 찾아 분할
        new_chunks = [(t, [])]   # [(title, lines)]
        for line in ls:
            plain = re.sub(r'<[^>]+>', '', line).strip()
            mm = gap_pat.match(plain)
            if mm and int(mm.group(1)) in missing:
                missing.discard(int(mm.group(1)))
                new_chunks.append((plain, []))
            else:
                em = None
                for _em in embedded_gap_pat.finditer(plain):
                    try:
                        if int(_em.group(1)) in missing:
                            em = _em
                    except Exception:
                        continue
                if em:
                    _n = int(em.group(1))
                    before = plain[:em.start()].strip()
                    title = plain[em.start():].strip()
                    if before:
                        new_chunks[-1][1].append(_html_mod.escape(before))
                    missing.discard(_n)
                    new_chunks.append((title, []))
                else:
                    new_chunks[-1][1].append(line)
        out.extend(new_chunks)
    return out


def _is_pure_chapter_marker(title: str) -> bool:
    """제목이 '0화', '제1화', '1화', 'Chapter 0', '#1' 등 순수 챕터 마커뿐이면 True.
    내용 없이 제목만 나뉜 챕터(예: '전역 후 메이저리그 정복 0화') 판별용 — 마커 뒤
    부제가 없으면 진정한 본문이 아닐 가능성이 큼.
    """
    if not title:
        return True
    t = title.strip()
    # 순수 마커 형태
    pure_pats = [
        r'^제?\s*\d+\s*[화장편권부절막회회차]\s*\.?$',
        r'^(?:Chapter|CHAPTER|chapter|Ch\.?)\s*\d+\s*\.?$',
        r'^(?:Part|PART|Volume|VOLUME)\s+\d+\s*\.?$',
        r'^(?:Prologue|Epilogue|Interlude|프롤로그|에필로그|서장|종장|외전)\s*\.?$',
        r'^[#＃]\s*\d+\s*\.?$',
        r'^\d+\s*[\.\:\)]\s*$',
    ]
    for p in pure_pats:
        if re.match(p, t, re.IGNORECASE):
            return True
    # "...... 0화" 처럼 끝에 0화로 끝나면 공지/표지 가능성 — 마지막 마커 추출 후 부제 유무 확인
    m = re.search(r'\b\d+\s*[화장편권부]\b', t)
    if m and m.end() >= len(t) - 1:   # 마커가 문자열 끝에 있음
        # 마커 앞 텍스트가 시리즈명(타이틀)이고 마커 뒤가 비어있으면 마커-only로 간주
        rest_after = t[m.end():].strip(' .')
        if not rest_after:
            return True
    return False


def merge_short_chapters(chapters, min_chars: int = 0):
    """본문 길이가 min_chars 미만인 챕터를 이전 챕터에 병합.
    - body_len == 0 (본문 0자)인 챕터는 min_chars 설정과 관계없이 항상 제거
        · 단, 제목이 의미 있는 부제(예: '1화 첫만남')이면 다음 챕터의 prefix로 흡수
    - min_chars > 0이면 그 미만 챕터를 이전(없으면 다음) 챕터로 흡수
    """
    if not chapters:
        return chapters

    # 1차 패스: 본문 0자 챕터 제거 — 제목만 있는 의미 있는 부제는 다음 챕터에 prefix로 합침
    cleaned = []
    pending_prefix = ''
    for t, ls in chapters:
        body_len = sum(len(x) for x in ls)
        if body_len == 0:
            # 순수 챕터 마커("0화", "Chapter 0" 등)면 그냥 폐기
            if _is_pure_chapter_marker(t):
                continue
            # 제목에 의미 있는 부제가 있으면 다음 챕터 prefix로 흡수
            if t and not _is_pure_chapter_marker(t):
                pending_prefix = (pending_prefix + ' ' + t).strip() if pending_prefix else t
            continue
        if pending_prefix:
            t = (pending_prefix + ' ' + t).strip() if t else pending_prefix
            pending_prefix = ''
        cleaned.append((t, list(ls)))

    if not cleaned:
        return chapters[:1] if chapters else []

    if min_chars <= 0:
        return cleaned

    # 2차 패스: min_chars 미만 챕터를 인접 챕터로 흡수
    out = []
    for t, ls in cleaned:
        body_len = sum(len(x) for x in ls)
        is_structured_title = _is_structured_txt_chapter_title(t)
        if out and body_len < min_chars and not is_structured_title:
            prev_t, prev_l = out[-1]
            prev_l.append(f"<b>{t}</b>")
            prev_l.extend(ls)
            out[-1] = (prev_t, prev_l)
        else:
            out.append((t, list(ls)))

    # 첫 챕터가 너무 짧으면 다음 챕터로 흡수 (이전 항목이 없어 1차 패스에서 보존됐던 경우)
    if len(out) >= 2:
        first_t, first_l = out[0]
        first_len = sum(len(x) for x in first_l)
        first_structured = _is_structured_txt_chapter_title(first_t)
        if first_len < min_chars and not first_structured:
            nxt_t, nxt_l = out[1]
            nxt_l_new = list(first_l)
            nxt_l_new.append(f"<b>{nxt_t}</b>")
            nxt_l_new.extend(nxt_l)
            out[1] = (first_t or nxt_t, nxt_l_new) if not first_t else (first_t, nxt_l_new)
            # 첫 챕터의 제목이 의미 있는 부제였으면 prefix로 합침
            if first_t and not _is_pure_chapter_marker(first_t):
                out[1] = (f"{first_t} {nxt_t}".strip() if nxt_t else first_t, nxt_l_new)
            else:
                out[1] = (nxt_t or first_t, nxt_l_new)
            out.pop(0)
    return out


def normalize_chapter_style(chapters):
    """챕터 제목 스타일 통일: N화/N장/N. 혼재 시 다수 스타일로 일괄 변환."""
    if not chapters:
        return chapters

    def _parse_title(title: str):
        t = re.sub(r'\s+', ' ', _normalize_title(title or '')).strip()
        if not t:
            return None

        m = re.match(r'^(?:\uC2DC\uC791\s+)?0*(\d{1,5})\s*[:\uFF1A]\s*(.+)$', t)
        if m:
            return int(m.group(1)), m.group(2).strip(), 'dot'

        # 외전123 / 번외 12화 같은 뒤번호형은 번호를 앞으로 빼서 통일한다.
        m = re.match(
            r'^(외전|번외|특전)\s*(\d{1,5})(?:\s*[화장편회])?\s*'
            r'(?:[.\:：\-–—]\s*)?(.*)$',
            t, re.IGNORECASE)
        if m:
            rest = f"{m.group(1)} {m.group(3).strip()}".strip()
            return int(m.group(2)), rest, 'unit'

        m = re.match(r'^(?:제\s*)?(\d{1,5})\s*[.)．]\s*(.*)$', t)
        if m:
            num = int(m.group(1))
            rest = m.group(2).strip()
            rest = re.sub(
                rf'^(?:제\s*)?{num}\s*[화장편회]\s*[.)．:：\-–—]?\s*',
                '', rest).strip()
            rest = re.sub(r'^(외전|번외|특전)(\d+)\b', r'\1 \2', rest)
            return num, rest, 'dot'

        m = re.match(
            r'^(?:제\s*)?(\d{1,5})\s*([화장편회])\s*'
            r'(?:[.)．:：\-–—]\s*)?(.*)$',
            t)
        if m:
            num = int(m.group(1))
            rest = m.group(3).strip()
            rest = re.sub(r'^(외전|번외|특전)(\d+)\b', r'\1 \2', rest)
            return num, rest, 'unit'

        return None

    parsed = [_parse_title(title) for title, _ in chapters]
    hwa_like = sum(1 for p in parsed if p and p[2] == 'unit')
    dot_like = sum(1 for p in parsed if p and p[2] == 'dot')
    if hwa_like == 0 and dot_like == 0:
        return chapters
    dominant = 'hwa' if hwa_like >= dot_like else 'dot'

    chapters = list(chapters)
    for i, p in enumerate(parsed):
        if not p:
            continue
        num, rest, _style = p
        _, ls = chapters[i]
        rest = re.sub(r'\s+', ' ', rest).strip()
        if dominant == 'hwa':
            new_title = f'{num}화 {rest}'.rstrip() if rest else f'{num}화'
        else:
            new_title = f'{num}. {rest}'.rstrip() if rest else f'{num}.'
        chapters[i] = (new_title, ls)
    return chapters

def extract_txt_metadata(filename: str, text: str = ''):
    """파일명·본문 첫 부분에서 (title, author) 추출.
    파일명 우선: '제목 - 작가' / '[작가] 제목' / '제목 by 작가' 등
    """
    name = Path(filename).stem
    title, author = name, "미상"

    # [작가] 제목
    m = re.match(r'^\s*\[([^\]]+)\]\s*(.+)$', name)
    if m:
        author = m.group(1).strip()
        title = m.group(2).strip()
    elif " - " in name:
        a, b = name.split(" - ", 1)
        title, author = a.strip(), b.strip()
    elif re.search(r'\sby\s', name, re.IGNORECASE):
        a, b = re.split(r'\sby\s', name, maxsplit=1, flags=re.IGNORECASE)
        title, author = a.strip(), b.strip()

    # 본문 헤더에서 보강
    if text:
        head = text[:1500]
        m1 = re.search(r'^\s*(?:제\s*목|Title)\s*[:：]\s*(.+)$', head, re.MULTILINE | re.IGNORECASE)
        if m1 and title == name:
            title = m1.group(1).strip()
        m2 = re.search(r'^\s*(?:작\s*가|작\s*자|지은이|Author)\s*[:：]\s*(.+)$',
                       head, re.MULTILINE | re.IGNORECASE)
        if m2 and author == "미상":
            author = m2.group(1).strip()
        # 본문 맨 앞 "제목@작가" 라인 감지 (인트로 섹션)
        first_line = next((l.strip() for l in text.splitlines() if l.strip()), '')
        m_at = re.match(r'^([^@\n]{1,80}?)@([^\s@][^\n]{0,60})$', first_line)
        if m_at:
            t_at = m_at.group(1).strip()
            a_at = m_at.group(2).strip()
            if title == name and t_at:
                title = t_at
            if author == "미상" and a_at:
                author = a_at
    if _core_clean_series_title_author:
        return _core_clean_series_title_author(title, author)
    return title.replace('_', ' ').strip(), author


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎨 공통 위젯 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_card(title: str, dot_color: str = None):
    card = QFrame(); card.setObjectName("card")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
    # 헤더 없음 — 테두리로만 구분
    body = QWidget()
    bl   = QVBoxLayout(body); bl.setContentsMargins(10, 8, 10, 8); bl.setSpacing(6)
    cl.addWidget(body)
    return card, body, bl

def mk_btn(text, style="gray"):
    b = QPushButton(text); b.setObjectName(f"btn_{style}"); return b

def mk_lbl(text, color=None, size=12, bold=False):
    l = QLabel(text)
    s = f"color:{color or C['text2']};font-size:{size}px;background:transparent;"
    if bold: s += "font-weight:700;"
    l.setStyleSheet(s); return l

try:
    from epub_binder_app.ui.helpers import natural_sort_key as natural_sort_key
except Exception:
    pass

try:
    from epub_binder_core.toc import (
        extract_all_subheadings as extract_all_subheadings,
        extract_chapter_title as extract_chapter_title,
        has_episode_subtitle as _has_episode_subtitle,
        inject_subheading_anchors as inject_subheading_anchors,
        is_consistent_filename_label_set as _is_consistent_filename_label_set,
        is_episode_only_label as _is_episode_only_label,
        _is_primary_chapter_heading as _is_primary_chapter_heading,
        _is_probable_plain_number_sentence as _is_probable_plain_number_sentence,
        _looks_like_body_sentence as _looks_like_body_sentence,
        is_reliable_filename_toc_label as _is_reliable_filename_toc_label,
        is_structured_episode_filename_label as _is_structured_episode_filename_label,
        _is_subnav_heading_candidate as _is_subnav_heading_candidate,
        clean_chapter_display_title as _core_clean_chapter_display_title,
        merge_page_title_from_sources as _core_merge_page_title_from_sources,
        prefer_filename_toc_title as _prefer_filename_toc_title,
        remove_continued_notice_html as _core_remove_continued_notice_html,
        toc_episode_no as _toc_episode_no,
        toc_label_from_filename as _toc_label_from_filename,
        toc_subtitle_score as _toc_subtitle_score,
        toc_duplicate_key as _core_toc_duplicate_key,
    )
except Exception:
    _core_clean_chapter_display_title = None
    _core_merge_page_title_from_sources = None
    _core_remove_continued_notice_html = None
    _core_toc_duplicate_key = None
    pass

def _clean_chapter_display_title(title: str, series_title: str = "") -> str:
    if _core_clean_chapter_display_title:
        return _core_clean_chapter_display_title(title, series_title)
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return ""
    text = re.sub(r"^#\s*(\d+)\s*[.)]?\s*$", r"\1화", text)
    text = re.sub(r"^(?:제\s*)?(\d+)\s*화\s*#\s*\1\s*[.)]?\s*", r"\1화 ", text)
    text = re.sub(r"^(?:제\s*)?(\d+)\s*화\b", r"\1화", text)
    text = re.sub(r"^#\s*(\d+)\s*[.)]?\s*", r"\1화 ", text)

    series = re.sub(r"\.epub$", "", str(series_title or ""), flags=re.IGNORECASE).strip()
    series = re.sub(r"^\[[^\]]+\]\s*", "", series).strip()
    series = re.sub(r"\s+\d+(?:[-~]\d+)?\s*(?:권|화|장|부)?(?:\+.*)?$", "", series).strip()
    if series and len(series) >= 3:
        text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip()
        text = re.sub(r"^" + re.escape(series) + r"\s*", "", text).strip()

    repeated = re.search(r"((?:제\s*)?\d+\s*(?:화|장|권|부)\b.*)$", text)
    if repeated and (text.startswith("[") or series and series in text[:repeated.start()]):
        text = repeated.group(1).strip()
    text = re.sub(r"^(\d+화)\s+\1\b", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📂 드롭존
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 파일 목록 + 드롭존 통합 위젯
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _toc_duplicate_key(title: str) -> str:
    """Consecutive identical chapter titles usually mean a chapter split across volumes."""
    if _core_toc_duplicate_key:
        return _core_toc_duplicate_key(title)
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return ""
    text = re.sub(r"^#\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip()
    text = re.sub(r"[.。．]\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _is_volume_only_toc_label(title: str, series_title: str = "") -> bool:
    """True for labels like 'Series 4권' that should not appear inside flat chapter TOCs."""
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return False
    if re.search(r"\d+\s*[\ud654\uc7a5\ud3b8]|chapter\s*\d+|#\s*\d+", text, re.IGNORECASE):
        return False
    text = re.sub(r"\.epub$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip()
    text = re.sub(r"\s*\((?:완결|完|complete|end)\)\s*$", "", text, flags=re.IGNORECASE).strip()

    series = re.sub(r"\.epub$", "", str(series_title or ""), flags=re.IGNORECASE).strip()
    series = re.sub(r"^\[[^\]]+\]\s*", "", series).strip()
    series = re.sub(r"\s+\d+(?:[-~]\d+)?\s*[\uad8c\ud654\ubd80]?(?:\s*\([^)]*\))?\s*$", "", series).strip()
    if series and text.startswith(series):
        text = text[len(series):].strip()
    return bool(re.fullmatch(r"\d+\s*\uad8c(?:\s*\([^)]*\))?", text))


def _remove_continued_notice_html(raw: str) -> tuple[str, int]:
    """Remove standalone end-of-volume continuation notices from merged body HTML."""
    if _core_remove_continued_notice_html:
        return _core_remove_continued_notice_html(raw)
    removed = 0

    def _is_notice(inner_html: str) -> bool:
        text = re.sub(r"<style[^>]*>.*?</style>", "", inner_html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.strip("「」『』[]()（）<>〈〉-–—_*·.。…!！~")
        if not text:
            return False
        compact = re.sub(r"\s+", "", text)
        return bool(re.fullmatch(
            r"(?:다음|다음번|차기|차권|다음권|다음 권|다음화|다음 화|다음장|다음 장)"
            r"(?:에|에서|으로)?(?:계속|이어집니다|이어짐|계속됩니다|계속됩니다\.?|계속됨)"
            r"|(?:다음|다음권|다음 권)(?:에서|에)?만나요",
            compact,
        ))

    def _drop_block(m):
        nonlocal removed
        if _is_notice(m.group(0)):
            removed += 1
            return ""
        return m.group(0)

    block_pat = re.compile(
        r"<(?P<tag>p|div|h[1-6])\b[^>]*>.*?</(?P=tag)>",
        re.DOTALL | re.IGNORECASE,
    )
    raw = block_pat.sub(_drop_block, raw)

    line_pat = re.compile(
        r"(?im)^\s*(?:다음\s*권|다음권|다음\s*화|다음화|다음\s*장|다음장)"
        r"\s*(?:에|에서|으로)?\s*(?:계속(?:됩니다|됨)?|이어집니다|이어짐)\s*[.!。…]*\s*$"
    )
    raw, line_removed = line_pat.subn("", raw)
    return raw, removed + line_removed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ 병합 워커
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔎 공백코드 스캔 — 제거 없이 카운트만
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def scan_invisible_chars(epub_bytes: bytes) -> tuple:
    """EPUB에서 공백코드 개수만 스캔 (파일 수정 없음).
    returns (total_count, char_counts_dict)
    """
    try:
        orig = zipfile.ZipFile(io.BytesIO(epub_bytes), 'r')
    except Exception:
        return 0, {}
    char_counts = {}
    for item in orig.infolist():
        fl = item.filename.lower()
        if item.filename.startswith('META-INF/'):
            continue
        try:
            file_data = orig.read(item.filename)
        except Exception:
            continue
        if fl.endswith('.opf'):
            n = len(_BOOK_TOKEN.findall(file_data))
            if n:
                char_counts['book-token'] = char_counts.get('book-token', 0) + n
            continue
        if not any(fl.endswith(e) for e in _TARGET_EXTS):
            continue
        for pat, name in _FULL_PATTERNS.items():
            cnt = file_data.count(pat)
            if cnt:
                char_counts[name] = char_counts.get(name, 0) + cnt
        matches = _TAGS_BLOCK.findall(file_data)
        if matches:
            char_counts['U+E0020~'] = char_counts.get('U+E0020~', 0) + len(matches)
    orig.close()
    total = sum(v for k, v in char_counts.items() if k != 'book-token')
    return total, char_counts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖥️ 메인 윈도우
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class CenteredCheckBoxDelegate(QStyledItemDelegate):
    """선택 열 체크박스를 셀 가운데에 그려 빈 라벨 공간처럼 보이지 않게 한다."""

    def _checkbox_rect(self, option):
        button = QStyleOptionButton()
        indicator = QApplication.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, button, None
        )
        return QRect(
            option.rect.x() + (option.rect.width() - indicator.width()) // 2,
            option.rect.y() + (option.rect.height() - indicator.height()) // 2,
            indicator.width(),
            indicator.height(),
        )

    def paint(self, painter, option, index):
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is None:
            super().paint(painter, option, index)
            return
        button = QStyleOptionButton()
        button.rect = self._checkbox_rect(option)
        button.state = QStyle.StateFlag.State_Enabled
        if check_state == Qt.CheckState.Checked:
            button.state |= QStyle.StateFlag.State_On
        else:
            button.state |= QStyle.StateFlag.State_Off
        QApplication.style().drawControl(QStyle.ControlElement.CE_CheckBox, button, painter)

    def editorEvent(self, event, model, option, index):
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is None:
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.Type.MouseButtonRelease and option.rect.contains(event.position().toPoint()):
            new_state = Qt.CheckState.Unchecked if check_state == Qt.CheckState.Checked else Qt.CheckState.Checked
            return model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Select):
            new_state = Qt.CheckState.Unchecked if check_state == Qt.CheckState.Checked else Qt.CheckState.Checked
            return model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
        return False


class EPUBMergerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epub Binder")
        self.setMinimumWidth(600)
        self.setMinimumHeight(660)
        self.setAcceptDrops(True)          # 윈도우 전체에서 드래그 수신
        self.setStyleSheet(QSS)
        self._files: list[tuple] = []   # (path, name, size_str)
        self._manual_mode = False
        self._worker = None
        self._toc_titles: list[str] = []   # 목차 표시 제목 리스트
        self._custom_cover: bytes | None = None   # 사용자 지정 커버 이미지
        self._cover_user_set: bool = False        # 사용자가 직접 표지 지정했는지 여부
        self._custom_cover_ext: str = '.jpg'
        self._extra_front_covers: list[tuple[bytes, str, str]] = []
        self._title_auto   = True          # 제목이 자동 추출 상태면 True
        self._scan_results: dict = {}      # {path: (total, char_counts)} — 공백코드 스캔 결과
        self._scan_worker  = None
        self._path_to_row: dict = {}       # {path: row_index} — 스캔 결과 O(1) 반영용
        self._file_meta: dict = {}         # {path: (name, size)} — 스캔 결과 O(1) 반영용
        self._temp_dirs: list[str] = []    # zip/7z 드래그 시 생성된 임시폴더 (병합 후 정리)
        # 저장경로 기억용 설정 (OS 레지스트리/앱 데이터에 영구 저장)
        from PyQt6.QtCore import QSettings
        self._settings = QSettings("EpubBinder", "EpubBinder")
        self._build_ui()
        self._load_merge_options()   # 합본 옵션 체크박스 상태 복원

    # ── 합본 옵션 체크박스 저장/복원 ──────────────────
    def _save_merge_options(self):
        """합본 탭 체크박스 상태를 QSettings에 저장."""
        s = self._settings
        s.setValue("merge_chk_timestamp",  self.chk_timestamp.isChecked())
        s.setValue("merge_chk_flat_toc",   self.chk_flat_toc.isChecked())
        s.setValue("merge_chk_vol_covers", self.chk_vol_covers.isChecked())
        s.setValue("merge_chk_compress",   self.chk_compress.isChecked())
        s.setValue("merge_chk_complete",   self.chk_complete.isChecked())
        s.setValue("merge_chk_noise",      self.chk_noise.isChecked())
        s.setValue("merge_noise_level",    self.noise_combo.currentIndex())
        s.setValue("merge_chk_txt_save",   self.chk_merge_txt_save.isChecked())

    def _load_merge_options(self):
        """QSettings에서 합본 탭 체크박스 상태 복원."""
        s = self._settings
        def _b(key, default): return s.value(key, default, type=bool)
        self.chk_timestamp.setChecked(      _b("merge_chk_timestamp",  True))
        self.chk_flat_toc.setChecked(       _b("merge_chk_flat_toc",   False))
        # flat_toc 상태에 맞춰 권별 표지 체크박스 활성화
        _vce = self.chk_flat_toc.isChecked()
        self.chk_vol_covers.setEnabled(_vce)
        if _vce:
            self.chk_vol_covers.setChecked(_b("merge_chk_vol_covers", False))
        self.chk_compress.setChecked(       _b("merge_chk_compress",   False))
        self.chk_complete.setChecked(       _b("merge_chk_complete",   False))
        self.chk_noise.setChecked(          _b("merge_chk_noise",      False))
        self.noise_combo.setCurrentIndex(   s.value("merge_noise_level", 0, type=int))
        self.chk_merge_txt_save.setChecked( _b("merge_chk_txt_save",   False))

    # ── ZIP/7z 드래그 지원 — 내부의 EPUB만 추출 ──────
    def _extract_archives_for_epub(self, paths):
        """ZIP/7z 파일이 섞여 있으면 내부 EPUB만 임시 폴더로 추출해 경로 치환.
        일반 파일/폴더는 그대로 반환.
        """
        result = []
        for p in paths:
            low = p.lower()
            try:
                if low.endswith('.zip'):
                    extracted = self._extract_zip_epubs(p)
                    if extracted:
                        result.extend(extracted)
                    # 추출 실패/EPUB 없음 → 조용히 무시 (이후 .epub 필터에서 제외됨)
                elif low.endswith('.7z'):
                    extracted = self._extract_7z_epubs(p)
                    if extracted:
                        result.extend(extracted)
                else:
                    result.append(p)
            except ImportError:
                QMessageBox.warning(
                    self, "py7zr 없음",
                    "7z 파일 추출에는 py7zr 패키지가 필요합니다.\n"
                    "pip install py7zr")
            except Exception as ex:
                QMessageBox.warning(
                    self, "압축 해제 실패",
                    f"{Path(p).name}\n\n{ex}")
        return result

    def _archive_extract_dir(self, archive_path):
        """압축파일 전용 임시 폴더 경로 생성 (중복 시 넘버링)."""
        import tempfile, time
        base = Path(tempfile.gettempdir()) / "epub_binder_extract"
        stem = Path(archive_path).stem
        out = base / f"{stem}_{int(time.time()*1000)}"
        out.mkdir(parents=True, exist_ok=True)
        self._temp_dirs.append(str(out))
        return out

    @staticmethod
    def _recover_zip_member_name(name: str, flag_bits: int = 0) -> str:
        """Recover Korean filenames from legacy Windows ZIP archives."""
        if flag_bits & 0x800:
            return name
        try:
            raw = name.encode("cp437")
        except Exception:
            return name

        candidates = [name]
        for enc in ("cp949", "utf-8"):
            try:
                decoded = raw.decode(enc)
            except Exception:
                continue
            if decoded and decoded not in candidates:
                candidates.append(decoded)

        def _score(value: str) -> int:
            hangul = sum(1 for ch in value if "\uac00" <= ch <= "\ud7a3")
            bad = sum(
                1 for ch in value
                if ch == "\ufffd" or "\u2500" <= ch <= "\u259f" or "\x00" <= ch <= "\x1f"
            )
            return hangul * 10 - bad * 6 - value.count("?") * 3

        return max(candidates, key=_score)

    def _extract_zip_epubs(self, archive_path):
        """ZIP 내부의 .epub 파일을 임시 폴더로 추출, 경로 리스트 반환."""
        out_dir = self._archive_extract_dir(archive_path)
        extracted = []
        with zipfile.ZipFile(archive_path, 'r') as zf:
            for info in zf.infolist():
                name = info.filename
                if name.endswith('/') or not name.lower().endswith('.epub'):
                    continue
                safe_name = Path(name).name  # 경로 구분자 제거 (zip slip 방지)
                display_name = self._recover_zip_member_name(name, info.flag_bits)
                safe_name = Path(display_name.replace('\\', '/')).name
                target = out_dir / safe_name
                i = 1
                while target.exists():
                    target = out_dir / f"{target.stem}_{i}{target.suffix}"
                    i += 1
                with zf.open(info) as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                extracted.append(str(target))
        return extracted

    def _extract_7z_epubs(self, archive_path):
        """7z 내부의 .epub 파일을 임시 폴더로 추출, 경로 리스트 반환."""
        import py7zr
        out_dir = self._archive_extract_dir(archive_path)
        extracted = []
        with py7zr.SevenZipFile(archive_path, 'r') as archive:
            names = archive.getnames()
            epub_names = [n for n in names if n.lower().endswith('.epub') and not n.endswith('/')]
            if not epub_names:
                return []
            archive.extract(path=str(out_dir), targets=epub_names)
        # 하위 폴더에 추출될 수 있으므로 walk
        for root, _, files in os.walk(out_dir):
            for fn in files:
                if fn.lower().endswith('.epub'):
                    extracted.append(os.path.join(root, fn))
        return extracted

    # ── 완료 후 폴더 열기 (설정 기반) ───────────────
    def _open_folder_confirm(self, path, title="완료", pre_msg=""):
        """설정(open_folder_mode)에 따라 저장 폴더 열기 처리.
        ask   → 팝업으로 확인 후 Yes면 열기
        auto  → 팝업 없이 자동으로 열기
        never → 팝업 없이 열지 않음
        """
        mode = self._settings.value("open_folder_mode", "ask", type=str)
        if mode == "auto":
            try: os.startfile(str(path))
            except Exception: pass
            return
        if mode == "never":
            return
        # ask (기본)
        body = (pre_msg + "\n\n" if pre_msg else "") + "저장 폴더를 열까요?"
        r = QMessageBox.information(
            self, title, body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            try: os.startfile(str(path))
            except Exception: pass

    # ── 윈도우 레벨 드래그앤드롭 ───────────────────
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls()]
            if paths:
                # 현재 탭에 따라 드롭 대상 분기
                idx = self.tab_widget.currentIndex()
                if idx == 1:
                    self._rename_add_files(paths)
                elif idx == 2:
                    self._txt_add_files(paths)
                elif idx == 3:
                    self._e2t_add_files(paths)
                else:
                    self._replace_files(paths)
            e.acceptProposedAction()

    def _build_ui(self):
        central = QWidget(); central.setObjectName("central")
        self.setCentralWidget(central)

        # 전체: 수직 (타이틀 + 좌우 분할 + 하단 여백)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 16); root.setSpacing(10)

        # 타이틀 + 버전 배지 + 핀 버튼
        title_row = QHBoxLayout(); title_row.setSpacing(8)
        t = QLabel("📚  Epub Binder")
        t.setStyleSheet(
            f"color:{C['text']};font-size:17px;font-weight:700;background:transparent;")
        title_row.addWidget(t)
        ver_badge = QLabel("v5.1.0")
        ver_badge.setStyleSheet(
            f"color:{C['text3']};font-size:10px;background:transparent;"
            f"border:1px solid {C['border']};border-radius:4px;padding:1px 6px;margin-top:4px;")
        title_row.addWidget(ver_badge)
        if APP_EXPIRATION_DATE:
            exp_badge = QLabel(f"만료 {APP_EXPIRATION_DATE.isoformat()}")
            exp_badge.setStyleSheet(
                f"color:{C['text3']};font-size:10px;background:transparent;"
                f"border:1px solid {C['border']};border-radius:4px;padding:1px 6px;margin-top:4px;")
            title_row.addWidget(exp_badge)
        title_row.addStretch()

        # ── 완료 후 폴더 열기 동작 옵션 ────────────────
        _open_label = QLabel("완료 후:")
        _open_label.setStyleSheet(
            f"color:{C['text3']};font-size:11px;background:transparent;")
        title_row.addWidget(_open_label)
        self.open_mode_combo = QComboBox()
        self.open_mode_combo.addItem("묻기", "ask")
        self.open_mode_combo.addItem("자동 열기", "auto")
        self.open_mode_combo.addItem("열지 않기", "never")
        self.open_mode_combo.setToolTip(
            "병합/변환 완료 후 저장 폴더 열기 동작\n"
            " • 묻기: 팝업으로 확인 (기본)\n"
            " • 자동 열기: 묻지 않고 자동으로 열기\n"
            " • 열지 않기: 팝업·자동 열기 모두 생략")
        _saved_open = self._settings.value("open_folder_mode", "ask", type=str)
        for _i in range(self.open_mode_combo.count()):
            if self.open_mode_combo.itemData(_i) == _saved_open:
                self.open_mode_combo.setCurrentIndex(_i)
                break
        self.open_mode_combo.currentIndexChanged.connect(
            lambda: self._settings.setValue(
                "open_folder_mode", self.open_mode_combo.currentData()))
        title_row.addWidget(self.open_mode_combo)

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setFixedSize(32, 28)
        self.pin_btn.setToolTip("항상 위에 표시")
        self.pin_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {C['border']};"
            f"border-radius:6px;font-size:15px;padding:0 2px;color:{C['text3']};}}"
            f"QPushButton:hover{{background:{C['bg2']};border-color:{C['accent']};}}"
            f"QPushButton:checked{{background:rgba(34,114,216,0.12);"
            f"border-color:{C['accent']};color:{C['accent']};}}")
        self.pin_btn.toggled.connect(
            lambda on: (
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on),
                self.show()))
        title_row.addWidget(self.pin_btn)

        # ── 네이버 시리즈 쿠키 설정 버튼 ──────────────
        self.naver_cookie_btn = QPushButton("🍪 설정")
        self.naver_cookie_btn.setFixedHeight(28)
        self.naver_cookie_btn.setToolTip(
            "네이버 시리즈 쿠키 설정\n"
            "NID_AUT / NID_SES 를 입력하면 표지 검색 시\n"
            "시리즈 표지를 직접 가져올 수 있습니다.")
        self.naver_cookie_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {C['border']};"
            f"border-radius:6px;font-size:11px;padding:0 8px;color:#111;}}"
            f"QPushButton:hover{{background:{C['bg2']};border-color:{C['accent']};color:{C['accent']};}}")
        self.naver_cookie_btn.clicked.connect(self._open_naver_cookie_settings)
        title_row.addWidget(self.naver_cookie_btn)

        root.addLayout(title_row)

        # ── 탭 위젯 ─────────────────────────────────
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("")   # QSS에서 처리
        root.addWidget(self.tab_widget, 1)

        # 탭1: 병합
        merge_tab = QWidget()
        merge_tab_layout = QVBoxLayout(merge_tab)
        merge_tab_layout.setContentsMargins(0, 8, 0, 0)
        merge_tab_layout.setSpacing(10)
        self.tab_widget.addTab(merge_tab, "병합")

        # 탭2: 이름 변경
        rename_tab = QWidget()
        rename_tab_layout = QVBoxLayout(rename_tab)
        rename_tab_layout.setContentsMargins(0, 8, 0, 0)
        rename_tab_layout.setSpacing(10)
        self.tab_widget.addTab(rename_tab, "이름 변경")

        # 탭3: txt2epub (TXT → EPUB)
        txt_tab = QWidget()
        txt_tab_layout = QVBoxLayout(txt_tab)
        txt_tab_layout.setContentsMargins(0, 8, 0, 0)
        txt_tab_layout.setSpacing(10)
        self.tab_widget.addTab(txt_tab, "txt2epub")

        # 탭4: EPUB → TXT
        e2t_tab = QWidget()
        e2t_tab_layout = QVBoxLayout(e2t_tab)
        e2t_tab_layout.setContentsMargins(0, 8, 0, 0)
        e2t_tab_layout.setSpacing(10)
        self.tab_widget.addTab(e2t_tab, "epub2txt")

        dedupe_tab = QWidget()
        dedupe_tab_layout = QVBoxLayout(dedupe_tab)
        dedupe_tab_layout.setContentsMargins(0, 8, 0, 0)
        dedupe_tab_layout.setSpacing(10)
        self.tab_widget.addTab(dedupe_tab, "중복 정리")

        # 이름 변경 탭 선택 시 컬럼 비율 재적용 (탭 전환 후 뷰포트 크기 확정)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # 병합 탭 내용 빌드
        self._build_merge_tab(merge_tab_layout)
        # 이름 변경 탭 내용 빌드
        self._build_rename_tab(rename_tab_layout)
        # 텍스트 변환 탭 내용 빌드
        self._build_txt_tab(txt_tab_layout)
        # epub2txt 탭 내용 빌드
        self._build_epub2txt_tab(e2t_tab_layout)
        self._build_dedupe_tab(dedupe_tab_layout)

    def _build_merge_tab(self, root):
        card1, _, bl1 = make_card("📋 병합할 EPUB 목록", C["accent"])

        # [➕ 파일] [🗑] │ [□ 수동] [▲][▼][✕] stretch 0개 │ [↕]
        top_row = QHBoxLayout(); top_row.setSpacing(5)
        b_add = mk_btn("📂 파일 열기", "blue")
        b_add.setToolTip("EPUB 파일 선택 (기존 목록 교체)\n드래그앤드롭도 목록 교체"); b_add.clicked.connect(self._browse_files)
        b_clear = mk_btn("🗑 비우기", "gray")
        b_clear.setToolTip("목록 초기화"); b_clear.clicked.connect(self._clear_files)
        top_row.addWidget(b_add); top_row.addWidget(b_clear)
        div1 = QFrame(); div1.setFrameShape(QFrame.Shape.VLine)
        div1.setStyleSheet(f"color:{C['border']};"); div1.setFixedWidth(1)
        top_row.addWidget(div1)
        self.manual_chk = QCheckBox("수동")
        self.manual_chk.setToolTip("체크 시 드래그 또는 ▲▼ 버튼으로 순서 조절")
        self.manual_chk.stateChanged.connect(self._on_manual_toggle)
        top_row.addWidget(self.manual_chk)
        self.b_up   = mk_btn("▲", "gray");   self.b_up.setFixedWidth(28)
        self.b_down = mk_btn("▼", "gray");   self.b_down.setFixedWidth(28)
        self.b_del  = mk_btn("X", "danger"); self.b_del.setFixedWidth(28)
        self.b_del.setStyleSheet(
            f"QPushButton{{background:#fff1f1;color:{C['red']};border:1px solid #f2caca;"
            "border-radius:6px;font-weight:800;font-size:13px;padding:0;}}"
            "QPushButton:hover{background:#ffe5e5;border-color:#e5a8a8;}"
            "QPushButton:disabled{background:#f8eeee;color:#d8a0a0;border-color:#edd1d1;}")
        self.b_up.setToolTip("위로"); self.b_down.setToolTip("아래로")
        self.b_del.setToolTip("선택 항목 삭제")
        self.b_up.clicked.connect(self._move_up)
        self.b_down.clicked.connect(self._move_down)
        self.b_del.clicked.connect(self._delete_selected)
        self.b_up.setEnabled(False); self.b_down.setEnabled(False)
        top_row.addWidget(self.b_up); top_row.addWidget(self.b_down); top_row.addWidget(self.b_del)
        top_row.addStretch()
        self.count_lbl = mk_lbl("0개", C["text3"], 11)
        top_row.addWidget(self.count_lbl)
        div2 = QFrame(); div2.setFrameShape(QFrame.Shape.VLine)
        div2.setStyleSheet(f"color:{C['border']};"); div2.setFixedWidth(1)
        top_row.addWidget(div2)
        b_sort = mk_btn("↕ 정렬", "gray")
        b_sort.setToolTip("자동 정렬 (권·부·완결·외전 순)"); b_sort.clicked.connect(self._auto_sort)
        top_row.addWidget(b_sort)
        bl1.addLayout(top_row)

        self.file_list = FileListWidget()
        self.file_list.files_dropped.connect(self._replace_files)
        self.file_list.order_changed.connect(self._on_order_changed)
        bl1.addWidget(self.file_list)
        root.addWidget(card1)

        # ── 옵션 카드 — [표지][목차] | 두 줄(날짜·노이즈 / 용량·완결·단일화) ─────
        card2, _, bl2 = make_card("⚙️ 병합 옵션", C["green"])

        _chk_style = (
            f"QCheckBox{{font-family:'맑은 고딕';font-size:12px;color:{C['text2']};spacing:5px;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;}}"
            f"QCheckBox::indicator:unchecked{{background:{C['surface2']};border:1.5px solid {C['border']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}")
        _date_edit_base = (
            f"QLineEdit{{background:{C['surface']};border:1px solid {C['border']};"
            f"border-radius:5px;padding:2px 6px;font-family:'맑은 고딕';font-size:11px;"
            f"color:{C['text']};}}"
            f"QLineEdit:disabled{{background:{C['bg2']};color:{C['text3']};}}")
        _cmb_style = (
            f"QComboBox{{background:{C['surface']};border:1px solid {C['border']};"
            f"border-radius:5px;padding:1px 4px;font-family:'맑은 고딕';font-size:11px;"
            f"color:{C['text']};}}"
            f"QComboBox:disabled{{background:{C['bg2']};color:{C['text3']};}}"
            f"QComboBox::drop-down{{border:none;width:14px;}}")

        # 버튼 영역 (표지·목차)
        self.cover_lbl = mk_lbl("", C["text3"], 11)
        self.cover_lbl.setVisible(False)
        b_cover_paste = mk_btn("📋 표지", "blue")
        b_cover_paste.setToolTip("클립보드 이미지를 표지로 설정 (Ctrl+V)")
        b_cover_paste.clicked.connect(self._paste_cover)
        b_cover_pick  = mk_btn("🖼 선택", "blue")
        b_cover_pick.setToolTip(
            "1권 EPUB 내부의 표지 후보(또는 모든 이미지)를 보고 직접 선택합니다.\n"
            "표지 후보가 2개 이상일 때는 합본 시작 시 자동으로 열립니다.")
        b_cover_pick.clicked.connect(self._open_cover_picker)
        self.b_cover_clear = mk_btn("X", "danger")
        self.b_cover_clear.setFixedWidth(30)
        self.b_cover_clear.setStyleSheet(
            f"QPushButton{{background:#fff1f1;color:{C['red']};border:1px solid #f2caca;"
            "border-radius:6px;font-weight:800;font-size:13px;padding:0;}}"
            "QPushButton:hover{background:#ffe5e5;border-color:#e5a8a8;}")
        self.b_cover_clear.setToolTip("표지 초기화 (자동 추출로 복귀)")
        self.b_cover_clear.setVisible(False)
        self.b_cover_clear.clicked.connect(self._clear_cover)
        b_toc_edit = mk_btn("목차", "blue")
        b_toc_edit.setToolTip("목차 구조 미리보기 및 제목 편집")
        b_toc_edit.clicked.connect(self._open_toc_dialog)

        # Row 1: 표지 / 표지선택 / 목차 / 파일날짜
        self.chk_timestamp = QCheckBox("날짜")
        self.chk_timestamp.setChecked(True)
        self.chk_timestamp.setToolTip("저장할 EPUB 파일의 내부 날짜를 지정합니다.")
        self.chk_timestamp.setStyleSheet(_chk_style)
        self.date_edit = QLineEdit("2001-01-01")
        self.date_edit.setFixedWidth(82)
        self.date_edit.setToolTip("YYYY-MM-DD 형식으로 직접 입력")
        self.date_edit.setStyleSheet(_date_edit_base)
        self.chk_timestamp.toggled.connect(self.date_edit.setEnabled)

        self.chk_vol_covers = QCheckBox("권표지")
        self.chk_vol_covers.setChecked(False)
        self.chk_vol_covers.setEnabled(False)   # 권 목차 ON일 때만 활성
        self.chk_vol_covers.setToolTip(
            "각 권의 표지 페이지를 제거하지 않고 본문에 포함합니다.\n"
            "권 목차 옵션이 켜져 있을 때만 적용됩니다.")
        self.chk_vol_covers.setStyleSheet(_chk_style)

        self.chk_noise = QCheckBox("노이즈")
        self.chk_noise.setChecked(False)
        self.chk_noise.setToolTip(
            "표지·삽화 이미지 픽셀에 미세한 랜덤 노이즈를 추가합니다.\n"
            "레벨 1(미세 ±3) / 2(보통 ±8) / 3(강함 ±18)\n"
            "PIL(Pillow) 패키지가 필요합니다.")
        self.chk_noise.setStyleSheet(_chk_style)
        self.noise_combo = QComboBox()
        self.noise_combo.addItems(["1", "2", "3"])
        self.noise_combo.setFixedWidth(44)
        self.noise_combo.setEnabled(False)
        self.noise_combo.setToolTip("노이즈 강도  1 = 미세 / 2 = 보통 / 3 = 강함")
        self.noise_combo.setStyleSheet(_cmb_style)
        self.chk_noise.toggled.connect(self.noise_combo.setEnabled)

        self.chk_flat_toc = QCheckBox("권목차")
        self.chk_flat_toc.setChecked(False)
        self.chk_flat_toc.setToolTip(
            "체크 시: 권별 계층 목차(권 상위노드 + 화 하위노드)를 사용합니다.\n"
            "기본(체크 해제)은 단일 목차로 모든 화를 한 목록에 표시합니다.")
        self.chk_flat_toc.setStyleSheet(_chk_style)
        # 권 목차 OFF → 권별 표지 비활성 + 체크 해제
        self.chk_flat_toc.toggled.connect(
            lambda on: (self.chk_vol_covers.setEnabled(on),
                        self.chk_vol_covers.setChecked(False) if not on else None))

        # Row 2: 용량 줄이기 | 완결표시 | 권 목차 | TXT 저장
        self.chk_compress = QCheckBox("용량↓")
        self.chk_compress.setChecked(False)
        self.chk_compress.setToolTip("이미지 압축 적용 (JPEG 재압축 + PNG→JPEG 변환)\n체크 해제 시 원본 이미지 그대로 복사 (기본값)")
        self.chk_compress.setStyleSheet(_chk_style)

        self.chk_complete = QCheckBox("완결")
        self.chk_complete.setChecked(False)
        self.chk_complete.setToolTip("체크 시 파일명에 (완결) 추가")
        self.chk_complete.setStyleSheet(_chk_style)
        self.chk_complete.toggled.connect(self._on_complete_toggle)

        self.chk_merge_txt_save = QCheckBox("txt저장")
        self.chk_merge_txt_save.setChecked(False)
        self.chk_merge_txt_save.setToolTip(
            "병합이 모두 끝난 뒤 결과 EPUB를 TXT로 마지막에 변환해 저장합니다.")
        self.chk_merge_txt_save.setStyleSheet(_chk_style)

        # 체크박스 상태 변경 시 자동 저장
        for _save_chk in (self.chk_timestamp, self.chk_flat_toc, self.chk_compress,
                          self.chk_complete, self.chk_noise, self.chk_merge_txt_save,
                          self.chk_vol_covers):
            _save_chk.toggled.connect(self._save_merge_options)
        self.noise_combo.currentIndexChanged.connect(self._save_merge_options)

        # ── 1줄: 표지·목차 버튼 + 날짜 ─────────────────
        opt_row_1 = QHBoxLayout(); opt_row_1.setSpacing(8)
        opt_row_1.setContentsMargins(0, 0, 0, 0)
        opt_row_1.addWidget(b_cover_paste)
        opt_row_1.addWidget(b_cover_pick)
        opt_row_1.addWidget(self.cover_lbl)
        opt_row_1.addWidget(self.b_cover_clear)
        opt_row_1.addWidget(b_toc_edit)
        opt_row_1.addSpacing(10)
        opt_row_1.addWidget(self.chk_timestamp)
        opt_row_1.addWidget(self.date_edit)
        opt_row_1.addStretch()

        # ── 2줄: 권목차 권표지 용량↓ 완결 노이즈 [레벨] txt저장 ─
        opt_row_2 = QHBoxLayout(); opt_row_2.setSpacing(8)
        opt_row_2.setContentsMargins(0, 0, 0, 0)
        opt_row_2.addWidget(self.chk_flat_toc)
        opt_row_2.addWidget(self.chk_vol_covers)
        opt_row_2.addWidget(self.chk_compress)
        opt_row_2.addWidget(self.chk_complete)
        opt_row_2.addWidget(self.chk_noise)
        opt_row_2.addWidget(self.noise_combo)
        opt_row_2.addWidget(self.chk_merge_txt_save)
        opt_row_2.addStretch()

        opts_box = QVBoxLayout(); opts_box.setSpacing(6)
        opts_box.setContentsMargins(0, 0, 0, 0)
        opts_box.addLayout(opt_row_1)
        opts_box.addLayout(opt_row_2)
        bl2.addLayout(opts_box)

        root.addWidget(card2)

        # ── 저장 설정 카드 ────────────────────────────
        card3, _, bl3 = make_card("💾 저장 설정", C["orange"])
        LBL_W = 54

        # 파일명 행: 라벨(고정폭) | 입력창(flex) | .epub
        fname_row = QHBoxLayout(); fname_row.setSpacing(6)
        lbl_fname = mk_lbl("파일명", C["text2"], 11)
        lbl_fname.setFixedWidth(LBL_W)
        fname_row.addWidget(lbl_fname)
        self.fname_edit = QLineEdit("merged")
        self.fname_edit.setToolTip("출력 EPUB 파일명을 입력합니다.")
        self.fname_edit.textEdited.connect(lambda: setattr(self, '_title_auto', False))
        fname_row.addWidget(self.fname_edit, 1)
        fname_row.addWidget(mk_lbl(".epub", C["accent"], 12))
        bl3.addLayout(fname_row)

        # 저장 폴더 행: 라벨(고정폭) | 경로(flex) | [📁 찾기]
        dir_row = QHBoxLayout(); dir_row.setSpacing(6)
        lbl_dir = mk_lbl("저장 위치", C["text2"], 11)
        lbl_dir.setFixedWidth(LBL_W)
        dir_row.addWidget(lbl_dir)
        _saved_merge_dir = self._settings.value(
            "last_merge_dir", str(Path.home() / "Downloads"))
        self.dir_edit = QLineEdit(_saved_merge_dir)
        self.dir_edit.setReadOnly(True)
        dir_row.addWidget(self.dir_edit, 1)
        b_dir = mk_btn("📁 찾기", "gray"); b_dir.clicked.connect(self._browse_dir)
        b_dir.setToolTip("병합 결과를 저장할 폴더를 선택합니다.")
        dir_row.addWidget(b_dir)
        bl3.addLayout(dir_row)
        root.addWidget(card3)

        # ── 진행 카드 + 병합 버튼 (하단) ─────────────
        card4, _, bl4 = make_card("", C["text3"])
        card4.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.prog_bar = QProgressBar(); self.prog_bar.setValue(0)
        bl4.addWidget(self.prog_bar)
        self.log_area = QTextEdit()
        self.log_area.setObjectName("log_area")
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(70)
        self.log_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bl4.addWidget(self.log_area)
        root.addWidget(card4, 1)   # stretch=1 → 윈도우 높이에 따라 늘어남

        # ── 하단 버튼 행: [🧹 코드만 제거] [🚀 병합 시작] ──────
        _btn_row = QHBoxLayout(); _btn_row.setSpacing(8)

        self.strip_btn = mk_btn("🧹  코드만 제거", "blue")
        self.strip_btn.setFixedHeight(42)
        self.strip_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;font-size:13px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#1a63c8;}}"
            f"QPushButton:disabled{{background:#a8c4e8;color:#ddeaf8;}}")
        self.strip_btn.setToolTip("합본 없이 각 EPUB의 공백코드/판권·목차 페이지만 정리합니다.")
        self.strip_btn.clicked.connect(self._start_strip_only)
        _btn_row.addWidget(self.strip_btn, 1)

        self.merge_btn = mk_btn("✨ 병합 시작", "green")
        self.merge_btn.setFixedHeight(42)
        self.merge_btn.setStyleSheet(
            f"QPushButton{{background:{C['green']};color:white;font-size:14px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#16b87a;}}"
            f"QPushButton:disabled{{background:#a8d8c4;color:#ddf0ea;}}")
        self.merge_btn.setToolTip("현재 목록을 설정한 옵션으로 병합합니다.")
        self.merge_btn.clicked.connect(self._start_merge)
        _btn_row.addWidget(self.merge_btn, 2)

        root.addLayout(_btn_row)
        self.resize(520, 720)

    # ── 이름 변경 탭 ──────────────────────────────
    def _build_rename_tab(self, root):
        self._rename_files: list = []   # (path, name, size_str)

        # ── 파일 목록 + 미리보기 통합 카드 ──
        card_p, _, bl_p = make_card("📂 이름 변경  (파일을 드래그하거나 [파일 열기]로 추가)", C["accent"])

        # 버튼 툴바
        top_row = QHBoxLayout(); top_row.setSpacing(5)
        b_radd = mk_btn("📂 파일 열기", "blue")
        b_radd.setToolTip("이름 변경할 EPUB 파일을 추가합니다.")
        b_radd.clicked.connect(self._rename_browse_files)
        b_rclear = mk_btn("🗑 비우기", "gray")
        b_rclear.setToolTip("이름 변경 목록을 모두 비웁니다.")
        b_rclear.clicked.connect(self._rename_clear_files)
        b_rdel = mk_btn("❌ 삭제", "danger")
        b_rdel.setToolTip("선택한 행을 삭제합니다. Ctrl/Shift 다중 선택과 Del 키를 지원합니다.")
        b_rdel.clicked.connect(self._rename_delete_selected)
        b_batch = mk_btn("🔧 일괄 변경", "blue")
        b_batch.setToolTip("선택 행 또는 전체 변경될 이름에 일괄 수정 규칙을 적용합니다.")
        b_batch.clicked.connect(self._rename_open_batch_dialog)
        top_row.addWidget(b_radd)
        top_row.addWidget(b_rclear)
        top_row.addWidget(b_rdel)
        top_row.addWidget(b_batch)
        b_reset_names = mk_btn("↺ 초기화", "gray")
        b_reset_names.setToolTip("변경될 이름을 원본 파일명으로 되돌립니다.")
        b_reset_names.clicked.connect(self._rename_reset_preview)
        top_row.addWidget(b_reset_names)
        top_row.addStretch()
        self.rename_count_lbl = mk_lbl("0개", C["text3"], 11)
        top_row.addWidget(self.rename_count_lbl)
        bl_p.addLayout(top_row)

        self.rename_table = QTableWidget(0, 2)
        self.rename_table.setHorizontalHeaderLabels(["원본 파일명  (클릭 시 복사)", "변경될 이름  (더블클릭 · Ctrl+Enter)"])
        self.rename_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive)
        # 오른쪽 열: Stretch → 항상 뷰포트 나머지를 꽉 채움 (가로 스크롤 방지)
        self.rename_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.rename_table.horizontalHeader().setMinimumSectionSize(80)
        self._rename_col0_ratio = 0.5  # 왼쪽 열 비율 (showEvent에서 적용)
        self.rename_table.verticalHeader().setVisible(False)
        self.rename_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.rename_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rename_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed)
        self.rename_table.setStyleSheet(
            f"QTableWidget{{background:{C['surface2']};border:1px solid {C['border']};"
            f"border-radius:6px;outline:none;gridline-color:{C['border']};"
            f"font-family:'맑은 고딕';font-size:12px;color:{C['text']};"
            f"selection-background-color:rgba(34,114,216,0.1);selection-color:{C['accent']};}}"
            f"QTableWidget::item{{padding:4px 8px;color:{C['text']};}}"
            f"QTableWidget::item:selected{{background:rgba(34,114,216,0.1);color:{C['accent']};}}"
            f"QTableWidget::item:focus{{background:rgba(34,114,216,0.1);color:{C['accent']};}}"
            f"QTableWidget::item:hover{{background:{C['bg2']};}}"
            f"QHeaderView::section{{background:{C['bg2']};border:none;"
            f"border-bottom:1px solid {C['border']};border-right:1px solid {C['border']};"
            f"padding:4px 8px;color:{C['text2']};font-size:11px;font-family:'맑은 고딕';}}"
        )
        self.rename_table.installEventFilter(self)
        self.rename_table.viewport().installEventFilter(self)
        self.rename_table.cellClicked.connect(self._rename_copy_original_name_if_clicked)
        self.rename_table.cellDoubleClicked.connect(self._rename_copy_original_name_if_clicked)
        self.rename_table.itemClicked.connect(self._rename_copy_original_name_item)
        self.rename_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.rename_table.horizontalHeader().sectionResized.connect(self._on_rename_col_resized)
        bl_p.addWidget(self.rename_table)
        root.addWidget(card_p, 1)

        # ── 적용 버튼 ──
        self.rename_apply_btn = mk_btn("✔  이름 변경 적용", "green")
        self.rename_apply_btn.setFixedHeight(42)
        self.rename_apply_btn.setStyleSheet(
            f"QPushButton{{background:{C['green']};color:white;font-size:14px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#16b87a;}}"
            f"QPushButton:disabled{{background:#a8d8c4;color:#ddf0ea;}}")
        self.rename_apply_btn.setToolTip("미리보기의 이름으로 파일명을 실제 변경합니다.")
        self.rename_apply_btn.clicked.connect(self._rename_apply)
        root.addWidget(self.rename_apply_btn)

        # ── ZIP 묶기 카드 ──
        card_z, _, bl_z = make_card("📦 시리즈 묶기", C["text2"])

        # 압축 형식 선택
        from PyQt6.QtWidgets import QRadioButton
        fmt_row = QHBoxLayout(); fmt_row.setSpacing(12)
        fmt_lbl = mk_lbl("형식", C["text2"], 11); fmt_lbl.setFixedWidth(54)
        fmt_row.addWidget(fmt_lbl)
        self.radio_zip = QRadioButton("ZIP")
        self.radio_7z  = QRadioButton("7z")
        self.radio_zip.setChecked(True)
        for r in (self.radio_zip, self.radio_7z):
            r.setStyleSheet(
                f"QRadioButton{{font-family:'맑은 고딕';font-size:12px;color:{C['text2']};spacing:5px;}}"
                f"QRadioButton::indicator{{width:14px;height:14px;}}"
                f"QRadioButton::indicator:checked{{background:{C['accent']};border:2px solid {C['accent']};border-radius:7px;}}"
                f"QRadioButton::indicator:unchecked{{background:{C['surface2']};border:1.5px solid {C['border']};border-radius:7px;}}")
            fmt_row.addWidget(r)
        # ZIP/7z 와 공백코드 제거 사이 구분선
        _fmt_div = QFrame(); _fmt_div.setFrameShape(QFrame.Shape.VLine)
        _fmt_div.setStyleSheet(f"color:{C['border']};"); _fmt_div.setFixedWidth(1)
        fmt_row.addSpacing(6); fmt_row.addWidget(_fmt_div); fmt_row.addSpacing(6)
        _chk_style = (
            f"QCheckBox{{font-family:'맑은 고딕';font-size:12px;color:{C['text2']};spacing:5px;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;}}"
            f"QCheckBox::indicator:unchecked{{background:{C['surface2']};border:1.5px solid {C['border']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}")
        self.chk_rename_strip = QCheckBox("코드제거")
        self.chk_rename_strip.setChecked(False)
        self.chk_rename_strip.setToolTip("이름 변경·ZIP 묶기 시 각 EPUB에서 공백 유니코드(U+200B 등)를 제거합니다.")
        self.chk_rename_strip.setStyleSheet(_chk_style)
        fmt_row.addWidget(self.chk_rename_strip)
        self.chk_rename_copy = QCheckBox("복사본으로 저장")
        self.chk_rename_copy.setChecked(False)
        self.chk_rename_copy.setToolTip(
            "체크 시: 원본 파일을 유지하고, 변경된 이름으로 'renamed' 하위 폴더에 복사합니다.\n"
            "미체크 시: 원본 파일을 직접 이름 변경합니다.\n"
            "※ ZIP 묶기에도 적용 — 체크 시 1개짜리 단일 EPUB(낱개)도 출력 폴더에 함께 복사합니다.")
        self.chk_rename_copy.setStyleSheet(_chk_style)
        fmt_row.addWidget(self.chk_rename_copy)
        self.chk_rename_txt_save = QCheckBox("TXT 저장")
        self.chk_rename_txt_save.setChecked(False)
        self.chk_rename_txt_save.setToolTip(
            "이름 변경 작업이 모두 끝난 뒤 결과 EPUB를 TXT로 마지막에 변환해 저장합니다.")
        self.chk_rename_txt_save.setStyleSheet(_chk_style)
        fmt_row.addWidget(self.chk_rename_txt_save)
        fmt_row.addStretch()
        bl_z.addLayout(fmt_row)

        zip_dir_row = QHBoxLayout(); zip_dir_row.setSpacing(6)
        lbl_zdir = mk_lbl("저장 위치", C["text2"], 11); lbl_zdir.setFixedWidth(54)
        zip_dir_row.addWidget(lbl_zdir)
        _saved_zip_dir = self._settings.value(
            "last_zip_dir", str(Path.home() / "Downloads"))
        self.zip_dir_edit = QLineEdit(_saved_zip_dir)
        self.zip_dir_edit.setReadOnly(True)
        zip_dir_row.addWidget(self.zip_dir_edit, 1)
        b_zdir = mk_btn("📁 찾기", "gray")
        b_zdir.setToolTip("ZIP/7z 파일을 저장할 폴더를 선택합니다.")
        b_zdir.clicked.connect(self._zip_browse_dir)
        zip_dir_row.addWidget(b_zdir)
        bl_z.addLayout(zip_dir_row)

        self.zip_hint = mk_lbl(
            "변경된 파일명 기준으로 같은 시리즈끼리 ZIP으로 묶습니다.",
            C["text3"], 11)
        bl_z.addWidget(self.zip_hint)
        root.addWidget(card_z)

        action_row = QHBoxLayout(); action_row.setSpacing(8)

        self.zip_btn = mk_btn("📦  ZIP 묶기", "green")
        self.zip_btn.setFixedHeight(42)
        self.zip_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;font-size:14px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#1a63c8;}}"
            f"QPushButton:disabled{{background:#a8c4e8;color:#ddeaf8;}}")
        self.zip_btn.setToolTip("변경된 파일명을 기준으로 시리즈별 ZIP/7z를 생성합니다.")
        self.zip_btn.clicked.connect(self._zip_series)
        action_row.addWidget(self.zip_btn, 1)

        self.merge_from_rename_btn = mk_btn("📚  병합하기", "green")
        self.merge_from_rename_btn.setFixedHeight(42)
        self.merge_from_rename_btn.setStyleSheet(
            f"QPushButton{{background:{C['green']};color:white;font-size:14px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#16b87a;}}"
            f"QPushButton:disabled{{background:#a8d8c4;color:#ddf0ea;}}")
        self.merge_from_rename_btn.setToolTip("현재 이름 변경 목록을 병합 탭으로 보내 바로 병합합니다.")
        self.merge_from_rename_btn.clicked.connect(self._send_to_merge_safe)
        action_row.addWidget(self.merge_from_rename_btn, 1)

        root.addLayout(action_row)

        def _on_fmt_changed():
            if self.radio_7z.isChecked():
                self.zip_hint.setText("변경된 파일명 기준으로 같은 시리즈끼리 7z으로 묶습니다.")
                self.zip_btn.setText("🗃️  7z 묶기")
            else:
                self.zip_hint.setText("변경된 파일명 기준으로 같은 시리즈끼리 ZIP으로 묶습니다.")
                self.zip_btn.setText("📦  ZIP 묶기")
        self.radio_zip.toggled.connect(_on_fmt_changed)
        self.radio_7z.toggled.connect(_on_fmt_changed)

    # ── 이름 변경 탭 파일 관리 ──────────────────────
    def _rename_browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "EPUB 파일 선택", "",
            "EPUB / Archives (*.epub *.zip *.7z);;EPUB Files (*.epub);;Archives (*.zip *.7z);;All Files (*.*)")
        if paths:
            self._rename_add_files(paths)

    def _rename_add_files(self, paths):
        paths = self._extract_archives_for_epub(paths)
        expanded = []
        for p in paths:
            if os.path.isdir(p):
                for r, _, files in os.walk(p):
                    for fn in files:
                        if fn.lower().endswith(".epub"):
                            expanded.append(os.path.join(r, fn))
            else:
                expanded.append(p)
        new_paths = []
        for p in expanded:
            if not p.lower().endswith(".epub"): continue
            if any(f[0] == p for f in self._rename_files): continue
            import unicodedata as _ucd
            _disp_name = _ucd.normalize('NFC', Path(p).name)
            self._rename_files.append((p, _disp_name, human_size(os.path.getsize(p))))
            new_paths.append(p)
        if new_paths:
            self._rename_files.sort(key=lambda f: natural_sort_key(f[1]))
            self._rename_refresh_list()
            # 테이블에 편집 내용이 있으면 새 파일만 추가, 없으면 전체 추출
            if self.rename_table.rowCount() == 0:
                self._rename_extract()
            else:
                # 기존 편집 내용 유지 — 새로 추가된 파일만 테이블에 append
                from PyQt6.QtGui import QColor
                # 정렬 후 순서가 바뀌므로 테이블 전체를 _rename_files 순서에 맞게 재배치
                # 기존 편집값 백업
                existing: dict[str, str] = {}   # path → 편집된 변경명
                for row in range(self.rename_table.rowCount()):
                    item = self.rename_table.item(row, 1)
                    if item:
                        p = item.data(Qt.ItemDataRole.UserRole)
                        if p: existing[p] = item.text()
                # 테이블 재구성
                self.rename_table.setRowCount(0)
                for path, orig_name, _ in self._rename_files:
                    new_name = existing.get(path) or self._guess_new_name(path, orig_name)
                    row = self.rename_table.rowCount()
                    self.rename_table.insertRow(row)
                    orig_item = QTableWidgetItem(orig_name)
                    orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    orig_item.setForeground(QColor(C["text3"]))
                    orig_item.setToolTip(path)
                    self.rename_table.setItem(row, 0, orig_item)
                    new_item = QTableWidgetItem(new_name)
                    new_item.setData(Qt.ItemDataRole.UserRole, path)
                    changed = (new_name != orig_name)
                    new_item.setForeground(QColor(C["accent"] if changed else C["text"]))
                    self.rename_table.setItem(row, 1, new_item)
                    self.rename_table.setRowHeight(row, 28)

    def _rename_clear_files(self):
        if not self._rename_files: return
        self._rename_files.clear()
        self.rename_table.setRowCount(0)
        self._rename_refresh_list()

    def _rename_refresh_list(self):
        self.rename_count_lbl.setText(f"{len(self._rename_files)}개")

    def _rename_selected_rows(self):
        rows = sorted({idx.row() for idx in self.rename_table.selectedIndexes()})
        if rows:
            return rows
        cur = self.rename_table.currentRow()
        return [cur] if 0 <= cur < self.rename_table.rowCount() else []

    def _rename_copy_original_name_if_clicked(self, row, col):
        if col != 0:
            return
        item = self.rename_table.item(row, 0)
        if not item:
            return
        self._rename_copy_original_name_item(item)

    def _rename_copy_original_name_item(self, item):
        if not item or item.column() != 0:
            return False
        name = (item.text() or '').strip()
        if not name:
            return False
        QApplication.clipboard().setText(name)
        try:
            self.statusBar().showMessage(f"원본 파일명 복사됨: {name}", 2500)
        except Exception:
            pass
        return True

    def _rename_delete_selected(self):
        if self.rename_table.rowCount() == 0:
            return
        rows = self._rename_selected_rows()
        if not rows:
            return

        paths = set()
        for idx, row in enumerate(rows):
            item = self.rename_table.item(row, 1)
            if item and item.data(Qt.ItemDataRole.UserRole):
                paths.add(item.data(Qt.ItemDataRole.UserRole))

        for row in reversed(rows):
            self.rename_table.removeRow(row)

        if paths:
            self._rename_files = [f for f in self._rename_files if f[0] not in paths]
        self._rename_refresh_list()

    def _rename_open_batch_dialog(self):
        if self.rename_table.rowCount() == 0:
            QMessageBox.information(self, "파일 없음", "먼저 EPUB 파일을 추가해주세요.")
            return

        selected_rows = self._rename_selected_rows()
        dlg = RenameBatchDialog(
            self,
            total_count=self.rename_table.rowCount(),
            selected_count=len(selected_rows),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        cfg = dlg.get_config()
        rows = (selected_rows if cfg["scope"] == "selected" and selected_rows
                else list(range(self.rename_table.rowCount())))
        if not rows:
            return

        from PyQt6.QtGui import QColor

        def _replace_case_insensitive(src: str, needle: str, repl: str) -> str:
            return re.compile(re.escape(needle), re.IGNORECASE).sub(repl, src)

        changed = 0
        skipped_empty = 0
        for idx, row in enumerate(rows):
            orig_item = self.rename_table.item(row, 0)
            new_item = self.rename_table.item(row, 1)
            if not orig_item or not new_item:
                continue

            old_name = (new_item.text() or '').strip()
            if not old_name:
                continue
            stem, ext = self._split_preview_name(old_name)
            mode = cfg["mode"]
            src = cfg["source"]
            dst = cfg["target"]

            append_only = cfg.get("append_episode") and not src.strip()

            if append_only:
                updated_stem = stem
            elif mode == RenameBatchDialog.MODE_REPLACE:
                updated_stem = (
                    stem.replace(src, dst)
                    if cfg["case_sensitive"]
                    else _replace_case_insensitive(stem, src, dst)
                )
            elif mode == RenameBatchDialog.MODE_REMOVE:
                updated_stem = (
                    stem.replace(src, ' ')
                    if cfg["case_sensitive"]
                    else _replace_case_insensitive(stem, src, ' ')
                )
            elif mode == RenameBatchDialog.MODE_PREFIX:
                prefix = src.strip()
                if prefix and stem:
                    spacer = '' if src.endswith(' ') else ' '
                    updated_stem = f'{prefix}{spacer}{stem}'.strip()
                else:
                    updated_stem = prefix or stem
            else:
                updated_stem = src.strip() or stem

            if cfg.get("append_episode"):
                ep_no = cfg.get("append_episode_start", 1) + idx * cfg.get("append_episode_step", 1)
                ep_unit = cfg.get("append_episode_unit", "화")
                updated_stem = re.sub(r'\s*(?:\d+\s*[화권])\s*$', '', updated_stem).strip()
                updated_stem = f"{updated_stem} {ep_no}{ep_unit}".strip()

            updated_name = self._cleanup_rename_preview_name(f'{updated_stem}{ext}')
            if not updated_name:
                skipped_empty += 1
                continue
            if updated_name == old_name:
                continue

            new_item.setText(updated_name)
            new_item.setForeground(QColor(C["accent"] if updated_name != orig_item.text() else C["text"]))
            changed += 1

        ep_changed = 0
        if cfg["post_episode_fix"]:
            ep_changed = self._rename_apply_episode_numbers(target_rows=rows, quiet=True)

        msg = f"일괄 변경 완료: {changed}개"
        if ep_changed:
            msg += f"\n화수 보정 추가 적용: {ep_changed}개"
        if skipped_empty:
            msg += f"\n이름이 비게 되는 {skipped_empty}개는 건너뛰었습니다."
        if not changed and not ep_changed:
            msg = "적용할 변경이 없었습니다."
        QMessageBox.information(self, "완료", msg)

    # ── 이름 추출 ──────────────────────────────────
    def _rename_extract(self):
        if not self._rename_files:
            QMessageBox.warning(self, "파일 없음", "파일을 먼저 추가해주세요.")
            return
        from PyQt6.QtGui import QColor
        # 기존 편집값 백업
        existing: dict[str, str] = {}
        for row in range(self.rename_table.rowCount()):
            item = self.rename_table.item(row, 1)
            if item:
                p = item.data(Qt.ItemDataRole.UserRole)
                if p: existing[p] = item.text()
        self.rename_table.setRowCount(0)

        # 1단계: 파일별 새 이름 생성
        if _core_build_rename_preview_rows:
            try:
                preview_rows = _core_build_rename_preview_rows(
                    self._rename_files,
                    existing_names=existing,
                    guess_name=self._guess_new_name,
                    series_key_func=self._zip_series_key,
                )
                for preview in preview_rows:
                    row = self.rename_table.rowCount()
                    self.rename_table.insertRow(row)
                    orig_item = QTableWidgetItem(preview.original_name)
                    orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    orig_item.setForeground(QColor(C["text3"]))
                    orig_item.setToolTip(preview.path)
                    self.rename_table.setItem(row, 0, orig_item)
                    new_item = QTableWidgetItem(preview.new_name)
                    new_item.setData(Qt.ItemDataRole.UserRole, preview.path)
                    changed = (preview.new_name != preview.original_name)
                    new_item.setForeground(QColor(C["accent"] if changed else C["text"]))
                    self.rename_table.setItem(row, 1, new_item)
                    self.rename_table.setRowHeight(row, 28)
                return
            except Exception:
                pass

        rows: list[tuple[str, str, str]] = []  # (path, orig_name, new_name)
        for path, orig_name, _ in self._rename_files:
            new_name = existing.get(path) or self._guess_new_name(path, orig_name)
            rows.append((path, orig_name, new_name))

        # 2단계: 시리즈 내 제목 표기 통일 (공백 불일치 자동 보정)
        # 같은 시리즈(공백 제거 후 키 동일)끼리 묶어서 가장 많이 쓰인 표기로 통일
        from collections import Counter
        norm_to_rows: dict[str, list[int]] = {}   # 정규화키 → row 인덱스 목록
        for i, (_, _, new_name) in enumerate(rows):
            series_key = self._zip_series_key(new_name)
            norm_key   = re.sub(r'[\s._\-]+', '', series_key).lower()
            norm_to_rows.setdefault(norm_key, []).append(i)

        corrected: list[str] = [r[2] for r in rows]
        for norm_key, idxs in norm_to_rows.items():
            if len(idxs) < 2:
                continue  # 단독 파일은 보정 불필요
            # 각 파일에서 시리즈 키(제목 부분)만 추출
            keys = [self._zip_series_key(rows[i][2]) for i in idxs]
            # 가장 많이 등장하는 표기를 대표명으로 선택 (동수면 긴 쪽 — 더 상세한 표기 우선)
            canonical = Counter(keys).most_common(1)[0][0]
            for i, old_key in zip(idxs, keys):
                if old_key != canonical:
                    # 해당 파일명에서 old_key 부분만 canonical로 교체
                    corrected[i] = corrected[i].replace(old_key, canonical, 1)

        # 2.5단계: 시리즈 내 작가명 통일
        # 같은 시리즈에서 OPF 1권만 짧은 이름(권아)이고 나머지가 풀네임(권아인)인 경우 보정
        for norm_key, idxs in norm_to_rows.items():
            if len(idxs) < 2:
                continue
            authors = []
            for i in idxs:
                am = re.match(r'^\[([^\]]+)\]', corrected[i])
                authors.append(am.group(1) if am else '')
            valid = [a for a in authors if a]
            if not valid or len(set(valid)) <= 1:
                continue
            # 다수결, 동수면 긴 이름 우선 (짧은 이름은 긴 이름의 줄임일 가능성이 높음)
            counts = Counter(valid)
            canonical_author = max(counts, key=lambda a: (counts[a], len(a)))
            for i in idxs:
                am = re.match(r'^\[([^\]]+)\]', corrected[i])
                if am and am.group(1) != canonical_author:
                    corrected[i] = f'[{canonical_author}]' + corrected[i][am.end():]

        # 3단계: 테이블에 결과 삽입
        for (path, orig_name, _), new_name in zip(rows, corrected):
            row = self.rename_table.rowCount()
            self.rename_table.insertRow(row)
            orig_item = QTableWidgetItem(orig_name)
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            orig_item.setForeground(QColor(C["text3"]))
            orig_item.setToolTip(path)
            self.rename_table.setItem(row, 0, orig_item)
            new_item = QTableWidgetItem(new_name)
            new_item.setData(Qt.ItemDataRole.UserRole, path)
            changed = (new_name != orig_name)
            new_item.setForeground(QColor(C["accent"] if changed else C["text"]))
            self.rename_table.setItem(row, 1, new_item)
            self.rename_table.setRowHeight(row, 28)

    @staticmethod
    def _guess_new_name(path: str, orig_name: str) -> str:
        """파일명 파싱 + OPF 교차확인으로 새 파일명 추출.

        로직 (_auto_extract_title 단일파일 버전 + ridi_rename 누락 패치):
        1. 파일명에서 시리즈 기본 제목 추출 (권/화 번호는 별도 보존)
        2. OPF dc:title 정제 후 파일명 단어와 교집합 확인
        3. 작가명/제목 후처리 (장르태그, 부제, 외전괄호, 완결정규화)
        실패 시 원본 파일명 반환.
        """
        # ── 내부 헬퍼 ─────────────────────────────────
        if (
            _core_extract_epub_metadata
            and _core_parse_epub_name
            and _core_format_rename_name
            and _CoreEpubNameMeta
        ):
            try:
                meta = _core_extract_epub_metadata(path)
                parsed = _core_parse_epub_name(
                    path,
                    orig_name,
                    opf_meta=_CoreEpubNameMeta(meta.title, meta.creator),
                    html_headings=list(meta.headings) + list(meta.ncx_labels),
                )
                if parsed.series and (
                    parsed.volume
                    or parsed.part
                    or parsed.episode
                    or parsed.author
                    or parsed.series != Path(orig_name).stem
                ):
                    return _core_format_rename_name(parsed)
            except Exception:
                pass

        def _wrap_gaiden(t: str) -> str:
            """외전/번외 단독(괄호 없이) → (외전)/(외전N권) 로 감싸기"""
            # '특별 (외전)' / '특별외전' → '(특별외전)'
            t = re.sub(r'특별\s*\(외전\)', '(특별외전)', t)
            t = re.sub(r'(?<![\(가-힣])(특별외전)(?![\)가-힣])', r'(\1)', t)
            # '외전N' 붙여쓰기 → '외전 N권' 으로 먼저 정규화 (예: 외전1 → 외전 1권)
            t = re.sub(
                r'(?<![\(가-힣])(외전|번외|특전)(\d+)(?!권)',
                lambda m: f'{m.group(1)} {m.group(2)}권', t)
            # '외전 N권' 패턴 → (외전 N권) 괄호 감싸기
            def _rep_vol(m):
                before = t[:m.start()]
                if before.count('(') > before.count(')'): return m.group(0)
                return f'({m.group(1)} {m.group(2)}권)'
            t = re.sub(r'(?<![\(가-힣])(외전|번외편?)\s+(\d+)권(?![\)가-힣])', _rep_vol, t)
            # 외전 단독 (숫자 없음) — 영문·한글 접두어 포함 (IF외전, AU외전, 특별외전 등)
            def _rep(m):
                before = t[:m.start()]
                if before.count('(') > before.count(')'): return m.group(0)
                return f'({m.group(0)})'
            return re.sub(r'(?<![(\w])([A-Za-z가-힣]*(?:외전\d*|번외편?))(?![\)가-힣\d])', _rep, t)

        def _normalize_complete(t: str) -> str:
            """완결 마커 → 제거 후 플래그, 최종 (완결) 붙이기용"""
            has = bool(re.search(
                r'[\[(（]完[\]）)]|\(완결\)|\(완\)|(?<!\()(?<![가-힣])완결(?![가-힣])(?!\))'
                r'|(?<=[권화부])완결|(?<!\w)完(?!\w)', t))
            t = re.sub(r'[\[(（]完[\]）)]|\(완결\)|\(완\)', '', t)
            t = re.sub(r'(?<!\()(?<!\w)완결(?!\w)(?!\))|(?<=[권화부])완결', '', t)
            t = re.sub(r'(?<!\w)完(?!\w)', '', t)
            return re.sub(r'\s+', ' ', t).strip(), has

        try:
            # macOS NFD(자소분리) 파일명 → NFC(완성형)으로 정규화
            import unicodedata as _ucd
            orig_name = _ucd.normalize('NFC', orig_name)
            orig_name = _strip_filename_parse_noise(orig_name)
            stem = Path(orig_name).stem

            # ── 1. 파일명 기반 기준값 ──────────────────
            base_title = EPUBMergerGUI._base_title_from_filename(orig_name)
            base_title_from_file = base_title   # OPF 교체 전 파일명 기반 제목 (modifier 판별용)
            fname_words = set(re.findall(r'\S{2,}', base_title))
            base_has_korean = bool(re.search(r'[가-힣]', base_title))

            # 해시 접미사 제거 (예: 외전-3f5b084c → 외전, 파일명 중복 방지용 해시)
            stem_clean = re.sub(r'\s*-[0-9a-f]{6,12}\s*$', '', stem, flags=re.IGNORECASE).strip()
            _base_is_numeric_id = bool(re.match(r'^[\d_\s-]+$', stem_clean))
            _filename_volume_part = False

            # 권/화/부 번호 suffix 추출
            vol_suffix = ''
            # N부N권 복합 패턴 먼저 시도 (예: 1부1권, 1부_1권)
            vm = re.search(r'((?:(?<![가-힣])제)?[_\s]*\d+[_\s]*부[_\s]*\d+[_\s]*권)', stem_clean)
            if vm:
                vol_suffix = re.sub(r'[_\s]+', '', vm.group(1))
                vol_suffix = re.sub(r'(\d+부)(\d+권)', r'\1 \2', vol_suffix)  # 1부 1권 공백 유지
            else:
                # 외전 N권 패턴 먼저 체크 (외전이 숫자 앞에 오는 경우: 외전 1권, 특별외전 2권)
                vm_ext = re.search(r'([A-Za-z가-힣]*(?:외전|번외편?|특전)\s*\d+\s*권?)', stem_clean)
                if vm_ext:
                    _vx = re.sub(r'\s+', ' ', vm_ext.group(1)).strip()
                    if not re.search(r'권$', _vx):
                        _vx = re.sub(r'(\d+)\s*$', r'\1권', _vx)
                    vol_suffix = _vx
                    # 외전 N 뒤에 "- 부제" 패턴이 있으면 보존 (예: 외전 2 - 미래편)
                    _after_ext = stem_clean[vm_ext.end():]
                    _dash_sub = re.match(r'\s*[-–―]\s*([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s]{0,20})', _after_ext)
                    if _dash_sub:
                        vol_suffix += ' - ' + _dash_sub.group(1).strip()
                else:
                    # 권·화 우선 탐색 — "N부 ― 부제" 형 시리즈명에서 N부를 오인하지 않도록
                    vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화](?:[._\s]*(?:외전|번외|특전))?)', stem_clean)
                    if not vm:
                        # 부(部): 뒤에 _/공백+한글이 이어지면 시리즈 구분자이므로 건너뜀
                        vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부(?:[._\s]*(?:외전|번외|특전))?)(?![_\s]*[가-힣])', stem_clean)
                    if vm:
                        vol_suffix = re.sub(r'\s+', '', vm.group(1))
                        # N권.외전 / N권_외전 처럼 점·언더스코어로 연결된 경우 → N권외전 → 공백 삽입
                        vol_suffix = re.sub(r'[._]+', '', vol_suffix)
                        # N부외전 / N권외전 붙여쓰기 → N부 외전 / N권 외전 (공백 삽입)
                        vol_suffix = re.sub(r'(\d+[부권화])(외전|번외|특전)', r'\1 \2', vol_suffix)
                        # N권 - M 분권 파일명은 그대로 보존한다.
                        _after_vol = stem_clean[vm.end():]
                        _part_m = re.match(r'\s*[-–—]\s*(\d{1,4})\s*$', _after_vol)
                        if _part_m and re.search(r'권$', vol_suffix):
                            vol_suffix = f"{vol_suffix} - {int(_part_m.group(1))}"
                            _filename_volume_part = True
                        # 권 suffix인 경우 뒤에 화 번호도 있으면 함께 포함 (예: "1권 2화")
                        if re.search(r'^\d+\s*권$', vol_suffix):
                            _ep_m = re.search(r'\d+\s*권\D*?(\d+)\s*화', stem_clean)
                            if _ep_m:
                                vol_suffix = vol_suffix + ' ' + _ep_m.group(1) + '화'
            # N권/화/부 단독 vol_suffix인데 괄호 외전이 따로 붙어있는 경우 합치기
            # 예: "1부 (외전)" → vol_suffix: "1부" + "(외전)" → "1부 외전"
            if vol_suffix and not re.search(r'외전|번외|특전', vol_suffix):
                _trail_g = re.search(r'[\(（](외전|번외편?|특전)[\)）]', stem_clean)
                if _trail_g:
                    vol_suffix = f'{vol_suffix} {_trail_g.group(1)}'
                else:
                    # "(modifier 외전 N)" 패턴 — 수식어+외전+번호가 괄호 안에 있는 경우
                    # 기존 N권보다 가이덴 서술자를 우선 (예: "용의 표식(특별 외전 2) 1권" → 특별 외전 2권)
                    _mod_trail = re.search(
                        r'[\(（]([가-힣A-Za-z]+\s+(?:외전|번외편?|특전)(?:\s*\d+)?)[\)）]',
                        stem_clean)
                    if _mod_trail:
                        _mt = _mod_trail.group(1).strip()
                        _mt = re.sub(
                            r'(\s+)(\d+)$',
                            lambda _m: f'{_m.group(1)}{_m.group(2)}권', _mt)
                        vol_suffix = _mt
            if not vol_suffix and re.search(r'외전|번외|특전', stem_clean):
                # 끝에 위치한 외전 계열 추출 (영문·한글 접두어 포함: IF외전, 특별외전, AU외전 등)
                # "(외전)" 처럼 괄호로 감싸인 경우, "(외전) (완결)" 처럼 뒤에 추가 괄호가 있는 경우도 캡처
                # ① 숫자(외전) 패턴 — e.g., "시리즈 7(외전)", "7(번외)"
                _dpg = re.search(
                    r'(?:^|[_\s])(\d+)\s*[\(（]([A-Za-z가-힣]*(?:외전|번외편?|특전)\d*)[\)）](?!\w)',
                    stem_clean)
                if _dpg:
                    vol_suffix = f'{_dpg.group(2)} {_dpg.group(1)}권'
                else:
                    # ② N부 외전 패턴 — "(1부 외전)", "1부_외전" 등
                    _bu_g = re.search(
                        r'(?:^|[_\s\(（])(\d+\s*부\s*(?:외전|번외|특전))(?:[_\s\)）]|$)',
                        stem_clean)
                    if _bu_g:
                        vol_suffix = re.sub(r'\s+', ' ', _bu_g.group(1)).strip()
                    else:
                        # ③ 괄호 안 공백구분 수식어 외전 — "(특별 외전)", "(특별 외전 2)" 등 (끝 숫자 포함)
                        _mod_g = re.search(
                            r'[(\[（]([가-힣A-Za-z]+\s+(?:외전|번외편?|특전)(?:\s*\d+)?)[)\]）]',
                            stem_clean)
                        if _mod_g:
                            _mg_val = _mod_g.group(1).strip()
                            # 끝 숫자에 권 추가: "특별 외전 2" → "특별 외전 2권"
                            _mg_val = re.sub(
                                r'(\s+)(\d+)$',
                                lambda _m: f'{_m.group(1)}{_m.group(2)}권', _mg_val)
                            vol_suffix = _mg_val
                        else:
                            # ③.5 수식어(괄호 외부) + (외전) 패턴: "특별 (외전)", "스폐셜 (외전)" 등
                            _GAIDEN_MODS = {'특별', '스폐셜', '스페셜', '스폐설', '스페설', '추가', '별책', '보너스', '단편', 'AU', 'IF'}
                            _ext_mg = re.search(
                                r'([A-Za-z가-힣]+)\s+[\(（]((?:외전|번외편?|특전)\d*)[\)）](?!\w)',
                                stem_clean)
                            if _ext_mg and _ext_mg.group(1) in _GAIDEN_MODS:
                                vol_suffix = f'{_ext_mg.group(1)} {_ext_mg.group(2)}'
                            else:
                                # ④ underscore 구분자 파일도 처리: _를 공백으로 바꾼 버전 병행 시도
                                # 대괄호 [외전] 도 인식 — [\(（\[] / [\)）\]]
                                _stem_spaced = stem_clean.replace('_', ' ')
                                em = re.search(
                                    r'(?:^|\s)[(\[（]?([A-Za-z가-힣]*(?:외전|번외편?|특전)\d*)[)\]）]?'
                                    r'(?:\s*(?:[\(\[（【][^\)\]）】]*[\)\]）】]))*'
                                    r'(?:\s+(?:완결|완|完)(?![가-힣]))?\s*$',
                                    _stem_spaced.strip())
                                if em: vol_suffix = em.group(1)

            # 합본 감지: 파일명에 합본이 있으면 vol_suffix를 합본으로 고정 (OPF 권수 무시)
            is_hapbon = bool(re.search(r'합본', stem_clean))
            if is_hapbon:
                vol_suffix = '합본'

            # 판형 suffix 감지: 개정판, 증보판, 완전판, 외전증보판, 19세 완전판 등
            _ED_PAT_STEM = r'(?:\d+세\s*)?(?:개정증보판|증보판|개정판|완전판|외전증보판)'
            _ed_m_stem = re.search(_ED_PAT_STEM, stem_clean)
            edition_suffix_stem = re.sub(r'\s+', ' ', _ed_m_stem.group(0)).strip() if _ed_m_stem else ''
            # 인터뷰/작가노트 suffix 감지
            _IV_PAT_STEM = r'(?:인터뷰집|인터뷰|작가노트)'
            _iv_m_stem = re.search(_IV_PAT_STEM, stem_clean)
            interview_type_stem = _iv_m_stem.group(0) if _iv_m_stem else ''

            # 완결 마커 (파일명 기준) — 단독 '완'도 완결 축약어로 인식, 한자 完, N권완결 붙여쓰기도 감지
            is_complete = bool(re.search(
                r'[\[(（]完[\]）)]|\(완결\)|\(완\)|\(본편\s*완결\)|(?<!\w)완결(?!\w)'
                r'|[_\s]완결[_\s]|[_\s]완결$'              # 끝 위치 _완결 추가
                r'|[_\s]완\s*[\(\s]|[_\s]완\s*$'
                r'|(?<=[권화부])완결|(?<=[권화부])완\s*[\(\s]'
                r'|(?:외전|번외)완결'                        # 외전완결, 번외완결 추가
                r'|完\s*$|[_\s]完(?!\w)', stem_clean))

            # 화/권 없는 끝 숫자 추출 (예: 665598_31 → 31)
            _tail_num = ""
            if not vol_suffix:
                # 완결/완 앞 숫자도 잡기 (예: 시리즈_4__완결_)
                _tn = re.search(r'[_\s](\d+)\s*[\(（]?\s*(?:완결|완)\s*[\)）]?\s*$', stem)
                if not _tn:
                    _tn = re.search(r'[_\s](\d+)\s*$', stem)
                if _tn: _tail_num = _tn.group(1)

            # ── 2. OPF 교차확인 ───────────────────────
            creator = ''
            def _clean_opf_title(raw: str) -> str:
                return _clean_opf_series_title(raw, strip_genre_tag=True)

            _hash_subtitle = ''   # #N 소제목 (numeric ID 파일명 전용)
            import zipfile as _zf
            with _zf.ZipFile(path, 'r') as z:
                container = z.read('META-INF/container.xml').decode('utf-8', 'replace')
                m = re.search(r'full-path="([^"]+\.opf)"', container)
                if m:
                    opf = _decode_markup_bytes(z.read(m.group(1)))
                    raw_creator = _read_dc_tag(opf, 'dc:creator').strip()
                    raw_title   = _read_dc_tag(opf, 'dc:title').strip()
                    # creator는 title 유효성 무관하게 항상 추출
                    if raw_creator:
                        _c = _normalize_title(raw_creator)
                        _c = re.sub(r'\s+(?:표지|디자인|삽화|일러스트|번역|편집|감수|펴낸이).*$', '', _c, flags=re.IGNORECASE).strip()
                        _c = re.sub(r',\s*(?:표지|디자인).*$', '', _c, flags=re.IGNORECASE).strip()
                        if _c: creator = _c

                    # OPF dc:creator 없으면 dc:title 앞 [작가명] 접두어 추출 시도
                    # 예: "[시오노나나미]로마인 이야기 06" → creator = "시오노나나미"
                    if not creator and raw_title:
                        _title_author_m = re.match(r'^\s*\[([^\]]{2,20})\]', raw_title.strip())
                        if _title_author_m:
                            _tc = _normalize_title(_title_author_m.group(1)).strip()
                            # 장르태그(BL, GL 등), 숫자만, 연령제한 등은 제외
                            if _tc and not re.match(
                                    r'^(?:BL|GL|NL|TL|SF|성인|19금|R-18|\d+세?|완결|합본)$',
                                    _tc, re.IGNORECASE) and not re.search(
                                    r'(?i)title\s*here|insert\s*title|untitled|제목을?\s*넣으세요|제목없음',
                                    _tc):
                                creator = _tc

                    # OPF에 dc:creator 없으면 판권 페이지 xhtml에서 글쓴이/지은이/저자 추출 시도
                    if not creator:
                        _copy_patterns = re.compile(
                            r'(?:글쓴이|지은이|저자|저\s*자|글\s*\|\s*|글\s*/\s*|원\s*작|지\s*음)'
                            r'(?![가-힣])'
                            r'\s*(?:[：:|｜§\s]|&nbsp;|&#160;){0,8}\s*'
                            r'([가-힣]{2,8}|[A-Za-z][A-Za-z.\-]{0,15}(?:\s[A-Za-z][A-Za-z.\-]{0,15}){0,2})',
                            re.IGNORECASE)
                        # 판권 페이지일 가능성이 높은 파일 먼저 (copy/판권/colophon/info 이름 포함)
                        _all_xhtml = [n for n in z.namelist()
                                      if n.lower().endswith(('.xhtml', '.html', '.htm'))]
                        _copy_first = sorted(
                            _all_xhtml,
                            key=lambda n: 0 if re.search(r'copy|판권|colophon|rights?|imprint|info|endpg|end[_\-]?p(?:g|age)', n, re.IGNORECASE) else 1)
                        for _xn in _copy_first[:10]:   # 최대 10개만 확인
                            try:
                                _xhtml = z.read(_xn).decode('utf-8', 'replace')
                                _xt = re.sub(r'<[^>]+>', ' ', _xhtml)
                                _xt = re.sub(r'&nbsp;|&#160;', ' ', _xt)
                                _xt = re.sub(r'\s+', ' ', _xt).strip()
                                _am = _copy_patterns.search(_xt)
                                if _am:
                                    _ac = _am.group(1).strip()
                                    # 일반 단어(소설은, 글쓴이 등) 제외
                                    if _ac and not re.search(r'소설|글쓴|지은|저자|원작|작가|이야기', _ac):
                                        creator = _ac
                                        break
                            except Exception:
                                continue

                    # 파일명에서 권수 못 뽑았으면 OPF 제목에서 먼저 추출 (합본 파일은 스킵)
                    if not vol_suffix and raw_title and not is_hapbon:
                        # 권·화 우선 — "N부 ― 부제명" 형 시리즈에서 N부를 오인하지 않도록
                        _opf_vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화])', raw_title)
                        if not _opf_vm:
                            # 부(部): 뒤에 공백+dash 또는 한글이 이어지면 시리즈명 구성요소 → 스킵
                            _opf_vm = re.search(
                                r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부)(?!\s*[-–—―]|\s*[가-힣])',
                                raw_title)
                        if _opf_vm:
                            vol_suffix = re.sub(r'\s+', '', _opf_vm.group(1))
                        else:
                            # dc:title 끝 숫자 폴백: "풍신쾌 1" 같은 형태도 권/화로 승격
                            _opf_tail = re.search(r'(?:^|[\s._-])(\d{1,4})\s*$', raw_title.strip())
                            if _opf_tail:
                                try:
                                    _tn_int = int(_opf_tail.group(1))
                                    # 화/권 단위가 명시되지 않은 끝 숫자는 숫자만 유지
                                    vol_suffix = str(_tn_int)
                                except Exception:
                                    pass
                    cleaned_t   = _clean_opf_title(raw_title)
                    if _filename_volume_part and base_title:
                        # OPF title이 "쾌도무적 1-3"처럼 분권 번호를 제목 뒤에 붙이면
                        # 정제 후 "쾌도무적 1"이 되어 파일명 구조를 망가뜨리므로 파일명 제목을 우선한다.
                        cleaned_t = base_title
                    if vol_suffix:
                        # vol_suffix를 따로 붙일 것이므로 제목 끝 숫자는 제거해 중복 방지
                        cleaned_t = re.sub(r'(?:^|[\s._-])\d{1,4}\s*$', '', cleaned_t).strip()
                    _title_is_chap = _is_chapterish_title(raw_title)
                    # OPF title이 플레이스홀더면 무시
                    # "[Title here]" 계열도 포함 (Sigil 기본값 등) — cleaned_t와 raw_title 양쪽 체크
                    _PH_PAT = re.compile(
                        r'^제목을\s*넣으세요|^insert\s*title|^untitled|^제목없음|^title\s*here$'
                        r'|\[title\s*here\]', re.IGNORECASE)
                    if _PH_PAT.search(cleaned_t) or _PH_PAT.search(raw_title):
                        cleaned_t = ''
                    # dc:title이 화수 제목인 경우(정제 후 너무 짧음): NCX navLabel / h2 title 속성에서 시리즈명 추출
                    # 예) dc:title="0화 서(序)" → 정제 후 "서" (1글자) → NCX에서 실제 시리즈명 추출
                    _opf_dir_z = str(Path(m.group(1)).parent)
                    if _base_is_numeric_id:
                        _series_heading = _find_series_volume_heading_in_zip(z, opf, _opf_dir_z, max_files=6)
                        if _series_heading:
                            _hv = re.search(r'(\d{1,4})\s*권\s*$', _series_heading)
                            if _hv:
                                vol_suffix = f"{int(_hv.group(1))}권"
                            cleaned_t = _clean_opf_title(_series_heading)
                            _title_is_chap = False
                    if not cleaned_t or len(re.findall(r'[가-힣]{2,}', cleaned_t)) == 0:
                        # ① NCX navLabel 시도
                        try:
                            _ncx_href_rn = re.search(
                                r'<item\s[^>]*media-type=["\']application/x-dtbncx\+xml["\'][^>]*href=["\']([^"\']+)["\']'
                                r'|<item\s[^>]*href=["\']([^"\']*toc\.ncx)["\']',
                                opf, re.IGNORECASE)
                            if _ncx_href_rn:
                                _nv_rn = _ncx_href_rn.group(1) or _ncx_href_rn.group(2)
                                _nf_rn = (_opf_dir_z + '/' + _nv_rn).lstrip('./') if _opf_dir_z != '.' else _nv_rn
                                if _nf_rn not in z.namelist(): _nf_rn = _nv_rn
                                _ncx_rn = z.read(_nf_rn).decode('utf-8', 'replace')
                                import html as _html_rn
                                for _nlm in re.finditer(
                                        r'<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>',
                                        _ncx_rn, re.IGNORECASE | re.DOTALL):
                                    _lbl_rn = _html_rn.unescape(re.sub(r'\s+', ' ', _nlm.group(1))).strip()
                                    _lbl_rn = re.sub(r'\s*\(연재중?\)\s*', '', _lbl_rn).strip()
                                    if (not re.search(r'\d+\s*[화권부]|[#＃]\s*\d+', _lbl_rn)
                                            and len(re.findall(r'[가-힣]+', _lbl_rn)) >= 2
                                            and len(_lbl_rn) >= 6):
                                        cleaned_t = _lbl_rn
                                        break
                        except Exception:
                            pass
                        # ② h2~h3 title 속성 시도
                        if not cleaned_t or len(re.findall(r'[가-힣]{2,}', cleaned_t)) == 0:
                            try:
                                _sp_ids_rn = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf)
                                _mf_rn = {}
                                for _mm_rn in re.finditer(r'<item\s([^>]*?)/?>', opf, re.IGNORECASE):
                                    _mid_rn = re.search(r'\bid=["\']([^"\']+)["\']', _mm_rn.group(1))
                                    _mh_rn  = re.search(r'\bhref=["\']([^"\']+)["\']', _mm_rn.group(1))
                                    if _mid_rn and _mh_rn: _mf_rn[_mid_rn.group(1)] = _mh_rn.group(1)
                                for _sid_rn in _sp_ids_rn[:3]:
                                    _sh_rn = _mf_rn.get(_sid_rn, '')
                                    if not _sh_rn: continue
                                    _sf_rn = (_opf_dir_z + '/' + _sh_rn).lstrip('./') if _opf_dir_z != '.' else _sh_rn
                                    if _sf_rn not in z.namelist(): _sf_rn = _sh_rn
                                    _sr_rn = z.read(_sf_rn).decode('utf-8', 'replace')
                                    _ta_rn = re.search(
                                        r'<h[1-6][^>]+\btitle=["\']([^"\']{6,})["\']', _sr_rn, re.IGNORECASE)
                                    if _ta_rn:
                                        _tv_rn = _ta_rn.group(1).strip()
                                        _tv_rn = re.sub(r'\s*\(연재중?\)\s*', '', _tv_rn).strip()
                                        if len(re.findall(r'[가-힣]+', _tv_rn)) >= 2:
                                            cleaned_t = _tv_rn
                                            break
                            except Exception:
                                pass
                    # OPF 플레이스홀더인 경우 판권 페이지 h4/h3/h2에서 제목 추출 시도
                    if not cleaned_t:
                        _all_xhtml_t = [n for n in z.namelist()
                                        if n.lower().endswith(('.xhtml', '.html', '.htm'))]
                        # 판권 페이지 우선 (파일명 패턴), 없으면 마지막 파일부터 역순 탐색
                        _copy_pri = sorted(
                            _all_xhtml_t,
                            key=lambda n: (
                                0 if re.search(r'copy|판권|colophon|rights?|imprint|endpg|end[_\-]?p(?:g|age)', n, re.IGNORECASE) else
                                1 if n == _all_xhtml_t[-1] else 2))
                        for _tn in _copy_pri[:5]:
                            try:
                                _tx = z.read(_tn).decode('utf-8', 'replace')
                                # ── (NEW) class="title*" p 태그에서 제목 추출 ──
                                # 예) endpg.xhtml: <p class="titleE">서울역 바바리안 (연재)</p>
                                _ptm = re.search(
                                    r'<p[^>]*\bclass=["\'][^"\']*[Tt]itle[^"\']*["\'][^>]*>(.*?)</p>',
                                    _tx, re.IGNORECASE | re.DOTALL)
                                # 첫 매치가 br/공백뿐이면 다음 후보 찾기
                                _ptms_iter = re.finditer(
                                    r'<p[^>]*\bclass=["\'][^"\']*[Tt]itle[^"\']*["\'][^>]*>(.*?)</p>',
                                    _tx, re.IGNORECASE | re.DOTALL)
                                for _ptm_i in _ptms_iter:
                                    _pin = re.sub(r'<br\s*/?>', ' ', _ptm_i.group(1), flags=re.IGNORECASE)
                                    _pin = re.sub(r'<[^>]+>', '', _pin).strip()
                                    _pin = re.sub(r'\s+', ' ', _pin).strip()
                                    # 끝의 '(연재)/(완결)' 등 상태 표기 제거
                                    _pin = re.sub(
                                        r'\s*[\(（]\s*(?:연재(?:중)?|완결|完|개정판)\s*[\)）]\s*$',
                                        '', _pin).strip()
                                    if (_pin and re.search(r'[가-힣]{2,}', _pin)
                                            and 2 < len(_pin) < 60
                                            and not re.search(r'^(?:목차|작가의\s*말|프롤로그|에필로그|머리말|서문|차례)', _pin)):
                                        cleaned_t = _clean_opf_title(_pin)
                                        _title_is_chap = _is_chapterish_title(_pin)
                                        break
                                if cleaned_t:
                                    break
                                # h4/h3/h2/h1 태그에서 제목 후보 추출
                                _hm = re.search(
                                    r'<h[1-4][^>]*>\s*(?:&nbsp;|\s)*'
                                    r'[\[\[【]?\s*([가-힣A-Za-z0-9][^<\]\]】]{2,60}?)\s*[\]\]】]?\s*</h[1-4]>',
                                    _tx, re.IGNORECASE)
                                if _hm:
                                    _ht = _hm.group(1).strip()
                                    # 판권 상투어("목차", "작가의 말" 등)는 제외
                                    if _ht and not re.search(
                                            r'^(?:목차|작가의\s*말|프롤로그|에필로그|머리말|서문|차례)', _ht):
                                        cleaned_t = _clean_opf_title(_ht)
                                        break
                                # block_4 / font6+t-num2 판권 제목 패턴 추출
                                if not cleaned_t:
                                    _bt = _extract_title_from_html(_tx)
                                    if _bt:
                                        cleaned_t = _clean_opf_title(_bt)
                                        break
                            except Exception:
                                continue
                    opf_words   = set(re.findall(r'\S{2,}', cleaned_t))
                    # 공백 없는 파일명 vs 공백 있는 OPF 비교 (달을사랑한괴물 케이스)
                    _opf_nospace = re.sub(r'\s+', '', cleaned_t)
                    _base_nospace = re.sub(r'\s+', '', base_title)
                    _title_match = bool(fname_words & opf_words) or \
                        (_opf_nospace and _base_nospace and
                         (_opf_nospace in _base_nospace or _base_nospace in _opf_nospace))
                    # 영문 파일명은 `not base_has_korean` 단독으로 OPF 덮어쓰지 않음
                    # (e.g., "The Vow(서약) 1권" → "The Vow" 보존)
                    # ：(전각 콜론) 구분 부제 보호: "A ： B" 형태 파일명에서 OPF가 일부(B)만
                    # 커버할 때 파일명 우선 유지 (예: "안젤리카 ： 우리 아내가 달라졌어요")
                    _allow_opf_replace = True
                    if ('：' in base_title_from_file or '？' in base_title_from_file) and cleaned_t:
                        _ct_ns = re.sub(r'\s+', '', cleaned_t)
                        if _ct_ns and _ct_ns in _base_nospace and _ct_ns != _base_nospace:
                            _allow_opf_replace = False  # OPF가 파일명의 일부분 → 파일명 우선
                        else:
                            # OPF가 전각기호(：/？)를 ASCII 기호도 없이 생략했으면 파일명 우선
                            for _fw_chk, _asc_chk in [('：', ':'), ('？', '?')]:
                                if (_fw_chk in base_title_from_file
                                        and _fw_chk not in cleaned_t
                                        and _asc_chk not in cleaned_t):
                                    _allow_opf_replace = False
                                    break
                    # 박스 드로잉·블록 문자 포함 → 인코딩 깨진 파일명 → OPF 무조건 우선
                    # (EUC-KR 바이트를 CP437로 읽으면 U+2500~U+259F 계열 문자로 깨짐)
                    _fname_garbled = bool(re.search(r'[\u2500-\u259F\u25A0-\u25FF\u2300-\u23FF]', base_title))
                    # 숫자/ID형 파일명 감지: stem이 숫자·언더스코어·하이픈만으로 구성
                    # 예) 690935_2, 667336_6, 123456 → OPF 제목을 무조건 신뢰
                    _opf_is_hash_chap   = bool(raw_title and re.match(r'^[#＃]\s*\d+', raw_title.strip()))
                    if _base_is_numeric_id and _opf_is_hash_chap and cleaned_t:
                        # OPF가 "#N 소제목" 형식: numeric ID는 유지, 소제목만 따로 보존
                        _hash_subtitle = cleaned_t
                    elif _base_is_numeric_id and _title_is_chap:
                        # numeric-id + 챕터성 제목(OPF/판권)은 기본적으로 시리즈명으로 쓰지 않음
                        # 단, 정제 후 한글 2단어 이상이면 실질적 시리즈명으로 인정 (예: "다 해먹는 슈퍼스타 110화" → "다 해먹는 슈퍼스타")
                        if cleaned_t and len(re.findall(r'[가-힣]{2,}', cleaned_t)) >= 2:
                            base_title = cleaned_t
                    elif _allow_opf_replace and cleaned_t and (
                            not fname_words or _title_match or _fname_garbled or _base_is_numeric_id):
                        base_title = cleaned_t
                    # numeric ID + 제목 없음: 첫 본문 xhtml에서 #N 소제목 추출 시도
                    if _base_is_numeric_id and not _hash_subtitle and not cleaned_t:
                        try:
                            _sp_ids_nc = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf)
                            _mf_nc: dict = {}
                            for _mm_nc in re.finditer(r'<item\s([^>]*?)/?>', opf, re.IGNORECASE):
                                _mid_nc = re.search(r'\bid=["\']([^"\']+)["\']', _mm_nc.group(1))
                                _mh_nc  = re.search(r'\bhref=["\']([^"\']+)["\']', _mm_nc.group(1))
                                if _mid_nc and _mh_nc:
                                    _mf_nc[_mid_nc.group(1)] = _mh_nc.group(1)
                            for _sid_nc in _sp_ids_nc[:3]:
                                _sh_nc = _mf_nc.get(_sid_nc, '')
                                if not _sh_nc: continue
                                _sf_nc = (_opf_dir_z + '/' + _sh_nc).lstrip('./') if _opf_dir_z != '.' else _sh_nc
                                if _sf_nc not in z.namelist(): _sf_nc = _sh_nc
                                _ht_nc = extract_chapter_title(z.read(_sf_nc))
                                if _ht_nc and re.match(r'^[#＃]\s*\d+', _ht_nc):
                                    _sub_nc = re.sub(r'^[#＃]\s*\d+\s*', '', _ht_nc).strip()
                                    if _sub_nc:
                                        _hash_subtitle = _sub_nc
                                        break
                        except Exception:
                            pass
                    # numeric-id인데 제목이 숫자/챕터성으로만 판별되면 부모 폴더명에서 시리즈명 보정
                    if _base_is_numeric_id:
                        _base_numeric_like = bool(re.fullmatch(r'[\d\s._-]+', base_title or ''))
                        if (_base_numeric_like or _title_is_chap) and not _is_series_volume_heading(f"{base_title} {vol_suffix}".strip()):
                            _parent_series = _series_from_parent_dir(path)
                            if _parent_series:
                                base_title = _parent_series

            # ── 2b. OPF 후처리: full-width 기호 복원 / 파일명 괄호 부제 복원 ──────────
            # (A) OPF가 full-width 기호를 ASCII로 대체한 경우 파일명 버전의 기호를 복원
            #     예: OPF에 '구원이 필요하신가요?' (ASCII) → 파일명엔 '구원이 필요하신가요？' (full-width)
            for _fw_ch, _asc in [('？', '?'), ('：', ':'), ('＂', '"'),
                                   ('｜', '|'), ('＊', '*'), ('＜', '<'),
                                   ('＞', '>'), ('／', '/'), ('＼', '\\')]:
                if _fw_ch in base_title_from_file and _asc in base_title:
                    base_title = base_title.replace(_asc, _fw_ch)
            # (B) 파일명에 있던 의미있는 괄호 부제를 복원
            #     _base_title_from_filename과 _clean_opf_title 모두 괄호 블록을 제거하므로 직접 복원
            #     예: "The Vow(서약)" → "(서약)" 추가, "고스트 헌터(GHOST HUNTER)" → "(GHOST HUNTER)" 추가
            _PAREN_NOISE = re.compile(
                r'^(?:완결|완|합본|BL|GL|NL|TL|SF|성인|19금|R-18'
                r'|완전판|개정판|증보판|개정증보판|외전증보판'
                r'|\d+세|\d+권?|[A-Z]{1,2}'
                r'|[+＋][가-힣A-Za-z].*'                    # +외전, +번외 등 "포함" 표기
                r'|본편\s*완결)$', re.IGNORECASE)            # 본편 완결 → 완결 마커이므로 부제 제외
            # 파일명 깨진 경우 OPF 원본 제목의 괄호도 부제 후보에 포함
            _paren_src = stem_clean
            if _fname_garbled and raw_title:
                _paren_src = stem_clean + ' ' + raw_title
            _paren_hits = re.findall(r'[\(（]([^\)）]{2,40})[\)）]', _paren_src)
            _paren_hits = list(dict.fromkeys(_paren_hits))  # 중복 제거 (순서 유지)
            for _ps in _paren_hits:
                _ps = _ps.strip()
                if not _ps:
                    continue
                # 잡음 패턴 (완결·합본·장르태그·연령등급·단독 알파벳 1~2자 등) 제거
                if _PAREN_NOISE.match(_ps):
                    continue
                # 작가명이 괄호 안에 있는 경우 제외 (creator에 포함되어 있으면 부제가 아님)
                if creator and _ps in creator:
                    continue
                # 판형 suffix (개정판·증보판·완전판 등)는 edition_suffix_stem으로 별도 처리
                if re.match(_ED_PAT_STEM, _ps):
                    continue
                # 인터뷰·작가노트도 별도 처리
                if re.match(r'(?:인터뷰집|인터뷰|작가노트)', _ps):
                    continue
                # 이미 base_title에 포함된 경우 중복 방지
                if _ps in base_title:
                    continue
                # vol_suffix와 내용이 동일/포함 관계인 괄호 콘텐츠 → vol_suffix가 처리하므로 skip
                # 예: "(외전)" + vol_suffix="1부 외전", "(1부 외전)" + vol_suffix="1부 외전"
                _ps_norm = re.sub(r'\s+', '', _ps)
                _vol_norm = re.sub(r'\s+', '', vol_suffix)
                if _ps_norm and _vol_norm and (_ps_norm == _vol_norm
                        or _ps_norm in _vol_norm or _vol_norm in _ps_norm):
                    continue
                # 유효한 부제: base_title 뒤에 괄호로 추가
                base_title = base_title.rstrip() + f' ({_ps})'

            # 권/화/부 앞자리 0 제거: 01권→1권, 002화→2화 (10 이상은 유지)
            vol_suffix = re.sub(
                r'\b0+(\d+)([권화부])',
                lambda m: m.group(1) + m.group(2), vol_suffix)

            # ── 3. 조합 ────────────────────────────────
            # OPF 제목에 화수 없고 파일명 끝 숫자 있으면 화수로 붙이기
            if not vol_suffix and _tail_num:
                if not re.search(r'\d+\s*[권화부]', base_title):
                    _tn_int = int(_tail_num)
                    # 화/권 단위가 없으면 숫자만 사용 (예: 001.epub -> ... 1)
                    vol_suffix = str(_tn_int)
            # #N 소제목 추가: vol_suffix 뒤에 붙임 (예: "101" + "전쟁의 결과" → "101 전쟁의 결과")
            if _hash_subtitle:
                vol_suffix = (vol_suffix + ' ' + _hash_subtitle).strip() if vol_suffix else _hash_subtitle
            # OPF 원본 제목에 수식어+외전 패턴 있으면 vol_suffix 업그레이드 (추가 외전, 특별 외전 등)
            # 사용자가 명시한 수식어 목록만 허용 (부단장님·악녀 등 제목 단어가 오인식되는 것 방지)
            _KNOWN_GAIDEN_MODS = {'추가', '특별', '스페셜', '스폐셜', '스페설', '스폐설', '단편', '별책', '보너스'}
            if vol_suffix and re.search(r'(?:외전|번외|특전)', vol_suffix) and raw_title:
                _compound_m = re.search(
                    r'([가-힣A-Za-z]{2,6})\s+' + re.escape(vol_suffix) + r'\s*$', raw_title)
                if _compound_m:
                    _mod = _compound_m.group(1)
                    # 수식어가 명시 목록에 있고, 파일명 기반 제목에 포함되지 않은 경우만 업그레이드
                    if _mod in _KNOWN_GAIDEN_MODS and _mod not in base_title_from_file:
                        _base_without_mod = re.sub(r'\s+' + re.escape(_mod) + r'\s*$', '', base_title).strip()
                        if _base_without_mod and len(_base_without_mod) >= 4:
                            vol_suffix = f'{_mod} {vol_suffix}'
                            base_title = _base_without_mod
            # vol_suffix가 이미 base_title에 포함된 경우 중복 방지
            if vol_suffix and re.search(re.escape(vol_suffix), base_title):
                if re.search(r'(?:외전|번외|특전)', vol_suffix):
                    # 외전 계열 vol_suffix는 base_title에서 제거하고 vol_suffix 유지
                    # (OPF가 수식어+외전을 제목에 포함한 경우 → base_title에서 떼어내 괄호로 붙임)
                    base_title = re.sub(r'\s+' + re.escape(vol_suffix) + r'\s*$', '', base_title).strip()
                else:
                    vol_suffix = ''
            # 제목 끝에 한글 뒤 바로 붙은 권수 숫자 제거 (예: 막내온탑3 → 막내온탑)
            if vol_suffix:
                _vn = re.search(r'\d+', vol_suffix)
                if _vn:
                    base_title = re.sub(r'(?<=[가-힣])' + re.escape(_vn.group()) + r'\s*$', '', base_title).strip()
            title_part = base_title
            # 판형 suffix (개정판·증보판·완전판 등)를 권수 앞에 — e.g., "제목 (개정판) 3권"
            if not re.search(r'개정증보판|증보판|개정판|완전판|외전증보판', title_part):
                if edition_suffix_stem:
                    title_part = title_part.rstrip() + f' ({edition_suffix_stem})'
            # 인터뷰/작가노트 suffix — 권수 앞
            if not re.search(r'인터뷰집|인터뷰|작가노트', title_part):
                if interview_type_stem:
                    title_part = title_part.rstrip() + f' ({interview_type_stem})'
            # 그 다음 권수 붙이기
            if vol_suffix:
                # 중복 방지: vol_suffix 핵심어가 이미 title_part에 있으면 건너뜀
                # 예: OPF 타이틀에 "특별외전" 있는데 vol_suffix도 "특별 외전"
                _vs_core = re.sub(r'[^가-힣A-Za-z0-9]', '', vol_suffix)
                _tp_core = re.sub(r'[^가-힣A-Za-z0-9]', '', title_part)
                if _vs_core and _vs_core in _tp_core:
                    pass  # 이미 포함됨 → 추가하지 않음
                elif re.match(r'(?:외전|번외편?|특전)', vol_suffix) and ' ' in vol_suffix:
                    # 외전-first 패턴 (외전 N권 등): 전체 괄호
                    title_part = f'{title_part} ({vol_suffix})'
                elif (' ' in vol_suffix
                      and re.search(r'(?:외전|번외|특전)', vol_suffix)
                      and not re.search(r'\d+[권화부]', vol_suffix)):
                    # 수식어+외전 (특별 외전, AU 외전 등, 숫자 없음): 전체 괄호
                    title_part = f'{title_part} ({vol_suffix})'
                elif (' ' in vol_suffix
                      and re.search(r'(?:외전|번외|특전)', vol_suffix)
                      and re.match(r'[가-힣A-Za-z]+\s+(?:외전|번외편?|특전)', vol_suffix)):
                    # 수식어-first + 외전 + N권 (특별 외전 2권 등): 전체 괄호
                    title_part = f'{title_part} ({vol_suffix})'
                else:
                    # N권 외전, N부 외전, 단독 vol: 그대로 붙이고 _wrap_gaiden이 외전 괄호 처리
                    title_part = f'{title_part} {vol_suffix}'

            # 외전 단독 → (외전) 괄호 감싸기
            title_part = _wrap_gaiden(title_part)

            # 외전 중복 제거: "(외전) (외전 N권)" 또는 "외전 (외전 N권)" → "(외전 N권)"
            title_part = re.sub(
                r'[\(（]?(외전|번외편?)[\)）]?\s+\(((?:외전|번외편?)[^)）]*)\)',
                r'(\2)', title_part)

            # 완결 마커 정규화: OPF 제목에서 완결 감지 후 통합
            title_part, has_complete_in_title = _normalize_complete(title_part)
            is_complete = is_complete or has_complete_in_title

            # 외전 계열 괄호가 이미 있으면 (완결) 생략 — (외전) 자체가 완결 의미 포함
            # 단, 숫자 있는 "(외전 2권)" 은 시리즈이므로 완결 마커 필요 → 생략하지 않음
            _has_gaiden_bracket = bool(re.search(
                r'\([^)]*(?:외전|번외|특전)(?!\s*\d)[^)]*\)', title_part))
            if is_complete and not _has_gaiden_bracket:
                title_part = title_part.rstrip() + ' (완결)'

            # numeric-id 낱펍에서 dc:creator가 시리즈명과 같은 경우
            # "[신가] 신가 1권"처럼 같은 이름이 중복되는 것을 막는다.
            if creator:
                _creator_key = re.sub(r'\s+', '', _normalize_title(creator))
                _title_key = re.sub(
                    r'\s+', '',
                    _strip_trailing_volume_suffix(
                        re.sub(r'\s*\(완결\)\s*$', '', title_part)).strip())
                if _creator_key and _creator_key == _title_key:
                    creator = ''

            new = f'[{creator}] {title_part}' if creator else title_part
            new = _safe_title(new)
            # 괄호 앞뒤 공백 정리
            new = re.sub(r'\(\s+', '(', new)
            new = re.sub(r'\s+\)', ')', new)
            new = re.sub(r'\s+', ' ', new).strip()
            if not new.lower().endswith('.epub'):
                new += '.epub'
            return new

        except Exception:
            return orig_name

    def _rename_reset_preview(self):
        """변경명 열을 원본 파일명으로 초기화."""
        for row in range(self.rename_table.rowCount()):
            orig_item = self.rename_table.item(row, 0)
            new_item  = self.rename_table.item(row, 1)
            if orig_item and new_item:
                from PyQt6.QtGui import QColor
                new_item.setText(orig_item.text())
                new_item.setForeground(QColor(C["text"]))

    @staticmethod
    def _cleanup_rename_preview_name(name: str) -> str:
        """일괄 편집 후 남는 공백/빈 괄호를 정리한 preview 파일명을 반환."""
        suffix = Path(name).suffix
        ext = suffix
        stem = name[:-len(ext)] if ext else name

        stem = stem.replace('\n', ' ')
        stem = re.sub(r'\s+', ' ', stem).strip()
        for empty_pat in (
            r'\(\s*\)', r'\[\s*\]', r'\{\s*\}',
            r'（\s*）', r'［\s*］', r'｛\s*｝',
            r'〈\s*〉', r'《\s*》', r'「\s*」', r'『\s*』', r'【\s*】',
        ):
            stem = re.sub(empty_pat, ' ', stem)
        stem = re.sub(r'([(\[{〈《「『【])\s+', r'\1', stem)
        stem = re.sub(r'\s+([)\]}〉》」』】])', r'\1', stem)
        stem = re.sub(r'\s+([,.;:!?])', r'\1', stem)
        stem = re.sub(r'(?:\s*[-_~]\s*){2,}', ' - ', stem)
        stem = re.sub(r'[-_~]{2,}', lambda m: m.group(0)[0], stem)
        stem = re.sub(r'\s+', ' ', stem).strip()
        stem = stem.strip(' .-_~')
        stem = _safe_title(stem)
        return f'{stem}{ext}' if stem else ''

    @staticmethod
    def _split_preview_name(name: str) -> tuple[str, str]:
        suffix = Path(name).suffix
        ext = suffix or ''
        stem = name[:-len(ext)] if ext else name
        return stem, ext

    @staticmethod
    def _split_author_prefix(stem: str) -> tuple[str, str]:
        m = re.match(r'^(\[[^\]]+\]\s*)(.*)$', (stem or '').strip())
        if m:
            return m.group(1), m.group(2).strip()
        return '', (stem or '').strip()

    def _rename_remove_text_batch(self):
        if self.rename_table.rowCount() == 0:
            QMessageBox.information(self, "파일 없음",
                "먼저 EPUB 파일을 추가해주세요.")
            return

        needle = self.rename_remove_text_edit.text().strip()
        if not needle:
            QMessageBox.information(self, "삭제할 문구 없음",
                "지울 문자열을 입력해 주세요.")
            return

        from PyQt6.QtGui import QColor
        changed = 0
        skipped = 0
        pattern = re.compile(re.escape(needle), re.IGNORECASE)

        for row in range(self.rename_table.rowCount()):
            orig_item = self.rename_table.item(row, 0)
            new_item = self.rename_table.item(row, 1)
            if not orig_item or not new_item:
                continue

            old_name = (new_item.text() or "").strip()
            if not old_name:
                continue

            suffix = Path(old_name).suffix
            stem = old_name[:-len(suffix)] if suffix else old_name

            updated = pattern.sub(' ', stem)
            updated = self._cleanup_rename_preview_name(f"{updated}{suffix}")
            if not updated:
                skipped += 1
                continue
            if updated == old_name:
                continue

            new_item.setText(updated)
            new_item.setForeground(QColor(C["accent"] if updated != orig_item.text() else C["text"]))
            changed += 1

        if changed:
            msg = f"문구 삭제 완료: {changed}개"
            if skipped:
                msg += f"\n이름이 비게 되는 {skipped}개는 건너뛰었습니다."
            QMessageBox.information(self, "완료", msg)
        else:
            msg = "일치하는 문자열이 없습니다."
            if skipped:
                msg += f"\n이름이 비게 되는 {skipped}개는 건너뛰었습니다."
            QMessageBox.information(self, "안내", msg)

    @staticmethod
    def _extract_episode_no_from_filename(name: str):
        return EPUBMergerGUI._extract_episode_no_from_text(Path(name).stem)

    @staticmethod
    def _extract_episode_no_from_text(text: str):
        t = _normalize_title(_strip_filename_parse_noise(text or ''))
        if not t:
            return None
        for pat in (
            r'(?<!\d)(\d+)\s*화(?!\d)',
            r'(?<!\d)(\d+)\s*회(?:차)?(?!\d)',
            r'^[#＃]\s*(\d+)\b',
            r'^(?:ep|episode)\.?\s*(\d+)\b',
        ):
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return None
        return None

    @staticmethod
    def _extract_trailing_serial_no_from_filename(name: str):
        stem = _strip_filename_parse_noise(Path(name).stem)
        if re.search(r'\d+\s*[권화부장절편막회]', stem):
            return None
        if re.search(r'(?:완결|외전|번외|특전|단행본|합본)', stem):
            return None
        m = re.search(r'(?:^|[\s._-])(\d{1,4})\s*$', stem)
        if not m:
            return None
        try:
            num = int(m.group(1))
        except Exception:
            return None
        return num if 0 < num <= 9999 else None

    @staticmethod
    def _numbers_look_serial_episode(numbers, *, explicit: bool):
        uniq = sorted({int(n) for n in numbers if n is not None and int(n) > 0})
        if len(uniq) < (2 if explicit else 3):
            return False
        span = uniq[-1] - uniq[0]
        if span < 1:
            return False
        coverage = len(uniq) / max(span + 1, 1)
        if explicit:
            return coverage >= 0.35 or len(uniq) >= 5 or span <= 5
        return coverage >= 0.6 and (uniq[-1] >= 10 or len(uniq) >= 7 or span >= 9)

    def _detect_episode_range_from_epub(self, path: str):
        cache = getattr(self, '_rename_episode_cache', None)
        if cache is None:
            cache = {}
            self._rename_episode_cache = cache
        if path in cache:
            return cache[path]

        result = None
        try:
            with zipfile.ZipFile(path, 'r') as z:
                names = set(z.namelist())
                container = z.read('META-INF/container.xml').decode('utf-8', 'replace')
                m = re.search(r'full-path=["\']([^"\']+\.opf)["\']', container, re.IGNORECASE)
                if not m:
                    cache[path] = None
                    return None
                opf_path = m.group(1).replace('\\', '/')
                opf = z.read(opf_path).decode('utf-8', 'replace')
                opf_dir = posixpath.dirname(opf_path)
                manifest = {}
                for mm in re.finditer(r'<item\b[^>]*>', opf, re.IGNORECASE):
                    tag = mm.group(0)
                    item_id = _xml_attr(tag, 'id')
                    href = _xml_attr(tag, 'href')
                    if item_id and href:
                        manifest[item_id] = href
                spine_ids = re.findall(r'<itemref\b[^>]*idref=["\']([^"\']+)["\']', opf, re.IGNORECASE)

                ncx_labels = {}
                try:
                    ncx_href_m = re.search(
                        r'<item\b[^>]*media-type=["\']application/x-dtbncx\+xml["\'][^>]*href=["\']([^"\']+)["\']'
                        r'|<item\b[^>]*href=["\']([^"\']*toc\.ncx)["\']',
                        opf, re.IGNORECASE)
                    if ncx_href_m:
                        ncx_href = ncx_href_m.group(1) or ncx_href_m.group(2)
                        ncx_full = posixpath.normpath(
                            posixpath.join(opf_dir, ncx_href)).replace('\\', '/')
                        if ncx_full not in names:
                            ncx_full = ncx_href
                        ncx_raw = z.read(ncx_full).decode('utf-8', 'replace')
                        for nm in re.finditer(
                                r'<navPoint[^>]*>.*?<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>.*?'
                                r'<content[^>]*src=["\']([^"\'#]+)',
                                ncx_raw, re.IGNORECASE | re.DOTALL):
                            lbl = _CDATA_PAT.sub(r'\1', re.sub(r'\s+', ' ', nm.group(1))).strip()
                            fn = Path(nm.group(2).strip().replace('\\', '/')).name.lower()
                            if lbl and fn:
                                ncx_labels[fn] = lbl
                except Exception:
                    ncx_labels = {}

                numbers = []
                for sid in spine_ids:
                    href = manifest.get(sid)
                    if not href:
                        continue
                    full = posixpath.normpath(posixpath.join(opf_dir, href)).replace('\\', '/')
                    if full not in names:
                        full = href
                    if full not in names:
                        continue
                    data = z.read(full)
                    if is_skip_page(href, data):
                        continue
                    candidates = []
                    ncx_title = ncx_labels.get(Path(href).name.lower(), '').strip()
                    html_title = extract_chapter_title(data) or ''
                    if ncx_title:
                        candidates.append(ncx_title)
                    if html_title and html_title not in candidates:
                        candidates.append(html_title)
                    for cand in candidates:
                        ep_no = self._extract_episode_no_from_text(cand)
                        if ep_no is None:
                            continue
                        if not numbers or numbers[-1] != ep_no:
                            numbers.append(ep_no)
                        break

                uniq = sorted(set(numbers))
                if self._numbers_look_serial_episode(uniq, explicit=True):
                    result = (uniq[0], uniq[-1])
        except Exception:
            result = None

        cache[path] = result
        return result

    def _build_rename_episode_map(self, target_rows=None):
        row_count = self.rename_table.rowCount()
        if isinstance(target_rows, bool):
            target_rows = None
        rows = sorted(set(range(row_count) if target_rows is None else target_rows))
        target_set = set(rows)
        episode_map = {}

        for row in rows:
            new_item = self.rename_table.item(row, 1)
            if not new_item:
                continue
            path = new_item.data(Qt.ItemDataRole.UserRole)
            if not path:
                continue
            rng = self._detect_episode_range_from_epub(path)
            if rng:
                episode_map[row] = rng

        groups: dict[str, list[tuple[int, str]]] = {}
        for row in range(row_count):
            orig_item = self.rename_table.item(row, 0)
            if not orig_item:
                continue
            orig_name = orig_item.text().strip()
            key_src = self._zip_series_key(orig_name) or ''
            key = re.sub(r'\s+', '', key_src)
            key = key or re.sub(r'\s+', '', Path(orig_name).stem)
            groups.setdefault(key, []).append((row, orig_name))

        for items in groups.values():
            explicit_rows = []
            trailing_rows = []
            for row, orig_name in items:
                ep_no = self._extract_episode_no_from_filename(orig_name)
                if ep_no is not None:
                    explicit_rows.append((row, ep_no))
                    continue
                tail_no = self._extract_trailing_serial_no_from_filename(orig_name)
                if tail_no is not None:
                    trailing_rows.append((row, tail_no))

            if self._numbers_look_serial_episode([n for _, n in explicit_rows], explicit=True):
                for row, ep_no in explicit_rows:
                    if row in target_set and row not in episode_map:
                        episode_map[row] = (ep_no, ep_no)

            if self._numbers_look_serial_episode([n for _, n in trailing_rows], explicit=False):
                for row, ep_no in trailing_rows:
                    if row in target_set and row not in episode_map:
                        episode_map[row] = (ep_no, ep_no)

        return episode_map

    @staticmethod
    def _format_episode_label(start_no: int, end_no: int) -> str:
        return f"{start_no}화" if start_no == end_no else f"{start_no}-{end_no}화"

    def _apply_episode_label_to_preview_name(self, name: str, start_no: int, end_no: int) -> str:
        label = self._format_episode_label(start_no, end_no)
        stem, ext = self._split_preview_name(name)
        prefix, body = self._split_author_prefix(stem)
        if not body:
            body = stem.strip()
        if re.search(re.escape(label), body):
            return name

        body2 = re.sub(r'(?<!\d)\d+\s*[-~]\s*\d+\s*화', label, body, count=1)
        if body2 == body:
            body2 = re.sub(r'(?<!\d)\d+\s*(?:화|회(?:차)?)', label, body, count=1)
        if body2 == body:
            body2 = re.sub(r'^[#＃]\s*\d+\b', label, body, count=1)
        if body2 == body:
            clean_body = re.sub(r'^[#＃]?\s*\d+\s*[.:-]\s*', '', body).strip()
            if _is_chapterish_title(clean_body):
                body2 = f'{label} {clean_body}'.strip()
            else:
                body2 = f'{body} {label}'.strip()

        fixed = self._cleanup_rename_preview_name(f'{prefix}{body2}{ext}')
        return fixed or name

    def _rename_apply_episode_numbers(self, target_rows=None, quiet: bool = False):
        """이름 변경 미리보기의 연재 화수를 파일명/EPUB 내부 흐름 기준으로 보정."""
        try:
            if self.rename_table.rowCount() == 0:
                if not quiet:
                    QMessageBox.information(self, "파일 없음", "먼저 EPUB 파일을 추가해주세요.")
                return 0

            if isinstance(target_rows, bool):
                target_rows = None
            rows = sorted(set(range(self.rename_table.rowCount()) if target_rows is None else target_rows))
            if not rows:
                return 0

            from PyQt6.QtGui import QColor
            episode_map = self._build_rename_episode_map(rows)
            changed = 0

            for row in rows:
                if row not in episode_map:
                    continue
                orig_item = self.rename_table.item(row, 0)
                new_item = self.rename_table.item(row, 1)
                if not orig_item or not new_item:
                    continue

                new_name = (new_item.text() or '').strip()
                if not new_name:
                    continue

                start_no, end_no = episode_map[row]
                fixed = self._apply_episode_label_to_preview_name(new_name, start_no, end_no)
                if fixed != new_name:
                    new_item.setText(fixed)
                    new_item.setForeground(QColor(C["accent"] if fixed != orig_item.text() else C["text"]))
                    changed += 1

            if not quiet:
                if changed:
                    QMessageBox.information(self, "완료", f"화수 보정 완료: {changed}개")
                else:
                    QMessageBox.information(
                        self, "안내",
                        "연재 화수 흐름으로 판단되는 항목이 없었습니다.\n"
                        "단권/챕터형 파일은 오탐 방지를 위해 자동 보정을 건너뜁니다.")
            return changed
        except Exception as ex:
            import traceback
            traceback.print_exc()
            if not quiet:
                QMessageBox.warning(self, "화수 보정 오류", f"화수 보정 중 오류가 발생했습니다.\n{ex}")
            return 0

    # ── 이름 변경 적용 ─────────────────────────────
    def _rename_apply(self):
        if self.rename_table.rowCount() == 0:
            QMessageBox.warning(self, "파일 없음",
                "먼저 EPUB 파일을 추가해주세요.")
            return
        tasks = []
        for row in range(self.rename_table.rowCount()):
            orig_item = self.rename_table.item(row, 0)
            new_item  = self.rename_table.item(row, 1)
            if not orig_item or not new_item: continue
            path     = new_item.data(Qt.ItemDataRole.UserRole)
            new_name = new_item.text().strip()
            if not new_name: continue
            if not new_name.lower().endswith('.epub'):
                new_name += '.epub'
            orig_name = orig_item.text()
            if new_name != orig_name:
                tasks.append((path, new_name))

        if not tasks:
            QMessageBox.information(self, "변경 없음", "변경된 파일명이 없습니다.")
            return

        # 확인 다이얼로그
        preview_lines = "\n".join(
            f"  {Path(p).name}  →  {n}" for p, n in tasks[:10])
        if len(tasks) > 10:
            preview_lines += f"\n  ... 외 {len(tasks)-10}개"
        r = QMessageBox.question(
            self, "이름 변경 확인",
            f"총 {len(tasks)}개 파일 이름을 변경합니다.\n\n{preview_lines}\n\n진행할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return

        do_strip   = self.chk_rename_strip.isChecked()
        copy_mode  = self.chk_rename_copy.isChecked()
        ok_cnt = 0; fail_cnt = 0; fail_msgs = []; strip_total = 0
        result_paths = []
        result_seen = set()

        # 복사본 모드: 첫 번째 파일 기준으로 renamed 하위 폴더 생성
        renamed_dir = None
        if copy_mode and tasks:
            base_dir = Path(tasks[0][0]).parent
            renamed_dir = base_dir / "renamed"
            try:
                renamed_dir.mkdir(exist_ok=True)
            except Exception as ex:
                QMessageBox.critical(self, "폴더 생성 실패",
                    f"'renamed' 폴더를 만들 수 없습니다:\n{ex}")
                return

        for old_path, new_name in tasks:
            try:
                old_p = Path(old_path)
                if copy_mode:
                    # 복사 대상 폴더: 원본 파일의 부모 아래 renamed/
                    dst_dir = old_p.parent / "renamed"
                    dst_dir.mkdir(exist_ok=True)
                    new_p = dst_dir / new_name
                else:
                    new_p = old_p.parent / new_name

                if new_p.exists() and new_p != old_p:
                    fail_msgs.append(f"이미 존재: {new_name}")
                    fail_cnt += 1
                    continue

                # 코드제거 (체크 시)
                if do_strip:
                    try:
                        raw = old_p.read_bytes()
                        cleaned, removed, _ = remove_invisible_chars(raw)
                        if removed > 0:
                            strip_total += removed
                            if copy_mode:
                                # 복사 모드: 정제된 내용으로 복사
                                new_p.write_bytes(cleaned)
                                _np = str(new_p)
                                if _np not in result_seen:
                                    result_seen.add(_np)
                                    result_paths.append(_np)
                                ok_cnt += 1
                                continue
                            else:
                                old_p.write_bytes(cleaned)
                    except Exception as se:
                        fail_msgs.append(f"코드제거 실패({old_p.name}): {se}")

                if copy_mode:
                    import shutil
                    shutil.copy2(str(old_p), str(new_p))
                else:
                    old_p.rename(new_p)

                _np = str(new_p)
                if _np not in result_seen:
                    result_seen.add(_np)
                    result_paths.append(_np)
                ok_cnt += 1
                if not copy_mode:
                    # 인플레이스 이름 변경 시에만 내부 경로 업데이트
                    for i, (fp, fn, fs) in enumerate(self._rename_files):
                        if fp == old_path:
                            self._rename_files[i] = (str(new_p), new_name, fs)
                            break
                    for row in range(self.rename_table.rowCount()):
                        item = self.rename_table.item(row, 1)
                        if item and item.data(Qt.ItemDataRole.UserRole) == old_path:
                            item.setData(Qt.ItemDataRole.UserRole, str(new_p))
                            break
            except Exception as ex:
                fail_msgs.append(f"{Path(old_path).name}: {ex}")
                fail_cnt += 1

        if not copy_mode:
            self._rename_refresh_list()
            # 테이블 원본명 갱신
            for row in range(self.rename_table.rowCount()):
                new_item = self.rename_table.item(row, 1)
                if new_item:
                    from PyQt6.QtGui import QColor
                    orig_item = self.rename_table.item(row, 0)
                    if orig_item:
                        orig_item.setText(new_item.text())
                        orig_item.setForeground(QColor(C["text3"]))
                    new_item.setForeground(QColor(C["text"]))

        txt_ok = 0
        txt_fail = 0
        if self.chk_rename_txt_save.isChecked() and result_paths:
            txt_ok, txt_fail, _ = self._save_txt_exports(result_paths, log_fn=None)

        msg = f"✅ {ok_cnt}개 완료"
        if copy_mode and renamed_dir:
            msg += f"\n📁 복사 위치: .../renamed/"
        if do_strip and strip_total > 0:
            msg += f"\n🧹 공백코드 {strip_total}개 제거"
        if self.chk_rename_txt_save.isChecked():
            msg += f"\n📝 TXT 저장: {txt_ok}개"
            if txt_fail:
                msg += f" / 실패 {txt_fail}개"
        if fail_cnt:
            msg += f"\n❌ {fail_cnt}개 실패\n" + "\n".join(fail_msgs[:5])
        QMessageBox.information(self, "완료", msg)

    def _save_txt_exports(self, epub_paths: list[str], log_fn=None):
        ok = 0
        fail = 0
        written = []

        for src in epub_paths:
            try:
                src_path = Path(src)
                if not src_path.exists():
                    raise FileNotFoundError("파일이 존재하지 않습니다.")

                sections = extract_epub_text_sections(
                    str(src_path),
                    remove_skip_pages=True,
                    strip_invisible=True,
                    cleanup_text=True,
                )
                if not sections:
                    raise RuntimeError("추출 가능한 본문을 찾지 못했습니다.")

                lines = []
                for _sec_name, sec_text in sections:
                    if not sec_text:
                        continue
                    lines.append(sec_text)
                    lines.append("")
                out_text = "\n".join(lines).strip() + "\n"
                out_path = src_path.with_suffix('.txt')
                out_path.write_text(out_text, encoding='utf-8')
                written.append(str(out_path))
                ok += 1
                if log_fn:
                    log_fn(f"📝 TXT 저장: {out_path.name}", "ok")
            except Exception as ex:
                fail += 1
                if log_fn:
                    log_fn(f"⚠ TXT 저장 실패: {Path(src).name} - {ex}", "warn")

        return ok, fail, written

    # ── ZIP 묶기 ───────────────────────────────────
    def _zip_browse_dir(self):
        fmt = "7z" if self.radio_7z.isChecked() else "ZIP"
        d = QFileDialog.getExistingDirectory(
            self, f"{fmt} 저장 폴더 선택", self.zip_dir_edit.text())
        if d:
            self.zip_dir_edit.setText(d)
            self._settings.setValue("last_zip_dir", d)

    @staticmethod
    def _zip_series_key(filename: str) -> str:
        """파일명에서 시리즈 키 추출 (권/화 번호 이전 부분).

        예:
          "[작가] 시리즈명 3권.epub"    → "[작가] 시리즈명"
          "[작가] 시리즈명 외전.epub"   → "[작가] 시리즈명"
          "시리즈명 15화.epub"          → "시리즈명"
          "시리즈명.epub"               → "시리즈명"  (단권 → 자체 ZIP)
        """
        stem = re.sub(r'[\s.]+$', '', Path(filename).stem)
        # 권/화/부 번호 앞까지 잘라내기
        # ※ _wrap_gaiden 이 외전/번외/특전을 (외전)/(특별외전) 형태로 괄호 감싸기 하므로
        #   열린 괄호 \(? 도 매치에 포함, 접두어([가-힣A-Za-z]*)도 함께 잡아야 key에
        #   '(' 이나 '특별' 등이 남지 않음
        m = re.search(
            r'\s*\(?'
            r'((?:(?<![가-힣])제)?\s*\d+\s*[권화부]'
            r'|[A-Za-z가-힣]*(?:외전|번외편?|특전)\d*)',
            stem)
        if m:
            key = stem[:m.start()].strip()
        else:
            # 끝 숫자/하위번호 제거:
            # "시리즈명 1", "시리즈명 1-1", "시리즈명 1-2", "시리즈명 1.1" → "시리즈명"
            key = re.sub(r'\s+\d+(?:\s*[-_.]\s*\d+)+\s*$', '', stem).strip()
            key = re.sub(r'\s+\d+\s*$', '', key).strip()
        # "쾌도무적 1 1권"처럼 잘못 붙은 중복 숫자도 같은 시리즈로 묶는다.
        key = re.sub(r'\s+\d+\s*$', '', key).strip()
        # 앞뒤 구두점 및 남은 열린 괄호 정리
        key = re.sub(r'^[\s.\-·(（]+|[\s.\-·(（]+$', '', key)
        return key or stem

    def _zip_series(self):
        """테이블의 변경명(열 1) 기준으로 시리즈 그룹핑 후 ZIP/7z 생성."""
        use_7z = self.radio_7z.isChecked()
        ext    = ".7z" if use_7z else ".zip"
        fmt_label = "7z" if use_7z else "ZIP"

        sources: list[tuple[str, str]] = []
        _seen_paths: set[str] = set()   # 동일 경로 중복 방지
        if self.rename_table.rowCount() > 0:
            for row in range(self.rename_table.rowCount()):
                new_item = self.rename_table.item(row, 1)
                if not new_item: continue
                path = new_item.data(Qt.ItemDataRole.UserRole)
                name = new_item.text().strip()
                if path and name:
                    actual = Path(path)
                    if not actual.exists():
                        found = next(
                            (f[0] for f in self._rename_files
                             if Path(f[0]).name == name), None)
                        if found: actual = Path(found)
                    _akey = str(actual)
                    if _akey not in _seen_paths:
                        _seen_paths.add(_akey)
                        sources.append((_akey, name))
        else:
            for fp, fn, _ in self._rename_files:
                if fp not in _seen_paths:
                    _seen_paths.add(fp)
                    sources.append((fp, fn))

        if not sources:
            QMessageBox.warning(self, "파일 없음",
                "파일을 추가하거나 이름 추출을 먼저 실행해주세요.")
            return

        if use_7z:
            try:
                import py7zr
            except ImportError:
                QMessageBox.critical(self, "py7zr 없음",
                    "7z 기능을 사용하려면 py7zr 패키지가 필요합니다.\n\n"
                    "pip install py7zr")
                return

        groups: dict[str, list[tuple[str, str]]] = {}
        key_canonical: dict[str, str] = {}   # 공백 정규화 키 → 대표 표시명
        for path, name in sources:
            key = self._zip_series_key(name)
            # 공백 제거 후 비교 → "버림받은 황비" / "버림 받은 황비" 동일 시리즈로 묶기
            norm_key = re.sub(r'[\s._\-]+', '', key).lower()
            if norm_key not in key_canonical:
                key_canonical[norm_key] = key  # 첫 번째 파일 키를 대표명으로 사용
            groups.setdefault(norm_key, []).append((path, name))

        # ── 단일/다중 그룹 분리 ──
        # '복사본으로 저장' 체크 시 1개짜리(낱개)도 출력 폴더에 함께 복사한다.
        copy_singles = self.chk_rename_copy.isChecked()
        single_groups = {k: v for k, v in groups.items() if len(v) < 2}
        multi_groups  = {k: v for k, v in groups.items() if len(v) >= 2}
        single_file_count = sum(len(v) for v in single_groups.values())

        if _core_build_series_groups:
            try:
                grouping = _core_build_series_groups(
                    sources,
                    keep_author=True,
                    min_items=2,
                )
                multi_groups = {
                    group.norm_key: list(group.items)
                    for group in grouping.groups
                }
                key_canonical = {
                    group.norm_key: group.key
                    for group in grouping.groups
                }
                single_groups = {
                    f"__single_{idx}": [item]
                    for idx, item in enumerate(grouping.single_items)
                }
                single_file_count = grouping.single_file_count
            except Exception:
                pass

        if not multi_groups and not (copy_singles and single_groups):
            QMessageBox.information(
                self, f"{fmt_label} 묶기",
                f"2개 이상인 같은 시리즈가 없습니다.\n"
                f"단일 파일 {single_file_count}개는 압축에서 제외했습니다.\n\n"
                f"※ '복사본으로 저장'을 체크하면 단일 EPUB(낱개)도 출력 폴더에 함께 복사됩니다.")
            return

        out_dir = Path(self.zip_dir_edit.text())
        out_dir.mkdir(parents=True, exist_ok=True)

        preview_lines = []
        icon = "🗃️" if use_7z else "📦"
        for norm_key, items in sorted(multi_groups.items()):
            key = key_canonical[norm_key]  # ZIP 파일명은 원본 표시명 사용
            arc_name = _safe_title(f"{key} ({len(items)})") + ext
            preview_lines.append(f"{icon} {arc_name}")
            for _, n in items[:3]:
                preview_lines.append(f"     • {n}")
            if len(items) > 3:
                preview_lines.append(f"     ... 외 {len(items)-3}개")

        # 단일 EPUB 복사 미리보기
        if copy_singles and single_groups:
            if preview_lines:
                preview_lines.append("")
            preview_lines.append(f"📄 단일 EPUB 복사: {single_file_count}개")
            _shown = 0
            for _nk in sorted(single_groups.keys()):
                for _p, _n in single_groups[_nk]:
                    if _shown < 3:
                        preview_lines.append(f"     • {_n}")
                    _shown += 1
            if single_file_count > 3:
                preview_lines.append(f"     ... 외 {single_file_count-3}개")

        head_lines = [f"총 {len(multi_groups)}개 {fmt_label}을 생성합니다."]
        if copy_singles and single_groups:
            head_lines.append(f"단일 EPUB(낱개) {single_file_count}개도 함께 복사합니다.")
        confirm_msg = (
            "\n".join(head_lines) + "\n\n"
            + "\n".join(preview_lines[:30])
            + ("\n..." if len(preview_lines) > 30 else "")
            + (f"\n\n단일 파일 {single_file_count}개는 제외합니다."
               if (single_file_count and not copy_singles) else "")
            + f"\n\n저장 위치: {out_dir}\n\n진행할까요?"
        )
        r = QMessageBox.question(
            self, f"{fmt_label} 묶기 확인",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return

        ok_cnt = 0; fail_cnt = 0; fail_msgs = []
        copied_cnt = 0
        for norm_key, items in multi_groups.items():
            key = key_canonical[norm_key]   # 공백 정규화 전 원본 표시명 사용
            arc_name = _safe_title(f"{key} ({len(items)})") + ext
            arc_path = out_dir / arc_name
            try:
                if use_7z:
                    import py7zr
                    with py7zr.SevenZipFile(arc_path, 'w') as zf:
                        _written_names: set[str] = set()
                        for src_path, display_name in items:
                            p = Path(src_path)
                            if display_name in _written_names:
                                continue  # 동일 arcname 중복 방지
                            if p.exists():
                                zf.write(p, display_name)
                                _written_names.add(display_name)
                            else:
                                fail_msgs.append(f"파일 없음: {display_name}")
                                fail_cnt += 1
                else:
                    with zipfile.ZipFile(arc_path, 'w', zipfile.ZIP_STORED) as zf:
                        _written_names2: set[str] = set()
                        for src_path, display_name in items:
                            p = Path(src_path)
                            if display_name in _written_names2:
                                continue  # 동일 arcname 중복 방지
                            if p.exists():
                                zf.write(p, display_name)
                                _written_names2.add(display_name)
                            else:
                                fail_msgs.append(f"파일 없음: {display_name}")
                                fail_cnt += 1
                ok_cnt += 1
            except Exception as ex:
                fail_msgs.append(f"{arc_name}: {ex}")
                fail_cnt += 1

        # ── 단일 EPUB(낱개) 복사 처리 ──
        if copy_singles and single_groups:
            for norm_key, items in single_groups.items():
                for src_path, display_name in items:
                    src = Path(src_path)
                    if not src.exists():
                        fail_msgs.append(f"파일 없음: {display_name}")
                        fail_cnt += 1
                        continue
                    dst = out_dir / display_name
                    try:
                        # 원본 = 대상이 동일 위치면 복사 스킵 (이미 그 자리에 있음)
                        if dst.exists() and dst.resolve() == src.resolve():
                            copied_cnt += 1
                            continue
                        # 동일 이름 충돌 시 (2), (3) … 접미사 부여
                        if dst.exists():
                            stem = Path(display_name).stem
                            sfx  = Path(display_name).suffix
                            n = 2
                            while True:
                                cand = out_dir / f"{stem} ({n}){sfx}"
                                if not cand.exists():
                                    dst = cand
                                    break
                                n += 1
                        shutil.copy2(src, dst)
                        copied_cnt += 1
                    except Exception as ex:
                        fail_msgs.append(f"복사 실패 {display_name}: {ex}")
                        fail_cnt += 1

        msg = f"✅ {ok_cnt}개 {fmt_label} 생성 완료"
        if copied_cnt:
            msg += f" / 단일 EPUB {copied_cnt}개 복사"
        if fail_cnt:
            msg += f"\n❌ {fail_cnt}개 오류\n" + "\n".join(fail_msgs[:5])
        self._open_folder_confirm(str(out_dir), title="완료", pre_msg=msg)

    def _send_to_merge_safe(self):
        """Move rename-preview files to the merge tab without letting slot errors close the app."""
        try:
            from collections import Counter as _Counter

            sources: list[str] = []
            renamed_by_abs: dict[str, str] = {}

            def _add_source(path_value, display_name: str):
                if not path_value or not display_name:
                    return
                actual = Path(str(path_value))
                if not actual.exists():
                    found = next(
                        (f[0] for f in self._rename_files
                         if Path(f[0]).name == display_name or os.path.abspath(f[0]) == os.path.abspath(str(path_value))),
                        None,
                    )
                    if found:
                        actual = Path(found)
                if not actual.exists():
                    return
                actual_s = str(actual)
                actual_key = os.path.abspath(actual_s)
                if actual_key not in renamed_by_abs:
                    sources.append(actual_s)
                renamed_by_abs[actual_key] = display_name if display_name.lower().endswith('.epub') else f"{display_name}.epub"

            if self.rename_table.rowCount() > 0:
                for row in range(self.rename_table.rowCount()):
                    new_item = self.rename_table.item(row, 1)
                    if not new_item:
                        continue
                    _add_source(new_item.data(Qt.ItemDataRole.UserRole), new_item.text().strip())
            else:
                for _p, *_rest in self._rename_files:
                    if Path(_p).exists():
                        _add_source(_p, Path(_p).name)

            if not sources:
                QMessageBox.warning(self, "파일 없음", "파일을 추가하거나 이름 추출을 먼저 실행해주세요.")
                return

            self._replace_files(sources)
            if not self._files:
                QMessageBox.warning(self, "병합 목록 없음", "병합 탭으로 보낼 EPUB 파일을 찾지 못했습니다.")
                return

            patched_files = []
            patched_toc_titles = []
            display_names = []
            for p, old_name, size_s in self._files:
                new_name = renamed_by_abs.get(os.path.abspath(p), old_name or Path(p).name)
                if not new_name.lower().endswith('.epub'):
                    new_name = f"{new_name}.epub"
                patched_files.append((p, new_name, size_s))
                patched_toc_titles.append(_toc_label_from_filename(new_name))
                display_names.append(new_name)

            self._files = patched_files
            self._toc_titles = patched_toc_titles
            if not self._manual_mode:
                paired = sorted(
                    zip(self._files, self._toc_titles),
                    key=lambda item: natural_sort_key(item[0][1]),
                )
                self._files = [item[0] for item in paired]
                self._toc_titles = [item[1] for item in paired]

            series_keys = []
            for name in display_names:
                key = self._zip_series_key(name) or Path(name).stem
                key = _safe_title(key).strip()
                if key:
                    series_keys.append(key)
            base_title = _Counter(series_keys).most_common(1)[0][0] if series_keys else Path(display_names[0]).stem

            vol_range = self._volume_range(display_names) or self._volume_range_from_toc(self._files)
            if vol_range:
                first_token = vol_range.split()[0] if ' ' in vol_range else ''
                if first_token and base_title.endswith(first_token):
                    vol_range = vol_range[len(first_token):].strip()
                if vol_range and vol_range not in base_title:
                    base_title = f"{base_title} {vol_range}".strip()

            self.fname_edit.setText(_safe_title(base_title))
            self._toc_titles = [
                _compact_toc_label_for_series(title, base_title)
                for title in self._toc_titles
            ]
            self._title_auto = False
            self._refresh_list()
            self.tab_widget.setCurrentIndex(0)
            if hasattr(self, 'log_area'):
                self.log_area.append(f"이름 변경 탭에서 {len(sources)}개 파일을 병합 탭으로 불러왔습니다.")
        except Exception as ex:
            import traceback
            traceback.print_exc()
            try:
                self._log(f"이름 변경 -> 병합 이동 실패: {ex}", "err")
            except Exception:
                pass
            QMessageBox.critical(self, "병합 이동 오류", f"이름 변경 목록을 병합 탭으로 보내는 중 오류가 발생했습니다.\n\n{ex}")

    def _send_to_merge(self):
        """이름변경 탭의 파일 목록을 병합 탭으로 넘기고 탭 전환."""
        sources: list[str] = []
        renamed_name_by_path: dict[str, str] = {}
        if self.rename_table.rowCount() > 0:
            for row in range(self.rename_table.rowCount()):
                new_item = self.rename_table.item(row, 1)
                if not new_item: continue
                path = new_item.data(Qt.ItemDataRole.UserRole)
                name = new_item.text().strip()
                if not path or not name: continue
                actual = Path(path)
                if not actual.exists():
                    found = next(
                        (f[0] for f in self._rename_files
                         if Path(f[0]).name == name), None)
                    if found: actual = Path(found)
                if actual.exists():
                    actual_s = str(actual)
                    sources.append(actual_s)
                    renamed_name_by_path[actual_s] = name
        else:
            sources = [f[0] for f in self._rename_files if Path(f[0]).exists()]
            for _p in sources:
                renamed_name_by_path[_p] = Path(_p).name

        if not sources:
            QMessageBox.warning(self, "파일 없음",
                "파일을 추가하거나 이름 추출을 먼저 실행해주세요.")
            return

        self._replace_files(sources)
        if self._files:
            patched_files = []
            patched_toc_titles = []
            for p, _old_name, size_s in self._files:
                new_name = renamed_name_by_path.get(p, Path(p).name)
                patched_files.append((p, new_name, size_s))
                patched_toc_titles.append(_toc_label_from_filename(new_name))
            self._files = patched_files
            self._toc_titles = patched_toc_titles

            title_candidates = [
                re.sub(r'^\[[^\]]+\]\s*', '', renamed_name_by_path.get(p, Path(p).name))
                for p, *_ in self._files
            ]
            title_candidates = [
                re.sub(r'\s+\d+(?:\s*[-_.]\s*\d+)*\s*(?:沅?솕|??)?\s*$', '', name).strip()
                for name in title_candidates
                if name
            ]
            if title_candidates:
                from collections import Counter as _Counter
                base_title = _Counter(title_candidates).most_common(1)[0][0]
                ep_numbers = []
                for _p, *_ in self._files:
                    _nm = renamed_name_by_path.get(_p, Path(_p).name)
                    _ep = self._extract_episode_no_from_filename(_nm)
                    if _ep is not None:
                        ep_numbers.append(int(_ep))
                if self._numbers_look_serial_episode(ep_numbers, explicit=True):
                    _start, _end = min(ep_numbers), max(ep_numbers)
                    _ep_label = self._format_episode_label(_start, _end)
                    if _ep_label and _ep_label not in base_title:
                        base_title = f"{base_title} {_ep_label}".strip()
                self.fname_edit.setText(base_title)
                self._title_auto = False
                self._refresh_list()
        self.tab_widget.setCurrentIndex(0)
        # 상단 로그 영역에 안내
        if hasattr(self, 'log_area'):
            self.log_area.append(f"✅ 이름 변경 탭에서 {len(sources)}개 파일을 불러왔습니다.")

    def _on_tab_changed(self, index):
        """탭 전환 시 이름 변경 탭(index=1)이면 컬럼 비율 재적용."""
        if index == 1:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._apply_rename_col_ratio)
            QTimer.singleShot(100, self._apply_rename_col_ratio)

    def showEvent(self, e):
        super().showEvent(e)
        # 레이아웃 확정 후 열 너비 적용 — 0ms 직후 + 150ms 두 번 호출로 안정적으로 5:5 보장
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_rename_col_ratio)
        QTimer.singleShot(150, self._apply_rename_col_ratio)

    def _apply_rename_col_ratio(self):
        """왼쪽 열만 비율로 설정 — 오른쪽은 Stretch가 자동으로 나머지를 채움."""
        if hasattr(self, 'rename_table'):
            total = self.rename_table.viewport().width()
            if total > 0:
                self.rename_table.setColumnWidth(0, int(total * self._rename_col0_ratio))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_rename_col_ratio()

    def _on_rename_col_resized(self, logical_index, old_size, new_size):
        """사용자가 왼쪽 헤더를 드래그하면 비율 저장."""
        if logical_index != 0:
            return
        if not hasattr(self, '_rename_col0_ratio'):
            return
        total = self.rename_table.viewport().width()
        if total > 0:
            self._rename_col0_ratio = new_size / total

    def eventFilter(self, obj, e):
        from PyQt6.QtCore import QEvent
        if (hasattr(self, 'rename_table')
                and obj is self.rename_table.viewport()
                and e.type() in (
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseButtonRelease,
                    QEvent.Type.MouseButtonDblClick,
                )):
            idx = self.rename_table.indexAt(e.pos())
            if idx.isValid() and idx.column() == 0:
                item = self.rename_table.item(idx.row(), 0)
                self._rename_copy_original_name_item(item)
                return False
        if obj is self.rename_table and e.type() == QEvent.Type.KeyPress:
            if e.key() == Qt.Key.Key_Delete:
                self._rename_delete_selected()
                return True
            if (e.key() == Qt.Key.Key_C
                    and e.modifiers() == Qt.KeyboardModifier.ControlModifier):
                cur = self.rename_table.currentItem()
                if cur and cur.column() == 0:
                    self._rename_copy_original_name_item(cur)
                    return True
            if (e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and e.modifiers() == Qt.KeyboardModifier.ControlModifier):
                cur = self.rename_table.currentRow()
                nxt = cur + 1
                if nxt < self.rename_table.rowCount():
                    self.rename_table.setCurrentCell(nxt, 1)
                    self.rename_table.editItem(self.rename_table.item(nxt, 1))
                return True
        if obj is getattr(self, 'txt_list', None) and e.type() == QEvent.Type.KeyPress:
            if e.key() == Qt.Key.Key_Delete:
                self._txt_delete_selected()
                return True
        if obj is getattr(self, 'e2t_list', None) and e.type() == QEvent.Type.KeyPress:
            if e.key() == Qt.Key.Key_Delete:
                self._e2t_delete_selected()
                return True
        return super().eventFilter(obj, e)

    def keyPressEvent(self, e):
        from PyQt6.QtCore import Qt as _Qt
        if e.key() == _Qt.Key.Key_V and e.modifiers() == _Qt.KeyboardModifier.ControlModifier:
            self._paste_cover()
        else:
            super().keyPressEvent(e)

    # ── 파일 추가/삭제 ──────────────────────────────
    def _browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "EPUB 파일 선택", "",
            "EPUB / Archives (*.epub *.zip *.7z);;EPUB Files (*.epub);;Archives (*.zip *.7z);;All Files (*.*)")
        if paths:
            self._replace_files(paths)

    def _replace_files(self, paths):
        """기존 목록을 비우고 새 파일로 교체 (드롭, 파일 열기 공통)."""
        self._files.clear()
        self._toc_titles.clear()
        self._page_title_overrides = {}
        self._title_auto = True
        self._add_files(paths)

    def _add_files(self, paths):
        """파일 경로 or 폴더 경로 리스트를 받아 epub 추가.
        폴더는 하위까지 재귀 탐색. ZIP/7z은 내부 EPUB 자동 추출.
        """
        BULK_FAST_ADD_THRESHOLD = 80
        paths = self._extract_archives_for_epub(paths)
        added = 0
        # 폴더 → epub 목록으로 전개
        expanded = []
        for p in paths:
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for fn in files:
                        if fn.lower().endswith(".epub"):
                            expanded.append(os.path.join(root, fn))
            else:
                expanded.append(p)

        existing_paths = {f[0] for f in self._files}
        for p in expanded:
            if not p.lower().endswith(".epub"): continue
            if p in existing_paths: continue
            import unicodedata as _ucd
            _disp_name = _ucd.normalize('NFC', Path(p).name)
            self._files.append((p, _disp_name, human_size(os.path.getsize(p))))
            existing_paths.add(p)
            added += 1
        if added:
            if not self._manual_mode: self._do_auto_sort()
            bulk_fast_mode = len(self._files) >= BULK_FAST_ADD_THRESHOLD
            # 새 파일의 기본 제목 추가 (기존 편집값 유지)
            self._toc_titles = [
                (self._toc_titles[i]
                 if i < len(self._toc_titles)
                 else (_toc_label_from_filename(f[1]) if bulk_fast_mode
                       else self._toc_label_from_file(f[0], f[1])))
                for i, f in enumerate(self._files)
            ]
            # 제목 자동 추출 (사용자가 아직 수동으로 바꾸지 않은 경우)
            if self._title_auto:
                if bulk_fast_mode:
                    self._auto_extract_title_fast()
                else:
                    self._auto_extract_title()
            # 새로 추가된 파일 중 아직 스캔 안 된 것만 큐에 넣기
            new_paths = [f[0] for f in self._files if f[0] not in self._scan_results]
            if new_paths:
                self._start_scan(new_paths)
            self._refresh_list()
            if bulk_fast_mode:
                self._log(
                    f"⚡ 대량 추가 모드: {len(self._files)}개 파일 "
                    f"(빠른 파일명 기반 라벨/제목 적용)")

    # ── 파일명에서 기본 제목 추출 (권/화/완결/외전 제거) ──
    @staticmethod
    def _base_title_from_filename(filename: str) -> str:
        name = _strip_filename_parse_noise(Path(filename).stem)
        # 언더스코어 구분자 → 공백
        name = name.replace('_', ' ')
        # Sigil 등 편집기 기본 플레이스홀더 제거 ("Title here", "Author here" 등)
        # 파일명 앞/뒤에 붙어있는 경우 모두 처리
        name = re.sub(r'(?i)(?:^|\s)Title\s+here(?:\s|$)', ' ', name).strip()
        name = re.sub(r'(?i)(?:^|\s)Author\s+here(?:\s|$)', ' ', name).strip()
        name = re.sub(r'\s+', ' ', name).strip()
        # "제N화. 부제" 패턴 전체 제거 (선행하는 경우)
        name = re.sub(r'^(?:(?<![가-힣])제)?\s*\d+\s*화\s*[._]?\s*', '', name)
        # 권/화/부 번호 제거
        name = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부]\s*', ' ', name)
        # 공백-구분 수식어 + 외전괄호 패턴 통째 제거 (예: "특별 (외전)", "스폐셜 (외전)" → 제거)
        # ※ 괄호 블록 제거 전에 실행해야 함
        name = re.sub(
            r'\s+(?:특별|스폐셜|스페셜|스폐설|스페설|추가|별책|보너스|단편|AU|IF)\s*'
            r'[\(（](외전|번외편?|특전)[^)）]*[\)）]\s*$', '', name)
        # 괄호 블록 제거
        name = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*', ' ', name)
        # "외전/번외 포함단행본" 계열 먼저 제거 (예: ",외전 포함단행본", "외전포함단행본")
        name = re.sub(r'[,\s]*[A-Za-z가-힣]*(?:외전|번외|특전)\s*포함\s*(?:단행본|합본)?\s*$', '', name)
        # 완/완결/完 단독 먼저 제거 (외전 뒤에 붙은 경우 lookahead 블로킹 방지: "외전 완")
        name = re.sub(r'\s+(완결|완|完)(?![가-힣])\s*$', ' ', name)
        # 끝 위치의 외전/번외/특전 계열 제거 (영문·한글 접두어 포함: IF외전, 특별외전, AU외전 등)
        # 단, 한글 조사 앞에 붙은 경우는 유지 (외전이, 외전을); 쉼표 구분자도 처리
        name = re.sub(r'[,\s]+[A-Za-z가-힣]*(?:외전|번외|특전)(?![가-힣])\d*\s*$', '', name)
        # 완결/단행본/합본 단독 제거
        name = re.sub(r'\s*(완결|단행본|합본)(?![가-힣])\s*', ' ', name)
        # 제목 끝 쉼표 제거 (파일명에서 구분자로 쓰인 경우)
        name = re.sub(r'\s*,\s*$', '', name)
        # 화/권 없는 끝 단독 숫자 제거 (예: "시리즈명 1" → "시리즈명", "시리즈명1" → "시리즈명")
        name = re.sub(r'(?:\s+|(?<=[가-힣]))\d+\s*$', '', name)
        # 앞뒤 구두점 정리
        name = re.sub(r'^[\s.\-·]+|[\s.\-·]+$', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    @staticmethod
    def _toc_label_from_file(path: str, filename: str) -> str:
        """목차 라벨 생성: OPF dc:title → NCX navPoint → 판권 → 파일명 순으로 시도.
        파일명의 [작가명] 접두어는 항상 보존."""
        # macOS NFD(자소분리) 파일명 → NFC(완성형)으로 정규화
        import unicodedata as _ucd
        filename = _ucd.normalize('NFC', filename)
        filename = _strip_filename_parse_noise(filename)
        label = _toc_label_from_filename(filename)
        stem = Path(filename).stem
        stem_clean = re.sub(r'\s*-[0-9a-f]{6,12}\s*$', '', stem, flags=re.IGNORECASE).strip()
        _base_is_numeric_id = bool(re.match(r'^[\d_\s-]+$', stem_clean))
        # 파일명에서 [작가명] 접두어 추출 (OPF 결과 앞에 붙이기 위해)
        # 단, 순서번호 형태([0001], [123화], [12권] 등)는 제외 → 한글/영문 포함이어도
        # "숫자+화권부" 패턴이면 순서번호로 간주
        _bp_m = re.match(
            r'^(\[(?!\s*\d+\s*[화권부]?\s*\])(?=[^\]]*[가-힣A-Za-z])[^\]]+\]\s*)',
            label)
        _bracket_prefix = _bp_m.group(1) if _bp_m else ''
        try:
            import zipfile as _zf
            with _zf.ZipFile(path, 'r') as z:
                    namelist = z.namelist()
                    container = z.read('META-INF/container.xml').decode('utf-8', 'replace')
                    m = re.search(r'full-path="([^"]+\.opf)"', container)
                    opf_title = ''
                    opf_raw   = ''
                    opf_path_val = ''
                    if m:
                        opf_path_val = m.group(1)
                        opf_raw = z.read(opf_path_val).decode('utf-8', 'replace')
                        t = _read_dc_tag(opf_raw, 'dc:title').strip()
                        if _base_is_numeric_id:
                            _opf_dir_vh = str(Path(opf_path_val).parent)
                            _series_heading = _find_series_volume_heading_in_zip(
                                z, opf_raw, _opf_dir_vh, max_files=6)
                            if _series_heading:
                                return (_bracket_prefix + _series_heading).strip()
                        _t_is_chap = _is_chapterish_title(t)
                        t_clean = _clean_opf_series_title(
                            t, strip_genre_tag=True, preserve_complete_paren=True)
                        # 한글 포함된 경우만 사용 (숫자만 있는 OPF 제목 제외)
                        if t_clean and re.search(r'[가-힣]', t_clean):
                            vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부])', stem)
                            vol = re.sub(r'\s+', '', vm.group(1)) if vm else ''
                            # 파일명에서 권수 못 뽑았으면 OPF 제목에서 추출 (파일명이 "3.epub" 같은 경우)
                            if not vol:
                                _opf_vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부])', t)
                                if _opf_vm:
                                    vol = re.sub(r'\s+', '', _opf_vm.group(1))
                            # OPF 제목에도 권화부 없으면 파일명 끝 숫자를 권호로 사용
                            # 예) 667336_6.epub → 6권 / 3.epub → 3권
                            if not vol:
                                _stem_num = re.search(r'(?:^|[_\s-])(\d{1,4})$', stem)
                                if _stem_num:
                                    _sn_int = int(_stem_num.group(1))
                                    try:
                                        _sn_unit = _guess_tail_volume_unit_from_zip(
                                            z, _sn_int, numeric_id_hint=_base_is_numeric_id)
                                    except Exception: pass
                                    vol = str(_sn_int) + _sn_unit
                            t = t_clean
                            # 제목 끝에 한글 뒤 바로 붙은 권수 숫자 제거 (예: 막내온탑3 → 막내온탑)
                            if vol:
                                _vn = re.search(r'\d+', vol)
                                if _vn:
                                    t = re.sub(r'(?<=[가-힣])' + re.escape(_vn.group()) + r'\s*$', '', t).strip()
                            # numeric-id + 챕터성 OPF 제목은 시리즈명으로 채택하지 않음
                            if not (_base_is_numeric_id and _t_is_chap):
                                opf_title = f'{t} {vol}'.strip() if vol else t

                    if opf_title:
                        return (_bracket_prefix + opf_title).strip()

                    # ── OPF 실패 시 NCX navPoint 폴백 ────────────
                    if opf_raw:
                        _ncx_m = re.search(r'href=["\']([^"\']+\.ncx)["\']', opf_raw)
                        if _ncx_m:
                            _opf_dir = str(Path(opf_path_val).parent)
                            _ncx_rel = _ncx_m.group(1)
                            _ncx_full = (_opf_dir + '/' + _ncx_rel).lstrip('./') \
                                if _opf_dir != '.' else _ncx_rel
                            try:
                                _ncx = z.read(_ncx_full).decode('utf-8', 'replace')
                            except Exception:
                                try: _ncx = z.read(_ncx_rel).decode('utf-8', 'replace')
                                except Exception: _ncx = ''
                            if _ncx:
                                _navs = re.findall(
                                    r'<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>',
                                    _ncx, re.DOTALL)
                                for _nav in _navs:
                                    _nt = re.sub(r'<[^>]+>', '', _nav).strip()
                                    _nt = _normalize_title(_nt)
                                    # 연재/완결 괄호 제거, 한글 2자 이상, 적당한 길이
                                    _nt = re.sub(r'\s*[\(（](?!완결\s*[\)）])[연완재결중]+[\)）]\s*', '', _nt).strip()
                                    if re.search(r'[가-힣]{2,}', _nt) and 2 < len(_nt) < 60:
                                        if _base_is_numeric_id and _is_chapterish_title(_nt):
                                            continue
                                        stem = Path(filename).stem
                                        vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부])', stem)
                                        vol = re.sub(r'\s+', '', vm.group(1)) if vm else ''
                                        if not vol:
                                            _stem_num = re.search(r'(?:^|[_\s-])(\d{1,4})$', stem)
                                            if _stem_num:
                                                _sn_int = int(_stem_num.group(1))
                                                try:
                                                    _sn_unit = _guess_tail_volume_unit_from_zip(
                                                        z, _sn_int, numeric_id_hint=_base_is_numeric_id)
                                                except Exception: pass
                                                vol = str(_sn_int) + _sn_unit
                                        _nt = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부]\s*', ' ', _nt).strip()
                                        return (_bracket_prefix + (f'{_nt} {vol}'.strip() if vol else _nt)).strip()

                    # ── NCX 실패 시 판권 파일 폴백 ──────────────
                    # endpg: 하이스토리(주) 등 일부 출판사가 사용하는 판권페이지 파일명
                    _COPY_KW = ('copyright', 'copy', 'colophon', 'rights',
                                '판권', 'credit', 'titlepage', 'title_page',
                                'info', 'pubinfo', 'endpg', 'end_pg', 'endpage',
                                'imprint')
                    _XHTML_EXT = ('.xhtml', '.html', '.htm')
                    copy_files = [n for n in namelist
                                  if any(k in n.lower() for k in _COPY_KW)
                                  and n.lower().endswith(_XHTML_EXT)]
                    if not copy_files:
                        copy_files = [n for n in namelist
                                      if n.lower().endswith(_XHTML_EXT)][:3]

                    def _strip_title_suffix(_t: str) -> str:
                        """제목 끝의 '(연재)', '(완결)' 같은 상태 표기 제거."""
                        _t = re.sub(r'\s*[\(（]\s*(?:연재(?:중)?|완결|完|개정판)\s*[\)）]\s*$', '', _t).strip()
                        return _t

                    import html as _html
                    for cf in copy_files:
                        try:
                            raw = z.read(cf).decode('utf-8', 'replace')
                            # ── [연재]/[완결] + N화/권 패턴 순수 p 태그 (클래스·h태그 없는 판권 페이지)
                            # 예: <p>[연재]인류 대표가 되었다 1화</p>
                            for ptag_m in re.finditer(r'<p[^>]*>(.*?)</p>', raw, re.IGNORECASE | re.DOTALL):
                                pt = re.sub(r'<br\s*/?>', ' ', ptag_m.group(1), flags=re.IGNORECASE)
                                pt = re.sub(r'<[^>]+>', '', pt).strip()
                                pt = _html.unescape(pt)
                                pt = re.sub(r'\s+', ' ', pt).strip()
                                if (re.search(r'^\s*\[(?:연재|완결)\]', pt)
                                        and re.search(r'[가-힣]{2,}', pt)
                                        and len(pt) < 80):
                                    _cv_m = re.search(r'\s*(\d+\s*[화권])\s*$', pt)
                                    vol = re.sub(r'\s+', '', _cv_m.group(1)) if _cv_m else ''
                                    t = re.sub(r'^\s*\[(?:연재|완결)\]\s*', '', pt)
                                    t = re.sub(r'\s*\d+\s*[화권]\s*$', '', t).strip()
                                    t = _strip_title_suffix(t)
                                    if re.search(r'[가-힣]{2,}', t) and 1 < len(t) < 60:
                                        if _base_is_numeric_id and _is_chapterish_title(pt):
                                            continue
                                        return (_bracket_prefix + (f'{t} {vol}'.strip() if vol else t)).strip()
                            # ── (NEW) class에 'title' 포함된 p 태그 — endpg.xhtml의 titleE 등 ──
                            # 첫 번째 비어있지 않은 한글 텍스트를 제목으로 사용
                            for ptag in re.findall(
                                    r'<p[^>]*\bclass=["\'][^"\']*[Tt]itle[^"\']*["\'][^>]*>(.*?)</p>',
                                    raw, re.IGNORECASE | re.DOTALL):
                                t = re.sub(r'<br\s*/?>', ' ', ptag, flags=re.IGNORECASE)
                                t = re.sub(r'<[^>]+>', '', t).strip()
                                t = _html.unescape(t)
                                t = re.sub(r'\s+', ' ', t).strip()
                                t = _strip_title_suffix(t)
                                if re.search(r'[가-힣]{2,}', t) and 2 < len(t) < 60:
                                    if _base_is_numeric_id and _is_chapterish_title(t):
                                        continue
                                    stem = Path(filename).stem
                                    vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부])', stem)
                                    vol = re.sub(r'\s+', '', vm.group(1)) if vm else ''
                                    if not vol:
                                        _stem_num = re.search(r'(?:^|[_\s-])(\d{1,4})$', stem)
                                        if _stem_num:
                                            _sn_int = int(_stem_num.group(1))
                                            try:
                                                _sn_unit = _guess_tail_volume_unit_from_zip(
                                                    z, _sn_int, numeric_id_hint=_base_is_numeric_id)
                                            except Exception: pass
                                            vol = str(_sn_int) + _sn_unit
                                    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화]\s*', ' ', t)
                                    t = re.sub(r'(\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부)(?!\s*[-–—―]|\s+[가-힣])', ' ', t).strip()
                                    return (_bracket_prefix + (f'{t} {vol}'.strip() if vol else t)).strip()
                            # h태그 먼저
                            for htag in re.findall(
                                    r'<h[1-4][^>]*>(.*?)</h[1-4]>',
                                    raw, re.IGNORECASE | re.DOTALL):
                                t = re.sub(r'<[^>]+>', '', htag).strip()
                                t = _html.unescape(t)
                                t = re.sub(r'\s+', ' ', t).strip()
                                t = _strip_title_suffix(t)
                                if re.search(r'[가-힣]{2,}', t) and len(t) < 60:
                                    if _base_is_numeric_id and _is_chapterish_title(t):
                                        continue
                                    stem = Path(filename).stem
                                    vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부])', stem)
                                    vol = re.sub(r'\s+', '', vm.group(1)) if vm else ''
                                    if not vol:
                                        _stem_num = re.search(r'(?:^|[_\s-])(\d{1,4})$', stem)
                                        if _stem_num:
                                            _sn_int = int(_stem_num.group(1))
                                            try:
                                                _sn_unit = _guess_tail_volume_unit_from_zip(
                                                    z, _sn_int, numeric_id_hint=_base_is_numeric_id)
                                            except Exception:
                                                _sn_unit = '권'
                                            vol = str(_sn_int) + _sn_unit
                                    # 권·화 제거 (부는 별도 처리)
                                    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화]\s*', ' ', t)
                                    # 부(部): 뒤에 dash(―—–) 또는 한글이 이어지면 시리즈명 구성요소 → 보호
                                    t = re.sub(r'(\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부)(?!\s*[-–—―]|\s+[가-힣])', ' ', t).strip()
                                    return (_bracket_prefix + (f'{t} {vol}'.strip() if vol else t)).strip()
                            # b/strong 태그
                            for btag in re.findall(
                                    r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>',
                                    raw, re.IGNORECASE | re.DOTALL):
                                # <br /> 태그를 공백으로 치환 후 나머지 태그 제거
                                t = re.sub(r'<br\s*/?>', ' ', btag, flags=re.IGNORECASE)
                                t = re.sub(r'<[^>]+>', '', t).strip()
                                t = _html.unescape(t)
                                t = re.sub(r'\s+', ' ', t).strip()
                                t = _strip_title_suffix(t)
                                if re.search(r'[가-힣]{2,}', t) and len(t) < 60:
                                    if _base_is_numeric_id and _is_chapterish_title(t):
                                        continue
                                    stem = Path(filename).stem
                                    vm = re.search(r'((?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부])', stem)
                                    vol = re.sub(r'\s+', '', vm.group(1)) if vm else ''
                                    if not vol:
                                        _stem_num = re.search(r'(?:^|[_\s-])(\d{1,4})$', stem)
                                        if _stem_num:
                                            _sn_int = int(_stem_num.group(1))
                                            try:
                                                _sn_unit = _guess_tail_volume_unit_from_zip(
                                                    z, _sn_int, numeric_id_hint=_base_is_numeric_id)
                                            except Exception:
                                                _sn_unit = '권'
                                            vol = str(_sn_int) + _sn_unit
                                    # 권·화 제거 (부는 별도 처리)
                                    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화]\s*', ' ', t)
                                    # 부(部): 뒤에 dash(―—–) 또는 한글이 이어지면 시리즈명 구성요소 → 보호
                                    t = re.sub(r'(\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부)(?!\s*[-–—―]|\s+[가-힣])', ' ', t).strip()
                                    return (_bracket_prefix + (f'{t} {vol}'.strip() if vol else t)).strip()
                        except Exception:
                            continue
        except Exception:
            pass
        # numeric-id 파일인데 메타 추출 실패 시 부모 폴더명으로 시리즈명 폴백
        if _base_is_numeric_id:
            _parent = _series_from_parent_dir(path)
            if _parent:
                _stem_num = re.search(r'(?:^|[_\s-])(\d{1,4})$', stem)
                if _stem_num:
                    _sn_int = int(_stem_num.group(1))
                    _sn_unit = '권'
                    try:
                        import zipfile as _zf_fallback
                        with _zf_fallback.ZipFile(path, 'r') as _z_fb:
                            _sn_unit = _guess_tail_volume_unit_from_zip(
                                _z_fb, _sn_int, numeric_id_hint=True)
                    except Exception:
                        pass
                    return (_bracket_prefix + f'{_parent} {_sn_int}{_sn_unit}').strip()
                return (_bracket_prefix + _parent).strip()
        return label

    @staticmethod
    def _toc_label_from_filename(filename: str) -> str:
        return _toc_label_from_filename(filename)

    # ── 전체 파일에서 권/화 범위 문자열 생성 ──────
    @staticmethod
    def _volume_range(filenames: list) -> str:
        def _extra_labels() -> list[str]:
            found = {"에필로그": False, "외전": False, "특외": False, "특전": False}
            for _fn in filenames:
                _stem = _strip_filename_parse_noise(Path(_fn).stem)
                if re.search(r'에필로그|후일담', _stem, re.IGNORECASE):
                    found["에필로그"] = True
                if re.search(r'외전|번외', _stem, re.IGNORECASE):
                    found["외전"] = True
                if re.search(r'특별\s*외전|특별외전|특\s*외|특외', _stem, re.IGNORECASE):
                    found["특외"] = True
                if re.search(r'특전', _stem, re.IGNORECASE):
                    found["특전"] = True
            return [label for label in ("에필로그", "외전", "특외", "특전") if found[label]]

        def _is_side_story_name(value: str) -> bool:
            stem = _strip_filename_parse_noise(Path(value).stem)
            return bool(re.search(r'에필로그|후일담|특별\s*외전|특별외전|특\s*외|특외|외전|번외|특전', stem, re.IGNORECASE))

        robust_vols = []
        robust_eps = []
        side_count = 0
        main_volume_count = 0
        for fn in filenames:
            stem = _strip_filename_parse_noise(Path(fn).stem).replace('_', ' ')
            stem = re.sub(r'\s+', ' ', stem).strip()
            is_side = _is_side_story_name(fn)
            if is_side:
                side_count += 1
            for rm in re.finditer(r'(?<!\d)(\d{1,4})\s*[-~]\s*(\d{1,4})\s*\uAD8C\b', stem):
                robust_vols.extend([int(rm.group(1)), int(rm.group(2))])
                if not is_side:
                    main_volume_count += 1
            for m in re.finditer(r'(?<!\d)(\d{1,4})\s*\uAD8C\b', stem):
                robust_vols.append(int(m.group(1)))
                if not is_side:
                    main_volume_count += 1
        if robust_vols:
            if side_count and main_volume_count:
                return f"1-{len(filenames)}권"
            mn, mx = min(robust_vols), max(robust_vols)
            base = f'{mn}\uAD8C' if mn == mx else f'{mn}-{mx}\uAD8C'
            extras = _extra_labels()
            if extras and all(_is_side_story_name(fn) for fn in filenames):
                return extras[0] + ' ' + base
            return base + (''.join(f'+{e}' for e in extras) if extras else '')
        for fn in filenames:
            stem = _strip_filename_parse_noise(Path(fn).stem).replace('_', ' ')
            stem = re.sub(r'\s+', ' ', stem).strip()
            for rm in re.finditer(r'(?<!\d)(\d{1,5})\s*[-~]\s*(\d{1,5})\s*\uD654\b', stem):
                robust_eps.extend([int(rm.group(1)), int(rm.group(2))])
            for m in re.finditer(r'(?<!\d)(\d{1,5})\s*\uD654\b', stem):
                robust_eps.append(int(m.group(1)))
        if robust_eps:
            mn, mx = min(robust_eps), max(robust_eps)
            base = f'{mn}\uD654' if mn == mx else f'{mn}-{mx}\uD654'
            extras = _extra_labels()
            if extras and all(_is_side_story_name(fn) for fn in filenames):
                return extras[0] + ' ' + base
            return base + (''.join(f'+{e}' for e in extras) if extras else '')
        vols = []
        extras = []   # 순서 유지하며 외전 종류 수집
        for fn in filenames:
            stem = _strip_filename_parse_noise(Path(fn).stem)
            rm = re.search(r'(\d+)\s*[-~]\s*(\d+)\s*권', stem)
            if rm:
                vols.append(int(rm.group(1))); vols.append(int(rm.group(2)))
            else:
                m = re.search(r'(\d+)\s*권', stem)
                if m: vols.append(int(m.group(1)))
            # 외전 종류 구분: 특별외전/특외 → '특외', 외전 → '외전', 번외 → '번외'
            if re.search(r'특별\s*외전|특\s*외', stem):
                if '특외' not in extras: extras.append('특외')
            elif re.search(r'외전', stem):
                if '외전' not in extras: extras.append('외전')
            if re.search(r'번외', stem):
                if '번외' not in extras: extras.append('번외')
        unit = '권'
        if not vols:
            for fn in filenames:
                stem = _strip_filename_parse_noise(Path(fn).stem)
                rm = re.search(r'(\d+)\s*[-~]\s*(\d+)\s*화', stem)
                if rm:
                    vols.append(int(rm.group(1))); vols.append(int(rm.group(2)))
                else:
                    m = re.search(r'(\d+)\s*화', stem)
                    if m: vols.append(int(m.group(1)))
            unit = '화'
        if not vols and not extras:
            for fn in filenames:
                stem = _strip_filename_parse_noise(Path(fn).stem)
                stem_c = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*$', '', stem).strip()
                tail_m = re.search(r'(\d+)\s*$', stem_c)
                if tail_m: vols.append(int(tail_m.group(1)))
            unit = '화' if vols and max(vols) >= 45 else ''
        if not vols and not extras: return ''
        extras_str = ''.join(f'+{e}' for e in extras)
        if vols:
            mn, mx = min(vols), max(vols)
            base = f'{mn}{unit}' if mn == mx else f'{mn}-{mx}{unit}'
            if extras and all(re.search(r'외전|번외|특전|특별외전', _strip_filename_parse_noise(Path(fn).stem)) for fn in filenames):
                return extras[0] + ' ' + base
            return base + extras_str
        # 번호 없이 extras만 있는 경우 — 본편 파일이 섞여 있으면 '본편+외전' 형식
        _extra_pat = r'외전|번외|특전|특외'
        has_main = any(
            not re.search(_extra_pat, _strip_filename_parse_noise(Path(fn).stem))
            for fn in filenames
        )
        parts = (['본편'] if has_main else []) + extras
        return '+'.join(parts) if parts else '외전'

    @staticmethod
    def _volume_range_from_toc(grp_files: list) -> str:
        """파일명에 화수가 없을 때 EPUB 내부 NCX에서 챕터 번호를 추출해 범위 반환."""
        import zipfile as _zf
        import html as _hl
        nums = []
        for path, name, *_ in grp_files:
            try:
                with _zf.ZipFile(path, 'r') as z:
                    container = z.read('META-INF/container.xml').decode('utf-8', 'replace')
                    m = re.search(r'full-path="([^"]+\.opf)"', container)
                    if not m: continue
                    opf_dir = str(Path(m.group(1)).parent)
                    opf = z.read(m.group(1)).decode('utf-8', 'replace')
                    ncx_m = re.search(
                        r'<item\s[^>]*media-type=["\']application/x-dtbncx\+xml["\'][^>]*href=["\']([^"\']+)["\']',
                        opf, re.IGNORECASE)
                    if not ncx_m: continue
                    ncx_path = (opf_dir + '/' + ncx_m.group(1)).lstrip('./')
                    if ncx_path not in z.namelist(): ncx_path = ncx_m.group(1)
                    ncx = z.read(ncx_path).decode('utf-8', 'replace')
                    for lbl in re.findall(
                            r'<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>',
                            ncx, re.IGNORECASE | re.DOTALL):
                        lbl = _hl.unescape(re.sub(r'\s+', ' ', lbl)).strip()
                        for pat in (r'(?:제\s*)?(\d+)\s*화', r'(\d+)\s*회\b'):
                            nm = re.search(pat, lbl)
                            if nm:
                                nums.append(int(nm.group(1)))
                                break
            except Exception:
                continue
        if not nums: return ''
        mn, mx = min(nums), max(nums)
        return f'{mn}화' if mn == mx else f'{mn}-{mx}화'

    def _auto_extract_title_fast(self):
        """대량 추가 시 빠른 제목 자동완성.
        기본은 파일명 기반으로 빠르게 처리하되,
        numeric-id(예: 519164_221.epub)처럼 파일명 정보가 약한 경우에는
        첫 파일에 한해 rename 엔진(_guess_new_name) 결과를 보강 사용한다.
        """
        if not self._files:
            return
        first_name = self._files[0][1]
        base_title = self._base_title_from_filename(first_name)
        if not base_title:
            base_title = Path(first_name).stem
        creator = ""

        # numeric-id 또는 빈약한 파일명이면 rename 엔진 결과로 시리즈명/작가 보강
        try:
            _p0, _n0, _ = self._files[0]
            _rn = self._guess_new_name(_p0, _n0)   # 예: [작가] 시리즈명 221화 부제.epub
            _stem = Path(_rn).stem
            _am = re.match(r'^\s*\[([^\]]+)\]\s*(.*)$', _stem)
            if _am:
                creator = _normalize_title(_am.group(1)).strip()
                _stem_wo_author = _am.group(2).strip()
            else:
                _stem_wo_author = _stem
            _series_key = self._zip_series_key(_stem_wo_author + '.epub').strip()
            _fname_weak = bool(re.fullmatch(r'[\d\s._-]+', base_title or ''))
            if _series_key and (_fname_weak or len(_series_key) > len(base_title)):
                base_title = _series_key
        except Exception:
            pass

        # 파일명 기반 base_title이 약하거나 첫 파일이 "화수+소제목" 형식일 때 OPF dc:title 직접 읽기
        # 예) "[0001] 1화. 답답하면 본인이 해보든지.epub"
        #   → _base_title_from_filename은 소제목 "답답하면 본인이 해보든지"를 반환 (잘못된 결과)
        #   → OPF dc:title = "다 해먹는 슈퍼스타 1화" → 정제 → "다 해먹는 슈퍼스타" (진짜 시리즈명)
        _first_stem_raw = Path(self._files[0][1]).stem
        # "[NNNN] N화. 소제목" / "[NNNN] N화_ 소제목" 형식 감지
        _ep_subtitle_fmt = bool(re.match(
            r'^\s*\[\d+\]\s*\d+\s*화\s*[._]', _first_stem_raw))
        _first_has_ep_num = bool(re.search(r'\d+\s*화', self._files[0][1]))
        _base_is_weak = (not base_title
                         or re.fullmatch(r'[\d\s._-]+', base_title)
                         or not re.search(r'[가-힣]{2,}', base_title))
        if _base_is_weak or _first_has_ep_num:
            try:
                import zipfile as _zf2
                _p0b, _, _ = self._files[0]
                with _zf2.ZipFile(_p0b, 'r') as _z2:
                    _cont2 = _z2.read('META-INF/container.xml').decode('utf-8', 'replace')
                    _om2 = re.search(r'full-path="([^"]+\.opf)"', _cont2)
                    if _om2:
                        _opf2 = _z2.read(_om2.group(1)).decode('utf-8', 'replace')
                        _t2 = _clean_opf_series_title(
                            _read_dc_tag(_opf2, 'dc:title'),
                            strip_genre_tag=True, preserve_complete_paren=True)
                        if _t2 and re.search(r'[가-힣]{2,}', _t2):
                            # ① base_title가 약하면 무조건 교체
                            # ② "[NNNN] N화. 소제목" 형식이면 소제목 오인식이므로 OPF 우선
                            # ③ 일반: OPF 결과가 더 길 때만 교체
                            if (_base_is_weak
                                    or _ep_subtitle_fmt
                                    or len(_t2) > len(base_title)):
                                base_title = _t2
            except Exception:
                pass

        rng = self._volume_range([f[1] for f in self._files])
        title_part = f"{base_title} {rng}".strip() if rng else base_title
        auto_name = f'[{creator}] {title_part}' if creator else title_part
        auto_name = _safe_title(auto_name)
        self.fname_edit.setText(auto_name)

    def _auto_extract_title(self):
        """
        제목: 첫 번째 파일의 파일명에서 권수/화수 제거
        작가: 파일명과 OPF 메타가 일치하는 epub에서 dc:creator 추출
              (첫 번째 epub 메타가 오염된 경우 전체 목록을 순회해 일치하는 것 사용)
        범위: 전체 파일 목록 분석 → 1-4권 / 50-55화 / 외전 등
        """
        if not self._files: return
        try:
            # 1. 제목: 파일명 기반 (기준값)
            first_name = self._files[0][1]
            base_title = self._base_title_from_filename(first_name)
            fname_words = set(re.findall(r'\S{2,}', base_title))
            base_has_korean = bool(re.search(r'[가-힣]', base_title))

            # 2. 작가/제목: 전체 epub 순회 → 파일명과 OPF 제목이 일치하는 첫 번째 epub 사용
            creator = ''
            import zipfile as _zf

            def _clean_opf_title(raw: str) -> str:
                t = _clean_opf_series_title(
                    raw, strip_interview=True, protect_edition_paren=True)
                t = re.sub(r'\s*완\s*\([^)]+\)\s*', ' ', t)
                return re.sub(r'\s+', ' ', t).strip()

            for path, name, _ in self._files:
                try:
                    with _zf.ZipFile(path, 'r') as z:
                        container = z.read('META-INF/container.xml').decode('utf-8', 'replace')
                        m = re.search(r'full-path="([^"]+\.opf)"', container)
                        if not m: continue
                        opf = z.read(m.group(1)).decode('utf-8', 'replace')
                        v = _read_dc_tag(opf, 'dc:creator')
                        t = _clean_opf_title(_read_dc_tag(opf, 'dc:title'))
                        opf_words = set(re.findall(r'\S{2,}', t))
                        if t and re.search(r'[가-힣]', t) and \
                                (not base_has_korean or not fname_words or
                         bool(fname_words & opf_words) or
                         (re.sub(r'\s+','',t) and re.sub(r'\s+','',base_title) and
                          (re.sub(r'\s+','',t) in re.sub(r'\s+','',base_title) or
                           re.sub(r'\s+','',base_title) in re.sub(r'\s+','',t)))):
                            base_title = t
                            if v: creator = _normalize_title(v)
                            break
                except Exception:
                    continue

            # 작가 미검출 시: rename 엔진 결과([작가] 제목...)에서 작가명 폴백 추출
            if not creator and self._files:
                try:
                    _p0, _n0, _ = self._files[0]
                    _rn = self._guess_new_name(_p0, _n0)
                    _am = re.match(r'^\s*\[([^\]]+)\]\s+', Path(_rn).stem)
                    if _am:
                        creator = _normalize_title(_am.group(1)).strip()
                except Exception:
                    pass

            # numeric-id 세트에서 OPF 제목이 비어있을 때:
            # rename 엔진 결과(강한 추출) → 부모 폴더명/TOC 라벨 순으로 시리즈명 보강
            if re.fullmatch(r'[\d\s._-]+', base_title or ''):
                try:
                    _p0, _n0, _ = self._files[0]
                    _rn = self._guess_new_name(_p0, _n0)   # 예: [작가] 시리즈명 1화 소제목.epub
                    _stem = re.sub(r'^\[[^\]]+\]\s*', '', Path(_rn).stem).strip()
                    _series_key = self._zip_series_key(_stem + '.epub').strip()
                    if _series_key and not re.fullmatch(r'[\d\s._-]+', _series_key):
                        base_title = _series_key
                except Exception:
                    pass
                _parent_series = _series_from_parent_dir(self._files[0][0])
                if re.fullmatch(r'[\d\s._-]+', base_title or '') and _parent_series:
                    base_title = _parent_series
                elif re.fullmatch(r'[\d\s._-]+', base_title or ''):
                    try:
                        _lbl = self._toc_label_from_file(self._files[0][0], self._files[0][1])
                        _bt = _strip_trailing_volume_suffix(_lbl)
                        if _bt:
                            base_title = _bt
                    except Exception:
                        pass

            # 3. 범위: 전체 파일 목록
            rng = self._volume_range([f[1] for f in self._files])

            # 완결 자동 감지
            # 파일명에 완결 표시가 있으면 자동으로 켜되,
            # 사용자가 저장해 둔 완결 체크 상태를 파일명 자동 감지로 끄지는 않는다.
            has_complete = any(
                re.search(r'완결', Path(f[1]).stem, re.IGNORECASE)
                for f in self._files)
            if has_complete and not self.chk_complete.isChecked():
                self.chk_complete.setChecked(True)

            # 조합
            title_part = f'{base_title} {rng}'.strip() if rng else base_title
            if self.chk_complete.isChecked():
                title_part = title_part.rstrip() + ' (완결)'
            auto_name  = f'[{creator}] {title_part}' if creator else title_part
            auto_name  = _safe_title(auto_name)
            self.fname_edit.setText(auto_name)
        except Exception:
            pass

    def _clear_files(self):
        if not self._files: return
        r = QMessageBox.question(self, "초기화", "목록을 전부 지울까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._files.clear()
            self._toc_titles.clear()
            self._page_title_overrides = {}
            self._scan_results.clear()
            self._title_auto = True
            self.fname_edit.setText("merged")
            self._refresh_list()
            # 리스트 전부 비울 때는 임시 폴더 강제 정리
            self._cleanup_temp_dirs(force=True)

    def _clear_files_after_successful_merge(self):
        """병합 성공 후 같은 목록을 실수로 다시 병합하지 않도록 조용히 초기화."""
        if not self._files:
            return
        self._files.clear()
        self._toc_titles.clear()
        self._page_title_overrides = {}
        self._scan_results.clear()
        self._title_auto = True
        self.fname_edit.setText("merged")
        self._refresh_list()
        self._log("병합 완료: 파일 목록을 초기화했습니다.", "info")

    def _delete_selected(self):
        rows = sorted(
            {self.file_list.row(item) for item in self.file_list.selectedItems()},
            reverse=True)
        if not rows:
            row = self.file_list.currentRow()
            if 0 <= row < len(self._files):
                rows = [row]
        for row in rows:
            if 0 <= row < len(self._files):
                self._files.pop(row)
                if row < len(self._toc_titles):
                    self._toc_titles.pop(row)
        self._refresh_list()
        # 더 이상 참조되지 않는 임시 폴더 정리 (압축에서 추출한 파일이 모두 빠졌으면 삭제)
        self._cleanup_temp_dirs(force=False)

    def _move_up(self):
        row = self.file_list.currentRow()
        if row > 0:
            self._files[row-1], self._files[row] = self._files[row], self._files[row-1]
            if len(self._toc_titles) > row:
                self._toc_titles[row-1], self._toc_titles[row] = self._toc_titles[row], self._toc_titles[row-1]
            self._refresh_list(); self.file_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.file_list.currentRow()
        if 0 <= row < len(self._files) - 1:
            self._files[row], self._files[row+1] = self._files[row+1], self._files[row]
            if len(self._toc_titles) > row + 1:
                self._toc_titles[row], self._toc_titles[row+1] = self._toc_titles[row+1], self._toc_titles[row]
            self._refresh_list(); self.file_list.setCurrentRow(row + 1)

    def _on_order_changed(self):
        """수동 드래그 후 self._files 순서를 UI 순서에 맞게 동기화.
        toc_titles 도 같이 재정렬해서 목차 편집 시 반영되게 함.
        """
        # 기존 path → toc_title 매핑 저장
        old_titles = {self._files[i][0]: self._toc_titles[i]
                      for i in range(min(len(self._files), len(self._toc_titles)))}
        new_order = []
        for i in range(self.file_list.count()):
            path = self.file_list.item(i).data(Qt.ItemDataRole.UserRole)
            e = next((f for f in self._files if f[0] == path), None)
            if e: new_order.append(e)
        self._files = new_order
        # toc_titles 도 새 순서에 맞게 재정렬
        self._toc_titles = [old_titles.get(f[0], Path(f[1]).stem)
                            for f in self._files]
        self._refresh_list_nums()

    # ── 정렬 ────────────────────────────────────────
    def _do_auto_sort(self):
        self._files.sort(key=lambda f: natural_sort_key(f[1]))

    def _auto_sort(self):
        if not self._files: return
        self._do_auto_sort(); self._refresh_list()
        self._log("↕ 자동 정렬 완료", "ok")

    def _on_complete_toggle(self, checked: bool):
        cur = self.fname_edit.text()
        cur = re.sub(r'\s*\(완결\)\s*$', '', cur).strip()
        if checked:
            cur = cur + ' (완결)'
        self.fname_edit.setText(cur)

    def _on_manual_toggle(self, state):
        self._manual_mode = bool(state)
        if self._manual_mode:
            # 수동 모드: 내부 재정렬 드래그
            self.file_list.setDragDropMode(
                QAbstractItemView.DragDropMode.InternalMove)
            self.b_up.setEnabled(True); self.b_down.setEnabled(True)
        else:
            # 자동 모드: 외부 파일 드롭만 허용 (DragDrop 유지)
            self.file_list.setDragDropMode(
                QAbstractItemView.DragDropMode.DragDrop)
            self.b_up.setEnabled(False); self.b_down.setEnabled(False)

    # ── 리스트 렌더링 ──────────────────────────────
    def _refresh_list(self):
        from PyQt6.QtGui import QColor
        cur = self.file_list.currentRow()
        self.file_list.clear()
        self._path_to_row.clear()
        self._file_meta.clear()
        if not self._files:
            self.file_list.set_has_files(False)
            self.count_lbl.setText("0개")
            return
        _THRESHOLD = 5  # 이 이하는 유의미한 공백코드로 보지 않음
        for i, (path, name, size) in enumerate(self._files):
            self._path_to_row[path] = i
            self._file_meta[path] = (name, size)
            scan = self._scan_results.get(path)
            if scan is None:
                badge = "  🔍"
                tooltip = path
            elif scan[0] < 0:
                badge = ""
                tooltip = path
            elif scan[0] > _THRESHOLD:
                total, counts = scan
                has_token = 'book-token' in counts
                details = []
                if total > 0:
                    details.append(f"공백코드 {total}개: " + ", ".join(
                        f"{k}({v})" for k, v in counts.items() if k != 'book-token'))
                if has_token:
                    details.append(f"book-token {counts['book-token']}개")
                badge = f"  ⚠ {total}개" if total > 0 else "  ⚠ token"
                tooltip = path + "\n" + "\n".join(details)
            else:
                # total==0 이거나 임계값 이하 — book-token은 개수 무관 표시
                counts = scan[1]
                if 'book-token' in counts:
                    badge = f"  ⚠ token"
                    tooltip = path + f"\nbook-token {counts['book-token']}개"
                else:
                    badge = "  ✓"
                    tooltip = path
            item = QListWidgetItem(f"  {i+1:02d}.  {name}  ({size}){badge}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(tooltip)
            _s = scan[1] if scan and scan[0] >= 0 else {}
            _has_invis = scan is not None and (scan[0] > _THRESHOLD or 'book-token' in _s)
            if _has_invis:
                item.setForeground(QColor(C["orange"]))
                item.setBackground(QColor("#fff3e0"))
            elif scan is not None and scan[0] >= 0:
                item.setForeground(QColor(C["text"]))
            self.file_list.addItem(item)
        if 0 <= cur < self.file_list.count():
            self.file_list.setCurrentRow(cur)
        self.count_lbl.setText(f"{len(self._files)}개")

    def _refresh_list_nums(self):
        from PyQt6.QtGui import QColor
        self._path_to_row.clear()
        self._file_meta.clear()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            e = next((f for f in self._files if f[0] == path), None)
            if not e:
                continue
            self._path_to_row[path] = i
            self._file_meta[path] = (e[1], e[2])
            _THRESHOLD = 10
            scan = self._scan_results.get(path)
            if scan is None:
                badge = "  🔍"
            elif scan[0] < 0:
                badge = ""
            elif scan[0] > _THRESHOLD:
                badge = f"  ⚠ {scan[0]}개"
                item.setForeground(QColor(C["orange"]))
                item.setBackground(QColor("#fff3e0"))
            else:
                if 'book-token' in scan[1]:
                    badge = "  ⚠ token"
                    item.setForeground(QColor(C["orange"]))
                    item.setBackground(QColor("#fff3e0"))
                else:
                    badge = "  ✓"
                    item.setForeground(QColor(C["text"]))
            item.setText(f"  {i+1:02d}.  {e[1]}  ({e[2]}){badge}")
        self.count_lbl.setText(f"{len(self._files)}개")


    # ── 공백코드 스캔 ──────────────────────────────
    def _start_scan(self, paths: list):
        """paths 리스트를 백그라운드에서 스캔 시작."""
        if self._scan_worker and self._scan_worker.isRunning():
            # 이전 워커가 살아있으면 새 경로는 아직 없는 것만 추가
            # (간단하게: 이전 워커 완료 후 남은 건 _add_files 재호출 시 처리됨)
            # 여기서는 실행 중인 워커를 교체하지 않고 현재 paths만 바로 스캔
            pass
        self._scan_worker = ScanWorker(paths)
        self._scan_worker.scan_done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, path: str, total: int, counts: dict):
        """스캔 결과 수신 → 리스트 해당 항목 업데이트."""
        self._scan_results[path] = (total, counts)
        row = self._path_to_row.get(path)
        if row is None or row >= self.file_list.count():
            return
        item = self.file_list.item(row)
        if not item:
            return

        from PyQt6.QtGui import QColor
        name, size = self._file_meta.get(path, (Path(path).name, human_size(os.path.getsize(path)) if os.path.exists(path) else ""))
        if total < 0:
            badge = ""
        elif total > 10:
            badge = f"  ⚠ {total}개"
            item.setForeground(QColor(C["orange"]))
            item.setBackground(QColor("#fff3e0"))
            details = []
            details.append(f"공백코드 {total}개: " + ", ".join(
                f"{k}({v})" for k, v in counts.items() if k != 'book-token'))
            if 'book-token' in counts:
                details.append(f"book-token {counts['book-token']}개")
            item.setToolTip(path + "\n" + "\n".join(details))
        else:
            if 'book-token' in counts:
                badge = "  ⚠ token"
                item.setForeground(QColor(C["orange"]))
                item.setBackground(QColor("#fff3e0"))
                item.setToolTip(path + f"\nbook-token {counts['book-token']}개")
            else:
                badge = "  ✓"
                item.setForeground(QColor(C["text"]))
        item.setText(f"  {row+1:02d}.  {name}  ({size}){badge}")

    # ── 저장 폴더 ──────────────────────────────────
    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "저장 폴더 선택", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)
            self._settings.setValue("last_merge_dir", d)

    # ── 로그 ───────────────────────────────────────
    def _log(self, msg, tag="info"):
        if tag == "html":
            self.log_area.append(msg)
            return
        colors = {
            "ok":   C["text"],
            "err":  C["red"],
            "warn": C["orange"],
            "info": C["text3"],
        }
        color = colors.get(tag, C["text3"])
        self.log_area.append(
            f'<span style="color:{color};font-size:11px;">{msg}</span>')

    # ── 시리즈 그룹핑 ─────────────────────────────
    def _group_by_series(self):
        """
        self._files 를 시리즈별로 그룹핑.
        반환: list of (group_files, group_toc_titles)
              group_files = [(path, name, size_str), ...]
        그룹이 1개면 기존 단일 병합과 동일.
        """
        # toc_titles 길이 보정
        toc = list(self._toc_titles)
        while len(toc) < len(self._files):
            toc.append(Path(self._files[len(toc)][1]).stem)

        # 각 파일의 시리즈 키 추출
        # _base_title_from_filename 는 사람이 읽기 좋은 라벨용이고,
        # 그룹 키는 _zip_series_key(공백/권화 변형 내성 높음)를 우선 사용한다.
        groups: dict[str, list] = {}   # series_key → [(file_entry, toc_title), ...]
        order:  list[str]       = []   # 삽입 순서 유지
        for i, f in enumerate(self._files):
            _name = f[1]
            _pretty = self._base_title_from_filename(_name)
            _key_src = self._zip_series_key(_name) or _pretty or Path(_name).stem
            _key = re.sub(r'\s+', '', _normalize_title(_key_src)).strip().lower()
            if not _key:
                _key = re.sub(r'\s+', '', _normalize_title(Path(_name).stem)).strip().lower()

            if _key not in groups:
                groups[_key] = []
                order.append(_key)
            groups[_key].append((f, toc[i]))

        result = []
        for _k in order:
            items = groups[_k]
            grp_files = [x[0] for x in items]
            grp_tocs  = [x[1] for x in items]
            result.append((grp_files, grp_tocs))
        return result

    def _auto_fname_for_group(self, grp_files):
        """그룹 파일 리스트에서 출력 파일명 자동 생성 (확장자 제외)."""
        if not grp_files:
            return "merged"
        try:
            first_name = grp_files[0][1]
            base_title = self._base_title_from_filename(first_name)
            fname_words = set(re.findall(r'\S{2,}', base_title))
            base_has_korean = bool(re.search(r'[가-힣]', base_title))

            creator = ''
            import zipfile as _zf

            def _clean_opf_title(raw: str) -> str:
                t = _clean_opf_series_title(
                    raw, strip_interview=True, protect_edition_paren=True)
                t = re.sub(r'\s*완\s*\([^)]+\)\s*', ' ', t)
                return re.sub(r'\s+', ' ', t).strip()

            for path, name, _ in grp_files:
                try:
                    with _zf.ZipFile(path, 'r') as z:
                        container = z.read('META-INF/container.xml').decode('utf-8', 'replace')
                        m = re.search(r'full-path="([^"]+\.opf)"', container)
                        if not m: continue
                        opf_fname = m.group(1)
                        opf_dir_z = str(Path(opf_fname).parent)
                        opf = z.read(opf_fname).decode('utf-8', 'replace')
                        v = _read_dc_tag(opf, 'dc:creator')
                        # creator는 타이틀 매칭 여부와 무관하게 첫 번째로 발견된 값 사용
                        if not creator and v:
                            creator = _normalize_title(v)
                        t = _clean_opf_title(_read_dc_tag(opf, 'dc:title'))
                        # dc:title이 너무 짧으면 NCX navLabel / h2 title 속성에서 시리즈명 추출
                        if not t or len(re.findall(r'[가-힣]{2,}', t)) == 0:
                            # ① NCX navLabel(들) 중 화수 없는 긴 것 시도
                            try:
                                _ncx_href = re.search(
                                    r'<item\s[^>]*media-type=["\']application/x-dtbncx\+xml["\'][^>]*href=["\']([^"\']+)["\']'
                                    r'|<item\s[^>]*href=["\']([^"\']*toc\.ncx)["\']',
                                    opf, re.IGNORECASE)
                                if _ncx_href:
                                    _nv = _ncx_href.group(1) or _ncx_href.group(2)
                                    _nfull = (opf_dir_z + '/' + _nv).lstrip('./') if opf_dir_z != '.' else _nv
                                    if _nfull not in z.namelist(): _nfull = _nv
                                    _ncx = z.read(_nfull).decode('utf-8', 'replace')
                                    import html as _html_af
                                    for _nm in re.finditer(
                                            r'<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>',
                                            _ncx, re.IGNORECASE | re.DOTALL):
                                        _lbl = _html_af.unescape(re.sub(r'\s+', ' ', _nm.group(1))).strip()
                                        _lbl = re.sub(r'\s*\(연재중?\)\s*', '', _lbl).strip()
                                        # 화/권 번호가 없고 3어절 이상인 라벨 = 시리즈명
                                        if (not re.search(r'\d+\s*[화권부]', _lbl)
                                                and len(re.findall(r'[가-힣]+', _lbl)) >= 2
                                                and len(_lbl) >= 6):
                                            t = _lbl
                                            break
                            except Exception:
                                pass
                            # ② 첫 본문 xhtml의 h2~h3 title 속성
                            if not t or len(re.findall(r'[가-힣]{2,}', t)) == 0:
                                try:
                                    _spine_ids = re.findall(
                                        r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf)
                                    _mf = {}
                                    for _mm in re.finditer(r'<item\s([^>]*?)/?>', opf, re.IGNORECASE):
                                        _mid = re.search(r'\bid=["\']([^"\']+)["\']', _mm.group(1))
                                        _mh  = re.search(r'\bhref=["\']([^"\']+)["\']', _mm.group(1))
                                        if _mid and _mh: _mf[_mid.group(1)] = _mh.group(1)
                                    for _sid in _spine_ids[:3]:
                                        _sh = _mf.get(_sid, '')
                                        if not _sh: continue
                                        _sf = (opf_dir_z + '/' + _sh).lstrip('./') if opf_dir_z != '.' else _sh
                                        if _sf not in z.namelist(): _sf = _sh
                                        _sraw = z.read(_sf).decode('utf-8', 'replace')
                                        _ta = re.search(
                                            r'<h[1-6][^>]+\btitle=["\']([^"\']{6,})["\']',
                                            _sraw, re.IGNORECASE)
                                        if _ta:
                                            _tv = _ta.group(1).strip()
                                            _tv = re.sub(r'\s*\(연재중?\)\s*', '', _tv).strip()
                                            if len(re.findall(r'[가-힣]+', _tv)) >= 2:
                                                t = _tv
                                                break
                                except Exception:
                                    pass
                        opf_words = set(re.findall(r'\S{2,}', t))
                        if t and re.search(r'[가-힣]', t) and \
                                (not base_has_korean or not fname_words or
                                 bool(fname_words & opf_words) or
                                 (re.sub(r'\s+','',t) in re.sub(r'\s+','',base_title) or
                                  re.sub(r'\s+','',base_title) in re.sub(r'\s+','',t))):
                            base_title = t
                            break
                        elif t and not base_has_korean and len(re.findall(r'[가-힣]{2,}', t)) >= 2:
                            # 파일명에 한글 없는 경우(숫자 파일명 등): 타이틀 조건 완화해서 사용
                            base_title = t
                            break
                except Exception:
                    continue

            # 작가 미검출 시: rename 엔진 결과([작가] 제목...)에서 작가명 폴백 추출
            if not creator and grp_files:
                try:
                    _p0, _n0, _ = grp_files[0]
                    _rn = self._guess_new_name(_p0, _n0)
                    _am = re.match(r'^\s*\[([^\]]+)\]\s+', Path(_rn).stem)
                    if _am:
                        creator = _normalize_title(_am.group(1)).strip()
                except Exception:
                    pass
            # 그래도 없으면 첫 파일의 판권/끝페이지에서 작가명 직접 추출
            if not creator and grp_files:
                try:
                    with _zf.ZipFile(grp_files[0][0], 'r') as _z0:
                        _xhtmls = [n for n in _z0.namelist()
                                   if n.lower().endswith(('.xhtml', '.html', '.htm'))]
                        _kw = ('endpg', 'end_page', 'copyright', 'copy', 'colophon', 'imprint')
                        _cand = [n for n in _xhtmls if any(k in n.lower() for k in _kw)]
                        if not _cand:
                            _cand = _xhtmls[-5:]
                        for _cn in _cand:
                            try:
                                _raw = _z0.read(_cn).decode('utf-8', 'replace')
                            except Exception:
                                continue
                            _fc = _extract_creator_from_html(_raw)
                            if _fc:
                                creator = _normalize_title(_fc).strip()
                                break
                except Exception:
                    pass

            # numeric-id 그룹에서 OPF 제목이 비어있을 때:
            # rename 엔진 결과(강한 추출) → 부모 폴더명/TOC 라벨 순으로 시리즈명 보강
            if re.fullmatch(r'[\d\s._-]+', base_title or ''):
                try:
                    _p0, _n0, _ = grp_files[0]
                    _rn = self._guess_new_name(_p0, _n0)
                    _stem = re.sub(r'^\[[^\]]+\]\s*', '', Path(_rn).stem).strip()
                    _series_key = self._zip_series_key(_stem + '.epub').strip()
                    if _series_key and not re.fullmatch(r'[\d\s._-]+', _series_key):
                        base_title = _series_key
                except Exception:
                    pass
                _parent_series = _series_from_parent_dir(grp_files[0][0])
                if re.fullmatch(r'[\d\s._-]+', base_title or '') and _parent_series:
                    base_title = _parent_series
                elif re.fullmatch(r'[\d\s._-]+', base_title or ''):
                    try:
                        _lbl = self._toc_label_from_file(grp_files[0][0], grp_files[0][1])
                        _bt = _strip_trailing_volume_suffix(_lbl)
                        if _bt:
                            base_title = _bt
                    except Exception:
                        pass

            rng = self._volume_range([f[1] for f in grp_files])
            # 파일명에 화수 없으면 NCX 목차에서 챕터 범위 추출
            if not rng:
                rng = self._volume_range_from_toc(grp_files)
            has_complete = any(
                re.search(r'완결', Path(f[1]).stem, re.IGNORECASE)
                for f in grp_files)
            title_part = f'{base_title} {rng}'.strip() if rng else base_title
            if has_complete:
                title_part = title_part.rstrip() + ' (완결)'
            auto_name = f'[{creator}] {title_part}' if creator else title_part
            return _safe_title(auto_name)
        except Exception:
            return Path(grp_files[0][1]).stem

    # ── 타임스탬프 파싱 ─────────────────────────────
    def _get_timestamp(self):
        """chk_timestamp + date_edit에서 (y, mo, d, 0, 0, 0) 반환. 미체크·파싱 실패 시 None."""
        if not self.chk_timestamp.isChecked():
            return None
        try:
            parts = re.split(r'[-/.]', self.date_edit.text().strip())
            y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
            return (y, mo, d, 0, 0, 0)
        except Exception:
            return None

    # ── 코드만 제거 실행 ────────────────────────────
    def _start_strip_only(self):
        """파일 목록의 EPUB 각각에 대해 공백코드 + 판권·표지·목차 제거 후 저장."""
        if not self._files:
            QMessageBox.warning(self, "파일 없음", "EPUB 파일을 1개 이상 추가해주세요.")
            return

        out_dir = self.dir_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "저장 위치 없음", "저장 위치를 설정해주세요.")
            return

        n = len(self._files)
        r = QMessageBox.question(
            self, "코드만 제거 확인",
            f"총 {n}개 파일을 정제합니다.\n\n"
            f"• 공백 유니코드(U+200B 등) 제거\n"
            f"• 판권·표지·목차 페이지 제거\n\n"
            f"저장 위치: {out_dir}\n\n"
            f"원본과 동일한 파일명으로 저장됩니다. 진행할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return

        self.strip_btn.setEnabled(False)
        self.merge_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.log_area.clear()
        self._log(f"🧹 코드만 제거 시작 — {n}개 파일", "info")

        self._strip_worker = StripOnlyWorker(
            self._files, out_dir,
            timestamp       = self._get_timestamp(),
            compress_images = self.chk_compress.isChecked(),
            noise_level     = int(self.noise_combo.currentText()) if self.chk_noise.isChecked() else 0,
        )
        self._strip_worker.log_signal.connect(self._log)
        self._strip_worker.progress_signal.connect(self.prog_bar.setValue)
        self._strip_worker.done_signal.connect(self._on_strip_done)
        self._strip_worker.start()

    def _on_strip_done(self, ok: int, fail: int, total_pages: int, total_chars: int):
        self.strip_btn.setEnabled(True)
        self.merge_btn.setEnabled(True)
        self.prog_bar.setValue(100)

        summary_parts = [f"✅ {ok}개 처리 완료"]
        if total_chars > 0:
            summary_parts.append(f"공백코드 총 {total_chars:,}개 제거")
        if total_pages > 0:
            summary_parts.append(f"판권·표지·목차 총 {total_pages}페이지 제거")
        if fail > 0:
            summary_parts.append(f"❌ {fail}개 실패")
        summary = " / ".join(summary_parts)
        self._log(f"\n── {summary}", "ok")

        out_dir = self.dir_edit.text().strip()
        self._open_folder_confirm(
            out_dir, title="완료",
            pre_msg=f"{summary}\n\n저장 위치: {out_dir}")

    # ── 병합 실행 ──────────────────────────────────
    def _start_merge(self):
        if len(self._files) < 2:
            QMessageBox.warning(self, "파일 부족",
                                "EPUB 파일을 2개 이상 추가해주세요.")
            return

        # 병합 시작은 항상 "현재 목록 전체"를 단일 합본으로 생성한다.
        # (시리즈 분할은 ZIP 묶기/이름변경 쪽에서 처리)
        fname = self.fname_edit.text().strip() or "merged"
        if not fname.endswith(".epub"):
            fname += ".epub"
        titles = list(self._toc_titles)
        while len(titles) < len(self._files):
            titles.append(Path(self._files[len(titles)][1]).stem)
        queue = [(
            list(self._files),
            titles[:len(self._files)],
            os.path.join(self.dir_edit.text(), fname)
        )]

        self._merge_queue   = queue          # 남은 그룹 큐
        self._merge_total   = len(queue)     # 전체 그룹 수
        self._merge_done    = 0              # 완료된 수
        self._merge_failed  = []             # 실패 파일명
        self._merge_outputs = []             # 성공 산출물 경로
        self._missing_cover_prompted = set()

        self.merge_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.log_area.clear()

        self._log(f"📦 목록 {len(self._files)}개 → 단일 합본 생성 시작", "info")

        self._run_next_merge()

    def _run_next_merge(self):
        """큐에서 다음 그룹 병합 시작."""
        if not self._merge_queue:
            return
        grp_files, grp_tocs, out_path = self._merge_queue.pop(0)

        # 사용자가 직접 표지를 지정하지 않았으면 그룹마다 표지 후보를 새로 선택
        if not self._cover_user_set:
            self._custom_cover     = None
            self._custom_cover_ext = '.jpg'
            self._extra_front_covers = []
            try:
                self._maybe_prompt_cover_choice(grp_files[0][0])
            except Exception as e:
                self._log(f"⚠ 표지 후보 점검 실패: {e}", "warn")
            try:
                missing_cover_prompted = self._maybe_prompt_missing_cover_search(
                    grp_files[0][0],
                    suggested_title=re.sub(r'^\[[^\]]+\]\s*', '', Path(out_path).stem).strip(),
                )
                if missing_cover_prompted and not self._custom_cover:
                    self._merge_queue = []
                    self.merge_btn.setEnabled(True)
                    self.merge_btn.setText("✨ 병합 시작")
                    self._log("표지 없음: 합본을 중단했습니다. 표지 설정 후 다시 실행해주세요.", "warn")
                    return
            except Exception as e:
                self._log(f"표지 없음 안내 실패: {e}", "warn")

        idx = self._merge_total - len(self._merge_queue)  # 현재 순번
        if self._merge_total > 1:
            self.merge_btn.setText(f"⏳  병합 중... ({idx}/{self._merge_total})")
            self._log(f"── [{idx}/{self._merge_total}] {Path(out_path).name}", "info")
        else:
            self.merge_btn.setText("⏳  병합 중...")

        self.prog_bar.setValue(0)

        # toc_titles 길이 보정
        titles = list(grp_tocs)
        while len(titles) < len(grp_files):
            titles.append(Path(grp_files[len(titles)][1]).stem)

        self._worker = MergeWorker(
            epub_files            = [f[0] for f in grp_files],
            output_path           = out_path,
            title                 = re.sub(r'^\[[^\]]+\]\s*', '', Path(out_path).stem).strip(),
            add_toc               = False,
            toc_titles            = titles[:len(grp_files)],
            custom_cover          = self._custom_cover,
            custom_cover_ext      = self._custom_cover_ext,
            extra_front_covers    = self._extra_front_covers,
            page_title_overrides  = getattr(self, '_page_title_overrides', {}),
            compress_images       = self.chk_compress.isChecked(),
            timestamp             = self._get_timestamp(),
            # UI 체크박스는 '권 목차' 의미이므로 내부 flat_toc(단일화)와 반대로 전달
            flat_toc              = (not self.chk_flat_toc.isChecked()),
            keep_vol_covers       = self.chk_vol_covers.isChecked(),
        )
        self._worker.log_signal.connect(self._log)
        self._worker.progress_signal.connect(self.prog_bar.setValue)
        self._worker.cover_missing_signal.connect(
            self._on_worker_cover_missing,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.done_signal.connect(self._on_done)
        self._worker.start()

    # ── 표지 선택 ─────────────────────────────────
    def _set_cover(self, data: bytes, ext: str, label: str):
        self._custom_cover     = data
        self._custom_cover_ext = ext
        self._cover_user_set   = True
        self.cover_lbl.setVisible(True)
        kb = len(data) // 1024
        self.cover_lbl.setText(f"{label}  ({kb:,} KB)")
        self.cover_lbl.setStyleSheet(
            f"color:{C['green']};font-size:11px;background:transparent;")
        self.b_cover_clear.setVisible(True)   # ✕ 버튼 표시
        self._log(f"🖼 표지 설정: {label}  ({kb:,} KB)", "ok")
        self._txt_update_cover_label()

    def _clear_cover(self):
        self._custom_cover     = None
        self._custom_cover_ext = '.jpg'
        self._extra_front_covers = []
        self._cover_user_set   = False
        self.cover_lbl.setVisible(False)
        self.cover_lbl.setText("1권에서 자동 추출")
        self.cover_lbl.setStyleSheet(
            f"color:{C['text3']};font-size:11px;background:transparent;")
        self.b_cover_clear.setVisible(False)   # ✕ 버튼 숨김
        self._txt_update_cover_label()

    # ── 표지 후보 선택 다이얼로그 (수동 호출) ──
    def _open_cover_picker(self):
        """전체 병합 목록에서 표지 후보를 모아 다이얼로그를 연다."""
        if not self._files:
            QMessageBox.information(self, "알림", "먼저 EPUB 파일을 추가해주세요.")
            return
        first_path = self._files[0][0]
        try:
            with open(first_path, 'rb') as f:
                eb = f.read()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"1권 파일을 읽을 수 없습니다:\n{e}")
            return
        cands = extract_cover_candidates(eb, include_all_images=False)
        if not cands:
            QMessageBox.information(self, "알림",
                "1권 EPUB 안에서 표지 후보 이미지를 찾지 못했습니다.\n"
                "[모든 이미지 표시] 옵션을 켜면 삽화 등도 볼 수 있습니다.")
            # 모든 이미지로 다시 시도
            cands = extract_cover_candidates(eb, include_all_images=True)
            if not cands:
                return
        # 권별 전환용 파일 목록 구성 (toc_titles가 있으면 사용, 없으면 파일명)
        _all_vols = []
        for _vi, (_vp, _vn, _) in enumerate(self._files):
            _vlbl = (self._toc_titles[_vi] if _vi < len(self._toc_titles)
                     else _vn)
            _all_vols.append((_vp, _vlbl))
        dlg = CoverPickerDialog(
            self, cands,
            show_apply_to_all=False,        # 수동 호출은 시리즈 적용 옵션 불필요
            show_browse_toggle=True,        # 모든 이미지 토글
            epub_bytes=eb,
            file_label=Path(first_path).name,
            all_epub_files=_all_vols)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data, ext, label, _ = dlg.get_choice()
            if data:
                self._set_cover(data, ext, f"📁 {label}")
                self._extra_front_covers = dlg.get_extra_front_covers()
                total_cover_count = 1 + len(self._extra_front_covers)
                if self._extra_front_covers:
                    self._log(
                        f"   → 총 표지 {total_cover_count}개 선택 (대표 1개 + 추가 {len(self._extra_front_covers)}개)",
                        "info",
                    )
        # 삭제 요청 이미지 처리 — 권별로 각각 처리
        deleted_by_vol = dlg.get_deleted_by_vol()
        for _dvp, _dfns in deleted_by_vol.items():
            if _dfns:
                self._delete_epub_images(_dvp, _dfns)

    # ── 합본 시작 시 표지 후보 다중 감지 ──
    def _maybe_prompt_cover_choice(self, first_epub_path: str) -> bool:
        """전체 목록에 표지 후보가 2개 이상이고 사용자 지정 표지가 없으면 다이얼로그를 띄운다.
        반환: 계속 진행해도 되면 True, 사용자가 취소(=닫기)했어도 자동선택으로 진행 True.
        실패/예외 시에도 True (방해하지 않음).
        """
        if self._custom_cover:
            return True
        try:
            with open(first_epub_path, 'rb') as f:
                eb = f.read()
            cands = extract_cover_candidates(eb, include_all_images=False)
        except Exception:
            return True
        _all_vols = []
        for _vi, (_vp, _vn, _) in enumerate(self._files):
            _vlbl = (self._toc_titles[_vi] if _vi < len(self._toc_titles)
                     else _vn)
            _all_vols.append((_vp, _vlbl))
        all_count = 0
        try:
            for _vp, _vlbl in _all_vols:
                with open(_vp, 'rb') as _vf:
                    all_count += len(extract_cover_candidates(_vf.read(), include_all_images=False))
        except Exception:
            all_count = len(cands)
        if all_count < 2:
            return True
        # 경고 로그
        names = ', '.join(f"{os.path.basename(c['filename'])}({c['size']//1024:,}KB)" for c in cands)
        self._log(f"⚠ 전체 목록에서 표지 후보 {all_count}개 감지", "warn")
        self._log("   기본값은 OPF 메타데이터를 따르지만, 잘못된 경우가 있어 선택 다이얼로그를 엽니다.", "info")
        dlg = CoverPickerDialog(
            self, cands,
            show_apply_to_all=True,
            show_browse_toggle=True,
            epub_bytes=eb,
            file_label="전체 표지 후보",
            all_epub_files=_all_vols)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data, ext, label, apply_all = dlg.get_choice()
            if data:
                self._set_cover(data, ext, f"📁 {label}")
                self._extra_front_covers = dlg.get_extra_front_covers()
                total_cover_count = 1 + len(self._extra_front_covers)
                if self._extra_front_covers:
                    self._log(
                        f"   → 총 표지 {total_cover_count}개를 합본 앞부분에 넣습니다. "
                        f"(대표 1개 + 추가 {len(self._extra_front_covers)}개)",
                        "info",
                    )
                if not apply_all:
                    self._log("   (이 선택은 1권에만 적용 — 시리즈 전체 적용 해제됨)", "info")
        else:
            self._log("   → 자동 선택(기본값) 그대로 진행", "info")
        # 삭제 요청 이미지 처리 (다이얼로그 종료 후, 수락/취소 관계없이)
        deleted = dlg.get_deleted_filenames()
        if deleted:
            self._delete_epub_images(first_epub_path, deleted)
        return True

    def _show_missing_cover_search_prompt(self, epub_path: str, suggested_title: str = "") -> bool:
        """표지 없음 안내를 띄우고, 사용자가 원하면 구글 이미지 검색을 연다."""
        _key = os.path.abspath(epub_path)
        if _key in getattr(self, "_missing_cover_prompted", set()):
            return False
        self._missing_cover_prompted.add(_key)

        title = (suggested_title or Path(epub_path).stem).strip()
        title = re.sub(r'\s+', ' ', title)
        query = f"{title} 표지".strip()
        search_url = "https://www.google.com/search?tbm=isch&q="

        choice = QMessageBox.question(
            self,
            "표지 없음",
            "1권 EPUB에서 표지 이미지를 찾지 못했습니다.\n\n"
            f"파일: {Path(epub_path).name}\n"
            f"검색어: {query}\n\n"
            "구글 이미지 검색 창을 열까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            self._log(f"표지 없음 감지 (검색 취소): {query}", "warn")
            return True

        opened = False
        try:
            import webbrowser
            from urllib.parse import quote_plus
            opened = bool(webbrowser.open(search_url + quote_plus(query)))
        except Exception as e:
            self._log(f"구글 검색창 자동 열기 실패: {e}", "warn")

        if not opened:
            self._log(f"브라우저 자동 열기 실패: {search_url + query}", "warn")
            opened = True

        if not opened:
            QMessageBox.information(
                self,
                "브라우저 열기 실패",
                "기본 브라우저를 자동으로 열지 못했습니다.\n"
                "아래 주소를 직접 열어주세요.\n\n"
                + search_url + query,
            )
        return True

    def _maybe_prompt_missing_cover_search(self, first_epub_path: str, suggested_title: str = "") -> bool:
        """1권 EPUB에 추출 가능한 표지가 없으면 검색 안내를 띄운다."""
        if self._custom_cover:
            return False
        _key = os.path.realpath(first_epub_path)
        if _key in getattr(self, "_missing_cover_prompted", set()):
            return False
        try:
            with open(first_epub_path, "rb") as f:
                eb = f.read()
            cover_data, _cover_ext = extract_cover_image(eb)
            if cover_data:
                return False
            try:
                cands = extract_cover_candidates(eb, include_all_images=True)
            except Exception:
                cands = []
            if cands:
                return False
        except Exception:
            return self._show_missing_cover_search_prompt(first_epub_path, suggested_title)
        return self._show_missing_cover_search_prompt(first_epub_path, suggested_title)

    def _on_worker_cover_missing(self, epub_path: str, suggested_title: str):
        if self._custom_cover:
            return
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(
            0,
            lambda: self._show_missing_cover_search_prompt(epub_path, suggested_title),
        )

    # ── EPUB 이미지 삭제 헬퍼 ──────────────────────────────
    def _delete_epub_images(self, epub_path: str, filenames_to_delete: set):
        """EPUB 파일에서 지정된 이미지를 제거하고 덮어씁니다.
        - ZIP 내 이미지 파일 제거
        - OPF manifest에서 해당 항목 제거
        - 해당 이미지만 포함하는 xhtml 표지 페이지 제거 (내용이 이미지 하나뿐인 경우)
        """
        try:
            import zipfile, io as _io2
            with open(epub_path, 'rb') as _f:
                original = _f.read()

            # 삭제 대상 basename (소문자)
            del_basenames = {Path(fn).name.lower() for fn in filenames_to_delete}

            # OPF 경로 확인
            opf_name = None
            opf_content = None
            xhtml_to_remove = set()  # 이미지만 포함한 xhtml 페이지 제거 후보

            with zipfile.ZipFile(_io2.BytesIO(original), 'r') as _zin:
                try:
                    container = _zin.read('META-INF/container.xml').decode('utf-8', 'replace')
                    _m = re.search(r'full-path=["\']([^"\']+\.opf)["\']', container)
                    if _m:
                        opf_name    = _m.group(1)
                        opf_content = _zin.read(opf_name).decode('utf-8', 'replace')
                except Exception:
                    pass

                # 삭제 이미지만 포함한 xhtml 페이지 찾기
                opf_dir_z = '/'.join(opf_name.split('/')[:-1]) if opf_name and '/' in opf_name else ''
                for _info in _zin.infolist():
                    if not _info.filename.lower().endswith(('.xhtml', '.html', '.htm')):
                        continue
                    try:
                        _raw_x = _zin.read(_info.filename).decode('utf-8', 'replace')
                        # img src들을 추출
                        _img_srcs = re.findall(r'<img\b[^>]+src=["\']([^"\']+)["\']',
                                               _raw_x, re.IGNORECASE)
                        if not _img_srcs:
                            continue
                        # 페이지 텍스트 (태그·스타일 제거)
                        _txt = re.sub(r'<style[^>]*>.*?</style>', '', _raw_x,
                                      flags=re.DOTALL | re.IGNORECASE)
                        _txt = re.sub(r'<[^>]+>', '', _txt)
                        _txt = re.sub(r'\s+', ' ', _txt).strip()
                        # 이미지만 있고 텍스트가 거의 없으며, 모든 img가 삭제 대상이면 페이지 통째 제거
                        all_imgs_deleted = all(
                            Path(src).name.lower() in del_basenames for src in _img_srcs)
                        if all_imgs_deleted and len(_txt) < 80:
                            xhtml_to_remove.add(_info.filename)
                    except Exception:
                        pass

            # OPF 수정: manifest 항목 제거 + spine 항목 제거
            if opf_content:
                all_del = del_basenames | {Path(fn).name.lower() for fn in xhtml_to_remove}
                # manifest item 제거
                opf_content = re.sub(
                    r'<item\b[^>]+href=["\'][^"\']*["\'][^>]*/?>',
                    lambda m: '' if any(
                        Path(re.search(r'href=["\']([^"\']+)["\']', m.group()).group(1)).name.lower()
                        in all_del for _ in [1]) else m.group(),
                    opf_content, flags=re.IGNORECASE)
                # spine itemref: xhtml 제거 대상의 id를 OPF에서 찾아서 spine에서도 제거
                for _xfn in xhtml_to_remove:
                    _xbase = Path(_xfn).name.lower()
                    # OPF manifest에서 해당 xhtml의 id 추출
                    _id_m = re.search(
                        rf'<item\b[^>]+id=["\']([^"\']+)["\'][^>]+href=["\'][^"\']*{re.escape(_xbase)}["\']',
                        opf_content, re.IGNORECASE)
                    if not _id_m:
                        _id_m = re.search(
                            rf'<item\b[^>]+href=["\'][^"\']*{re.escape(_xbase)}["\'][^>]+id=["\']([^"\']+)["\']',
                            opf_content, re.IGNORECASE)
                    if _id_m:
                        _xid = re.escape(_id_m.group(1))
                        opf_content = re.sub(
                            rf'<itemref\b[^>]+idref=["\']' + _xid + r'["\'][^>]*/?>',
                            '', opf_content, flags=re.IGNORECASE)

            # 새 ZIP 빌드
            out_buf = _io2.BytesIO()
            with zipfile.ZipFile(_io2.BytesIO(original), 'r') as _zin2:
                with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as _zout:
                    for _info in _zin2.infolist():
                        _bn = Path(_info.filename).name.lower()
                        if _bn in del_basenames:
                            continue   # 이미지 파일 제거
                        if _info.filename in xhtml_to_remove:
                            continue   # 이미지 전용 xhtml 페이지 제거
                        _data = _zin2.read(_info.filename)
                        if opf_content and _info.filename == opf_name:
                            _data = opf_content.encode('utf-8')
                        _zout.writestr(_info, _data)

            with open(epub_path, 'wb') as _f:
                _f.write(out_buf.getvalue())

            _names = ', '.join(Path(fn).name for fn in filenames_to_delete)
            _extra = f" + 표지 페이지 {len(xhtml_to_remove)}개" if xhtml_to_remove else ""
            self._log(
                f"🗑 이미지 {len(filenames_to_delete)}개 삭제{_extra}: {_names}", "ok")
        except Exception as _e:
            self._log(f"⚠ 이미지 삭제 실패: {_e}", "warn")

    def _paste_cover(self):
        from PyQt6.QtWidgets import QApplication as _QApp
        from PyQt6.QtGui import QImage
        import io as _io
        cb = _QApp.clipboard()
        img = cb.image()
        if img and not img.isNull():
            # QImage → PNG bytes
            buf = _io.BytesIO()
            ba  = __import__('PyQt6.QtCore', fromlist=['QByteArray']).QByteArray()
            buf2 = __import__('PyQt6.QtCore', fromlist=['QBuffer']).QBuffer(ba)
            buf2.open(__import__('PyQt6.QtCore', fromlist=['QIODevice']).QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf2, 'PNG')
            data = bytes(ba)
            self._set_cover(data, '.png', '클립보드 이미지')
            return
        # 파일 경로가 클립보드에 있는 경우
        mime = cb.mimeData()
        if mime and mime.hasUrls():
            for url in mime.urls():
                p = url.toLocalFile()
                if p and Path(p).suffix.lower() in ('.jpg','.jpeg','.png','.webp'):
                    try:
                        data = Path(p).read_bytes()
                        ext  = Path(p).suffix.lower()
                        if ext == '.webp': ext = '.jpg'
                        self._set_cover(data, ext, Path(p).name)
                        return
                    except: pass
        self._log("⚠ 클립보드에 이미지가 없습니다", "warn")

    def _open_toc_dialog(self):
        if not self._files:
            QMessageBox.information(self, "알림", "먼저 EPUB 파일을 추가해주세요.")
            return

        # 미리보기에서도 파일명 화수(N화)를 실제 병합과 동일하게 보정
        _chap_only_filename_dlg: dict[int, int] = {}
        _filename_toc_labels_dlg: dict[int, str] = {}
        for _i, (_p, _n, _s) in enumerate(self._files):
            _filename_toc_labels_dlg[_i] = _toc_label_from_filename(_n)
            _m = re.search(r'(\d+)\s*화', Path(_n).stem)
            if _m:
                _chap_only_filename_dlg[_i] = int(_m.group(1))
        _force_filename_toc_dlg = _is_consistent_filename_label_set(
            list(_filename_toc_labels_dlg.values()))

        def _ensure_chap_prefix_dlg(fi: int, title: str, label_hint: str = '') -> str:
            if fi not in _chap_only_filename_dlg:
                return title
            _n = _chap_only_filename_dlg[fi]
            if not title:
                return f'{_n}화'
            if re.search(rf'(?<!\d){_n}\s*화', title):
                return title
            if re.search(r'\d+\s*화', title):
                return title
            if label_hint:
                _t_norm = _normalize_title(re.sub(r'\s+', ' ', title)).strip().lower()
                _l_norm = _normalize_title(re.sub(r'\s+', ' ', label_hint)).strip().lower()
                _l_norm = re.sub(r'^\[[^\]]+\]\s*', '', _l_norm).strip()
                _l_norm = _strip_trailing_volume_suffix(_l_norm).strip().lower()
                if _l_norm and (_t_norm == _l_norm or _t_norm.startswith(_l_norm + ' ')):
                    return title
            return f'{_n}화 {title}'.strip()

        # ── 권 라벨 준비 ──────────────────────────
        titles = list(self._toc_titles)
        while len(titles) < len(self._files):
            titles.append('')
        for i, (path, name, _) in enumerate(self._files):
            stem = Path(name).stem
            current = titles[i] if i < len(titles) else ''
            if current and current != stem:
                continue
            auto = self._toc_titles[i] if i < len(self._toc_titles) and self._toc_titles[i] != stem else ''
            titles[i] = auto if auto else _toc_label_from_filename(name)
        titles = titles[:len(self._files)]
        titles = [
            _compact_toc_label_for_series(title, self.fname_edit.text())
            for title in titles
        ]

        # ── 화 제목 추출 (epub 내부 spine 순서로) ──
        page_titles = []   # list of list of (item_id, href, ptitle)
        _last_dialog_title_key = ""
        for fi, (path, name, _) in enumerate(self._files):
            chaps = []
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    container = z.read('META-INF/container.xml').decode('utf-8','replace')
                    m = re.search(r'full-path="([^"]+\.opf)"', container)
                    if m:
                        opf_path = m.group(1)
                        opf = z.read(opf_path).decode('utf-8','replace')
                        opf_dir = str(Path(opf_path).parent)
                        manifest = {}
                        for mm in re.finditer(r'<item\s([^>]*?)\s*/?>', opf, re.IGNORECASE):
                            attrs = mm.group(1)
                            mid  = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
                            href = re.search(r'\bhref=["\']([^"\']+)["\']', attrs)
                            if mid and href: manifest[mid.group(1)] = href.group(1)
                        spine_ids = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf)

                        # 원본 toc.ncx에서 {파일명(소문자): 챕터제목} 로드
                        ncx_labels_dlg = {}
                        ncx_doc_title_dlg = ''
                        try:
                            ncx_href_m = re.search(
                                r'<item\s[^>]*media-type=["\']application/x-dtbncx\+xml["\'][^>]*href=["\']([^"\']+)["\']'
                                r'|<item\s[^>]*href=["\']([^"\']*toc\.ncx)["\']',
                                opf, re.IGNORECASE)
                            if ncx_href_m:
                                ncx_href_val = ncx_href_m.group(1) or ncx_href_m.group(2)
                                ncx_full = (opf_dir + '/' + ncx_href_val).lstrip('./') if opf_dir != '.' else ncx_href_val
                                if ncx_full not in z.namelist(): ncx_full = ncx_href_val
                                ncx_raw = z.read(ncx_full).decode('utf-8', 'replace')
                                import html as _html_dlg
                                # docTitle 추출
                                _dt = re.search(r'<docTitle[^>]*>.*?<text[^>]*>(.*?)</text>', ncx_raw,
                                                re.IGNORECASE | re.DOTALL)
                                if _dt:
                                    ncx_doc_title_dlg = _CDATA_PAT.sub(r'\1', re.sub(r'\s+', ' ', _html_dlg.unescape(_dt.group(1)))).strip()
                                _nav_pat = re.compile(
                                    r'<navPoint[^>]*>.*?<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>.*?'
                                    r'<content[^>]*src=["\']([^"\'#]+)',
                                    re.IGNORECASE | re.DOTALL)
                                for nm in _nav_pat.finditer(ncx_raw):
                                    _lbl = _CDATA_PAT.sub(r'\1', re.sub(r'\s+', ' ', _html_dlg.unescape(nm.group(1)))).strip()
                                    _fn  = Path(nm.group(2).strip().replace('\\', '/')).name.lower()
                                    if _lbl and _fn:
                                        ncx_labels_dlg[_fn] = _lbl
                        except Exception:
                            pass

                        for sid in spine_ids:
                            if sid not in manifest: continue
                            href = manifest[sid]
                            full = (opf_dir + '/' + href).lstrip('./') if opf_dir != '.' else href
                            if full not in z.namelist(): full = href
                            try: data = z.read(full)
                            except: continue
                            if is_skip_page(href, data): continue
                            # NCX 라벨이 "cover"인 이미지 전용 페이지도 제거 (실제 병합과 동일 기준)
                            if ncx_labels_dlg:
                                _skip_lbl = ncx_labels_dlg.get(Path(href).name.lower(), '').strip().lower()
                                if _skip_lbl == 'cover':
                                    _raw_s = data.decode('utf-8', 'replace')
                                    _has_img = bool(re.search(r'<img\b', _raw_s, re.IGNORECASE))
                                    _txt = re.sub(r'<style[^>]*>.*?</style>', '', _raw_s, flags=re.DOTALL|re.IGNORECASE)
                                    _txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', _txt)).strip()
                                    if _has_img and len(_txt) < 80:
                                        continue
                            # 우선순위: 사용자 편집값 > 원본 NCX > HTML 자동추출(NCX 없는 epub만)
                            override_key = f"{fi}:{sid}"
                            if hasattr(self, '_page_title_overrides') and override_key in self._page_title_overrides:
                                ptitle = self._page_title_overrides[override_key]
                                _manual_ptitle = True
                            else:
                                _manual_ptitle = False
                                if _core_merge_page_title_from_sources:
                                    ptitle = _core_merge_page_title_from_sources(
                                        data,
                                        out_filename=href,
                                        ncx_labels=ncx_labels_dlg,
                                        ncx_doc_title=ncx_doc_title_dlg,
                                        series_title=self.fname_edit.text(),
                                    )
                                else:
                                    _fname_lc = Path(href).name.lower()
                                    if ncx_labels_dlg:
                                        # NCX가 있는 epub: NCX에 등록된 페이지만 제목 표시
                                        ptitle = ncx_labels_dlg.get(_fname_lc, '')
                                        # NCX에 해당 파일 항목 없으면 HTML 자동추출 폴백
                                        if not ptitle:
                                            ptitle = extract_chapter_title(data) or ''
                                        # generic 라벨 → docTitle 우선, 없으면 HTML 추출
                                        if _is_generic_ncx_label(ptitle):
                                            if (ncx_doc_title_dlg
                                                    and not _is_generic_ncx_label(ncx_doc_title_dlg)
                                                    and re.search(r'\d+\s*[화권]', ncx_doc_title_dlg)):
                                                ptitle = ncx_doc_title_dlg
                                            else:
                                                ptitle = extract_chapter_title(data) or ptitle
                                    else:
                                        # NCX 없는 epub: HTML 자동추출 폴백
                                        ptitle = extract_chapter_title(data) or ''
                            # (연재)/(연재중) 제거
                            if ptitle:
                                ptitle = re.sub(r'\s*\(연재중?\)\s*', '', ptitle).strip()
                            # 시리즈명 반복 제거: "시리즈명 N화 [부제]" → "N화 [부제]"
                            if ptitle:
                                _dlg_title = re.sub(r'^\[[^\]]*\]\s*', '', self.fname_edit.text().strip()).strip()
                                _sname_dlg = re.sub(r'\s*\d+(?:[-~]\d+)?\s*[권화부]?\s*$', '', _dlg_title).strip()
                                if _sname_dlg and len(_sname_dlg) >= 4:
                                    _chap_only = re.sub(r'^' + re.escape(_sname_dlg) + r'\s*', '', ptitle).strip()
                                    if _chap_only and re.search(r'^\d+\s*[화권]', _chap_only):
                                        ptitle = _chap_only
                                        # 시리즈명 제거 후 generic(N화)만 남으면 HTML에서 소제목 재추출
                                        if _is_generic_ncx_label(ptitle):
                                            _html_sub = extract_chapter_title(data)
                                            if _html_sub and len(_html_sub) > len(ptitle):
                                                ptitle = _html_sub
                            if not _manual_ptitle:
                                ptitle = _prefer_filename_toc_title(
                                    _filename_toc_labels_dlg.get(fi, ''), ptitle,
                                    force_filename=_force_filename_toc_dlg)
                            ptitle = _ensure_chap_prefix_dlg(fi, ptitle, titles[fi] if fi < len(titles) else '')
                            if ptitle:
                                ptitle = _clean_chapter_display_title(ptitle, self.fname_edit.text())
                                ptitle = _compact_toc_label_for_series(ptitle, self.fname_edit.text())
                                _ptitle_key = _toc_duplicate_key(ptitle)
                                if _ptitle_key and _ptitle_key == _last_dialog_title_key:
                                    ptitle = ''
                                elif _ptitle_key:
                                    _last_dialog_title_key = _ptitle_key
                            chaps.append((sid, href, ptitle))
            except Exception as _dlg_exc:
                import traceback; traceback.print_exc()
            page_titles.append(chaps)

        # ── # 접두어 일괄 정규화 ─────────────────────────────────────────
        # 전체 목차 title 중 "#N화" 형식 vs "N화" 형식 다수결로 통일
        # 동수(또는 # 쪽이 많으면) # 제거 방향 우선 (표시용 목차이므로 # 불필요)
        _flat = [pt for chaps in page_titles for (_, _, pt) in chaps if pt]
        _hash_cnt   = sum(1 for t in _flat if re.match(r'^#\s*\d+\s*[화권]', t))
        _nohash_cnt = sum(1 for t in _flat if re.match(r'^\d+\s*[화권]',    t))
        if _hash_cnt > 0 or _nohash_cnt > 0:
            # # 없는 쪽이 과반이면 # 제거, 그 외(# 쪽이 더 많거나 동수)면 # 추가
            _use_hash = _hash_cnt > _nohash_cnt
            _norm = []
            for chaps in page_titles:
                _nc = []
                for (iid, href, pt) in chaps:
                    if pt:
                        if _use_hash:
                            # "N화..." 패턴이면 # 접두어 추가
                            if re.match(r'^\d+\s*[화권]', pt):
                                pt = '#' + pt
                        else:
                            # "#N화..." 패턴이면 # 접두어 제거
                            pt = re.sub(r'^#\s*', '', pt)
                    _nc.append((iid, href, pt))
                _norm.append(_nc)
            page_titles = _norm

        dlg = TocEditDialog(self, self._files, titles, page_titles)
        if dlg.exec():
            self._toc_titles = dlg.get_titles()
            # 화 제목 편집 결과 저장
            if not hasattr(self, '_page_title_overrides'):
                self._page_title_overrides = {}
            for fi, chap_list in enumerate(dlg.get_chap_labels()):
                for (iid, href, ptitle) in chap_list:
                    self._page_title_overrides[f"{fi}:{iid}"] = ptitle
            self._log("✏ 목차 제목 저장 완료", "ok")

    def _on_done(self, ok, out_path):
        # ── 병합 후처리: 용량 줄이기 / 노이즈 (merge worker 후 파일에 직접 적용) ──
        if ok and out_path:
            try:
                data = Path(out_path).read_bytes()
                changed = False
                # 용량 줄이기는 MergeWorker 내부에서 이미 처리되므로 여기선 skip
                # 노이즈 삽입
                if self.chk_noise.isChecked():
                    lvl  = int(self.noise_combo.currentText())
                    data = add_noise_to_epub(data, lvl)
                    changed = True
                if changed:
                    Path(out_path).write_bytes(data)
            except Exception as ex:
                self._log(f"⚠ 후처리 오류: {ex}", "warn")
            if out_path not in self._merge_outputs:
                self._merge_outputs.append(out_path)

        if ok:
            self._merge_done += 1
        else:
            self._merge_failed.append(Path(out_path).name if out_path else "?")

        # 큐에 남은 그룹이 있으면 다음 실행
        if self._merge_queue:
            self._run_next_merge()
            return

        # 모든 그룹 완료
        self.merge_btn.setEnabled(True)
        self.merge_btn.setText("✨ 병합 시작")

        txt_ok = 0
        txt_fail = 0
        if self.chk_merge_txt_save.isChecked() and self._merge_outputs:
            txt_ok, txt_fail, _ = self._save_txt_exports(self._merge_outputs, log_fn=self._log)
        txt_msg = ""
        if self.chk_merge_txt_save.isChecked():
            txt_msg = f"\n\nTXT 저장: {txt_ok}개"
            if txt_fail:
                txt_msg += f" / 실패 {txt_fail}개"

        total = self._merge_total
        if total == 1:
            # 단일 그룹: 기존 동작
            if ok:
                self._open_folder_confirm(
                    os.path.dirname(out_path),
                    title="완료 🎉",
                    pre_msg=f"병합 완료!\n\n{out_path}{txt_msg}")
            else:
                QMessageBox.critical(self, "오류",
                    "병합 중 오류가 발생했습니다.\n로그를 확인해주세요.")
        else:
            # 다중 그룹: 요약
            failed = len(self._merge_failed)
            done   = self._merge_done
            if failed == 0:
                self._open_folder_confirm(
                    self.dir_edit.text(),
                    title="일괄 병합 완료 🎉",
                    pre_msg=f"전체 {total}개 시리즈 병합 완료! ✅{txt_msg}")
            else:
                msg = (f"완료: {done}개 / 실패: {failed}개\n\n"
                       f"실패 목록:\n" + "\n".join(f"  • {n}" for n in self._merge_failed))
                if txt_msg:
                    msg += txt_msg
                QMessageBox.warning(self, "일괄 병합 결과", msg)

        # 병합 완료 시 압축 임시 폴더 강제 정리
        if self._cover_user_set:
            self._clear_cover()
        if self._merge_done and not self._merge_failed:
            self._clear_files_after_successful_merge()
        self._cleanup_temp_dirs(force=True)

    def closeEvent(self, e):
        """윈도우 종료 시 압축 임시 폴더 강제 정리."""
        try:
            self._cleanup_temp_dirs(force=True)
        except Exception:
            pass
        super().closeEvent(e)

    def _cleanup_temp_dirs(self, force: bool = False):
        """압축파일에서 추출한 임시 폴더 정리.
        force=False: 현재 self._files에 참조되지 않는 폴더만 삭제 (개별 delete 후 호출)
        force=True : 모든 임시 폴더 삭제 (병합 완료 / 전체 비우기 후 호출)
        """
        if not self._temp_dirs:
            return
        if force:
            for d in self._temp_dirs:
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass
            self._temp_dirs.clear()
            return
        # 부분 정리 — 현재 _files 또는 _rename_files에 남은 경로가 가리키지 않는 폴더만 제거
        in_use_paths = set()
        for f in getattr(self, '_files', []) or []:
            try:
                in_use_paths.add(os.path.realpath(f[0]))
            except Exception:
                pass
        for f in getattr(self, '_rename_files', []) or []:
            try:
                p = f[0] if isinstance(f, tuple) else f.get('path', '')
                if p:
                    in_use_paths.add(os.path.realpath(p))
            except Exception:
                pass

        kept = []
        for d in self._temp_dirs:
            try:
                d_real = os.path.realpath(d)
                # 이 폴더 안에 사용 중인 파일이 있으면 보존
                still_used = any(p.startswith(d_real + os.sep) or p == d_real
                                 for p in in_use_paths)
                if still_used:
                    kept.append(d)
                else:
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                kept.append(d)
        self._temp_dirs = kept

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📝 텍스트 변환 탭 (TXT → EPUB)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _build_txt_tab(self, root):
        # 인스턴스 상태 — [{path, title, author, raw_text, chapters}, ...]
        self._txt_files: list[dict] = []
        self._txt_worker = None

        # ── 카드1: 파일 목록 ──────────────────────────
        card1, _, bl1 = make_card("📄 변환할 TXT 파일", C["accent"])
        top_row = QHBoxLayout(); top_row.setSpacing(5)
        b_add = mk_btn("📂 파일 열기", "blue")
        b_add.setToolTip("TXT 파일 선택 (드래그앤드롭도 가능)")
        b_add.clicked.connect(self._txt_browse_files)
        b_clr = mk_btn("🗑 비우기", "gray")
        b_clr.clicked.connect(self._txt_clear_files)
        b_del = mk_btn("❌ 삭제", "danger")
        b_del.setToolTip("선택 항목 삭제")
        b_del.clicked.connect(self._txt_delete_selected)
        top_row.addWidget(b_add); top_row.addWidget(b_clr); top_row.addWidget(b_del)
        top_row.addStretch()
        self.txt_count_lbl = mk_lbl("0개", C["text3"], 11)
        top_row.addWidget(self.txt_count_lbl)
        bl1.addLayout(top_row)

        self.txt_list = QListWidget()
        self.txt_list.setFixedHeight(220)
        self.txt_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.txt_list.installEventFilter(self)
        self.txt_list.currentRowChanged.connect(
            lambda _: self._txt_update_cover_label())
        self._txt_show_placeholder()
        bl1.addWidget(self.txt_list)
        root.addWidget(card1)

        # ── 카드2: 챕터 감지 옵션 ─────────────────────
        card2, _, bl2 = make_card("⚙️ 챕터 감지 옵션", C["green"])
        self.txt_strength_combo = QComboBox()
        self.txt_strength_combo.addItem("약함 (제N화/N화)", "weak")
        self.txt_strength_combo.addItem("보통 (한+영 기본)", "normal")
        self.txt_strength_combo.addItem("강함 (전체 패턴)", "strong")
        self.txt_strength_combo.addItem("커스텀 정규식", "custom")
        self.txt_strength_combo.setCurrentIndex(1)
        self.txt_strength_combo.setToolTip(
            "약함: 제1화/1화만 인식\n"
            "보통: 한글·영문 일반 패턴 (Chapter, 프롤로그 등)\n"
            "강함: 1-1, 1.5, #1, ## 등 전체 확장 패턴\n"
            "커스텀: 사용자 정의 정규식 (한 줄당 한 패턴)")
        self.txt_strength_combo.currentIndexChanged.connect(self._txt_on_strength_changed)
        self.txt_chk_ascending = QCheckBox("숫자 오름차순 보정")
        self.txt_chk_ascending.setChecked(True)
        self.txt_chk_ascending.setToolTip(
            "체크 시:\n"
            " • 챕터 번호가 연속 오름차순이 아닌 항목은 오인식으로 보고 이전 챕터에 흡수\n"
            " • 본문에 흡수돼 누락된 번호(예: 308~340)는 다시 챕터로 분할")
        self.txt_chk_ascending.toggled.connect(lambda _: self._txt_redetect_all())

        # 커스텀 정규식 입력 (강도 = custom 일 때만 표시)
        self.txt_custom_row = QHBoxLayout(); self.txt_custom_row.setSpacing(6)
        self.txt_custom_row.addWidget(mk_lbl("정규식", C["text2"], 11))
        self.txt_custom_edit = QLineEdit()
        self.txt_custom_edit.setPlaceholderText(
            r"예) ^제\s?\d+\s?화   |   ^Chapter\s+\d+")
        self.txt_custom_row.addWidget(self.txt_custom_edit, 1)
        bl2.addLayout(self.txt_custom_row)
        self._txt_custom_set_visible(False)

        # 표지 + 목차
        meta_row = QHBoxLayout(); meta_row.setSpacing(6)
        b_cover = mk_btn("🖼 표지", "blue")
        b_cover.setToolTip("클립보드 이미지를 선택된 파일의 표지로 설정 (Ctrl+V)")
        b_cover.clicked.connect(self._txt_paste_cover)
        meta_row.addWidget(b_cover)
        b_cover_search = mk_btn("🔍 검색", "blue")
        b_cover_search.setToolTip("선택한 TXT 제목으로 구글 이미지 검색을 바로 엽니다.")
        b_cover_search.clicked.connect(self._txt_open_cover_search)
        meta_row.addWidget(b_cover_search)
        b_series = mk_btn("📚 시리즈", "blue")
        b_series.setToolTip("네이버 시리즈 URL 또는 productNo로 표지를 직접 가져옵니다.")
        b_series.clicked.connect(self._txt_open_series_cover)
        meta_row.addWidget(b_series)
        self.txt_cover_lbl = mk_lbl("표지: 없음", C["text3"], 11)
        meta_row.addWidget(self.txt_cover_lbl)
        meta_row.addStretch()
        b_preview = mk_btn("🔍 목차", "blue")
        b_preview.setToolTip("선택한 파일의 챕터 목차 미리보기 / 편집")
        b_preview.clicked.connect(self._txt_open_preview)
        meta_row.addWidget(b_preview)
        bl2.addLayout(meta_row)
        root.addWidget(card2)

        # ── 카드3: 저장 설정 ──────────────────────────
        card3, _, bl3 = make_card("💾 저장 설정", C["orange"])
        dir_row = QHBoxLayout(); dir_row.setSpacing(6)
        lbl_dir = mk_lbl("저장 위치", C["text2"], 11); lbl_dir.setFixedWidth(54)
        dir_row.addWidget(lbl_dir)
        _saved_txt_dir = self._settings.value(
            "last_txt_dir", str(Path.home() / "Downloads"))
        self.txt_dir_edit = QLineEdit(_saved_txt_dir)
        self.txt_dir_edit.setReadOnly(True)
        dir_row.addWidget(self.txt_dir_edit, 1)
        b_dir = mk_btn("📁 찾기", "gray")
        b_dir.clicked.connect(self._txt_browse_dir)
        dir_row.addWidget(b_dir)
        bl3.addLayout(dir_row)
        root.addWidget(card3)

        # ── 카드4: 진행/로그 ─────────────────────────
        card4, _, bl4 = make_card("", C["text3"])
        card4.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.txt_prog_bar = QProgressBar(); self.txt_prog_bar.setValue(0)
        bl4.addWidget(self.txt_prog_bar)
        self.txt_log_area = QTextEdit()
        self.txt_log_area.setObjectName("log_area")
        self.txt_log_area.setReadOnly(True)
        self.txt_log_area.setMinimumHeight(70)
        self.txt_log_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bl4.addWidget(self.txt_log_area)
        root.addWidget(card4, 1)

        # ── 변환 시작 버튼 ────────────────────────────
        self.txt_convert_btn = mk_btn("✨  EPUB 변환 시작", "green")
        self.txt_convert_btn.setFixedHeight(42)
        self.txt_convert_btn.setStyleSheet(
            f"QPushButton{{background:{C['green']};color:white;font-size:14px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#16b87a;}}"
            f"QPushButton:disabled{{background:#a8d8c4;color:#ddf0ea;}}")
        self.txt_convert_btn.clicked.connect(self._txt_start_convert)
        root.addWidget(self.txt_convert_btn)

    # ── 텍스트 탭 헬퍼 ────────────────────────────────
    _TXT_PLACEHOLDER = "📄  TXT 파일을 여기에 드래그하거나 위 [파일 열기] 버튼을 눌러주세요"

    def _txt_show_placeholder(self):
        self.txt_list.clear()
        item = QListWidgetItem(self._TXT_PLACEHOLDER)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        from PyQt6.QtGui import QColor
        item.setForeground(QColor(C['text3']))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_list.addItem(item)

    def _txt_log(self, msg, tag="info"):
        colors = {"ok": C["text"], "err": C["red"],
                  "warn": C["orange"], "info": C["text3"]}
        color = colors.get(tag, C["text3"])
        self.txt_log_area.append(
            f'<span style="color:{color};font-size:11px;">{msg}</span>')

    def _txt_custom_set_visible(self, visible: bool):
        for i in range(self.txt_custom_row.count()):
            w = self.txt_custom_row.itemAt(i).widget()
            if w: w.setVisible(visible)

    def _txt_on_strength_changed(self, _idx):
        self._txt_custom_set_visible(
            self.txt_strength_combo.currentData() == "custom")
        # 강도 변경 시 챕터 재감지
        self._txt_redetect_all()

    def _txt_browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "저장 폴더 선택", self.txt_dir_edit.text())
        if d:
            self.txt_dir_edit.setText(d)
            self._settings.setValue("last_txt_dir", d)

    def _txt_browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "TXT 파일 선택", "",
            "Text Files (*.txt);;All Files (*.*)")
        if paths:
            self._txt_add_files(paths)

    def _txt_clear_files(self):
        self._txt_files.clear()
        self._txt_show_placeholder()
        self.txt_count_lbl.setText("0개")

    def _txt_delete_selected(self):
        if (self.txt_list.count() == 1
                and self.txt_list.item(0).text() == self._TXT_PLACEHOLDER):
            return
        rows = sorted({self.txt_list.row(it) for it in self.txt_list.selectedItems()}, reverse=True)
        if not rows:
            cur = self.txt_list.currentRow()
            if 0 <= cur < len(self._txt_files):
                rows = [cur]
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._txt_files):
                self._txt_files.pop(row)
                self.txt_list.takeItem(row)
        self.txt_count_lbl.setText(f"{len(self._txt_files)}개")
        if not self._txt_files:
            self._txt_show_placeholder()

    def _txt_remove_converted_paths(self, paths):
        done = {os.path.normcase(os.path.normpath(str(p))) for p in paths}
        if not done:
            return 0
        removed = 0
        for row in range(len(self._txt_files) - 1, -1, -1):
            cur = os.path.normcase(os.path.normpath(str(self._txt_files[row].get('path', ''))))
            if cur in done:
                self._txt_files.pop(row)
                self.txt_list.takeItem(row)
                removed += 1
        self.txt_count_lbl.setText(f"{len(self._txt_files)}개")
        if not self._txt_files:
            self._txt_show_placeholder()
            self._custom_cover = None
            self._custom_cover_ext = '.jpg'
        self._txt_update_cover_label()
        return removed

    # ── 네이버 시리즈 쿠키 설정 ─────────────────────
    def _open_naver_cookie_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("네이버 시리즈 쿠키 설정")
        dlg.setModal(True)
        dlg.setMinimumWidth(440)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        hdr = QLabel("🍪  네이버 시리즈 쿠키 설정")
        hdr.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:700;background:transparent;")
        root.addWidget(hdr)

        desc = QLabel(
            "브라우저의 네이버 시리즈 쿠키(NID_AUT, NID_SES)를 입력하면\n"
            "표지 검색 시 시리즈 표지를 직접 다운로드할 수 있습니다.\n"
            "쿠키는 이 PC에만 저장되며 외부로 전송되지 않습니다.")
        desc.setStyleSheet(f"color:{C['text3']};font-size:11px;background:transparent;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};")
        root.addWidget(sep)

        grid = QGridLayout(); grid.setSpacing(8)
        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(
                f"color:{C['text2']};font-size:11px;background:transparent;font-weight:600;")
            return l

        nid_aut_edit = QLineEdit()
        nid_aut_edit.setPlaceholderText("NID_AUT 값 붙여넣기")
        nid_aut_edit.setEchoMode(QLineEdit.EchoMode.Password)
        nid_aut_edit.setText(self._settings.value("naver_nid_aut", "", type=str))

        nid_ses_edit = QLineEdit()
        nid_ses_edit.setPlaceholderText("NID_SES 값 붙여넣기")
        nid_ses_edit.setEchoMode(QLineEdit.EchoMode.Password)
        nid_ses_edit.setText(self._settings.value("naver_nid_ses", "", type=str))

        chk_show = QCheckBox("입력값 표시")
        chk_show.setStyleSheet(
            f"QCheckBox{{color:{C['text3']};font-size:10px;background:transparent;}}"
            f"QCheckBox::indicator{{width:13px;height:13px;border:1.5px solid {C['border']};"
            f"border-radius:3px;background:{C['surface']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}")
        def _toggle_echo(on):
            mode = QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            nid_aut_edit.setEchoMode(mode)
            nid_ses_edit.setEchoMode(mode)
        chk_show.toggled.connect(_toggle_echo)

        grid.addWidget(_lbl("NID_AUT"), 0, 0)
        grid.addWidget(nid_aut_edit,    0, 1)
        grid.addWidget(_lbl("NID_SES"), 1, 0)
        grid.addWidget(nid_ses_edit,    1, 1)
        grid.addWidget(chk_show,        2, 1)
        root.addLayout(grid)

        how_lbl = QLabel(
            "📌 쿠키 얻는 법: 크롬에서 naver.com 접속 → F12 → Application → Cookies → NID_AUT/NID_SES 복사")
        how_lbl.setStyleSheet(
            f"color:{C['text3']};font-size:10px;background:transparent;")
        how_lbl.setWordWrap(True)
        root.addWidget(how_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        btn_row.addStretch()
        b_clear = QPushButton("초기화")
        b_clear.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:5px 14px;color:{C['text2']};font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg3']};}}")
        def _clear():
            nid_aut_edit.clear(); nid_ses_edit.clear()
        b_clear.clicked.connect(_clear)
        b_save = QPushButton("저장")
        b_save.setStyleSheet(
            f"QPushButton{{background:{C['accent']};border:none;"
            f"border-radius:6px;padding:5px 20px;color:#fff;font-size:11px;font-weight:600;}}"
            f"QPushButton:hover{{background:#1a5fc4;}}")
        def _save():
            self._settings.setValue("naver_nid_aut", nid_aut_edit.text().strip())
            self._settings.setValue("naver_nid_ses", nid_ses_edit.text().strip())
            dlg.accept()
        b_save.clicked.connect(_save)
        b_cancel = QPushButton("취소")
        b_cancel.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:5px 14px;color:{C['text2']};font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg3']};}}")
        b_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(b_clear)
        btn_row.addWidget(b_cancel)
        btn_row.addWidget(b_save)
        root.addLayout(btn_row)
        dlg.exec()

    def _txt_open_cover_search(self):
        if not self._txt_files:
            QMessageBox.information(self, "파일 없음", "먼저 TXT 파일을 추가해주세요.")
            return
        row = self.txt_list.currentRow()
        if row < 0 or row >= len(self._txt_files):
            row = 0
        title = (self._txt_files[row].get('title') or Path(self._txt_files[row]['path']).stem).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        if not title:
            QMessageBox.information(self, "제목 없음", "검색할 제목을 찾지 못했습니다.")
            return
        import webbrowser
        from urllib.parse import quote_plus
        query = f"{title} 표지"
        webbrowser.open(f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}")
        self._txt_log(f"🔎 표지 검색 열기: {query}", "info")

    def _txt_open_series_cover(self):
        if not self._txt_files:
            QMessageBox.information(self, "파일 없음", "먼저 TXT 파일을 추가해주세요.")
            return
        row = self.txt_list.currentRow()
        if row < 0 or row >= len(self._txt_files):
            row = 0
        title = (self._txt_files[row].get('title') or Path(self._txt_files[row]['path']).stem).strip()
        title = re.sub(r'\s+', ' ', title).strip()

        nid_aut = self._settings.value("naver_nid_aut", "", type=str)
        nid_ses = self._settings.value("naver_nid_ses", "", type=str)

        dlg = NaverSeriesCoverDialog(self, title=title, nid_aut=nid_aut, nid_ses=nid_ses)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            img_data, img_ext, fetched_title, fetched_author = dlg.get_cover()
            if img_data and row < len(self._txt_files):
                f = self._txt_files[row]
                f['cover_data'] = img_data
                f['cover_ext']  = img_ext
                kb = len(img_data) // 1024
                self._txt_update_cover_label()
                self._txt_refresh_list_item(row)
                self._txt_log(f"🖼 [{Path(f['path']).name}] 네이버 시리즈 표지 설정 ({kb:,} KB)", "ok")
                # 작가 자동 적용 (없거나 미상인 경우만)
                if fetched_author:
                    if not f.get('author') or f.get('author') == '미상':
                        f['author'] = fetched_author
                        if _core_clean_series_title_author:
                            f['title'], f['author'] = _core_clean_series_title_author(
                                f.get('title') or Path(f['path']).stem,
                                f['author'],
                            )
                        self._txt_log(f"👤 작가 자동 설정: {fetched_author}", "ok")

    def _txt_add_files(self, paths):
        # 폴더 → txt 재귀
        expanded = []
        for p in paths:
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for fn in files:
                        if fn.lower().endswith('.txt'):
                            expanded.append(os.path.join(root, fn))
            elif p.lower().endswith('.txt'):
                expanded.append(p)

        if not expanded:
            self._txt_log("⚠ TXT 파일이 없습니다", "warn")
            return

        # 플레이스홀더 제거
        if (self.txt_list.count() == 1
                and self.txt_list.item(0).text() == self._TXT_PLACEHOLDER):
            self.txt_list.clear()

        existing = {f['path'] for f in self._txt_files}
        added = 0
        for p in expanded:
            if p in existing:
                continue
            try:
                raw = Path(p).read_bytes()
                text = _decode_txt_bytes(raw)
                title, author = extract_txt_metadata(p, text)
                chapters, subtitle_style = self._txt_detect(text)
                self._txt_files.append({
                    "path": p, "title": title, "author": author,
                    "raw_text": text, "chapters": chapters,
                    "subtitle_style": subtitle_style,
                    "cover_data": None, "cover_ext": ".jpg",  # 파일별 표지
                })
                size = len(raw)
                size_s = (f"{size/1024:.1f}KB" if size < 1024*1024
                          else f"{size/1024/1024:.2f}MB")
                self.txt_list.addItem(
                    f"  {Path(p).name}   ({size_s} · {len(chapters)} 챕터)")
                added += 1
            except Exception as ex:
                self._txt_log(f"❌ {Path(p).name} 로드 실패: {ex}", "err")

        self.txt_count_lbl.setText(f"{len(self._txt_files)}개")
        if added:
            self._txt_log(f"✅ {added}개 파일 추가", "ok")

    def _txt_detect(self, text, force_subtitle_style=None, override_strength=None):
        strength = override_strength or self.txt_strength_combo.currentData()
        custom = self.txt_custom_edit.text().strip() if strength == "custom" else ""
        actual_strength = "normal" if strength == "custom" else strength
        from epub_binder_core.txt_detection import detect_chapters as _core_detect_chapters
        from epub_binder_core.txt_chapters import (
            absorb_flow_subheadings as _core_absorb_flow_subheadings,
            absorb_low_number_runs_between_flow as _core_absorb_low_number_runs_between_flow,
            absorb_obvious_numeric_flow_noise as _core_absorb_obvious_numeric_flow_noise,
            fill_numeric_gaps as _core_fill_numeric_gaps,
            filter_ascending_chapters as _core_filter_ascending_chapters,
            merge_auto_suspect_chapters as _core_merge_auto_suspect_chapters,
            merge_short_chapters as _core_merge_short_chapters,
            normalize_chapter_style as _core_normalize_chapter_style,
            normalize_messy_toc_markers,
            preserve_unicode_chapter_subtitles as _core_preserve_unicode_chapter_subtitles,
            restore_unicode_chapter_subtitles as _core_restore_unicode_chapter_subtitles,
            strip_angle_wrapped_chapter_titles as _core_strip_angle_wrapped_chapter_titles,
            strip_chapter_subtitles as _core_strip_chapter_subtitles,
        )
        normalized_text = normalize_messy_toc_markers(text)
        chapters, subtitle_style = _core_detect_chapters(
            normalized_text, actual_strength, custom,
            # TXT 변환은 목차 스타일 혼합 케이스가 많아 일관성 강제를 완화
            enforce_consistency=False,
            force_subtitle_style=force_subtitle_style)
        # 숫자 오름차순 보정 (체크박스)
        if hasattr(self, 'txt_chk_ascending') and self.txt_chk_ascending.isChecked():
            chapters = _core_filter_ascending_chapters(chapters)
            chapters = _core_fill_numeric_gaps(chapters)
            chapters = _core_absorb_low_number_runs_between_flow(chapters)
            chapters = _core_absorb_obvious_numeric_flow_noise(chapters)
            chapters = _core_absorb_flow_subheadings(chapters)
            chapters = _core_merge_auto_suspect_chapters(chapters)
        min_chars = 100
        chapters = _core_preserve_unicode_chapter_subtitles(chapters)
        chapters = _core_restore_unicode_chapter_subtitles(chapters, normalized_text)
        chapters = _core_merge_short_chapters(chapters, min_chars)
        chapters = _core_strip_angle_wrapped_chapter_titles(chapters)
        if hasattr(self, 'txt_chk_ascending') and self.txt_chk_ascending.isChecked():
            chapters = _core_filter_ascending_chapters(chapters)
            chapters = _core_absorb_low_number_runs_between_flow(chapters)
            chapters = _core_absorb_obvious_numeric_flow_noise(chapters)
            chapters = _core_absorb_flow_subheadings(chapters)
        if force_subtitle_style is False:
            chapters = _core_strip_chapter_subtitles(chapters)
        chapters = _core_normalize_chapter_style(chapters)
        return chapters, subtitle_style

    def _txt_redetect_all(self):
        if not self._txt_files:
            return
        for i, f in enumerate(self._txt_files):
            # 사용자가 수동으로 소제목 설정을 바꾼 경우 유지, 아니면 재감지
            force = f.get('subtitle_style_manual')
            chapters, subtitle_style = self._txt_detect(
                f['raw_text'], force_subtitle_style=force,
                override_strength=f.get('strength_override'))
            f['chapters'] = chapters
            if force is None:          # 재감지 값으로 갱신
                f['subtitle_style'] = subtitle_style
            # 리스트 항목 업데이트
            row = i if (self.txt_list.count() > i
                        and self.txt_list.item(0).text() != self._TXT_PLACEHOLDER) else -1
            if row >= 0:
                size = len(f['raw_text'].encode('utf-8'))
                size_s = (f"{size/1024:.1f}KB" if size < 1024*1024
                          else f"{size/1024/1024:.2f}MB")
                self.txt_list.item(row).setText(
                    f"  {Path(f['path']).name}   "
                    f"({size_s} · {len(f['chapters'])} 챕터)")

    def _txt_open_preview(self):
        if not self._txt_files:
            QMessageBox.information(self, "알림", "먼저 TXT 파일을 추가해주세요.")
            return
        row = self.txt_list.currentRow()
        if row < 0:
            row = 0
        if row >= len(self._txt_files):
            return
        f = self._txt_files[row]
        dlg = TxtPreviewDialog(f, self, detect_fn=self._txt_detect)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            f['title']    = dlg.get_title()
            f['author']   = dlg.get_author()
            f['chapters'] = dlg.get_chapters()
            # 사용자가 소제목 체크박스를 직접 바꾼 경우 → 재감지 시에도 유지
            new_ss = dlg.get_subtitle_style()
            f['subtitle_style'] = new_ss
            f['subtitle_style_manual'] = new_ss  # None=재감지, bool=수동고정
            f['strength_override'] = dlg.get_strength_override()
            # 리스트 항목 갱신 (🖼 아이콘 유지)
            self._txt_refresh_list_item(row)
            self._txt_log(
                f"✏ {Path(f['path']).name} 편집 저장 — "
                f"{len(f['chapters'])} 챕터", "ok")

    def _txt_update_cover_label(self):
        """선택된 파일의 표지 상태를 txt_cover_lbl에 반영."""
        if not hasattr(self, 'txt_cover_lbl'):
            return
        row = self.txt_list.currentRow() if hasattr(self, 'txt_list') else -1
        cd = None
        ext = '.jpg'
        if 0 <= row < len(self._txt_files):
            f = self._txt_files[row]
            cd  = f.get('cover_data')
            ext = f.get('cover_ext', '.jpg')
        if cd:
            kb = len(cd) // 1024
            self.txt_cover_lbl.setText(f"표지 설정됨 ({kb:,} KB, {ext})")
            self.txt_cover_lbl.setStyleSheet(
                f"color:{C['green']};font-size:11px;background:transparent;")
        else:
            self.txt_cover_lbl.setText("표지: 없음")
            self.txt_cover_lbl.setStyleSheet(
                f"color:{C['text3']};font-size:11px;background:transparent;")

    def _txt_refresh_list_item(self, row):
        """리스트 항목 텍스트에 표지 설정 여부(🖼) 반영."""
        if row < 0 or row >= len(self._txt_files):
            return
        item = self.txt_list.item(row)
        if item is None:
            return
        f = self._txt_files[row]
        p = Path(f['path'])
        try:
            size = p.stat().st_size
        except Exception:
            size = 0
        size_s = (f"{size/1024:.1f}KB" if size < 1024 * 1024
                  else f"{size/1024/1024:.2f}MB")
        chap_cnt = len(f.get('chapters', []))
        prefix = "🖼 " if f.get('cover_data') else "  "
        item.setText(f"{prefix}{p.name}   ({size_s} · {chap_cnt} 챕터)")

    def _txt_set_file_cover(self, row, data, ext, label):
        """선택된 파일의 표지 데이터를 저장하고 UI 갱신."""
        if row < 0 or row >= len(self._txt_files):
            return
        f = self._txt_files[row]
        f['cover_data'] = data
        f['cover_ext']  = ext
        kb = len(data) // 1024
        self._txt_update_cover_label()
        self._txt_refresh_list_item(row)
        self._txt_log(
            f"🖼 [{Path(f['path']).name}] 표지 설정: {label} ({kb:,} KB)", "ok")

    def _txt_paste_cover(self):
        """텍스트 탭 전용 — 클립보드 이미지를 선택된 파일의 표지로 저장."""
        from PyQt6.QtWidgets import QApplication as _QApp
        from PyQt6.QtGui import QImage
        import io as _io
        row = self.txt_list.currentRow()
        if row < 0 or row >= len(self._txt_files):
            if self._txt_files:
                row = 0
            else:
                self._txt_log("⚠ 파일을 먼저 추가/선택하세요", "warn")
                return
        cb = _QApp.clipboard()
        img = cb.image()
        if img and not img.isNull():
            ba   = __import__('PyQt6.QtCore', fromlist=['QByteArray']).QByteArray()
            buf2 = __import__('PyQt6.QtCore', fromlist=['QBuffer']).QBuffer(ba)
            buf2.open(
                __import__('PyQt6.QtCore', fromlist=['QIODevice'])
                .QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf2, 'PNG')
            data = bytes(ba)
            self._txt_set_file_cover(row, data, '.png', '클립보드 이미지')
            return
        mime = cb.mimeData()
        if mime and mime.hasUrls():
            for url in mime.urls():
                p = url.toLocalFile()
                if p and Path(p).suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                    try:
                        data = Path(p).read_bytes()
                        ext  = Path(p).suffix.lower()
                        if ext == '.webp':
                            ext = '.jpg'
                        self._txt_set_file_cover(row, data, ext, Path(p).name)
                        return
                    except Exception:
                        pass
        self._txt_log("⚠ 클립보드에 이미지가 없습니다", "warn")

    def _txt_start_convert(self):
        if not self._txt_files:
            QMessageBox.information(self, "알림", "변환할 TXT 파일을 추가해주세요.")
            return
        out_dir = self.txt_dir_edit.text().strip()
        if not out_dir or not os.path.isdir(out_dir):
            QMessageBox.warning(self, "오류", "유효한 저장 폴더를 선택해주세요.")
            return

        jobs = []
        for f in self._txt_files:
            jobs.append({
                'path':       f['path'],
                'title':      f['title'],
                'author':     f['author'],
                'chapters':   f['chapters'],
                'cover_data': f.get('cover_data'),
                'cover_ext':  f.get('cover_ext', '.jpg'),
            })

        self.txt_convert_btn.setEnabled(False)
        self.txt_convert_btn.setText("변환 중...")
        self.txt_prog_bar.setValue(0)
        self._txt_log(f"🚀 {len(jobs)}개 파일 변환 시작", "info")

        self._txt_worker = TxtEpubWorker(
            jobs, out_dir,
            cover_data=self._custom_cover,
            cover_ext=self._custom_cover_ext)
        self._txt_worker.log_signal.connect(self._txt_log)
        self._txt_worker.progress_signal.connect(self.txt_prog_bar.setValue)
        self._txt_worker.done_signal.connect(self._txt_on_done)
        self._txt_worker.start()

    def _txt_on_done(self, ok_cnt, fail_cnt, out_dir):
        self.txt_convert_btn.setEnabled(True)
        self.txt_convert_btn.setText("✨  EPUB 변환 시작")
        succeeded = getattr(getattr(self, '_txt_worker', None), 'succeeded_paths', [])
        removed = self._txt_remove_converted_paths(succeeded)
        if removed:
            self._txt_log(f"🧹 변환 완료 파일 {removed}개를 목록에서 제거했습니다.", "ok")
        if fail_cnt == 0:
            self._open_folder_confirm(
                out_dir, title="변환 완료 🎉",
                pre_msg=f"전체 {ok_cnt}개 파일 변환 완료! ✅")
        else:
            QMessageBox.warning(
                self, "변환 결과",
                f"성공: {ok_cnt}개 / 실패: {fail_cnt}개\n로그를 확인하세요.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 텍스트 변환 미리보기 다이얼로그
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ── EPUB → TXT 탭 ────────────────────────────────
    _E2T_PLACEHOLDER = "📘 EPUB/TXT 파일을 여기로 드래그하거나 [파일 열기]를 눌러주세요"

    def _build_epub2txt_tab(self, root):
        self._e2t_files = []

        card1, _, bl1 = make_card("📘 변환할 EPUB/TXT 파일", C["accent"])
        top_row = QHBoxLayout(); top_row.setSpacing(5)
        b_add = mk_btn("📂 파일 열기", "blue")
        b_add.clicked.connect(self._e2t_browse_files)
        b_clr = mk_btn("🗑 비우기", "gray")
        b_clr.setToolTip("목록 초기화")
        b_clr.clicked.connect(self._e2t_clear_files)
        b_del = mk_btn("❌ 삭제", "danger")
        b_del.setToolTip("선택 항목 삭제")
        b_del.clicked.connect(self._e2t_delete_selected)
        top_row.addWidget(b_add); top_row.addWidget(b_clr); top_row.addWidget(b_del)
        top_row.addStretch()
        self.e2t_count_lbl = mk_lbl("0개", C["text3"], 11)
        top_row.addWidget(self.e2t_count_lbl)
        bl1.addLayout(top_row)

        self.e2t_list = QListWidget()
        self.e2t_list.setFixedHeight(220)
        self.e2t_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.e2t_list.installEventFilter(self)
        bl1.addWidget(self.e2t_list)
        root.addWidget(card1)
        self._e2t_show_placeholder()

        card3, _, bl3 = make_card("🗂 저장/옵션", C["orange"])
        dir_row = QHBoxLayout(); dir_row.setSpacing(6)
        lbl_dir = mk_lbl("저장 위치", C["text2"], 11); lbl_dir.setFixedWidth(54)
        dir_row.addWidget(lbl_dir)
        _saved_e2t_dir = self._settings.value("last_e2t_dir", str(Path.home() / "Downloads"))
        self.e2t_dir_edit = QLineEdit(_saved_e2t_dir)
        self.e2t_dir_edit.setReadOnly(True)
        dir_row.addWidget(self.e2t_dir_edit, 1)
        b_dir = mk_btn("📁 찾기", "gray")
        b_dir.clicked.connect(self._e2t_browse_dir)
        dir_row.addWidget(b_dir)
        bl3.addLayout(dir_row)

        _chk_style = (
            f"QCheckBox{{font-family:'맑은 고딕';font-size:12px;color:{C['text2']};spacing:5px;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;}}"
            f"QCheckBox::indicator:unchecked{{background:{C['surface2']};border:1.5px solid {C['border']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}"
        )
        opt_row = QHBoxLayout(); opt_row.setSpacing(10)
        self.e2t_chk_remove_pages = QCheckBox("판권/표지/목차 제거")
        self.e2t_chk_remove_pages.setChecked(True)
        self.e2t_chk_remove_pages.setToolTip("체크 시 구조 페이지는 TXT에서 제외")
        self.e2t_chk_remove_pages.setStyleSheet(_chk_style)
        self.e2t_chk_strip_code = QCheckBox("공백코드 제거")
        self.e2t_chk_strip_code.setChecked(True)
        self.e2t_chk_strip_code.setToolTip("체크 시 U+200B 등 보이지 않는 공백 제거")
        self.e2t_chk_strip_code.setStyleSheet(_chk_style)
        self.e2t_chk_text_cleanup = QCheckBox("텍스트 정리")
        self.e2t_chk_text_cleanup.setChecked(True)
        self.e2t_chk_text_cleanup.setToolTip("체크 시 구조 라인(front/Section0001 등) 기본 제거")
        self.e2t_chk_text_cleanup.setStyleSheet(_chk_style)
        self.e2t_chk_indent = QCheckBox("들여쓰기")
        self.e2t_chk_indent.setChecked(True)
        self.e2t_chk_indent.setToolTip("체크 시 TXT 문단 앞에 전각 공백을 넣어 EPUB 본문처럼 보이게 합니다.")
        self.e2t_chk_indent.setStyleSheet(_chk_style)
        opt_row.addWidget(self.e2t_chk_remove_pages)
        opt_row.addWidget(self.e2t_chk_strip_code)
        opt_row.addWidget(self.e2t_chk_text_cleanup)
        opt_row.addWidget(self.e2t_chk_indent)
        opt_row.addStretch()
        bl3.addLayout(opt_row)

        combine_row = QHBoxLayout(); combine_row.setSpacing(6)
        self.e2t_chk_combine = QCheckBox("txt 합치기")
        self.e2t_chk_combine.setChecked(False)
        self.e2t_chk_combine.setToolTip("체크 시 목록 순서대로 한 개의 TXT 파일로 저장합니다.")
        self.e2t_chk_combine.setStyleSheet(_chk_style)
        combine_row.addWidget(self.e2t_chk_combine)
        combine_row.addWidget(mk_lbl("파일명", C["text2"], 11))
        self.e2t_combine_name_edit = QLineEdit("merged")
        self.e2t_combine_name_edit.setPlaceholderText("합본 TXT 파일명")
        combine_row.addWidget(self.e2t_combine_name_edit, 1)
        bl3.addLayout(combine_row)
        root.addWidget(card3)

        card4, _, bl4 = make_card("", C["text3"])
        card4.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.e2t_prog_bar = QProgressBar(); self.e2t_prog_bar.setValue(0)
        bl4.addWidget(self.e2t_prog_bar)
        self.e2t_log_area = QTextEdit()
        self.e2t_log_area.setObjectName("log_area")
        self.e2t_log_area.setReadOnly(True)
        self.e2t_log_area.setMinimumHeight(70)
        self.e2t_log_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bl4.addWidget(self.e2t_log_area)
        root.addWidget(card4, 1)

        self.e2t_convert_btn = mk_btn("✨ 텍스트 변환 시작", "green")
        self.e2t_convert_btn.setFixedHeight(42)
        self.e2t_convert_btn.setStyleSheet(
            f"QPushButton{{background:{C['green']};color:white;font-size:14px;"
            f"font-weight:700;border-radius:8px;font-family:'맑은 고딕';}}"
            f"QPushButton:hover{{background:#16b87a;}}"
            f"QPushButton:disabled{{background:#a8d8c4;color:#ddf0ea;}}")
        self.e2t_convert_btn.clicked.connect(self._e2t_start_convert)
        root.addWidget(self.e2t_convert_btn)

    def _e2t_show_placeholder(self):
        self.e2t_list.clear()
        item = QListWidgetItem(self._E2T_PLACEHOLDER)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        from PyQt6.QtGui import QColor
        item.setForeground(QColor(C['text3']))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.e2t_list.addItem(item)

    def _e2t_log(self, msg, tag="info"):
        colors = {"ok": C["text"], "err": C["red"], "warn": C["orange"], "info": C["text3"]}
        color = colors.get(tag, C["text3"])
        self.e2t_log_area.append(f'<span style="color:{color};font-size:11px;">{msg}</span>')

    def _e2t_browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "EPUB/TXT 파일 선택", "",
            "EPUB/TXT/Archives (*.epub *.txt *.zip *.7z);;EPUB Files (*.epub);;Text Files (*.txt);;Archives (*.zip *.7z);;All Files (*.*)")
        if paths:
            self._e2t_add_files(paths)

    def _e2t_browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", self.e2t_dir_edit.text())
        if d:
            self.e2t_dir_edit.setText(d)
            self._settings.setValue("last_e2t_dir", d)

    def _e2t_clear_files(self):
        self._e2t_files.clear()
        self._e2t_show_placeholder()
        self.e2t_count_lbl.setText("0개")

    def _e2t_delete_selected(self):
        if (self.e2t_list.count() == 1 and self.e2t_list.item(0).text() == self._E2T_PLACEHOLDER):
            return
        rows = sorted({self.e2t_list.row(it) for it in self.e2t_list.selectedItems()}, reverse=True)
        if not rows:
            cur = self.e2t_list.currentRow()
            if 0 <= cur < len(self._e2t_files):
                rows = [cur]
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._e2t_files):
                self._e2t_files.pop(row)
                self.e2t_list.takeItem(row)
        self.e2t_count_lbl.setText(f"{len(self._e2t_files)}개")
        if not self._e2t_files:
            self._e2t_show_placeholder()

    def _e2t_add_files(self, paths):
        paths = self._extract_archives_for_epub(paths)
        expanded = []
        for p in paths:
            if os.path.isdir(p):
                for rt, _, files in os.walk(p):
                    for fn in files:
                        if fn.lower().endswith(('.epub', '.txt')):
                            expanded.append(os.path.join(rt, fn))
            elif p.lower().endswith(('.epub', '.txt')):
                expanded.append(p)

        if not expanded:
            self._e2t_log("EPUB/TXT 파일이 없습니다.", "warn")
            return

        if (self.e2t_list.count() == 1 and self.e2t_list.item(0).text() == self._E2T_PLACEHOLDER):
            self.e2t_list.clear()

        existing = set(self._e2t_files)
        added = 0
        for p in expanded:
            if p in existing:
                continue
            try:
                sz = os.path.getsize(p)
                size_s = (f"{sz/1024:.1f}KB" if sz < 1024*1024 else f"{sz/1024/1024:.2f}MB")
                self._e2t_files.append(p)
                self.e2t_list.addItem(f"  {Path(p).name}   ({size_s})")
                existing.add(p)
                added += 1
            except Exception as ex:
                self._e2t_log(f"{Path(p).name} 로드 실패: {ex}", "err")

        self.e2t_count_lbl.setText(f"{len(self._e2t_files)}개")
        if added:
            self._e2t_log(f"{added}개 파일 추가", "ok")

    def _e2t_start_convert(self):
        if not self._e2t_files:
            QMessageBox.information(self, "알림", "변환할 EPUB/TXT 파일을 추가해 주세요.")
            return
        out_dir = self.e2t_dir_edit.text().strip()
        if not out_dir or not os.path.isdir(out_dir):
            QMessageBox.warning(self, "오류", "유효한 저장 폴더를 선택해 주세요.")
            return

        self.e2t_convert_btn.setEnabled(False)
        self.e2t_convert_btn.setText("변환 중...")
        self.e2t_prog_bar.setValue(0)
        self._e2t_log(f"총 {len(self._e2t_files)}개 파일 변환 시작", "info")

        self._e2t_worker = EpubTxtWorker(
            list(self._e2t_files),
            out_dir,
            remove_skip_pages=self.e2t_chk_remove_pages.isChecked(),
            strip_invisible=self.e2t_chk_strip_code.isChecked(),
            cleanup_text=self.e2t_chk_text_cleanup.isChecked(),
            indent_paragraphs=self.e2t_chk_indent.isChecked(),
            combine_output=self.e2t_chk_combine.isChecked(),
            combined_stem=self.e2t_combine_name_edit.text().strip() or "merged",
        )
        self._e2t_worker.log_signal.connect(self._e2t_log)
        self._e2t_worker.progress_signal.connect(self.e2t_prog_bar.setValue)
        self._e2t_worker.done_signal.connect(self._e2t_on_done)
        self._e2t_worker.start()

    def _e2t_on_done(self, ok_cnt, fail_cnt, out_dir):
        self.e2t_convert_btn.setEnabled(True)
        self.e2t_convert_btn.setText("✨ 텍스트 변환 시작")
        if fail_cnt == 0:
            self._open_folder_confirm(
                out_dir, title="변환 완료 🎉",
                pre_msg=f"전체 {ok_cnt}개 파일 변환 완료!")
        else:
            QMessageBox.warning(
                self, "변환 결과",
                f"성공: {ok_cnt}개 / 실패: {fail_cnt}개\n로그를 확인해 주세요.")


    def _build_dedupe_tab(self, root):
        self._dedupe_groups = []
        self._dedupe_selected_paths = set()

        card1, _, bl1 = make_card("중복 정리 대상 폴더", C["accent"])
        folder_row = QHBoxLayout(); folder_row.setSpacing(6)
        folder_row.addWidget(mk_lbl("폴더", C["text2"], 11))
        saved_dir = self._settings.value("last_dedupe_dir", str(Path.home() / "Downloads"))
        self.dedupe_dir_edit = QLineEdit(saved_dir)
        self.dedupe_dir_edit.setPlaceholderText("폴더 경로를 붙여넣거나 찾기로 선택")
        self.dedupe_dir_edit.returnPressed.connect(self._dedupe_scan)
        folder_row.addWidget(self.dedupe_dir_edit, 1)
        b_dir = mk_btn("찾기", "gray")
        b_dir.clicked.connect(self._dedupe_browse_dir)
        folder_row.addWidget(b_dir)
        b_scan = mk_btn("스캔", "blue")
        b_scan.clicked.connect(self._dedupe_scan)
        folder_row.addWidget(b_scan)
        bl1.addLayout(folder_row)

        chk_style = (
            f"QCheckBox{{font-family:'맑은 고딕';font-size:12px;color:{C['text2']};spacing:5px;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;}}"
            f"QCheckBox::indicator:unchecked{{background:{C['surface2']};border:1.5px solid {C['border']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}"
        )
        opt_chk_row = QHBoxLayout(); opt_chk_row.setSpacing(10)
        self.dedupe_keep_ext_chk = QCheckBox("확장자별 최종본 유지")
        self.dedupe_keep_ext_chk.setChecked(True)
        self.dedupe_keep_ext_chk.setToolTip("켜짐: epub/txt/zip 등 확장자별로 하나씩 남깁니다.\n꺼짐: 확장자와 관계없이 작품당 하나만 남깁니다.")
        self.dedupe_keep_ext_chk.setStyleSheet(chk_style)
        self.dedupe_recursive_chk = QCheckBox("하위 폴더 포함")
        self.dedupe_recursive_chk.setChecked(False)
        self.dedupe_recursive_chk.setStyleSheet(chk_style)
        self.dedupe_fuzzy_chk = QCheckBox("비슷한 제목도 찾기")
        self.dedupe_fuzzy_chk.setChecked(False)
        self.dedupe_fuzzy_chk.setToolTip("켜짐: 제목이 조금 달라도 유사 후보로 묶습니다. 확인 필요 그룹은 기본 선택하지 않습니다.")
        self.dedupe_fuzzy_chk.setStyleSheet(chk_style)
        self.dedupe_hash_chk = QCheckBox("해시 정밀 확인")
        self.dedupe_hash_chk.setChecked(False)
        self.dedupe_hash_chk.setToolTip("켜짐: 후보 파일 내용을 읽어 SHA-256 해시가 같은지 확인합니다. 큰 파일이 많으면 스캔이 느려질 수 있습니다.")
        self.dedupe_hash_chk.setStyleSheet(chk_style)
        opt_chk_row.addWidget(self.dedupe_keep_ext_chk)
        opt_chk_row.addWidget(self.dedupe_recursive_chk)
        opt_chk_row.addWidget(self.dedupe_fuzzy_chk)
        opt_chk_row.addWidget(self.dedupe_hash_chk)
        opt_chk_row.addStretch()
        bl1.addLayout(opt_chk_row)

        opt_row = QHBoxLayout(); opt_row.setSpacing(10)
        opt_row.addWidget(mk_lbl("대상", C["text2"], 11))
        self.dedupe_ext_edit = QLineEdit("epub, txt, zip, 7z")
        opt_row.addWidget(self.dedupe_ext_edit, 1)
        opt_row.addWidget(mk_lbl("우선순위", C["text2"], 11))
        self.dedupe_priority_edit = QLineEdit("epub, txt, zip, 7z")
        opt_row.addWidget(self.dedupe_priority_edit, 1)
        bl1.addLayout(opt_row)
        root.addWidget(card1)

        card2, _, bl2 = make_card("중복 후보 미리보기", C["orange"])
        summary_row = QHBoxLayout(); summary_row.setSpacing(8)
        self.dedupe_summary_lbl = mk_lbl("스캔 전", C["text3"], 11)
        summary_row.addWidget(self.dedupe_summary_lbl)
        summary_row.addWidget(mk_lbl("보기", C["text2"], 11))
        self.dedupe_filter_combo = QComboBox()
        self.dedupe_filter_combo.addItems(["전체", "확인 필요", "안전", "해시 같음", "해시 다름", "선택됨"])
        self.dedupe_filter_combo.setFixedWidth(96)
        self.dedupe_filter_combo.currentTextChanged.connect(lambda _text: self._dedupe_apply_filter())
        summary_row.addWidget(self.dedupe_filter_combo)
        summary_row.addStretch()
        b_hash = mk_btn("선택 그룹 해시 확인", "gray")
        b_hash.setToolTip("표에서 선택한 그룹 또는 체크된 후보가 있는 그룹만 파일 해시를 확인합니다.")
        b_hash.clicked.connect(self._dedupe_verify_selected_hashes)
        b_review_hash = mk_btn("확인대상 해시 확인", "gray")
        b_review_hash.setToolTip("확인 필요 그룹 전체의 파일 해시를 확인합니다.")
        b_review_hash.clicked.connect(self._dedupe_verify_review_hashes)
        b_all = mk_btn("삭제후보 자동선택", "gray")
        b_all.setToolTip("안전한 삭제 후보만 자동으로 체크합니다. 확인 필요 항목은 해시 확인 후 판단합니다.")
        b_all.clicked.connect(lambda: self._dedupe_set_all(True))
        b_none = mk_btn("전체 해제", "gray")
        b_none.clicked.connect(lambda: self._dedupe_set_all(False))
        summary_row.addWidget(b_hash)
        summary_row.addWidget(b_review_hash)
        summary_row.addWidget(b_all)
        summary_row.addWidget(b_none)
        bl2.addLayout(summary_row)

        self.dedupe_table = QTableWidget(0, 6)
        self.dedupe_table.setHorizontalHeaderLabels([
            "그룹", "선택", "상태", "파일명", "크기", "판정",
        ])
        self.dedupe_table.verticalHeader().setVisible(False)
        self.dedupe_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dedupe_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.dedupe_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.dedupe_table.horizontalHeader()
        header.setMinimumSectionSize(30)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 0)
        self.dedupe_table.setColumnHidden(0, True)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 34)
        header.sectionClicked.connect(self._dedupe_header_clicked)
        self.dedupe_table.setItemDelegateForColumn(1, CenteredCheckBoxDelegate(self.dedupe_table))
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 58)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 78)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.dedupe_table.itemChanged.connect(self._dedupe_item_changed)
        bl2.addWidget(self.dedupe_table, 1)
        root.addWidget(card2, 1)

        card3, _, bl3 = make_card("", C["text3"])
        self.dedupe_log_area = QTextEdit()
        self.dedupe_log_area.setObjectName("log_area")
        self.dedupe_log_area.setReadOnly(True)
        self.dedupe_log_area.setMinimumHeight(42)
        self.dedupe_log_area.setMaximumHeight(58)
        bl3.addWidget(self.dedupe_log_area)
        root.addWidget(card3)

        action_row = QHBoxLayout(); action_row.setSpacing(8)
        self.dedupe_restore_btn = mk_btn("최근 격리 복구", "gray")
        self.dedupe_restore_btn.setFixedHeight(42)
        self.dedupe_restore_btn.setToolTip("가장 최근 _dedupe_trash_ 폴더의 이동 로그를 읽어 원래 위치로 복구합니다.")
        self.dedupe_restore_btn.clicked.connect(self._dedupe_restore_latest)
        action_row.addWidget(self.dedupe_restore_btn)
        self.dedupe_run_btn = mk_btn("선택 항목 격리 폴더로 이동", "green")
        self.dedupe_run_btn.setFixedHeight(42)
        self.dedupe_run_btn.setToolTip("삭제하지 않고 선택한 정리 후보를 _dedupe_trash_날짜 폴더로 이동합니다.")
        self.dedupe_run_btn.clicked.connect(self._dedupe_run)
        action_row.addWidget(self.dedupe_run_btn, 1)
        root.addLayout(action_row)

    def _dedupe_log(self, msg, tag="info"):
        colors = {"ok": C["text"], "err": C["red"], "warn": C["orange"], "info": C["text3"]}
        self.dedupe_log_area.append(
            f'<span style="color:{colors.get(tag, C["text3"])};font-size:11px;">{msg}</span>'
        )

    def _dedupe_browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "중복 정리 폴더 선택", self.dedupe_dir_edit.text())
        if d:
            self.dedupe_dir_edit.setText(d)
            self._settings.setValue("last_dedupe_dir", d)

    def _dedupe_scan(self):
        folder = self.dedupe_dir_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "오류", "정리할 폴더를 먼저 선택해 주세요.")
            return
        try:
            from epub_binder_core.duplicate_service import normalize_extensions, scan_duplicate_folder
            ext_priority = normalize_extensions(self.dedupe_priority_edit.text())
            self._dedupe_groups = scan_duplicate_folder(
                folder,
                extensions=normalize_extensions(self.dedupe_ext_edit.text()),
                recursive=self.dedupe_recursive_chk.isChecked(),
                keep_per_extension=self.dedupe_keep_ext_chk.isChecked(),
                ext_priority=ext_priority,
                fuzzy_match=self.dedupe_fuzzy_chk.isChecked(),
                verify_hash=self.dedupe_hash_chk.isChecked(),
            )
        except Exception as ex:
            QMessageBox.critical(self, "스캔 실패", str(ex))
            return
        self._dedupe_render_table()
        removable_count = sum(len(group.removable) for group in self._dedupe_groups)
        self._dedupe_log(f"스캔 완료: 그룹 {len(self._dedupe_groups)}개, 정리 후보 {removable_count}개", "ok")

    def _dedupe_group_base_bg(self, group_index: int) -> str:
        """같은 시리즈 그룹은 같은 배경, 다음 그룹은 다른 배경으로 구분."""
        return "#f8fbf8" if group_index % 2 else "#ffffff"

    def _dedupe_action_label(self, decision, default_select: bool) -> str:
        if decision.keep:
            return "남김"
        return "삭제" if default_select else "확인"

    def _dedupe_action_label_for_path(self, path_value, checked: bool = False) -> str:
        if not path_value:
            return ""
        if checked:
            return "삭제"
        path = str(Path(path_value).resolve())
        for group in self._dedupe_groups:
            if any(str(Path(candidate.path).resolve()) == path for candidate in group.removable):
                return "확인"
        return ""

    def _dedupe_row_palette(self, group, decision, default_select, group_index: int = 1):
        """중복 정리 표용 저채도 그룹 배경 + 진한 상태 뱃지 팔레트."""
        row_bg = self._dedupe_group_base_bg(group_index)
        if decision.keep:
            return {
                "row_bg": row_bg,
                "badge_bg": "#2f855a",
                "keep_badge_bg": "#2f855a",
                "delete_badge_bg": "#dc2626",
                "review_badge_bg": "#d97706",
                "fg": "#ffffff",
                "muted_fg": "#334155",
            }
        if default_select:
            return {
                "row_bg": row_bg,
                "badge_bg": "#dc2626",
                "keep_badge_bg": "#2f855a",
                "delete_badge_bg": "#dc2626",
                "review_badge_bg": "#d97706",
                "fg": "#ffffff",
                "muted_fg": "#334155",
            }
        if group.confidence == "낮음":
            return {
                "row_bg": row_bg,
                "badge_bg": "#d97706",
                "keep_badge_bg": "#2f855a",
                "delete_badge_bg": "#dc2626",
                "review_badge_bg": "#d97706",
                "fg": "#ffffff",
                "muted_fg": "#334155",
            }
        return {
            "row_bg": row_bg,
            "badge_bg": "#d97706",
            "keep_badge_bg": "#2f855a",
            "delete_badge_bg": "#dc2626",
            "review_badge_bg": "#d97706",
            "fg": "#ffffff",
            "muted_fg": "#334155",
        }

    def _dedupe_render_table(self):
        self.dedupe_table.blockSignals(True)
        self.dedupe_table.setRowCount(0)
        self._dedupe_selected_paths = set()
        badge_font = QFont()
        badge_font.setBold(True)
        for index, group in enumerate(self._dedupe_groups, start=1):
            default_select = self._dedupe_group_is_safe(group)
            warning_text = ", ".join(group.warnings)
            for decision in group.decisions:
                candidate = decision.candidate
                row = self.dedupe_table.rowCount()
                self.dedupe_table.insertRow(row)
                palette = self._dedupe_row_palette(group, decision, default_select, index)

                group_item = QTableWidgetItem(f"G{index}")
                group_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                group_item.setData(Qt.ItemDataRole.UserRole, index - 1)
                group_item.setToolTip(self._dedupe_row_tooltip(group, decision, index, warning_text))
                self.dedupe_table.setItem(row, 0, group_item)

                select_item = QTableWidgetItem("")
                if decision.keep:
                    select_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    select_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    select_item.setFont(badge_font)
                else:
                    select_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    select_item.setCheckState(Qt.CheckState.Checked if default_select else Qt.CheckState.Unchecked)
                    select_item.setData(Qt.ItemDataRole.UserRole, candidate.path)
                    if default_select:
                        self._dedupe_selected_paths.add(str(Path(candidate.path).resolve()))
                select_item.setToolTip(self._dedupe_row_tooltip(group, decision, index, warning_text))
                self.dedupe_table.setItem(row, 1, select_item)
                values = [
                    self._dedupe_action_label(decision, default_select),
                    candidate.name,
                    self._dedupe_format_size(candidate.size),
                    self._dedupe_decision_label(group, decision, warning_text),
                ]
                for item in (group_item, select_item):
                    item.setBackground(QColor(palette["row_bg"]))
                    item.setForeground(QColor(palette["fg"] if decision.keep else palette["muted_fg"]))
                for col, value in enumerate(values, start=2):
                    item = QTableWidgetItem(value)
                    item.setToolTip(self._dedupe_row_tooltip(group, decision, index, warning_text))
                    if col == 2:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setBackground(QColor(palette["badge_bg"]))
                        item.setForeground(QColor(palette["fg"]))
                        item.setFont(badge_font)
                    else:
                        item.setBackground(QColor(palette["row_bg"]))
                        item.setForeground(QColor(palette["muted_fg"]))
                    self.dedupe_table.setItem(row, col, item)
                self.dedupe_table.setRowHeight(row, 28)
        self.dedupe_table.blockSignals(False)
        self._dedupe_update_summary()
        self._dedupe_apply_filter()

    def _dedupe_group_is_safe(self, group):
        if group.confidence == "높음":
            return True
        return tuple(group.warnings) == ("해시 일치",)

    def _dedupe_status_label(self, group, decision):
        if decision.keep:
            return "남김"
        if "해시 다름 확인 필요" in group.warnings:
            return "위험"
        if "해시 일치" in group.warnings:
            return "해시 같음"
        if self._dedupe_group_is_safe(group):
            return "안전"
        return "확인"

    def _dedupe_row_tooltip(self, group, decision, group_index, warning_text):
        candidate = decision.candidate
        lines = [
            f"그룹 G{group_index}: {group.display_title}",
            f"파일: {candidate.name}",
            f"경로: {candidate.path}",
            f"신뢰도: {group.confidence}",
        ]
        if warning_text:
            lines.append(f"확인: {warning_text}")
        lines.append(f"남길 파일: {group.keeper.name}")
        if decision.reason:
            lines.append(f"판정: {decision.reason}")
        return "\n".join(lines)

    def _dedupe_format_size(self, size):
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size:,} B"

    def _dedupe_decision_label(self, group, decision, warning_text=""):
        candidate = decision.candidate
        keeper = group.keeper
        parts = []
        if decision.keep:
            parts.append("유지")
            if candidate.complete:
                parts.append("완결")
            if candidate.range_end:
                parts.append(f"{candidate.range_start}-{candidate.range_end}")
            if warning_text:
                parts.append("확인 필요")
            return " · ".join(parts)
        parts.append("이동 후보" if self._dedupe_group_is_safe(group) else "확인 필요")
        if candidate.incomplete and not keeper.incomplete:
            parts.append("미완")
        if candidate.range_end and keeper.range_end and candidate.range_end < keeper.range_end:
            parts.append("범위 작음")
        if candidate.complete is False and keeper.complete:
            parts.append("완결본 아님")
        if candidate.ext != keeper.ext:
            parts.append("확장자 우선 낮음")
        if candidate.size and keeper.size and candidate.size < keeper.size:
            parts.append("용량 작음")
        if candidate.side_story:
            parts.append("외전/합본 확인")
        if "유사 제목 확인 필요" in group.warnings:
            parts.append("유사 제목")
        if "해시 일치" in group.warnings:
            parts.append("해시 같음")
        if "해시 일부 미확인" in group.warnings:
            parts.append("해시 일부 미확인")
        if "해시 다름 확인 필요" in group.warnings:
            parts.append("해시 다름")
        return " · ".join(dict.fromkeys(parts)) or "중복 후보"

    def _dedupe_item_changed(self, item):
        if item.column() != 1:
            return
        path_value = item.data(Qt.ItemDataRole.UserRole)
        if not path_value:
            return
        path = str(Path(path_value).resolve())
        if item.checkState() == Qt.CheckState.Checked:
            self._dedupe_selected_paths.add(path)
        else:
            self._dedupe_selected_paths.discard(path)
        status_item = self.dedupe_table.item(item.row(), 2)
        if status_item:
            status_item.setText(self._dedupe_action_label_for_path(path_value, checked=item.checkState() == Qt.CheckState.Checked))
            if item.checkState() == Qt.CheckState.Checked:
                status_item.setBackground(QColor("#dc2626"))
                status_item.setForeground(QColor("#ffffff"))
            else:
                status_item.setBackground(QColor("#d97706"))
                status_item.setForeground(QColor("#ffffff"))
        self._dedupe_update_summary()
        if self.dedupe_filter_combo.currentText() == "선택됨":
            self._dedupe_apply_filter()

    def _dedupe_set_all(self, checked: bool):
        self.dedupe_table.blockSignals(True)
        self._dedupe_selected_paths = set()
        for row in range(self.dedupe_table.rowCount()):
            item = self.dedupe_table.item(row, 1)
            if not item or item.text() == "남김":
                continue
            path_value = item.data(Qt.ItemDataRole.UserRole)
            if not path_value:
                continue
            safe = self._dedupe_path_is_safe(path_value)
            should_check = checked and safe
            item.setCheckState(Qt.CheckState.Checked if should_check else Qt.CheckState.Unchecked)
            status_item = self.dedupe_table.item(row, 2)
            if status_item:
                status_item.setText(self._dedupe_action_label_for_path(path_value, checked=should_check))
                status_item.setBackground(QColor("#dc2626" if should_check else "#d97706"))
                status_item.setForeground(QColor("#ffffff"))
            if should_check:
                self._dedupe_selected_paths.add(str(Path(path_value).resolve()))
        self.dedupe_table.blockSignals(False)
        self._dedupe_update_summary()

    def _dedupe_header_clicked(self, section: int):
        if section != 1:
            return
        self._dedupe_set_all(not bool(self._dedupe_selected_paths))

    def _dedupe_path_is_safe(self, path_value):
        path = str(Path(path_value).resolve())
        for group in self._dedupe_groups:
            if not self._dedupe_group_is_safe(group):
                continue
            if any(str(Path(candidate.path).resolve()) == path for candidate in group.removable):
                return True
        return False

    def _dedupe_update_summary(self):
        total_groups = len(self._dedupe_groups)
        removable = sum(len(group.removable) for group in self._dedupe_groups)
        selected = len(self._dedupe_selected_paths)
        self.dedupe_summary_lbl.setText(
            f"그룹 {total_groups}개 / 정리 후보 {removable}개 / 선택 {selected}개"
        )
        if selected:
            self.dedupe_run_btn.setText(f"선택 {selected}개 격리 폴더로 이동")
        else:
            self.dedupe_run_btn.setText("선택 항목 격리 폴더로 이동")

    def _dedupe_apply_filter(self):
        if not hasattr(self, "dedupe_filter_combo"):
            return
        mode = self.dedupe_filter_combo.currentText()
        visible_rows = 0
        for row in range(self.dedupe_table.rowCount()):
            group_item = self.dedupe_table.item(row, 0)
            select_item = self.dedupe_table.item(row, 1)
            status_item = self.dedupe_table.item(row, 2)
            group_index = group_item.data(Qt.ItemDataRole.UserRole) if group_item else None
            group = self._dedupe_groups[group_index] if isinstance(group_index, int) and 0 <= group_index < len(self._dedupe_groups) else None
            status = status_item.text() if status_item else ""
            checked = bool(select_item and select_item.checkState() == Qt.CheckState.Checked)
            show = True
            if mode == "확인 필요":
                show = bool(group and not self._dedupe_group_is_safe(group))
            elif mode == "안전":
                show = bool(group and self._dedupe_group_is_safe(group))
            elif mode == "해시 같음":
                show = bool(group and "해시 일치" in group.warnings)
            elif mode == "해시 다름":
                show = bool(group and "해시 다름 확인 필요" in group.warnings)
            elif mode == "선택됨":
                show = checked or bool(group and self._dedupe_group_has_selected_candidate(group))
            self.dedupe_table.setRowHidden(row, not show)
            if show:
                visible_rows += 1
        return visible_rows

    def _dedupe_group_has_selected_candidate(self, group):
        return any(
            str(Path(candidate.path).resolve()) in self._dedupe_selected_paths
            for candidate in group.removable
        )

    def _dedupe_selected_group_indexes(self):
        indexes: set[int] = set()
        for model_index in self.dedupe_table.selectionModel().selectedRows():
            group_item = self.dedupe_table.item(model_index.row(), 0)
            if group_item:
                group_index = group_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(group_index, int):
                    indexes.add(group_index)
        if indexes:
            return indexes
        for row in range(self.dedupe_table.rowCount()):
            select_item = self.dedupe_table.item(row, 1)
            group_item = self.dedupe_table.item(row, 0)
            if not select_item or not group_item:
                continue
            if select_item.checkState() != Qt.CheckState.Checked:
                continue
            group_index = group_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(group_index, int):
                indexes.add(group_index)
        return indexes

    def _dedupe_verify_selected_hashes(self):
        if not self._dedupe_groups:
            QMessageBox.information(self, "알림", "먼저 스캔해 주세요.")
            return
        group_indexes = self._dedupe_selected_group_indexes()
        if not group_indexes:
            QMessageBox.information(self, "알림", "해시 확인할 그룹의 행을 선택하거나 후보를 체크해 주세요.")
            return
        try:
            from epub_binder_core.duplicate_service import normalize_extensions, verify_duplicate_groups_hashes
            ext_priority = normalize_extensions(self.dedupe_priority_edit.text())
            selected_groups = [self._dedupe_groups[index] for index in sorted(group_indexes)]
            refreshed = verify_duplicate_groups_hashes(selected_groups, ext_priority=ext_priority)
        except Exception as ex:
            QMessageBox.critical(self, "해시 확인 실패", str(ex))
            return
        for index, group in zip(sorted(group_indexes), refreshed):
            self._dedupe_groups[index] = group
        checked_before = set(self._dedupe_selected_paths)
        self._dedupe_render_table()
        self._dedupe_restore_checked_paths(checked_before)
        self._dedupe_log(f"선택 그룹 {len(group_indexes)}개 해시 확인 완료", "ok")

    def _dedupe_verify_review_hashes(self):
        if not self._dedupe_groups:
            QMessageBox.information(self, "알림", "먼저 스캔해 주세요.")
            return
        group_indexes = {
            index for index, group in enumerate(self._dedupe_groups)
            if not self._dedupe_group_is_safe(group)
        }
        if not group_indexes:
            QMessageBox.information(self, "알림", "해시 확인이 필요한 그룹이 없습니다.")
            return
        try:
            from epub_binder_core.duplicate_service import normalize_extensions, verify_duplicate_groups_hashes
            ext_priority = normalize_extensions(self.dedupe_priority_edit.text())
            selected_groups = [self._dedupe_groups[index] for index in sorted(group_indexes)]
            refreshed = verify_duplicate_groups_hashes(selected_groups, ext_priority=ext_priority)
        except Exception as ex:
            QMessageBox.critical(self, "해시 확인 실패", str(ex))
            return
        for index, group in zip(sorted(group_indexes), refreshed):
            self._dedupe_groups[index] = group
        checked_before = set(self._dedupe_selected_paths)
        self._dedupe_render_table()
        self._dedupe_restore_checked_paths(checked_before)
        self._dedupe_log(f"확인대상 {len(group_indexes)}개 그룹 해시 확인 완료", "ok")

    def _dedupe_restore_checked_paths(self, paths):
        self.dedupe_table.blockSignals(True)
        self._dedupe_selected_paths = set()
        normalized = {str(Path(path).resolve()) for path in paths}
        for row in range(self.dedupe_table.rowCount()):
            item = self.dedupe_table.item(row, 1)
            if not item or item.text() == "남김":
                continue
            path_value = item.data(Qt.ItemDataRole.UserRole)
            if not path_value:
                continue
            path = str(Path(path_value).resolve())
            checked = path in normalized
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            status_item = self.dedupe_table.item(row, 2)
            if status_item:
                status_item.setText(self._dedupe_action_label_for_path(path_value, checked=checked))
                status_item.setBackground(QColor("#dc2626" if checked else "#d97706"))
                status_item.setForeground(QColor("#ffffff"))
            if checked:
                self._dedupe_selected_paths.add(path)
        self.dedupe_table.blockSignals(False)
        self._dedupe_update_summary()
        self._dedupe_apply_filter()

    def _dedupe_run(self):
        if not self._dedupe_groups:
            QMessageBox.information(self, "알림", "먼저 스캔해 주세요.")
            return
        if not self._dedupe_selected_paths:
            QMessageBox.information(self, "알림", "이동할 정리 후보를 선택해 주세요.")
            return
        folder = self.dedupe_dir_edit.text().strip()
        unsafe_count = self._dedupe_selected_unsafe_count()
        confirm_text = f"선택한 {len(self._dedupe_selected_paths)}개 파일을 삭제하지 않고 _dedupe_trash 폴더로 이동할까요?"
        if unsafe_count:
            confirm_text += f"\n\n확인 필요 후보 {unsafe_count}개가 포함되어 있습니다."
        reply = QMessageBox.question(
            self,
            "격리 이동 확인",
            confirm_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from epub_binder_core.duplicate_service import move_duplicate_candidates_to_trash
            result = move_duplicate_candidates_to_trash(
                self._dedupe_groups,
                set(self._dedupe_selected_paths),
                root_folder=folder,
            )
        except Exception as ex:
            QMessageBox.critical(self, "이동 실패", str(ex))
            return
        self._dedupe_log(f"{len(result.moved)}개 파일을 격리 폴더로 이동했습니다: {result.trash_dir}", "ok")
        self._dedupe_log(f"이동 로그: {result.log_path}", "info")
        self._dedupe_scan()

    def _dedupe_selected_unsafe_count(self):
        safe_paths: set[str] = set()
        for group in self._dedupe_groups:
            if self._dedupe_group_is_safe(group):
                safe_paths.update(str(Path(candidate.path).resolve()) for candidate in group.removable)
        return sum(1 for path in self._dedupe_selected_paths if path not in safe_paths)

    def _dedupe_restore_latest(self):
        folder = self.dedupe_dir_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "오류", "복구할 기준 폴더를 먼저 선택해 주세요.")
            return
        reply = QMessageBox.question(
            self,
            "최근 격리 복구",
            "가장 최근 _dedupe_trash 폴더의 파일을 원래 위치로 복구할까요?\n\n원래 위치에 파일이 있으면 덮어쓰지 않고 건너뜁니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from epub_binder_core.duplicate_service import restore_latest_dedupe_trash
            result = restore_latest_dedupe_trash(folder)
        except Exception as ex:
            QMessageBox.critical(self, "복구 실패", str(ex))
            return
        self._dedupe_log(
            f"복구 완료: {len(result.restored)}개 / 충돌 {len(result.conflicts)}개 / 누락 {len(result.missing)}개",
            "ok" if not result.conflicts and not result.missing else "warn",
        )
        if result.conflicts:
            self._dedupe_log("원래 위치에 파일이 있어 건너뛴 항목이 있습니다.", "warn")
        if result.missing:
            self._dedupe_log("격리 폴더에서 찾지 못한 항목이 있습니다.", "warn")
        self._dedupe_scan()


class TxtPreviewDialog(QDialog):
    """챕터 목록 미리보기 + 제목 편집 + 병합/삭제."""

    def __init__(self, file_dict, parent=None, detect_fn=None):
        super().__init__(parent)
        self.setWindowTitle(f"챕터 미리보기 — {Path(file_dict['path']).name}")
        self.resize(520, 560)
        self._chapters    = [(t, list(ls)) for t, ls in file_dict['chapters']]
        self._raw_text    = file_dict.get('raw_text', '')
        self._detect_fn   = detect_fn  # _txt_detect(text, force_subtitle_style=...)
        self._strength_override = file_dict.get('strength_override')
        self._view_indices = list(range(len(self._chapters)))
        self._suspect_rows = set()
        self._auto_merge_rows = set()

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        # 메타데이터
        meta = QHBoxLayout(); meta.setSpacing(6)
        meta.addWidget(QLabel("제목"))
        self.title_edit = QLineEdit(file_dict['title']); meta.addWidget(self.title_edit, 2)
        meta.addWidget(QLabel("작가"))
        self.author_edit = QLineEdit(file_dict['author']); meta.addWidget(self.author_edit, 1)
        root.addLayout(meta)

        option_row = QHBoxLayout(); option_row.setSpacing(10)

        # 챕터 테이블 — [제목, 본문길이] (소제목 열 제거 → 버튼 행 체크박스로 이동)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(
            ["챕터 제목 (더블클릭 편집)", "본문 길이"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)   # 제목 열 자동 채움
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setStretchLastSection(False)
        hdr.setMinimumSectionSize(50)
        self.table.setColumnWidth(1, 90)
        # 좌측 연번(수직 헤더)
        vh = self.table.verticalHeader()
        vh.setStyleSheet(
            "QHeaderView::section {"
            "  background-color: #eef2f7; color: #6b7280;"
            "  border: none; border-right: 1px solid #d6dae0;"
            "  padding: 0 8px; font-weight: 500;"
            "}"
        )
        vh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._refresh_table()
        root.addWidget(self.table, 1)

        # 버튼 행 ─────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)

        b_merge_up = mk_btn("⬆ 위와 병합", "gray")
        b_merge_up.clicked.connect(self._merge_up)
        b_del = mk_btn("❌ 삭제", "danger")
        b_del.clicked.connect(self._delete_selected)

        # 소제목 체크박스 — 이 파일 전체의 소제목 흡수 ON/OFF
        self.chk_subtitle = QCheckBox("소제목")
        self.chk_subtitle.setChecked(bool(file_dict.get('subtitle_style', False)))
        self.chk_subtitle.setToolTip(
            "체크: 챕터 헤더 뒤 짧은 줄을 소제목으로 흡수\n"
            "해제: 소제목 오탐 방지 — 챕터 제목에 소제목을 붙이지 않음\n"
            "(변경 시 챕터 목록이 재감지됩니다)")
        self.chk_subtitle.setStyleSheet(
            f"QCheckBox {{ color:{C['text']}; font-size:12px; spacing:5px; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; }}"
            f"QCheckBox::indicator:checked {{ background:{C['accent']}; border:1px solid {C['accent']};"
            f"  border-radius:3px; image: url({_check_svg_path}); }}"
            f"QCheckBox::indicator:unchecked {{ background:white; border:1px solid {C['border']};"
            f"  border-radius:3px; }}"
        )
        self.chk_subtitle.stateChanged.connect(self._on_subtitle_toggle)

        self.chk_strong = QCheckBox("목차 강함")
        self.chk_strong.setChecked(self._strength_override == "strong")
        self.chk_strong.setToolTip("이 파일만 확장 패턴으로 다시 감지")
        self.chk_strong.setStyleSheet(self.chk_subtitle.styleSheet())
        self.chk_strong.stateChanged.connect(self._on_strength_toggle)

        self.chk_suspect_only = QCheckBox("의심만 보기")
        self.chk_suspect_only.setChecked(False)
        self.chk_suspect_only.setToolTip("숫자 흐름이 끊기거나 오탐 가능성이 있는 행만 표시")
        self.chk_suspect_only.setStyleSheet(self.chk_subtitle.styleSheet())
        self.chk_suspect_only.stateChanged.connect(lambda _state: self._refresh_table())

        b_auto_merge = mk_btn("오탐 자동 병합", "gray")
        b_auto_merge.setToolTip("태그/특전/중복 번호처럼 확실한 오탐만 위 챕터에 병합")
        b_auto_merge.clicked.connect(self._merge_auto_suspects)

        option_row.addWidget(self.chk_subtitle)
        option_row.addWidget(self.chk_strong)
        option_row.addWidget(self.chk_suspect_only)
        option_row.addWidget(b_auto_merge)
        option_row.addStretch()
        root.insertLayout(1, option_row)

        btn_row.addWidget(b_merge_up)
        btn_row.addWidget(b_del)
        btn_row.addStretch()
        b_ok = mk_btn("✓ 저장", "green"); b_ok.clicked.connect(self.accept)
        b_cancel = mk_btn("취소", "gray"); b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_ok)
        btn_row.addWidget(b_cancel)
        root.addLayout(btn_row)

    # ── 소제목 체크박스 토글 → 재감지 ──────────────────────
    def _on_subtitle_toggle(self, state):
        """소제목 체크 변경 시 raw_text를 재감지해 챕터 목록 갱신."""
        self._redetect_preview()

    def _on_strength_toggle(self, state):
        """목차 강함 체크 변경 시 raw_text를 재감지해 챕터 목록 갱신."""
        self._redetect_preview()

    def _redetect_preview(self):
        if not self._detect_fn or not self._raw_text:
            return
        force = self.chk_subtitle.isChecked()
        self._strength_override = "strong" if self.chk_strong.isChecked() else None
        chapters, _ = self._detect_fn(
            self._raw_text,
            force_subtitle_style=force,
            override_strength=self._strength_override)
        self._chapters = [(t, list(ls)) for t, ls in chapters]
        self._refresh_table()

    def _refresh_table(self):
        try:
            from epub_binder_core.txt_chapters import analyze_chapter_suspects
            suspects = analyze_chapter_suspects(self._chapters)
        except Exception:
            suspects = []
        self._suspect_rows = {int(item.get("row", -1)) for item in suspects}
        self._auto_merge_rows = {
            int(item.get("row", -1))
            for item in suspects
            if item.get("auto_merge")
        }
        if hasattr(self, "chk_suspect_only") and self.chk_suspect_only.isChecked():
            self._view_indices = [i for i in range(len(self._chapters)) if i in self._suspect_rows]
        else:
            self._view_indices = list(range(len(self._chapters)))

        self.table.setRowCount(len(self._view_indices))
        for view_row, source_row in enumerate(self._view_indices):
            t, ls = self._chapters[source_row]
            it = QTableWidgetItem(t)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            if source_row in self._suspect_rows:
                color = QColor("#ffe8e8") if source_row in self._auto_merge_rows else QColor("#fff3c4")
                it.setBackground(color)
            self.table.setItem(view_row, 0, it)
            length = sum(len(x) for x in ls)
            it2 = QTableWidgetItem(f"{length:,} 자")
            it2.setFlags(it2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if source_row in self._suspect_rows:
                color = QColor("#ffe8e8") if source_row in self._auto_merge_rows else QColor("#fff3c4")
                it2.setBackground(color)
            self.table.setItem(view_row, 1, it2)

    def _commit_edits(self):
        for view_row, source_row in enumerate(getattr(self, "_view_indices", [])):
            it = self.table.item(view_row, 0)
            if it and 0 <= source_row < len(self._chapters):
                _t, ls = self._chapters[source_row]
                self._chapters[source_row] = (it.text(), ls)

    def _merge_up(self):
        self._commit_edits()
        view_rows = sorted({i.row() for i in self.table.selectedIndexes()})
        rows = sorted({
            self._view_indices[row]
            for row in view_rows
            if 0 <= row < len(self._view_indices)
        })
        if not rows:
            return
        rows = [r for r in rows if r > 0]
        for r in reversed(rows):
            t, ls = self._chapters.pop(r)
            prev_t, prev_l = self._chapters[r - 1]
            prev_l.append(f"<b>{t}</b>")
            prev_l.extend(ls)
            self._chapters[r - 1] = (prev_t, prev_l)
        self._refresh_table()

    def _delete_selected(self):
        self._commit_edits()
        view_rows = sorted({i.row() for i in self.table.selectedIndexes()})
        rows = sorted({
            self._view_indices[row]
            for row in view_rows
            if 0 <= row < len(self._view_indices)
        }, reverse=True)
        for r in rows:
            if 0 <= r < len(self._chapters):
                self._chapters.pop(r)
        self._refresh_table()

    def _merge_auto_suspects(self):
        self._commit_edits()
        try:
            from epub_binder_core.txt_chapters import merge_auto_suspect_chapters
            self._chapters = merge_auto_suspect_chapters(self._chapters)
        except Exception:
            return
        self._refresh_table()

    def get_title(self):    return self.title_edit.text().strip() or "제목 없음"
    def get_author(self):   return self.author_edit.text().strip() or "미상"
    def get_subtitle_style(self): return self.chk_subtitle.isChecked()
    def get_strength_override(self): return self._strength_override
    def get_chapters(self):
        self._commit_edits()
        return self._chapters


class RenameBatchDialog(QDialog):
    MODE_REPLACE = "replace"
    MODE_PREFIX = "prefix"
    MODE_REMOVE = "remove"
    MODE_OVERWRITE = "overwrite"

    def __init__(self, parent, total_count: int, selected_count: int):
        super().__init__(parent)
        self.setWindowTitle("🔧 일괄 변경")
        self.setModal(True)
        self.resize(500, 300)
        self.setStyleSheet(parent.styleSheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        guide = mk_lbl(
            "변경될 이름 열에만 적용되며 확장자는 유지됩니다. "
            "선택 행만 또는 전체에 일괄 적용할 수 있습니다.",
            C["text3"], 11)
        guide.setWordWrap(True)
        root.addWidget(guide)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.src_lbl = mk_lbl("찾을 문자열", C["text2"], 11)
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("예: 기존제목")
        form.addWidget(self.src_lbl, 0, 0)
        form.addWidget(self.src_edit, 0, 1, 1, 3)

        self.dst_lbl = mk_lbl("바꿀 문자열", C["text2"], 11)
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText("예: [작가] 제목")
        form.addWidget(self.dst_lbl, 1, 0)
        form.addWidget(self.dst_edit, 1, 1, 1, 3)

        form.addWidget(mk_lbl("변경 방식", C["text2"], 11), 2, 0)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        self.rb_replace = QRadioButton("찾아 바꾸기")
        self.rb_prefix = QRadioButton("앞에 추가")
        self.rb_remove = QRadioButton("삭제")
        self.rb_overwrite = QRadioButton("덮어쓰기")
        for rb in (self.rb_replace, self.rb_prefix, self.rb_remove, self.rb_overwrite):
            rb.toggled.connect(self._sync_mode_ui)
            mode_row.addWidget(rb)
        self.rb_replace.setChecked(True)
        mode_row.addStretch()
        form.addLayout(mode_row, 2, 1, 1, 3)

        self.chk_case = QCheckBox("대소문자 구분")
        self.chk_post_episode = QCheckBox("변경 후 화수 보정")
        self.chk_post_episode.setChecked(True)
        self.chk_append_episode = QCheckBox("뒤에 화수 붙이기")
        opt_row = QHBoxLayout()
        opt_row.setSpacing(14)
        opt_row.addWidget(self.chk_case)
        opt_row.addWidget(self.chk_post_episode)
        opt_row.addWidget(self.chk_append_episode)
        opt_row.addStretch()
        form.addWidget(mk_lbl("옵션", C["text2"], 11), 3, 0)
        form.addLayout(opt_row, 3, 1, 1, 3)

        ep_row = QHBoxLayout()
        ep_row.setSpacing(8)
        ep_row.addWidget(mk_lbl("시작 번호", C["text2"], 11))
        self.ep_start_spin = QSpinBox()
        self.ep_start_spin.setRange(1, 99999)
        self.ep_start_spin.setValue(1)
        self.ep_start_spin.setFixedWidth(90)
        ep_row.addWidget(self.ep_start_spin)
        ep_row.addWidget(mk_lbl("증가", C["text2"], 11))
        self.ep_step_spin = QSpinBox()
        self.ep_step_spin.setRange(1, 999)
        self.ep_step_spin.setValue(1)
        self.ep_step_spin.setFixedWidth(70)
        ep_row.addWidget(self.ep_step_spin)
        self.ep_unit_combo = QComboBox()
        self.ep_unit_combo.addItems(["화", "권"])
        self.ep_unit_combo.setFixedWidth(70)
        ep_row.addWidget(self.ep_unit_combo)
        ep_row.addStretch()
        form.addWidget(mk_lbl("화수 입력", C["text2"], 11), 4, 0)
        form.addLayout(ep_row, 4, 1, 1, 3)
        self.chk_append_episode.toggled.connect(lambda on: (
            self.ep_start_spin.setEnabled(on),
            self.ep_step_spin.setEnabled(on),
            self.ep_unit_combo.setEnabled(on)
        ))
        self.chk_append_episode.setChecked(False)
        self.ep_start_spin.setEnabled(False)
        self.ep_step_spin.setEnabled(False)
        self.ep_unit_combo.setEnabled(False)

        self.rb_scope_all = QRadioButton(f"전체 {total_count}개")
        self.rb_scope_selected = QRadioButton(f"선택 {selected_count}개")
        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)
        self.scope_group.addButton(self.rb_scope_all)
        self.scope_group.addButton(self.rb_scope_selected)
        self.rb_scope_selected.setEnabled(selected_count > 0)
        if selected_count > 0:
            self.rb_scope_selected.setChecked(True)
        else:
            self.rb_scope_all.setChecked(True)
        scope_row = QHBoxLayout()
        scope_row.setSpacing(12)
        scope_row.addWidget(self.rb_scope_all)
        scope_row.addWidget(self.rb_scope_selected)
        scope_row.addStretch()
        form.addWidget(mk_lbl("적용 범위", C["text2"], 11), 5, 0)
        form.addLayout(scope_row, 5, 1, 1, 3)
        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        b_cancel = mk_btn("취소", "gray")
        b_save = mk_btn("✔ 저장", "blue")
        b_cancel.clicked.connect(self.reject)
        b_save.clicked.connect(self._accept_if_valid)
        btn_row.addWidget(b_cancel)
        btn_row.addWidget(b_save)
        root.addLayout(btn_row)

        self._sync_mode_ui()

    def _current_mode(self) -> str:
        if self.rb_prefix.isChecked():
            return self.MODE_PREFIX
        if self.rb_remove.isChecked():
            return self.MODE_REMOVE
        if self.rb_overwrite.isChecked():
            return self.MODE_OVERWRITE
        return self.MODE_REPLACE

    def _sync_mode_ui(self):
        if not all(hasattr(self, attr) for attr in ("src_lbl", "src_edit", "dst_lbl", "dst_edit", "chk_case")):
            return
        mode = self._current_mode()
        show_dst = mode == self.MODE_REPLACE
        self.dst_lbl.setVisible(show_dst)
        self.dst_edit.setVisible(show_dst)
        self.chk_case.setEnabled(mode in (self.MODE_REPLACE, self.MODE_REMOVE))

        if mode == self.MODE_REPLACE:
            self.src_lbl.setText("찾을 문자열")
            self.src_edit.setPlaceholderText("예: 기존제목")
            self.dst_edit.setPlaceholderText("예: [작가] 제목")
        elif mode == self.MODE_PREFIX:
            self.src_lbl.setText("추가 문자열")
            self.src_edit.setPlaceholderText("예: [작가]")
        elif mode == self.MODE_REMOVE:
            self.src_lbl.setText("삭제 문자열")
            self.src_edit.setPlaceholderText("예: 특수문구")
        else:
            self.src_lbl.setText("새 이름")
            self.src_edit.setPlaceholderText("예: [작가] 새 제목")

    def _accept_if_valid(self):
        mode = self._current_mode()
        src = self.src_edit.text().strip()
        # 뒤에 화수만 붙이는 용도라면 기존 이름을 기준으로 삼으므로 입력 공란 허용
        if not src and not self.chk_append_episode.isChecked():
            QMessageBox.information(self, "입력 필요", f"{self.src_lbl.text()}을 입력해 주세요.")
            return
        append_only = self.chk_append_episode.isChecked() and not src
        if mode == self.MODE_REPLACE and not self.dst_edit.text() and not append_only:
            QMessageBox.information(self, "입력 필요", "바꿀 문자열을 입력해 주세요.")
            return
        self.accept()

    def get_config(self) -> dict:
        return {
            "mode": self._current_mode(),
            "source": self.src_edit.text(),
            "target": self.dst_edit.text(),
            "case_sensitive": self.chk_case.isChecked(),
            "post_episode_fix": self.chk_post_episode.isChecked(),
            "append_episode": self.chk_append_episode.isChecked(),
            "append_episode_start": int(self.ep_start_spin.value()),
            "append_episode_step": int(self.ep_step_spin.value()),
            "append_episode_unit": self.ep_unit_combo.currentText().strip() or "화",
            "scope": "selected" if self.rb_scope_selected.isChecked() else "all",
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 목차 제목 편집 다이얼로그
#    권 라벨(상위) + 화 제목(하위) 트리 구조 편집
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class TocEditDialog(QDialog):
    """
    _row_meta 각 행: {'kind': 'book'|'chapter', 'book_idx': int, 'chap_idx': int|None}
    kind='book'    → 파일 단위 상위노드 라벨 (편집 가능)
    kind='chapter' → 해당 파일 내 화 제목 (편집 가능, 빈칸=NCX에서 숨김)
    """
    def __init__(self, parent, files: list, toc_titles: list,
                 page_titles: list | None = None):
        """
        page_titles: list of list — files[i] 의 (item_id, href, page_title) 목록
                     None 이면 화 제목 행 없이 권 라벨만 표시 (기존 동작)
        """
        super().__init__(parent)
        self.setWindowTitle("📝 목차 제목 편집")
        self.setMinimumSize(540, 420)
        self.resize(540, 560)
        self.setModal(True)
        self.setStyleSheet(parent.styleSheet())
        self._files       = files
        self._toc_titles  = list(toc_titles)
        self._page_titles = page_titles or [[] for _ in files]
        # 저장용: book_labels / chap_labels
        self._book_labels = list(toc_titles)
        # chap_labels[i] = [(item_id, href, editable_title), ...]
        self._chap_labels = [list(pt) for pt in self._page_titles]
        self._row_meta    = []   # 각 테이블 행 메타

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # 안내
        hint = mk_lbl(
            "더블클릭 또는 F2로 편집  |  빈칸=NCX 숨김  |  Enter 확정  |  Esc 취소",
            C["text3"], 11)
        lay.addWidget(hint)

        # 내부 화 제목이 없으면 파일/권 라벨을 편집 대상으로 표시한다.
        # 이름변경 → 병합하기처럼 파일명 기반 목차만 가진 목록도 빈 창이 되지 않게 한다.
        self._show_book_rows = not any(self._chap_labels)
        row_count = (
            len(files)
            if self._show_book_rows
            else sum(len(self._chap_labels[i]) for i in range(len(files)))
        )

        self.table = QTableWidget(row_count, 2)
        self.table.setHorizontalHeaderLabels(["#", "목차 표시 제목"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 52)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setStyleSheet(
            f"QTableWidget{{background:{C['surface2']};border:1px solid {C['border']};"
            f"border-radius:6px;outline:none;gridline-color:{C['border']};"
            f"font-family:'맑은 고딕';font-size:12px;color:{C['text']};}}"
            f"QTableWidget::item{{padding:3px 6px;color:{C['text']};}}"
            f"QTableWidget::item:selected{{background:rgba(34,114,216,0.1);color:{C['accent']};}}"
            f"QTableWidget::item:hover{{background:{C['bg2']};}}"
            f"QHeaderView::section{{background:{C['bg2']};border:none;"
            f"border-bottom:1px solid {C['border']};border-right:1px solid {C['border']};"
            f"padding:4px 8px;color:{C['text2']};font-size:11px;font-family:'맑은 고딕';}}"
        )

        from PyQt6.QtGui import QColor, QFont as _QFont
        row = 0
        chap_seq = 0  # 전체 화 순번
        for i, (path, name, _) in enumerate(files):
            if self._show_book_rows:
                num_item = QTableWidgetItem(str(i + 1))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                num_item.setForeground(QColor(C["text3"]))
                self.table.setItem(row, 0, num_item)

                title = self._book_labels[i] if i < len(self._book_labels) else Path(name).stem
                book_title = QTableWidgetItem(title or Path(name).stem)
                book_title.setForeground(QColor(C["text2"]))
                self.table.setItem(row, 1, book_title)
                self.table.setRowHeight(row, 26)
                self._row_meta.append({'kind': 'book', 'book_idx': i, 'chap_idx': None})
                row += 1
                continue

            # ── 화 제목 행들만 표시 (권 라벨 행 없음) ──
            for j, (iid, href, ptitle) in enumerate(self._chap_labels[i]):
                chap_seq += 1
                num_item = QTableWidgetItem(str(chap_seq))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                num_item.setForeground(QColor(C["text3"]))
                self.table.setItem(row, 0, num_item)

                sub_title = QTableWidgetItem(ptitle or "")
                sub_title.setForeground(QColor(C["text2"] if ptitle else C["text3"]))
                self.table.setItem(row, 1, sub_title)
                self.table.setRowHeight(row, 26)
                self._row_meta.append({'kind': 'chapter', 'book_idx': i, 'chap_idx': j})
                row += 1

        lay.addWidget(self.table)

        # 버튼 행
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        b_delete = mk_btn("❌ 선택 행 삭제", "danger")
        b_delete.clicked.connect(self._delete_selected_rows)
        b_reset = mk_btn("↺ 파일명으로 초기화", "gray")
        b_reset.clicked.connect(self._reset)
        b_ok    = mk_btn("✔ 저장", "green"); b_ok.setMinimumWidth(90)
        b_ok.clicked.connect(self._save)
        b_cancel = mk_btn("취소", "gray"); b_cancel.setMinimumWidth(70)
        b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_delete)
        btn_row.addWidget(b_reset)
        btn_row.addStretch()
        btn_row.addWidget(b_ok); btn_row.addWidget(b_cancel)
        lay.addLayout(btn_row)

    def _reset(self):
        """화 제목은 빈칸으로, 파일/권 라벨은 파일명으로 초기화."""
        for row, meta in enumerate(self._row_meta):
            item = self.table.item(row, 1)
            if not item:
                continue
            if meta['kind'] == 'book':
                bi = meta['book_idx']
                if 0 <= bi < len(self._files):
                    item.setText(Path(self._files[bi][1]).stem)
            elif meta['kind'] == 'chapter':
                    item.setText("")

    def _delete_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._row_meta):
                meta = self._row_meta.pop(row)
                if meta['kind'] == 'chapter':
                    bi = meta['book_idx']
                    ci = meta['chap_idx']
                    if 0 <= bi < len(self._chap_labels) and 0 <= ci < len(self._chap_labels[bi]):
                        self._chap_labels[bi].pop(ci)
                self.table.removeRow(row)

        if getattr(self, '_show_book_rows', False):
            for row in range(self.table.rowCount()):
                num_item = self.table.item(row, 0)
                if num_item:
                    num_item.setText(str(row + 1))
            return

        chapter_rows = [m for m in self._row_meta if m['kind'] == 'chapter']
        new_meta = []
        chap_seq = 0
        for row, meta in enumerate(chapter_rows):
            bi = meta['book_idx']
            ci = len([m for m in new_meta if m['kind'] == 'chapter' and m['book_idx'] == bi])
            new_meta.append({'kind': 'chapter', 'book_idx': bi, 'chap_idx': ci})
            chap_seq += 1
            num_item = self.table.item(row, 0)
            if num_item:
                num_item.setText(str(chap_seq))
        self._row_meta = new_meta

    def _save(self):
        """테이블 값을 읽어 book/chapter labels 갱신."""
        for row, meta in enumerate(self._row_meta):
            item = self.table.item(row, 1)
            text = item.text().strip() if item else ""
            bi = meta['book_idx']
            if meta['kind'] == 'book':
                if 0 <= bi < len(self._book_labels):
                    fallback = Path(self._files[bi][1]).stem if bi < len(self._files) else ""
                    self._book_labels[bi] = text or fallback
            elif meta['kind'] == 'chapter':
                ci = meta['chap_idx']
                iid, href, _ = self._chap_labels[bi][ci]
                self._chap_labels[bi][ci] = (iid, href, text)
        self.accept()

    def get_titles(self):
        """기존 호환: 권 라벨 리스트 반환"""
        return self._book_labels

    def get_chap_labels(self):
        """화 제목 리스트 반환: list of list of (iid, href, title)"""
        return self._chap_labels


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 표지 선택 다이얼로그
#    EPUB에 표지 후보가 여러 개일 때 썸네일로 선택
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 네이버 시리즈 표지 검색 다이얼로그
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class NaverSeriesCoverDialog(QDialog):
    """표지 검색 통합 다이얼로그 — 네이버 시리즈 직접 추출 OR 구글 이미지 검색."""

    def __init__(self, parent, title: str = "", nid_aut: str = "", nid_ses: str = ""):
        super().__init__(parent)
        self.setWindowTitle("표지 검색")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._cover_data   = None
        self._cover_ext    = '.jpg'
        self._fetched_title  = ""
        self._fetched_author = ""
        self._nid_aut    = nid_aut
        self._nid_ses    = nid_ses
        self._fetch_thread = None
        self._title = title

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # ── 헤더 ─────────────────────────────────────
        hdr = QLabel("📚  네이버 시리즈 표지 가져오기")
        hdr.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:700;background:transparent;")
        root.addWidget(hdr)
        if title:
            sub = QLabel(f"작품: {title}")
            sub.setStyleSheet(
                f"color:{C['text3']};font-size:11px;background:transparent;")
            root.addWidget(sub)

        # ── URL 입력 ──────────────────────────────────
        no_row = QHBoxLayout(); no_row.setSpacing(6)
        no_lbl = QLabel("URL 또는 productNo")
        no_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;background:transparent;")
        no_row.addWidget(no_lbl)
        self.no_edit = QLineEdit()
        self.no_edit.setPlaceholderText(
            "예) 13364647  또는  https://series.naver.com/novel/detail.series?productNo=13364647")
        no_row.addWidget(self.no_edit, 1)
        root.addLayout(no_row)

        cookie_ok = bool(nid_aut and nid_ses)
        if not cookie_ok:
            warn = QLabel("⚠ 쿠키가 설정되지 않았습니다. 상단 [🍪 쿠키 설정]에서 먼저 입력해주세요.")
            warn.setStyleSheet(
                f"color:{C['orange']};font-size:11px;background:transparent;")
            warn.setWordWrap(True)
            root.addWidget(warn)

        self.status_lbl = QLabel("대기 중...")
        self.status_lbl.setStyleSheet(
            f"color:{C['text3']};font-size:11px;background:transparent;")
        self.status_lbl.setWordWrap(True)
        root.addWidget(self.status_lbl)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setVisible(False)
        self.prog_bar.setFixedHeight(6)
        root.addWidget(self.prog_bar)

        # ── 버튼 행 ───────────────────────────────────
        bot = QHBoxLayout(); bot.setSpacing(8)
        bot.addStretch()
        b_close = QPushButton("닫기")
        b_close.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:5px 16px;color:{C['text2']};font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg3']};}}")
        b_close.clicked.connect(self.reject)
        bot.addWidget(b_close)
        b_google = QPushButton("🔍 검색")
        b_google.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:5px 16px;color:#111;font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg3']};border-color:{C['accent']};color:{C['accent']};}}")
        b_google.clicked.connect(self._open_google)
        bot.addWidget(b_google)
        self.b_fetch = QPushButton("📥 네이버에서 가져오기")
        self.b_fetch.setEnabled(cookie_ok)
        self.b_fetch.setStyleSheet(
            f"QPushButton{{background:{C['accent']};border:none;border-radius:6px;"
            f"padding:6px 18px;color:#fff;font-size:11px;font-weight:600;}}"
            f"QPushButton:hover{{background:#1a5fc4;}}"
            f"QPushButton:disabled{{background:{C['bg3']};color:{C['text3']};}}")
        self.b_fetch.clicked.connect(self._start_fetch)
        bot.addWidget(self.b_fetch)
        root.addLayout(bot)

    # ── 내부 헬퍼 ────────────────────────────────────
    def _parse_product_no(self, text: str) -> str:
        text = text.strip()
        m = re.search(r'productNo=(\d+)', text)
        if m:
            return m.group(1)
        if re.fullmatch(r'\d+', text):
            return text
        return ""

    def _start_fetch(self):
        no = self._parse_product_no(self.no_edit.text())
        if not no:
            self.status_lbl.setText("⚠ 올바른 URL 또는 productNo를 입력해주세요.")
            return

        self.b_fetch.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.status_lbl.setText(f"productNo {no} 로 표지를 가져오는 중...")

        self._fetch_thread = NaverSeriesFetchThread(no, self._nid_aut, self._nid_ses)
        self._fetch_thread.progress.connect(self._on_progress)
        self._fetch_thread.finished.connect(self._on_finished)
        self._fetch_thread.failed.connect(self._on_failed)
        self._fetch_thread.start()

    def _on_progress(self, msg: str):
        self.status_lbl.setText(msg)

    def _on_finished(self, data: bytes, ext: str, title: str, author: str):
        self._cover_data     = data
        self._cover_ext      = ext
        self._fetched_title  = title
        self._fetched_author = author
        self.prog_bar.setVisible(False)
        self.accept()

    def _on_failed(self, msg: str):
        self.status_lbl.setText(f"❌ {msg}")
        self.prog_bar.setVisible(False)
        self.b_fetch.setEnabled(True)

    def _open_google(self):
        import webbrowser
        from urllib.parse import quote_plus
        query = f"{self._title} 표지" if self._title else "표지"
        webbrowser.open(f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}")
        self.status_lbl.setText(f"🔎 구글 검색 열림: {query}")

    def get_cover(self):
        """(data, ext, title, author) 반환. 미완료 시 (None, '.jpg', '', '')."""
        return self._cover_data, self._cover_ext, self._fetched_title, self._fetched_author


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 진입점
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import datetime
    from epub_binder_app.settings import APP_EXPIRATION_DATE
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 10))

    # 아이콘 설정 (base64 내장 — 파일 생성 없이 메모리에서 직접 로드)
    from PyQt6.QtGui import QIcon, QPixmap
    try:
        import base64 as _b64
        _ico_data = _b64.b64decode(_ICO_B64)
        _pix = QPixmap()
        _pix.loadFromData(_ico_data, 'ICO')
        app.setWindowIcon(QIcon(_pix))
    except Exception:
        pass
    if APP_EXPIRATION_DATE:
        days_left = (APP_EXPIRATION_DATE - datetime.date.today()).days
        if days_left < 0:
            QMessageBox.critical(None, "사용 기간 만료",
                f"이 버전의 사용 기간이 만료되었습니다.\n\n만료일: {APP_EXPIRATION_DATE.strftime('%Y년 %m월 %d일')}")
            sys.exit(0)
        if days_left <= 7:
            QMessageBox.warning(None, "사용 기간 안내",
                f"이 버전의 사용 기간이 {days_left}일 남았습니다.\n\n만료일: {APP_EXPIRATION_DATE.strftime('%Y년 %m월 %d일')}")
    gui = EPUBMergerGUI()
    gui.show()
    sys.exit(app.exec())
