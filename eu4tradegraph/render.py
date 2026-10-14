"""Build DOT and render each request in memory."""

import colorsys
from dataclasses import dataclass
import math
import platform

from graphviz import Digraph
from PIL import Image, ImageDraw

from .parser import TradeSnapshot


def default_font() -> str:
    return {"Darwin": "PingFang SC", "Windows": "Microsoft YaHei"}.get(
        platform.system(), "Noto Sans CJK SC")


@dataclass(frozen=True)
class GraphSettings:
    aspect_ratio: float = 2.16  # Width / height; DOT ratio uses the inverse.
    edge_width: tuple[float, float] = (1.0, 6.0)
    node_size: tuple[float, float] = (0.6, 1.8)
    font_size: tuple[float, float] = (12.0, 22.0)
    start_color: tuple[float, float, float] = (0.0, 0.5, 1.0)
    end_color: tuple[float, float, float] = (2 / 3, 0.5, 1.0)
    font_name: str = default_font()
    chinese_labels: bool = True

    def __post_init__(self) -> None:
        if not math.isfinite(self.aspect_ratio) or not 0.5 <= self.aspect_ratio <= 4:
            raise ValueError("图形宽高比必须在 0.5 到 4 之间。")
        for bounds in (self.edge_width, self.node_size, self.font_size):
            if any(not math.isfinite(v) or v <= 0 for v in bounds) or bounds[0] > bounds[1]:
                raise ValueError("图形尺寸范围必须为递增的正数。")
        for color in (self.start_color, self.end_color):
            if len(color) != 3 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in color):
                raise ValueError("HSV 颜色分量必须在 0 到 1 之间。")


def scale(value: float, minimum: float, maximum: float,
          bounds: tuple[float, float]) -> float:
    """Use the midpoint when the data range is constant (including all zero)."""
    fraction = (value - minimum) / (maximum - minimum) if maximum > minimum else 0.5
    return bounds[0] + fraction * (bounds[1] - bounds[0])


def build_graph(snapshot: TradeSnapshot, settings: GraphSettings = GraphSettings()) -> Digraph:
    graph = Digraph("eu4_trade", encoding="utf-8")
    graph.attr(rankdir="LR", ratio=str(1 / settings.aspect_ratio), bgcolor="white",
               pad="0.3", nodesep="0.3", ranksep="0.6", dpi="120")
    graph.attr("node", fontname=settings.font_name, style="filled", penwidth="1.5")
    graph.attr("edge", color="#64748b", arrowsize="0.7")
    current = [node.current for node in snapshot.nodes]
    local = [node.local_value for node in snapshot.nodes]
    flows = [route.value for route in snapshot.routes]
    for index, node in enumerate(snapshot.nodes):
        fraction = scale(node.local_value, min(local), max(local), (0, 1))
        hsv = tuple(a + fraction * (b - a)
                    for a, b in zip(settings.start_color, settings.end_color))
        rgb = colorsys.hsv_to_rgb(*hsv)
        fill = "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)
        size = scale(node.current, min(current), max(current), settings.node_size)
        label = node.label if settings.chinese_labels else node.name.replace("_", " ").title()
        graph.node(str(index), label=f"{label}\n{node.current:.2f}",
                   shape="box" if node.inland else "ellipse", fillcolor=fill,
                   fontcolor="white" if sum(a * b for a, b in zip(rgb, (0.2126, 0.7152, 0.0722))) < 0.45 else "#172033",
                   width=str(size), height=str(size * 0.618),
                   fontsize=str(scale(node.current, min(current), max(current), settings.font_size)),
                   tooltip=f"{node.name}: current={node.current:g}, local_value={node.local_value:g}, outgoing={node.outgoing:g}")
    for route in snapshot.routes:
        graph.edge(str(route.source), str(route.target),
                   style="dashed" if route.value == 0 else "solid",
                   penwidth=str(scale(route.value, min(flows), max(flows), settings.edge_width)),
                   tooltip=f"{route.value:g}")
    return graph


def render_graph(snapshot: TradeSnapshot, settings: GraphSettings = GraphSettings(),
                 image_format: str = "png") -> bytes:
    if image_format not in ("png", "svg"):
        raise ValueError("仅支持 PNG 和 SVG 导出。")
    return build_graph(snapshot, settings).pipe(format=image_format)


def gradient(settings: GraphSettings, width: int = 640, height: int = 24) -> Image.Image:
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for x in range(width):
        fraction = x / max(width - 1, 1)
        hsv = tuple(a + fraction * (b - a) for a, b in zip(settings.start_color, settings.end_color))
        rgb = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(*hsv))
        draw.line((x, 0, x, height), fill=rgb)
    return image
