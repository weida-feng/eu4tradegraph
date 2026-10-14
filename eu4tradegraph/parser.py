"""A brace-aware reader for trade fields, not a full Clausewitz parser."""

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import re
from typing import Iterator

MAX_SAVE_BYTES = 200 * 1024 * 1024
VERIFIED_VERSION = "1.34.4.0"
DATA_PATH = Path(__file__).parent / "data" / "trade_centers.tsv"
_TOKEN = re.compile(r'\s*(#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+)')
_STRUCTURE = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]')
_NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\Z")


class SaveError(ValueError):
    """An input is malformed or outside the supported save format."""


@dataclass(frozen=True)
class TradeNode:
    name: str
    label: str
    inland: bool
    current: float
    outgoing: float
    local_value: float


@dataclass(frozen=True)
class TradeRoute:
    source: int  # Zero-based index into TradeSnapshot.nodes.
    target: int
    value: float


@dataclass(frozen=True)
class TradeSnapshot:
    version: str
    date: str
    nodes: tuple[TradeNode, ...]
    routes: tuple[TradeRoute, ...]


@dataclass(frozen=True)
class _Field:
    name: str
    value: str
    block: bool = False


def _token(text: str, position: int) -> tuple[str, int]:
    while position < len(text):
        match = _TOKEN.match(text, position)
        if not match:
            if not text[position:].strip():
                return "", len(text)
            raise SaveError("存档包含无法读取的文本或未闭合的引号。")
        position = match.end()
        value = match.group(1)
        if not value.startswith("#"):
            return value, position
    return "", position


def _fields(text: str) -> Iterator[_Field]:
    position = 0
    while True:
        name, position = _token(text, position)
        if not name:
            return
        if name in ("{", "}", "="):
            raise SaveError("存档的字段或花括号结构不完整。")
        equals, after_equals = _token(text, position)
        if equals not in ("=", "{"):
            # Blocks may contain bare list values, such as DLC/mod names.
            continue
        # EU4 also writes some blocks without '=', e.g. map_area_data{...}.
        if equals == "{":
            value, position = equals, after_equals
        else:
            value, position = _token(text, after_equals)
        if not value or value in ("}", "="):
            raise SaveError(f"存档字段 {name} 缺少值。")
        if value != "{":
            yield _Field(name, value)
            continue
        start = position
        depth = 1
        for match in _STRUCTURE.finditer(text, start):
            if match.group() == "{":
                depth += 1
            elif match.group() == "}":
                depth -= 1
                if depth == 0:
                    position = match.end()
                    yield _Field(name, text[start:match.start()], True)
                    break
        else:
            raise SaveError(f"存档字段 {name} 的花括号未闭合。")


def _single(fields: list[_Field], name: str, default: str | None = None) -> str:
    matches = [field for field in fields if field.name == name]
    if not matches and default is not None:
        return default
    if len(matches) != 1 or matches[0].block:
        raise SaveError(f"存档字段 {name} 缺失、重复或格式不正确。")
    value = matches[0].value
    return re.sub(r"\\(.)", r"\1", value[1:-1]) if value.startswith('"') else value


def _number(fields: list[_Field], name: str) -> float:
    # EU4 omits some zero-valued fields, including current and outgoing.
    raw = _single(fields, name, "0")
    if not _NUMBER.fullmatch(raw):
        raise SaveError(f"贸易字段 {name} 不是有效数字。")
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise SaveError(f"贸易字段 {name} 必须是有限的非负数字。")
    return value


@lru_cache(maxsize=1)
def node_catalog() -> dict[str, tuple[str, bool]]:
    catalog = {}
    for line in DATA_PATH.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, label, inland = line.split("\t")
            catalog[name] = (label, inland == "1")
    return catalog


def parse_save(data: bytes) -> TradeSnapshot:
    """Read uncompressed vanilla EU4txt saves without a version allowlist.

    Only the 1.34.4.0 reference snapshot has been verified. Other versions
    may be attempted, but their compatibility and results are not guaranteed.
    """
    if len(data) > MAX_SAVE_BYTES:
        raise SaveError("存档超过 200 MB，请使用较小的非压缩存档。")
    if data.startswith(b"PK"):
        raise SaveError("不支持压缩存档，请在 EU4 中关闭压缩后重新保存。")
    if data.startswith(b"EU4bin") or b"\x00" in data:
        raise SaveError("不支持二进制或铁人存档，请使用非压缩文本存档。")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError as error:
            raise SaveError("无法读取存档编码，请使用 EU4 导出的文本存档。") from error
    if not text.startswith("EU4txt") or (len(text) > 6 and not text[6].isspace()):
        raise SaveError("不是有效的 EU4txt 非压缩文本存档。")

    metadata: list[_Field] = []
    trade: _Field | None = None
    for field in _fields(text[6:]):
        if field.name in ("savegame_version", "date"):
            metadata.append(field)
        elif field.name in ("mods_enabled", "mod_enabled"):
            value, _ = _token(field.value, 0)
            if (field.block and value) or (not field.block and value not in ("", '""', "no", "none", "0")):
                raise SaveError("当前仅支持无 Mod 存档，请使用原版 EU4 存档。")
        elif field.name == "ironman" and field.value != "no":
            raise SaveError("不支持铁人存档，请使用非压缩的普通文本存档。")
        elif field.name == "trade":
            if trade is not None or not field.block:
                raise SaveError("存档的 trade 区块重复或格式不正确。")
            trade = field

    versions = [field for field in metadata if field.name == "savegame_version"]
    if len(versions) != 1 or not versions[0].block:
        raise SaveError("存档的版本信息缺失、重复或格式不正确。")
    version_fields = list(_fields(versions[0].value))
    parts = [_single(version_fields, key, "0" if key in ("third", "forth") else None)
             for key in ("first", "second", "third", "forth")]
    if any(not part.isascii() or not part.isdigit() or len(part) > 6 for part in parts):
        raise SaveError("存档版本字段格式不正确。")
    parts = [str(int(part)) for part in parts]
    version = ".".join(parts)
    if trade is None:
        raise SaveError("存档中没有找到 trade 贸易数据区块。")

    catalog = node_catalog()
    nodes: list[TradeNode] = []
    routes: list[TradeRoute] = []
    names: set[str] = set()
    for block in _fields(trade.value):
        if block.name != "node":
            continue
        if not block.block:
            raise SaveError("贸易 node 字段必须是区块。")
        fields = list(_fields(block.value))
        name = _single(fields, "definitions")
        if name not in catalog:
            raise SaveError(f"无法识别贸易节点 {name}；当前节点名称与分类映射基于 1.34.4 参考数据。")
        if name in names:
            raise SaveError(f"存档包含重复贸易节点 {name}。")
        names.add(name)
        label, inland = catalog[name]
        nodes.append(TradeNode(name, label, inland, _number(fields, "current"),
                               _number(fields, "outgoing"), _number(fields, "local_value")))
        for incoming in (field for field in fields if field.name == "incoming"):
            if not incoming.block:
                raise SaveError("incoming 贸易路线必须是区块。")
            values = list(_fields(incoming.value))
            source = _single(values, "from")
            if not source.isascii() or not source.isdigit() or len(source) > 9 or int(source) < 1:
                raise SaveError("贸易路线 from 必须是从 1 开始的节点编号。")
            routes.append(TradeRoute(int(source) - 1, len(nodes) - 1, _number(values, "value")))
    if not nodes:
        raise SaveError("存档中没有可绘制的贸易节点。")
    if any(route.source >= len(nodes) for route in routes):
        raise SaveError("贸易路线引用了不存在的节点编号。")
    return TradeSnapshot(version, _single(metadata, "date", "未知"), tuple(nodes), tuple(routes))
