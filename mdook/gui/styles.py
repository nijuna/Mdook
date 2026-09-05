"""Qt stylesheets (QSS) for the dark (default) and light themes."""

DARK_STYLE = """
QWidget {
    background-color: #1e1f22;
    color: #e3e3e3;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1f22;
}

QLabel, QWidget#TransparentRow, QWidget#AISettingsWidget {
    /* Without this, child container QWidgets paint their own opaque background rect from
       the generic QWidget rule above, instead of blending into whatever
       container (e.g. QFrame#Card) they actually sit inside. */
    background-color: transparent;
}

QCheckBox {
    background-color: transparent;
    spacing: 8px;
    color: #e3e3e3;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #5a5b62;
    border-radius: 4px;
    background-color: #2c2d31;
}

QCheckBox::indicator:hover {
    border-color: #4a6cf7;
}

QCheckBox::indicator:checked {
    background-color: #4a6cf7;
    border-color: #4a6cf7;
}

#HeaderTitle {
    font-size: 22px;
    font-weight: 600;
    color: #f2f2f2;
}

#HeaderSubtitle {
    color: #9a9ba0;
    font-size: 12px;
}

QFrame#Card {
    background-color: #26272b;
    border: 1px solid #34353a;
    border-radius: 8px;
}

QLabel#FieldLabel {
    color: #b8b9be;
    font-weight: 600;
}

QLineEdit {
    background-color: #2c2d31;
    border: 1px solid #3a3b40;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e3e3e3;
}

QLineEdit:read-only {
    color: #9a9ba0;
}

QComboBox {
    background-color: #2c2d31;
    border: 1px solid #3a3b40;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e3e3e3;
}

QComboBox QAbstractItemView {
    background-color: #2c2d31;
    color: #e3e3e3;
    selection-background-color: #4a6cf7;
}

QPushButton {
    background-color: #34353a;
    border: 1px solid #3a3b40;
    border-radius: 6px;
    padding: 7px 14px;
    color: #e3e3e3;
}

QPushButton:hover {
    background-color: #3d3e44;
}

QPushButton:pressed {
    background-color: #2c2d31;
}

QPushButton:disabled {
    color: #6b6c70;
    background-color: #2a2b2f;
}

QPushButton#PrimaryButton {
    background-color: #4a6cf7;
    border: 1px solid #4a6cf7;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #5c7bf8;
}

QPushButton#PrimaryButton:disabled {
    background-color: #35406e;
    border: 1px solid #35406e;
    color: #9aa4c4;
}

QProgressBar {
    background-color: #2c2d31;
    border: 1px solid #3a3b40;
    border-radius: 6px;
    text-align: center;
    color: #e3e3e3;
}

QProgressBar::chunk {
    background-color: #4a6cf7;
    border-radius: 6px;
}

QLabel#StatusLabel {
    color: #9a9ba0;
    font-style: italic;
}

QListWidget {
    background-color: #26272b;
    border: 1px solid #34353a;
    border-radius: 8px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #34353a;
}

QLabel#DropHint {
    color: #6b6c70;
    font-size: 11px;
}

QPushButton#IconButton {
    background-color: transparent;
    border: 1px solid #3a3b40;
    border-radius: 6px;
    padding: 6px 10px;
}

QPushButton#IconButton:hover {
    background-color: #2c2d31;
}

QPushButton#ArrowButton {
    background-color: transparent;
    border: 1px solid #3a3b40;
    border-radius: 6px;
    padding: 0px;
    font-size: 13px;
    color: #b8b9be;
}

QPushButton#ArrowButton:hover {
    background-color: #2c2d31;
    color: #f2f2f2;
}

QLabel#TestStatusLabel {
    font-size: 12px;
    color: #9a9ba0;
}

QLabel#TestStatusLabel[status="pending"] {
    color: #9a9ba0;
}

QLabel#TestStatusLabel[status="success"] {
    color: #4ec9b0;
    font-weight: 600;
}

QLabel#TestStatusLabel[status="error"] {
    color: #f85149;
}

QFrame#Card[dragging="true"] {
    border: 2px dashed #4a6cf7;
    background-color: #262d45;
}
"""

LIGHT_STYLE = """
QWidget {
    background-color: #f5f5f7;
    color: #1d1d1f;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #f5f5f7;
}

QLabel, QWidget#TransparentRow, QWidget#AISettingsWidget {
    background-color: transparent;
}

QCheckBox {
    background-color: transparent;
    spacing: 8px;
    color: #1d1d1f;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #b8b8bc;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #4a6cf7;
}

QCheckBox::indicator:checked {
    background-color: #4a6cf7;
    border-color: #4a6cf7;
}

#HeaderTitle {
    font-size: 22px;
    font-weight: 600;
    color: #1d1d1f;
}

#HeaderSubtitle {
    color: #6e6e73;
    font-size: 12px;
}

QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #e0e0e2;
    border-radius: 8px;
}

QLabel#FieldLabel {
    color: #444447;
    font-weight: 600;
}

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d0d0d3;
    border-radius: 6px;
    padding: 6px 8px;
    color: #1d1d1f;
}

QLineEdit:read-only {
    color: #6e6e73;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d3;
    border-radius: 6px;
    padding: 6px 8px;
    color: #1d1d1f;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1d1d1f;
    selection-background-color: #4a6cf7;
    selection-color: #ffffff;
}

QPushButton {
    background-color: #e9e9eb;
    border: 1px solid #d0d0d3;
    border-radius: 6px;
    padding: 7px 14px;
    color: #1d1d1f;
}

QPushButton:hover {
    background-color: #dfdfe2;
}

QPushButton:pressed {
    background-color: #d3d3d6;
}

QPushButton:disabled {
    color: #a5a5a8;
    background-color: #eeeeef;
}

QPushButton#PrimaryButton {
    background-color: #4a6cf7;
    border: 1px solid #4a6cf7;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #3a5ce5;
}

QPushButton#PrimaryButton:disabled {
    background-color: #b7c3f5;
    border: 1px solid #b7c3f5;
    color: #eef1fd;
}

QProgressBar {
    background-color: #ffffff;
    border: 1px solid #d0d0d3;
    border-radius: 6px;
    text-align: center;
    color: #1d1d1f;
}

QProgressBar::chunk {
    background-color: #4a6cf7;
    border-radius: 6px;
}

QLabel#StatusLabel {
    color: #6e6e73;
    font-style: italic;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #e0e0e2;
    border-radius: 8px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #e9e9eb;
}

QLabel#DropHint {
    color: #9a9a9d;
    font-size: 11px;
}

QPushButton#IconButton {
    background-color: transparent;
    border: 1px solid #d0d0d3;
    border-radius: 6px;
    padding: 6px 10px;
}

QPushButton#IconButton:hover {
    background-color: #eeeeef;
}

QPushButton#ArrowButton {
    background-color: transparent;
    border: 1px solid #d0d0d3;
    border-radius: 6px;
    padding: 0px;
    font-size: 13px;
    color: #6e6e73;
}

QPushButton#ArrowButton:hover {
    background-color: #eeeeef;
    color: #1d1d1f;
}

QLabel#TestStatusLabel {
    font-size: 12px;
    color: #6e6e73;
}

QLabel#TestStatusLabel[status="pending"] {
    color: #6e6e73;
}

QLabel#TestStatusLabel[status="success"] {
    color: #1a7f37;
    font-weight: 600;
}

QLabel#TestStatusLabel[status="error"] {
    color: #cf222e;
}

QFrame#Card[dragging="true"] {
    border: 2px dashed #4a6cf7;
    background-color: #eef1fd;
}
"""
