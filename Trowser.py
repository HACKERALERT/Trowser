from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtWebEngineCore import *
from PyQt6.QtWebEngineWidgets import *
from PyQt6.QtNetwork import *
from urllib.parse import urlparse,urlunparse
from torpy import TorClient,utils
from torpy.cli.socks import SocksServer
from logging import INFO,Handler,getLogger
from threading import Thread
from socket import socket
from sys import argv,exit

class AddressBar(QLineEdit):
	def __init__(self):
		super(AddressBar,self).__init__()
		self.editing = False

	def mousePressEvent(self,e):
		super(AddressBar,self).mousePressEvent(e)
		if not self.editing:
			self.selectAll()
			self.editing = True

	def focusOutEvent(self,e):
		super(AddressBar,self).focusOutEvent(e)
		self.editing = False
		self.setCursorPosition(0)

class WebEnginePage(QWebEnginePage):
	def bind(self,window,tab):
		self.window = window
		self.tab = tab

	def createWindow(self,_):
		page = WebEnginePage(self)
		page.urlChanged.connect(self.changed)
		return page

	def changed(self,url):
		page = self.sender()
		self.window.addTab(url,self.tab)
		page.deleteLater()

class BrowserTab(QWidget):
	def __init__(self,window):
		super(QWidget,self).__init__()
		self.browser = QWebEngineView()
		self.browser.setPage(WebEnginePage(self.browser))
		self.browser.page().bind(window,self)

		layout = QVBoxLayout()
		layout.setContentsMargins(0,0,0,0)
		layout.setSpacing(0)
		nav = QToolBar()

		back = QPushButton()
		back.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
		back.setFixedWidth(30)
		back.pressed.connect(self.browser.back)
		nav.addWidget(back)

		forward = QPushButton()
		forward.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
		forward.setFixedWidth(30)
		forward.pressed.connect(self.browser.forward)
		nav.addWidget(forward)

		reload = QPushButton()
		reload.setFixedWidth(30)
		nav.addWidget(reload)

		address = AddressBar()
		address.returnPressed.connect(lambda:(
			self.browser.setUrl(QUrl(urlunparse(urlparse(address.text())._replace(scheme="https")))),
			self.browser.setFocus()
		))
		nav.addWidget(address)

		self.browser.urlChanged.connect(lambda url:(
			address.setText(url.toString()),
			self.browser.setFocus(),
			back.setDisabled(not self.browser.history().canGoBack()),
			forward.setDisabled(not self.browser.history().canGoForward())
		))

		progress = QProgressBar()
		progress.setFixedHeight(8)
		progress.setTextVisible(False)

		self.browser.loadStarted.connect(lambda:(
			progress.setVisible(True),
			reload.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserStop)),
			reload.pressed.connect(self.browser.stop)
		))
		self.browser.loadProgress.connect(lambda p:(
			progress.setValue(99 if p==100 else p)
		))
		self.browser.loadFinished.connect(lambda:(
			progress.setVisible(False),
			reload.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)),
			reload.pressed.connect(self.browser.reload)
		))

		layout.addWidget(nav)
		layout.addWidget(progress)
		layout.addWidget(self.browser)
		self.setLayout(layout)

class MainWindow(QMainWindow):
	connected = pyqtSignal()

	def __init__(self):
		super(MainWindow,self).__init__()
		self.tabs = QTabWidget()
		self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
		self.tabs.setMovable(True)
		self.tabs.setTabsClosable(True)
		self.tabs.setStyleSheet("QTabBar::tab{max-width:400px;}")
		self.tabs.tabCloseRequested.connect(lambda index:(
			self.tabs.removeTab(index),
			self.addTab(None) if self.tabs.count()==0 else None,
		))
		self.connected.connect(lambda:self.tabs.widget(0).browser.reload())

		newTab = QPushButton()
		newTab.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
		newTab.pressed.connect(lambda:(
			self.addTab(None)
		))
		self.tabs.setCornerWidget(newTab)

		self.status = QStatusBar()
		self.status.setSizeGripEnabled(False)
		self.setStatusBar(self.status)

		self.setContentsMargins(8,8,8,2)
		self.setCentralWidget(self.tabs)
		self.setWindowTitle("Trowser")
		self.addTab("https://check.torproject.org")
		self.show()

	def addTab(self,url,pos=None):
		tab = BrowserTab(self)
		tab.browser.setUrl(QUrl(url if url else "https://ddg.gg"))
		tab.browser.titleChanged.connect(lambda title:(
			self.tabs.setTabText(self.tabs.indexOf(tab),title)
		))
		tab.browser.iconChanged.connect(lambda icon:(
			self.tabs.setTabIcon(self.tabs.indexOf(tab),icon)
		))
		if not pos:
			self.tabs.addTab(tab,"Loading...")
		else:
			self.tabs.insertTab(self.tabs.indexOf(pos)+1,tab,"Loading...")
		self.tabs.setCurrentWidget(tab)

def startTor(port):
	with TorClient() as tor:
		with tor.create_circuit() as circuit:
			with SocksServer(circuit,"127.0.0.1",port) as socks:
				socks.start()

class LogReader(Handler):
	def __init__(self,window):
		super(LogReader,self).__init__()
		self.window = window
		self.connected = False

	def emit(self,record):
		message = self.format(record)
		if message.startswith("Start socks proxy at"):
			self.connected = True
			self.window.connected.emit()
		if self.connected:
			self.window.status.showMessage("Connected to Tor. ("+message+")")
		else:
			self.window.status.showMessage("Connecting to Tor... ("+message+")")

if __name__=="__main__":
	s = socket()
	s.bind(("127.0.0.1",0))
	port = s.getsockname()[1]
	s.close()

	Thread(target=startTor,args=(port,),daemon=True).start()
	utils.register_logger(True)
	logger = getLogger()
	logger.setLevel(INFO)

	proxy = QNetworkProxy()
	proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
	proxy.setHostName("127.0.0.1")
	proxy.setPort(port)
	QNetworkProxy.setApplicationProxy(proxy)

	app = QApplication(argv)
	app.setStyle("Fusion")
	window = MainWindow()
	logger.addHandler(LogReader(window))
	exit(app.exec())