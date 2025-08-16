from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtWidgets import QLayout, QSizePolicy, QLayoutItem

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=-1, v_spacing=-1, alignment=Qt.AlignLeft):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._alignment = alignment
        self._item_list = []
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QLayoutItem):
        self._item_list.append(item)

    def horizontalSpacing(self) -> int:
        if self._h_spacing >= 0:
            return self._h_spacing
        return self.smartSpacing(QSizePolicy.Horizontal)

    def verticalSpacing(self) -> int:
        if self._v_spacing >= 0:
            return self._v_spacing
        return self.smartSpacing(QSizePolicy.Vertical)
    
    def smartSpacing(self, orientation):
        if self.parent() is None:
            return -1
        if self.parent().isWidgetType():
            return self.parent().style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, orientation)
        return self.parent().spacing()

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective_rect = rect.adjusted(+m.left(), +m.top(), -m.right(), -m.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        
        line_items = []

        for item in self._item_list:
            next_x = x + item.sizeHint().width()
            if next_x > effective_rect.right() and line_height > 0:
                # New line
                self.align_line(line_items, effective_rect.width(), test_only)
                line_items = []
                x = effective_rect.x()
                y = y + line_height + self.verticalSpacing()
            
            if not test_only:
                 line_items.append((item, QPoint(x, y)))

            x += item.sizeHint().width() + self.horizontalSpacing()
            line_height = max(line_height, item.sizeHint().height())

        self.align_line(line_items, effective_rect.width(), test_only)

        return y + line_height - rect.y() + m.bottom()

    def align_line(self, items, line_width, test_only):
        if not items:
            return
        
        last_item, last_pos = items[-1]
        line_content_width = (last_pos.x() - items[0][1].x()) + last_item.sizeHint().width()
        
        offset = 0
        if self._alignment == Qt.AlignCenter:
            offset = (line_width - line_content_width) / 2
        elif self._alignment == Qt.AlignRight:
            offset = line_width - line_content_width
        
        if not test_only:
            for item, pos in items:
                item.setGeometry(QRect(pos + QPoint(offset, 0), item.sizeHint()))