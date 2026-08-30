import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView

class UltronDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ULTRON — Ward 4B Clinical Dashboard")
        self.setGeometry(100, 100, 1280, 800)

        # Embedded browser view directed to your local server
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("http://127.0.0.1:8000"))
        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UltronDesktopApp()
    window.show()
    sys.exit(app.exec())