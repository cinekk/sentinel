from plugins.base import BasePlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        self._plugins[plugin.layer_id] = plugin

    def get(self, layer_id: str) -> BasePlugin | None:
        return self._plugins.get(layer_id)

    def all(self) -> list[BasePlugin]:
        return list(self._plugins.values())


registry = PluginRegistry()
