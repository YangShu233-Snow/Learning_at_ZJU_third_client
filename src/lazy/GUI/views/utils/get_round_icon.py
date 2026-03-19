from PySide6.QtGui import QPainter, QBrush, QPixmap
from PySide6.QtCore import Qt

def get_round_icon(source_pixmap, size=64)->QPixmap:
    # 1. 创建一个等比例缩放的方形图片，确保裁切中心
    source_pixmap = source_pixmap.scaled(
        size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    
    # 2. 准备目标画布（开启透明支持）
    out_pixmap = QPixmap(size, size)
    out_pixmap.fill(Qt.transparent)
    
    # 3. 开始在画布上绘画
    painter = QPainter(out_pixmap)
    # 开启抗锯齿，否则圆边会有锯齿状
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    
    # 4. 创建圆形路径（或者是用 QBrush 填充圆）
    brush = QBrush(source_pixmap)
    painter.setBrush(brush)
    painter.setPen(Qt.NoPen) # 不要边框
    
    # 画圆：drawEllipse(x, y, width, height)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    
    return out_pixmap