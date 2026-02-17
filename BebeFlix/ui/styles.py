"""
Light theme stylesheet for BebeFlix.
Clean white background with baby pink accents.
"""

LIGHT_THEME = """
QWidget {
    background-color: #FAFAFA;
    color: #2C2C2C;
    font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #FFFFFF;
}
QScrollArea {
    border: none;
    background-color: #FFFFFF;
}
QScrollArea > QWidget > QWidget {
    background-color: #FFFFFF;
}
QScrollBar:vertical {
    background: #F5F5F5;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #F48FB1;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #EC407A;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    height: 0;
}
QLineEdit {
    background-color: #FFFFFF;
    color: #2C2C2C;
    border: 2px solid #E0E0E0;
    border-radius: 22px;
    padding: 10px 20px;
    font-size: 14px;
    selection-background-color: #F48FB1;
    selection-color: #FFFFFF;
}
QLineEdit:focus {
    border: 2px solid #F48FB1;
}
QLineEdit::placeholder {
    color: #BDBDBD;
}
QPushButton {
    background-color: #FFFFFF;
    color: #2C2C2C;
    border: 2px solid #E0E0E0;
    border-radius: 18px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #FCE4EC;
    border-color: #F48FB1;
    color: #D81B60;
}
QPushButton:pressed {
    background-color: #F8BBD0;
    border-color: #EC407A;
}
QPushButton#primaryButton {
    background-color: #F48FB1;
    color: #FFFFFF;
    border: none;
    border-radius: 18px;
    padding: 10px 24px;
    font-weight: bold;
}
QPushButton#primaryButton:hover {
    background-color: #EC407A;
}
QPushButton#primaryButton:pressed {
    background-color: #D81B60;
}
QComboBox {
    background-color: #FFFFFF;
    color: #2C2C2C;
    border: 2px solid #E0E0E0;
    border-radius: 14px;
    padding: 6px 16px;
    font-size: 13px;
    min-width: 120px;
}
QComboBox:hover {
    border-color: #F48FB1;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #F48FB1;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #2C2C2C;
    border: 2px solid #F8BBD0;
    border-radius: 8px;
    selection-background-color: #FCE4EC;
    selection-color: #D81B60;
    outline: none;
    padding: 4px;
}
QLabel {
    color: #2C2C2C;
    background-color: transparent;
}
QLabel#movieTitle {
    font-size: 12px;
    font-weight: 600;
    color: #2C2C2C;
}
QLabel#subtitleLabel {
    font-size: 11px;
    color: #9E9E9E;
}
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #E0E0E0;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #F48FB1;
    border: 2px solid #FFFFFF;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:hover {
    background: #EC407A;
}
QSlider::sub-page:horizontal {
    background: #F48FB1;
    border-radius: 3px;
}
QProgressBar {
    border: none;
    background-color: #F5F5F5;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #F48FB1, stop:1 #EC407A);
    border-radius: 6px;
}
QDialog {
    background-color: #FFFFFF;
}
QGroupBox {
    border: 2px solid #F8BBD0;
    border-radius: 12px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: bold;
    color: #D81B60;
    background-color: #FFFBFC;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #D81B60;
}
QCheckBox {
    spacing: 8px;
    color: #2C2C2C;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #F48FB1;
    border-color: #F48FB1;
}
QCheckBox::indicator:hover {
    border-color: #F48FB1;
}
QMenu {
    background-color: #FFFFFF;
    border: 2px solid #F8BBD0;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 24px;
    border-radius: 6px;
    color: #2C2C2C;
}
QMenu::item:selected {
    background-color: #FCE4EC;
    color: #D81B60;
}
QToolTip {
    background-color: #FFFFFF;
    color: #2C2C2C;
    border: 2px solid #F8BBD0;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}
"""
