from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtWebEngineWidgets import *
from PyQt6.QtWebEngineCore import *
from PyQt6.QtNetwork import *
from torpy import TorClient,utils
from torpy.cli.socks import SocksServer
from threading import Thread
import logging,socket,sys

class AddressBar(QLineEdit):
	def __init__(self,parent=None):
		super(AddressBar,self).__init__(parent)
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

class MainWindow(QMainWindow):
	connected = pyqtSignal(QUrl)

	def __init__(self,*args,**kwargs):
		super(MainWindow,self).__init__(*args,**kwargs)

		profile = QWebEngineProfile.defaultProfile()
		browser = QWebEngineView()
		webpage = QWebEnginePage(profile,browser)
		browser.setPage(webpage)
		browser.setUrl(QUrl("about:blank"))
		self.connected.connect(browser.setUrl)

		nav = QToolBar()
		nav.setStyleSheet("""
			QToolBar{
				background-color:#fff;
				padding:3px;
				border-bottom:1px solid #dbdcdd;
			}
		""")
		nav.setVisible(False)
		self.connected.connect(lambda:nav.setVisible(True))

		address = AddressBar()
		address.setStyleSheet("""
			QLineEdit{
				height:26px;
				font-size:14px;
				border-radius:13px;
				padding-left:6px;
				padding-right:6px;
				border:2px solid transparent;
				background-color:#f1f3f4;
				margin-bottom:1px;
				color:#696a6c;
				font-family:"Segoe UI";
			}
			QLineEdit:focus{
				color:#202124;
				background-color:#fff;
				border:2px solid #1a73e8;
			}
		""")
		address.returnPressed.connect(lambda:(
			browser.setUrl(QUrl(address.text())),
			address.setCursorPosition(0),
			browser.setFocus()
		))
		browser.urlChanged.connect(lambda u:(
			address.setText(u.toString()),
			address.setCursorPosition(0),
			browser.setFocus()
		))
		nav.addWidget(address)

		progress = QProgressBar()
		progress.setFixedHeight(3)
		progress.setTextVisible(False)
		progress.setStyleSheet("""
			QProgressBar{
				border:none;
				margin:0;
				padding:0;
				background-color:transparent;
			}
		""")
		browser.loadStarted.connect(lambda:(
			progress.setVisible(True)
		))
		browser.loadProgress.connect(lambda p:(
			progress.setValue(99 if p==100 else p)
		))
		browser.loadFinished.connect(lambda:(
			progress.setVisible(False)
		))

		self.status = QStatusBar()
		self.status.setSizeGripEnabled(False)
		self.setStatusBar(self.status)

		layout = QVBoxLayout()
		layout.setContentsMargins(0,0,0,0)
		layout.setSpacing(0)
		layout.addWidget(nav)
		layout.addWidget(progress)
		layout.addWidget(browser)
		widget = QWidget()
		widget.setLayout(layout)
		self.setCentralWidget(widget)
		self.setWindowTitle("Trowser")
		browser.setFocus()
		self.show()
	
def startTor(port):
	with TorClient() as tor:
		with tor.create_circuit() as circuit:
			with SocksServer(circuit,"127.0.0.1",port) as socks:
				socks.start()

class LogReader(logging.Handler):
	def __init__(self,window):
		super(LogReader,self).__init__()
		self.window = window
		self.connected = False

	def emit(self,record):
		message = self.format(record)
		if message.startswith("Start socks proxy at"):
			self.connected = True
			self.window.connected.emit(QUrl("https://check.torproject.org"))
		if self.connected:
			self.window.status.showMessage("Connected to Tor. ("+message+")")
		else:
			self.window.status.showMessage("Connecting to Tor... ("+message+")")

if __name__=="__main__":
	s = socket.socket()
	s.bind(("127.0.0.1",0))
	port = s.getsockname()[1]
	s.close()

	Thread(target=startTor,args=(port,),daemon=True).start()
	utils.register_logger(True)
	logger = logging.getLogger()
	logger.setLevel(logging.INFO)

	proxy = QNetworkProxy()
	proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
	proxy.setHostName("127.0.0.1")
	proxy.setPort(port)
	QNetworkProxy.setApplicationProxy(proxy)
	
	app = QApplication([])
	window = MainWindow()
	logger.addHandler(LogReader(window))

	sys.exit(app.exec())