from ..views.MainContent import MainContent
from ..views.Sidebar import Sidebar


class MainController:
    def __init__(self, sidebar_view: Sidebar, maincontent_view: MainContent):
        self.sidebar_view = sidebar_view
        self.maincontent_view = maincontent_view

        self._bind_global_connections()

    def _bind_global_connections(self):
        self.sidebar_view.sidebar_buttons_widgets.group.idClicked.connect(
            self.maincontent_view.stackwidget.setCurrentIndex
        )